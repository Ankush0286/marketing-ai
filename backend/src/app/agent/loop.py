import logging
import time
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID

from pydantic_ai.models import Model
from sqlalchemy.orm import Session

# Ensure all tool decorators register on marketing_agent
from app.agent import tools as _registered_tools  # noqa: F401
from app.agent.llm import AgentDeps, get_openrouter_model, marketing_agent
from app.common.enums import ChatRole, ToolExecutionStatus
from app.modules.copilot.commands import (
    AddChatMessageCommand,
    LogToolExecutionCommand,
)
from app.modules.copilot.models import ChatMessage
from app.modules.copilot.service import CopilotService

logger = logging.getLogger(__name__)


def _build_prompt_with_history(
    prior_context: list[dict[str, str]],
    current_user_prompt: str,
) -> str:
    """
    Formats prior conversation turns and any session system_prompt_override
    into a structured context block so the LLM maintains full multi-turn memory.
    """
    if not prior_context:
        return current_user_prompt

    lines: list[str] = ["=== CONVERSATION HISTORY ==="]
    for turn in prior_context:
        role_label = turn["role"].upper()
        lines.append(f"[{role_label}]: {turn['content']}")

    lines.append("\n=== CURRENT USER REQUEST ===")
    lines.append(current_user_prompt)
    return "\n".join(lines)


def _record_tool_traces(
    copilot_service: CopilotService,
    session_id: UUID,
    messages: list[Any],
    elapsed_ms: int,
) -> None:
    """Extracts tool-call parts from Pydantic AI messages and logs them to the DB."""
    for message in messages:
        parts = getattr(message, "parts", None)
        if not parts:
            continue
        for part in parts:
            if getattr(part, "part_kind", None) == "tool-call":
                tool_name = getattr(part, "tool_name", "unknown_tool")
                raw_args = getattr(part, "args", {})
                input_args = (
                    raw_args
                    if isinstance(raw_args, dict)
                    else {"arguments": str(raw_args)}
                )
                copilot_service.log_tool_execution(
                    LogToolExecutionCommand(
                        session_id=session_id,
                        tool_name=str(tool_name),
                        input_arguments=input_args,
                        status=ToolExecutionStatus.SUCCESS,
                        execution_time_ms=elapsed_ms,
                    )
                )


async def run_agent_turn(
    db: Session,
    session_id: UUID,
    user_prompt: str,
    model_override: str | Model | None = None,
) -> ChatMessage:
    """
    Executes a complete multi-turn ReAct agent cycle and returns the persisted
    assistant ChatMessage ORM record.
    """
    copilot_service = CopilotService(db)

    # 1. Fetch prior conversation context before appending the new user message
    prior_context = copilot_service.get_conversation_context(session_id, max_messages=20)

    # 2. Persist incoming User Message
    copilot_service.add_message(
        AddChatMessageCommand(
            session_id=session_id,
            role=ChatRole.USER,
            content=user_prompt,
        )
    )

    # 3. Resolve Model & Dependencies
    deps = AgentDeps(db=db, session_id=session_id)
    resolved_model: Model | None = None
    if isinstance(model_override, str):
        resolved_model = get_openrouter_model(model_override)
    elif model_override is not None:
        resolved_model = model_override

    contextualized_prompt = _build_prompt_with_history(prior_context, user_prompt)

    # 4. Run Agent
    logger.info("Executing Agent Turn in Session %s...", session_id)
    start_time = time.perf_counter()

    result = await marketing_agent.run(
        contextualized_prompt,
        deps=deps,
        model=resolved_model,
    )
    elapsed_ms = int((time.perf_counter() - start_time) * 1000)

    # 5. Record Tool Execution Traces
    _record_tool_traces(
        copilot_service=copilot_service,
        session_id=session_id,
        messages=list(result.new_messages()),
        elapsed_ms=elapsed_ms,
    )

    # 6. Persist and return Assistant Message (using .output for pydantic-ai >= 2.60)
    assistant_reply = str(result.output)
    model_label = model_override if isinstance(model_override, str) else "default"

    return copilot_service.add_message(
        AddChatMessageCommand(
            session_id=session_id,
            role=ChatRole.ASSISTANT,
            content=assistant_reply,
            model_name=model_label,
        )
    )


async def stream_agent_turn(
    db: Session,
    session_id: UUID,
    user_prompt: str,
    model_override: str | Model | None = None,
) -> AsyncGenerator[str, None]:
    """
    Streaming ReAct execution loop yielding text deltas in real time via SSE.
    """
    copilot_service = CopilotService(db)
    prior_context = copilot_service.get_conversation_context(session_id, max_messages=20)

    # 1. Persist User Prompt
    copilot_service.add_message(
        AddChatMessageCommand(
            session_id=session_id,
            role=ChatRole.USER,
            content=user_prompt,
        )
    )

    deps = AgentDeps(db=db, session_id=session_id)
    resolved_model: Model | None = None
    if isinstance(model_override, str):
        resolved_model = get_openrouter_model(model_override)
    elif model_override is not None:
        resolved_model = model_override

    contextualized_prompt = _build_prompt_with_history(prior_context, user_prompt)
    accumulated_chunks: list[str] = []
    start_time = time.perf_counter()

    # 2. Stream Tokens
    async with marketing_agent.run_stream(
        contextualized_prompt,
        deps=deps,
        model=resolved_model,
    ) as stream_result:
        async for chunk in stream_result.stream_text(delta=True):
            accumulated_chunks.append(chunk)
            yield chunk

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        _record_tool_traces(
            copilot_service=copilot_service,
            session_id=session_id,
            messages=list(stream_result.new_messages()),
            elapsed_ms=elapsed_ms,
        )

    # 3. Persist Completed Assistant Response
    full_response = "".join(accumulated_chunks)
    model_label = model_override if isinstance(model_override, str) else "default"

    copilot_service.add_message(
        AddChatMessageCommand(
            session_id=session_id,
            role=ChatRole.ASSISTANT,
            content=full_response,
            model_name=model_label,
        )
    )
