class AppError(Exception):
    """Base exception for all application errors."""
    def __init__(self, message: str = "An unexpected error occurred."):
        self.message = message
        super().__init__(self.message)


class NotFoundError(AppError):
    """Raised when an entity requested by ID or unique key does not exist."""


class ConflictError(AppError):
    """Raised when an operation would violate uniqueness or business invariants."""


class RateLimitExceededError(AppError):
    """Raised when daily quotas or cooldown windows prevent an action."""


class AuthenticationFailedError(AppError):
    """Raised when credentials, cookies, or tokens fail validation."""
