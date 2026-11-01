from uuid import UUID

from app.common.exceptions import AppError, ConflictError, NotFoundError


class WatchedHandleNotFoundError(NotFoundError):
    """Raised when a watched handle ID does not exist."""

    def __init__(self, handle_id: UUID | str):
        super().__init__(f"Watched handle with ID '{handle_id}' was not found.")
        self.handle_id = handle_id


class WatchedHandleAlreadyExistsError(ConflictError):
    """Raised when trying to monitor an already tracked handle."""

    def __init__(self, platform: str, handle: str):
        super().__init__(f"Account @{handle} on {platform} is already being watched.")
        self.platform = platform
        self.handle = handle


class TriggerRuleNotFoundError(NotFoundError):
    """Raised when a trigger rule ID does not exist."""

    def __init__(self, rule_id: UUID | str):
        super().__init__(f"Trigger rule with ID '{rule_id}' was not found.")
        self.rule_id = rule_id


class TriggerMatchNotFoundError(NotFoundError):
    """Raised when a trigger match ID does not exist."""

    def __init__(self, match_id: UUID | str):
        super().__init__(f"Trigger match with ID '{match_id}' was not found.")
        self.match_id = match_id


class InvalidTriggerRuleError(AppError):
    """Raised when rule lacks keywords or specifies invalid parameters."""

    def __init__(self, message: str = "Invalid trigger rule criteria provided."):
        super().__init__(message)
