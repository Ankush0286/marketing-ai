from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agent.loop import run_agent_turn, stream_agent_turn
from app.db.dependencies import get_db_session
from app.modules.copilot.schemas import (
    ChatMessageCreateRequest,
    ChatMessageResponse,
    ChatSessionCreateRequest,
    ChatSessionDetailResponse,
    ChatSessionResponse,
    ChatSessionUpdateRequest,
    ToolExecutionLogResponse,
)
from app.modules.copilot.service import CopilotService

router = APIRouter()


def get_copilot_service(db: Session = Depends(get_db_session)) -> CopilotService:
    """Dependency injection factory for CopilotService."""
    return CopilotService(db)


class AgentChatRequest(BaseModel):
    """Payload accepted by POST /api/v1/copilot/sessions/{session_id}/chat"""

    content: str = Field(..., min_length=1, max_length=20000)
    model_override: str | None = None


# =============================================================================
# Chat Session Endpoints
# =============================================================================


@router.post(
    "/sessions",
    response_model=ChatSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new AI conversation thread",
)
def create_session(
    payload: ChatSessionCreateRequest,
    service: CopilotService = Depends(get_copilot_service),
) -> ChatSessionResponse:
    session = service.create_session(payload.to_command())
    return ChatSessionResponse.model_validate(session)


@router.get(
    "/sessions",
    response_model=list[ChatSessionResponse],
    status_code=status.HTTP_200_OK,
    summary="List all AI conversation sessions",
)
def list_sessions(
    include_archived: bool = Query(default=False, description="Include archived sessions"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: CopilotService = Depends(get_copilot_service),
) -> list[ChatSessionResponse]:
    sessions = service.list_sessions(include_archived=include_archived, limit=limit, offset=offset)
    return [ChatSessionResponse.model_validate(session) for session in sessions]


@router.get(
    "/sessions/{session_id}",
    response_model=ChatSessionDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get conversation session with full message history",
)
def get_session(
    session_id: UUID,
    service: CopilotService = Depends(get_copilot_service),
) -> ChatSessionDetailResponse:
    session = service.get_session_by_id_or_raise(session_id)
    return ChatSessionDetailResponse.model_validate(session)


@router.patch(
    "/sessions/{session_id}",
    response_model=ChatSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Rename or archive a chat thread",
)
def update_session(
    session_id: UUID,
    payload: ChatSessionUpdateRequest,
    service: CopilotService = Depends(get_copilot_service),
) -> ChatSessionResponse:
    session = service.update_session(payload.to_command(session_id))
    return ChatSessionResponse.model_validate(session)


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a chat thread and all message traces",
)
def delete_session(
    session_id: UUID,
    service: CopilotService = Depends(get_copilot_service),
) -> None:
    service.delete_session(session_id)


# =============================================================================
# Chat Messages & Tool Trace Endpoints
# =============================================================================


@router.post(
    "/sessions/{session_id}/messages",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Append a user or assistant message to a conversation thread",
)
def add_message(
    session_id: UUID,
    payload: ChatMessageCreateRequest,
    service: CopilotService = Depends(get_copilot_service),
) -> ChatMessageResponse:
    message = service.add_message(payload.to_command(session_id))
    return ChatMessageResponse.model_validate(message)


@router.get(
    "/sessions/{session_id}/messages",
    response_model=list[ChatMessageResponse],
    status_code=status.HTTP_200_OK,
    summary="List all messages in a conversation thread with pagination",
)
def list_messages(
    session_id: UUID,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: CopilotService = Depends(get_copilot_service),
) -> list[ChatMessageResponse]:
    messages = service.list_messages(session_id=session_id, limit=limit, offset=offset)
    return [ChatMessageResponse.model_validate(msg) for msg in messages]


@router.get(
    "/sessions/{session_id}/tools",
    response_model=list[ToolExecutionLogResponse],
    status_code=status.HTTP_200_OK,
    summary="List all tool execution traces triggered during a conversation",
)
def list_tool_executions(
    session_id: UUID,
    service: CopilotService = Depends(get_copilot_service),
) -> list[ToolExecutionLogResponse]:
    tool_logs = service.list_tool_executions(session_id=session_id)
    return [ToolExecutionLogResponse.model_validate(trace) for trace in tool_logs]


# =============================================================================
# Interactive AI Agent Execution & Streaming Endpoints
# =============================================================================


@router.post(
    "/sessions/{session_id}/chat",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Send a prompt to the AI Copilot and receive the completed reply",
)
async def chat_with_agent(
    session_id: UUID,
    payload: AgentChatRequest,
    db: Session = Depends(get_db_session),
) -> ChatMessageResponse:
    assistant_msg = await run_agent_turn(
        db=db,
        session_id=session_id,
        user_prompt=payload.content,
        model_override=payload.model_override,
    )
    return ChatMessageResponse.model_validate(assistant_msg)


@router.post(
    "/sessions/{session_id}/stream",
    summary="Stream AI Copilot response tokens in real time via SSE",
)
async def stream_chat_with_agent(
    session_id: UUID,
    payload: AgentChatRequest,
    db: Session = Depends(get_db_session),
) -> StreamingResponse:
    token_generator = stream_agent_turn(
        db=db,
        session_id=session_id,
        user_prompt=payload.content,
        model_override=payload.model_override,
    )

    async def event_generator() -> AsyncGenerator[str, None]:
        async for token in token_generator:
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
