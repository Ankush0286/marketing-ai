from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.common.enums import ChatRole, ToolExecutionStatus
from app.modules.copilot.commands import (
    AddChatMessageCommand,
    CreateChatSessionCommand,
    LogToolExecutionCommand,
    UpdateChatSessionCommand,
)
from app.modules.copilot.exceptions import (
    ChatMessageNotFoundError,
    ChatSessionNotFoundError,
)
from app.modules.copilot.service import CopilotService

# =============================================================================
# Chat Session Unit Tests
# =============================================================================


def test_session_crud(db_session: Session):
    service = CopilotService(db_session)

    # 1. Create session
    cmd = CreateChatSessionCommand(
        title="Q4 Launch Brainstorm",
        system_prompt_override="You are an expert SaaS copywriter.",
        extra_metadata={"channel": "twitter"},
    )
    session = service.create_session(cmd)

    assert session.id is not None
    assert session.title == "Q4 Launch Brainstorm"
    assert session.system_prompt_override == "You are an expert SaaS copywriter."
    assert session.is_archived is False

    # 2. Get session by ID
    queried = service.get_session_by_id_or_raise(session.id)
    assert queried.id == session.id

    # 3. Update session
    updated = service.update_session(
        UpdateChatSessionCommand(
            session_id=session.id,
            title="Refined Brainstorm",
            is_archived=True,
        )
    )
    assert updated.title == "Refined Brainstorm"
    assert updated.is_archived is True

    # 4. List sessions
    active_sessions = service.list_sessions(include_archived=False)
    assert len(active_sessions) == 0

    all_sessions = service.list_sessions(include_archived=True)
    assert len(all_sessions) == 1

    # 5. Delete session
    service.delete_session(session.id)
    assert service.get_session_by_id(session.id) is None


def test_get_nonexistent_session_raises(db_session: Session):
    service = CopilotService(db_session)
    with pytest.raises(ChatSessionNotFoundError):
        service.get_session_by_id_or_raise(uuid4())


def test_session_cascade_deletion(db_session: Session):
    """Verifies deleting a session cascades to its messages and tool logs."""
    service = CopilotService(db_session)

    session = service.create_session(CreateChatSessionCommand(title="To Delete"))
    msg = service.add_message(
        AddChatMessageCommand(
            session_id=session.id,
            role=ChatRole.USER,
            content="Hello AI",
        )
    )
    service.log_tool_execution(
        LogToolExecutionCommand(
            session_id=session.id,
            message_id=msg.id,
            tool_name="get_accounts",
            input_arguments={},
        )
    )

    service.delete_session(session.id)

    assert service.get_session_by_id(session.id) is None
    with pytest.raises(ChatSessionNotFoundError):
        service.list_messages(session.id)
    with pytest.raises(ChatSessionNotFoundError):
        service.list_tool_executions(session.id)


# =============================================================================
# Chat Messages & Conversation History Unit Tests
# =============================================================================


def test_add_and_list_messages_with_pagination(db_session: Session):
    service = CopilotService(db_session)
    session = service.create_session(CreateChatSessionCommand(title="Chat Thread"))

    # Add messages
    msg1 = service.add_message(
        AddChatMessageCommand(
            session_id=session.id,
            role=ChatRole.USER,
            content="Can you draft a tweet?",
        )
    )
    msg2 = service.add_message(
        AddChatMessageCommand(
            session_id=session.id,
            role=ChatRole.ASSISTANT,
            content="Here is a draft tweet!",
            model_name="claude-3-5-sonnet",
            token_count=18,
        )
    )

    assert msg1.id is not None
    assert msg2.id is not None
    assert msg2.role == ChatRole.ASSISTANT
    assert msg2.token_count == 18

    # List messages
    messages = service.list_messages(session.id)
    assert len(messages) == 2
    assert messages[0].content == "Can you draft a tweet?"
    assert messages[1].content == "Here is a draft tweet!"

    # Pagination: limit 1, offset 1
    paged = service.list_messages(session.id, limit=1, offset=1)
    assert len(paged) == 1
    assert paged[0].id == msg2.id


def test_add_message_nonexistent_session_raises(db_session: Session):
    service = CopilotService(db_session)
    with pytest.raises(ChatSessionNotFoundError):
        service.add_message(
            AddChatMessageCommand(
                session_id=uuid4(),
                role=ChatRole.USER,
                content="Orphan message",
            )
        )


def test_get_conversation_context_hydrates_system_prompt(db_session: Session):
    """Verifies that conversation context prepends system_prompt_override and formats turns."""
    service = CopilotService(db_session)

    session = service.create_session(
        CreateChatSessionCommand(
            title="Context Test",
            system_prompt_override="Always answer in bullet points.",
        )
    )

    service.add_message(
        AddChatMessageCommand(
            session_id=session.id,
            role=ChatRole.USER,
            content="What is marketing automation?",
        )
    )
    service.add_message(
        AddChatMessageCommand(
            session_id=session.id,
            role=ChatRole.ASSISTANT,
            content="• Software that streamlines growth workflows.",
        )
    )

    context = service.get_conversation_context(session.id, max_messages=10)

    assert len(context) == 3
    # 1. System prompt is prepended
    assert context[0]["role"] == "system"
    assert context[0]["content"] == "Always answer in bullet points."

    # 2. Chronological conversation turns
    assert context[1]["role"] == "user"
    assert context[1]["content"] == "What is marketing automation?"
    assert context[2]["role"] == "assistant"
    assert context[2]["content"] == "• Software that streamlines growth workflows."


# =============================================================================
# Tool Execution Tracing Unit Tests
# =============================================================================


def test_log_and_list_tool_executions(db_session: Session):
    service = CopilotService(db_session)
    session = service.create_session(CreateChatSessionCommand(title="Tool Thread"))

    msg = service.add_message(
        AddChatMessageCommand(
            session_id=session.id,
            role=ChatRole.ASSISTANT,
            content="Checking connected accounts...",
        )
    )

    tool_log = service.log_tool_execution(
        LogToolExecutionCommand(
            session_id=session.id,
            message_id=msg.id,
            tool_name="get_accounts",
            input_arguments={"platform": "twitter"},
            output_result={"accounts_count": 2},
            status=ToolExecutionStatus.SUCCESS,
            execution_time_ms=45,
        )
    )

    assert tool_log.id is not None
    assert tool_log.tool_name == "get_accounts"
    assert tool_log.input_arguments["platform"] == "twitter"
    assert isinstance(tool_log.output_result, dict)  # <-- Narrows type for Mypy
    assert tool_log.output_result["accounts_count"] == 2
    assert tool_log.execution_time_ms == 45

    # List tool traces
    traces = service.list_tool_executions(session.id)
    assert len(traces) == 1
    assert traces[0].id == tool_log.id


def test_log_tool_execution_invalid_message_raises(db_session: Session):
    service = CopilotService(db_session)
    session = service.create_session(CreateChatSessionCommand(title="Tool Validation"))

    with pytest.raises(ChatMessageNotFoundError):
        service.log_tool_execution(
            LogToolExecutionCommand(
                session_id=session.id,
                message_id=uuid4(),  # Invalid message reference
                tool_name="draft_campaign",
                input_arguments={},
            )
        )
