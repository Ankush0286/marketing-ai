from uuid import UUID

from sqlalchemy.orm import Session, selectinload

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
from app.modules.copilot.models import ChatMessage, ChatSession, ToolExecutionLog


def _ensure_uuid(val: UUID | str) -> UUID:
    return val if isinstance(val, UUID) else UUID(str(val))


class CopilotService:
    def __init__(self, db: Session):
        self.db = db

    def get_session_by_id(self, session_id: UUID | str) -> ChatSession | None:
        target_id = _ensure_uuid(session_id)
        return (
            self.db.query(ChatSession)
            .options(selectinload(ChatSession.messages))
            .filter(ChatSession.id == target_id)
            .first()
        )

    def get_session_by_id_or_raise(self, session_id: UUID | str) -> ChatSession:
        session = self.get_session_by_id(session_id)
        if not session:
            raise ChatSessionNotFoundError(session_id)
        return session

    def list_sessions(
        self, include_archived: bool = False, limit: int = 50, offset: int = 0
    ) -> list[ChatSession]:
        query = self.db.query(ChatSession).order_by(ChatSession.updated_at.desc())
        if not include_archived:
            query = query.filter(ChatSession.is_archived.is_(False))
        return query.offset(offset).limit(limit).all()

    def create_session(self, cmd: CreateChatSessionCommand) -> ChatSession:
        session = ChatSession(
            title=cmd.title.strip(),
            system_prompt_override=cmd.system_prompt_override,
            extra_metadata=cmd.extra_metadata,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def update_session(self, cmd: UpdateChatSessionCommand) -> ChatSession:
        session = self.get_session_by_id_or_raise(cmd.session_id)

        if cmd.title is not None:
            session.title = cmd.title.strip()
        if cmd.is_archived is not None:
            session.is_archived = cmd.is_archived
        if cmd.system_prompt_override is not None:
            session.system_prompt_override = cmd.system_prompt_override
        if cmd.extra_metadata is not None:
            session.extra_metadata = cmd.extra_metadata

        self.db.commit()
        self.db.refresh(session)
        return session

    def delete_session(self, session_id: UUID | str) -> None:
        session = self.get_session_by_id_or_raise(session_id)
        # Purge dependent tool logs and messages to guarantee cascade safety
        self.db.query(ToolExecutionLog).filter(ToolExecutionLog.session_id == session.id).delete(
            synchronize_session="fetch"
        )
        self.db.query(ChatMessage).filter(ChatMessage.session_id == session.id).delete(
            synchronize_session="fetch"
        )
        self.db.delete(session)
        self.db.commit()

    def add_message(self, cmd: AddChatMessageCommand) -> ChatMessage:
        self.get_session_by_id_or_raise(cmd.session_id)

        message = ChatMessage(
            session_id=cmd.session_id,
            role=cmd.role,
            content=cmd.content,
            token_count=cmd.token_count,
            model_name=cmd.model_name,
            extra_metadata=cmd.extra_metadata,
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def get_message_by_id_or_raise(self, message_id: UUID | str) -> ChatMessage:
        target_id = _ensure_uuid(message_id)
        message = self.db.query(ChatMessage).filter(ChatMessage.id == target_id).first()
        if not message:
            raise ChatMessageNotFoundError(message_id)
        return message

    def list_messages(
        self, session_id: UUID | str, limit: int = 100, offset: int = 0
    ) -> list[ChatMessage]:
        target_id = _ensure_uuid(session_id)
        self.get_session_by_id_or_raise(target_id)
        return (
            self.db.query(ChatMessage)
            .filter(ChatMessage.session_id == target_id)
            .order_by(ChatMessage.created_at.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_conversation_context(
        self, session_id: UUID | str, max_messages: int = 20
    ) -> list[dict[str, str]]:
        """
        Hydrates conversational context into standardized LLM prompt payloads.
        Includes session's system_prompt_override if present.
        """
        session = self.get_session_by_id_or_raise(session_id)

        messages = (
            self.db.query(ChatMessage)
            .filter(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.created_at.desc())
            .limit(max_messages)
            .all()
        )
        messages.reverse()

        context: list[dict[str, str]] = []

        # 1. Prepend System Prompt if configured
        if session.system_prompt_override:
            context.append({"role": "system", "content": session.system_prompt_override})

        # 2. Append Chronological Conversation Turns
        for msg in messages:
            context.append({"role": msg.role.value, "content": msg.content})

        return context

    def log_tool_execution(self, cmd: LogToolExecutionCommand) -> ToolExecutionLog:
        self.get_session_by_id_or_raise(cmd.session_id)

        # Validate message association if supplied
        if cmd.message_id:
            self.get_message_by_id_or_raise(cmd.message_id)

        tool_log = ToolExecutionLog(
            session_id=cmd.session_id,
            message_id=cmd.message_id,
            tool_name=cmd.tool_name,
            input_arguments=cmd.input_arguments,
            output_result=cmd.output_result,
            status=cmd.status,
            execution_time_ms=cmd.execution_time_ms,
            error_message=cmd.error_message,
            extra_metadata=cmd.extra_metadata,
        )
        self.db.add(tool_log)
        self.db.commit()
        self.db.refresh(tool_log)
        return tool_log

    def list_tool_executions(self, session_id: UUID | str) -> list[ToolExecutionLog]:
        target_id = _ensure_uuid(session_id)
        self.get_session_by_id_or_raise(target_id)
        return (
            self.db.query(ToolExecutionLog)
            .filter(ToolExecutionLog.session_id == target_id)
            .order_by(ToolExecutionLog.created_at.asc())
            .all()
        )
