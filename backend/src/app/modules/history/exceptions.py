from uuid import UUID

from app.common.exceptions import NotFoundError


class ActivityLogNotFoundError(NotFoundError):
    """Raised when an activity log ID does not exist."""

    def __init__(self, log_id: UUID | str):
        super().__init__(f"Activity log with ID '{log_id}' was not found.")
        self.log_id = log_id
