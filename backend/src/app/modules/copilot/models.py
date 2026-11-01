from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_models import AuditBase
from app.common.enums import ChatRole, ToolExecutionStatus


class ChatSession(AuditBase):
    """
    An ongoing AI assistant conversation thread preserving context and goal history.
    """

    __tablename__ = "chat_sessions"

    title: Mapped[str] = mapped_column(
        String(150),
        default="New Conversation",
        nullable=False,
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    system_prompt_override: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    # Relationships
    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )
    tool_executions: Mapped[list["ToolExecutionLog"]] = relationship(
        "ToolExecutionLog",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ToolExecutionLog.created_at",
    )


class ChatMessage(AuditBase):
    """
    A single conversational turn (user prompt, assistant response, or tool return).
    """

    __tablename__ = "chat_messages"

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[ChatRole] = mapped_column(
        SAEnum(ChatRole, native_enum=False),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    token_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    model_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    # Relationships
    session: Mapped[ChatSession] = relationship(
        "ChatSession",
        back_populates="messages",
    )
    tool_executions: Mapped[list["ToolExecutionLog"]] = relationship(
        "ToolExecutionLog",
        back_populates="message",
    )


class ToolExecutionLog(AuditBase):
    """
    Detailed trace of a tool executed by the ReAct agent (e.g. get_accounts, queue_post).
    """

    __tablename__ = "tool_execution_logs"

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tool_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    input_arguments: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    output_result: Mapped[Any | None] = mapped_column(
        JSON,
        nullable=True,
    )
    status: Mapped[ToolExecutionStatus] = mapped_column(
        SAEnum(ToolExecutionStatus, native_enum=False),
        default=ToolExecutionStatus.SUCCESS,
        nullable=False,
        index=True,
    )
    execution_time_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    # Relationships
    session: Mapped[ChatSession] = relationship(
        "ChatSession",
        back_populates="tool_executions",
    )
    message: Mapped[ChatMessage | None] = relationship(
        "ChatMessage",
        back_populates="tool_executions",
    )

    __table_args__ = (
        Index("ix_tool_executions_session_status", "session_id", "status"),
    )
