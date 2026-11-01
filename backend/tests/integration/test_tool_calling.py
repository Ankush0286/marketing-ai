import pytest
from fastapi.testclient import TestClient
from pydantic_ai.models.test import TestModel
from sqlalchemy.orm import Session

from app.agent.llm import marketing_agent
from app.agent.loop import run_agent_turn, stream_agent_turn
from app.common.enums import ChatRole, PlatformType
from app.modules.accounts.commands import CreateAccountCommand
from app.modules.accounts.service import AccountService
from app.modules.copilot.commands import CreateChatSessionCommand
from app.modules.copilot.service import CopilotService


@pytest.mark.anyio
async def test_run_agent_turn_calls_tools_and_logs_traces(db_session: Session):
    """
    Verifies the complete ReAct cycle:
    1. User sends a prompt in a ChatSession.
    2. Agent invokes `get_connected_accounts` tool against the database.
    3. Tool trace is logged in `tool_execution_logs`.
    4. User prompt and Assistant reply are persisted in `chat_messages`.
    """
    account_service = AccountService(db_session)
    copilot_service = CopilotService(db_session)

    # Seed a connected account
    account_service.create_account(
        CreateAccountCommand(
            platform=PlatformType.TWITTER,
            handle="react_loop_bot",
        )
    )

    session = copilot_service.create_session(
        CreateChatSessionCommand(
            title="Account Audit Session",
            system_prompt_override="Be concise and factual.",
        )
    )

    # Configure deterministic TestModel to invoke `get_connected_accounts`
    deterministic_model = TestModel(
        call_tools=["get_connected_accounts"],
        custom_output_text="You have 1 connected Twitter account (@react_loop_bot).",
    )

    assistant_msg = await run_agent_turn(
        db=db_session,
        session_id=session.id,
        user_prompt="Which social accounts do I have connected?",
        model_override=deterministic_model,
    )

    # 1. Verify returned ChatMessage entity
    assert assistant_msg.id is not None
    assert assistant_msg.role == ChatRole.ASSISTANT
    assert "@react_loop_bot" in assistant_msg.content

    # 2. Verify conversation history persisted both User and Assistant turns
    messages = copilot_service.list_messages(session.id)
    assert len(messages) == 2
    assert messages[0].role == ChatRole.USER
    assert messages[0].content == "Which social accounts do I have connected?"
    assert messages[1].role == ChatRole.ASSISTANT

    # 3. Verify tool execution was traced in ToolExecutionLog
    tool_traces = copilot_service.list_tool_executions(session.id)
    assert len(tool_traces) >= 1
    assert tool_traces[0].tool_name == "get_connected_accounts"


@pytest.mark.anyio
async def test_stream_agent_turn_persists_streamed_response(db_session: Session):
    """Verifies that streaming token generation yields chunks and saves the final reply."""
    copilot_service = CopilotService(db_session)
    session = copilot_service.create_session(
        CreateChatSessionCommand(title="Streaming Session")
    )

    deterministic_model = TestModel(
        call_tools=[],
        custom_output_text="Streaming viral hook 1, 2, 3!",
    )

    chunks: list[str] = []
    async for token in stream_agent_turn(
        db=db_session,
        session_id=session.id,
        user_prompt="Stream a viral hook",
        model_override=deterministic_model,
    ):
        chunks.append(token)

    full_text = "".join(chunks)
    assert "Streaming viral hook 1, 2, 3!" in full_text

    # Verify both user prompt and completed assistant response are saved
    messages = copilot_service.list_messages(session.id)
    assert len(messages) == 2
    assert messages[1].role == ChatRole.ASSISTANT
    assert messages[1].content == full_text


def test_copilot_chat_and_sse_stream_api_endpoints(client: TestClient):
    """Verifies POST /sessions/{id}/chat and POST /sessions/{id}/stream HTTP endpoints."""
    # 1. Create session via API
    session_res = client.post(
        "/api/v1/copilot/sessions",
        json={"title": "API Agent Session"},
    )
    assert session_res.status_code == 201
    session_id = session_res.json()["id"]

    mock_model = TestModel(
        call_tools=[],
        custom_output_text="Campaign drafted and ready for launch!",
    )

    # 2. Test synchronous /chat endpoint with overridden TestModel
    with marketing_agent.override(model=mock_model):
        chat_res = client.post(
            f"/api/v1/copilot/sessions/{session_id}/chat",
            json={"content": "Draft a launch campaign"},
        )
        assert chat_res.status_code == 200
        chat_data = chat_res.json()
        assert chat_data["role"] == "assistant"
        assert chat_data["content"] == "Campaign drafted and ready for launch!"

        # 3. Test SSE /stream endpoint
        stream_res = client.post(
            f"/api/v1/copilot/sessions/{session_id}/stream",
            json={"content": "Stream the next steps"},
        )
        assert stream_res.status_code == 200
        assert "text/event-stream" in stream_res.headers["content-type"]
        assert "data: [DONE]" in stream_res.text
