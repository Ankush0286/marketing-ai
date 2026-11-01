from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.common.enums import ChatRole, ToolExecutionStatus
from app.modules.copilot.commands import (
    AddChatMessageCommand,
    CreateChatSessionCommand,
    UpdateChatSessionCommand,
)

# =============================================================================
# Ingress / Request Schemas (HTTP Inbound)
# =============================================================================


class ChatSessionCreateRequest(BaseModel):
    """Payload accepted by POST /api/v1/copilot/sessions"""

    title: str = Field(
        default="New Conversation",
        min_length=1,
        max_length=150,
        examples=["Q4 Campaign Brainstorm"],
    )
    system_prompt_override: str | None = Field(None, max_length=5000)
    extra_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("title")
    @classmethod
    def validate_title_not_empty(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("Session title cannot be empty or pure whitespace")
        return clean

    def to_command(self) -> CreateChatSessionCommand:
        return CreateChatSessionCommand(**self.model_dump())


class ChatSessionUpdateRequest(BaseModel):
    """Payload accepted by PATCH /api/v1/copilot/sessions/{session_id}"""

    title: str | None = Field(None, min_length=1, max_length=150)
    is_archived: bool | None = None
    system_prompt_override: str | None = Field(None, max_length=5000)
    extra_metadata: dict[str, Any] | None = None

    @field_validator("title")
    @classmethod
    def validate_title_not_empty(cls, value: str | None) -> str | None:
        if value is not None:
            clean = value.strip()
            if not clean:
                raise ValueError("Session title cannot be empty or pure whitespace")
            return clean
        return value

    def to_command(self, session_id: UUID) -> UpdateChatSessionCommand:
        return UpdateChatSessionCommand(
            session_id=session_id,
            **self.model_dump(exclude_unset=True),
        )


class ChatMessageCreateRequest(BaseModel):
    """Payload accepted by POST /api/v1/copilot/sessions/{session_id}/messages"""

    role: ChatRole = Field(default=ChatRole.USER)
    content: str = Field(
        ...,
        min_length=1,
        max_length=20000,
        examples=["Draft 3 tweets about our new AI features"],
    )
    model_name: str | None = Field(None, max_length=100)
    token_count: int | None = Field(None, ge=0)
    extra_metadata: dict[str, Any] = Field(default_factory=dict)

    def to_command(self, session_id: UUID) -> AddChatMessageCommand:
        return AddChatMessageCommand(
            session_id=session_id,
            **self.model_dump(),
        )


# =============================================================================
# Egress / Response Schemas (HTTP Outbound)
# =============================================================================


class ToolExecutionLogResponse(BaseModel):
    """Public trace of an AI tool execution."""

    id: UUID
    session_id: UUID
    message_id: UUID | None = None
    tool_name: str
    input_arguments: dict[str, Any]
    output_result: Any | None = None
    status: ToolExecutionStatus
    execution_time_ms: int | None = None
    error_message: str | None = None
    extra_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatMessageResponse(BaseModel):
    """Public view of a chat message."""

    id: UUID
    session_id: UUID
    role: ChatRole
    content: str
    token_count: int | None = None
    model_name: str | None = None
    extra_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatSessionResponse(BaseModel):
    """Summary view of a conversation thread."""

    id: UUID
    title: str
    is_archived: bool
    system_prompt_override: str | None = None
    extra_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatSessionDetailResponse(ChatSessionResponse):
    """Detailed view of a conversation thread including hydrated messages."""

    messages: list[ChatMessageResponse] = Field(default_factory=list)
