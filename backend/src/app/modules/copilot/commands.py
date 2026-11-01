from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.common.enums import ChatRole, ToolExecutionStatus


@dataclass(frozen=True)
class CreateChatSessionCommand:
    """Payload to create a new conversational AI thread."""

    title: str = "New Conversation"
    system_prompt_override: str | None = None
    extra_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UpdateChatSessionCommand:
    """Payload to rename, archive, or configure a chat thread."""

    session_id: UUID
    title: str | None = None
    is_archived: bool | None = None
    system_prompt_override: str | None = None
    extra_metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class AddChatMessageCommand:
    """Payload to persist a user, assistant, or tool message."""

    session_id: UUID
    role: ChatRole
    content: str
    token_count: int | None = None
    model_name: str | None = None
    extra_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LogToolExecutionCommand:
    """Payload to record an AI tool call with arguments and return payload."""

    session_id: UUID
    tool_name: str
    input_arguments: dict[str, Any]
    output_result: Any | None = None
    message_id: UUID | None = None
    status: ToolExecutionStatus = ToolExecutionStatus.SUCCESS
    execution_time_ms: int | None = None
    error_message: str | None = None
    extra_metadata: dict[str, Any] = field(default_factory=dict)
