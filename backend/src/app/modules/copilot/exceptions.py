from uuid import UUID

from app.common.exceptions import NotFoundError


class ChatSessionNotFoundError(NotFoundError):
    """Raised when a chat session ID does not exist."""

    def __init__(self, session_id: UUID | str):
        super().__init__(f"Chat session with ID '{session_id}' was not found.")
        self.session_id = session_id


class ChatMessageNotFoundError(NotFoundError):
    """Raised when a chat message ID does not exist."""

    def __init__(self, message_id: UUID | str):
        super().__init__(f"Chat message with ID '{message_id}' was not found.")
        self.message_id = message_id


class ToolExecutionNotFoundError(NotFoundError):
    """Raised when a tool execution log ID does not exist."""

    def __init__(self, execution_id: UUID | str):
        super().__init__(f"Tool execution with ID '{execution_id}' was not found.")
        self.execution_id = execution_id
