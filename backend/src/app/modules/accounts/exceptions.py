from uuid import UUID

from app.common.exceptions import ConflictError, NotFoundError, RateLimitExceededError


class AccountNotFoundError(NotFoundError):
    def __init__(self, account_id: UUID | str):
        super().__init__(f"Connected account with ID '{account_id}' was not found.")
        self.account_id = account_id

class AccountAlreadyExistsError(ConflictError):
    def __init__(self, platform: str, handle: str):
        super().__init__(f"Account @{handle} on {platform} is already connected.")
        self.platform = platform
        self.handle = handle

class DailyPostQuotaExceededError(RateLimitExceededError):
    def __init__(self, handle: str, limit: int):
        super().__init__(f"Account @{handle} reached its daily limit of {limit} posts.")
        self.handle = handle
        self.limit = limit

class AccountInCooldownError(RateLimitExceededError):
    def __init__(self, handle: str, until_iso: str):
        super().__init__(f"Account @{handle} is in anti-ban cooldown until {until_iso}.")
        self.handle = handle
        self.until_iso = until_iso
