from uuid import UUID

from app.common.exceptions import AppError, ConflictError, NotFoundError


class LeadNotFoundError(NotFoundError):
    """Raised when a lead ID does not exist."""

    def __init__(self, lead_id: UUID | str):
        super().__init__(f"Lead with ID '{lead_id}' was not found.")
        self.lead_id = lead_id


class LeadAlreadyExistsError(ConflictError):
    """Raised when importing an already tracked lead."""

    def __init__(self, platform: str, handle: str):
        super().__init__(f"Lead @{handle} on {platform} already exists.")
        self.platform = platform
        self.handle = handle


class LeadUncontactableError(ConflictError):
    """Raised when trying to message a lead marked 'do_not_contact' or 'converted'."""

    def __init__(self, handle: str, stage: str):
        super().__init__(f"Cannot contact @{handle} because their stage is '{stage}'.")
        self.handle = handle
        self.stage = stage


class OutreachCampaignNotFoundError(NotFoundError):
    """Raised when an outreach campaign ID does not exist."""

    def __init__(self, campaign_id: UUID | str):
        super().__init__(f"Outreach campaign with ID '{campaign_id}' was not found.")
        self.campaign_id = campaign_id


class OutreachMessageNotFoundError(NotFoundError):
    """Raised when an outreach message ID does not exist."""

    def __init__(self, message_id: UUID | str):
        super().__init__(f"Outreach message with ID '{message_id}' was not found.")
        self.message_id = message_id


class MessageAlreadyProcessedError(ConflictError):
    """Raised when trying to modify or review an already dispatched message."""

    def __init__(self, message_id: UUID | str):
        super().__init__(f"Outreach message '{message_id}' has already been processed and cannot be reviewed.")
        self.message_id = message_id


class DailyDMQuotaExceededError(AppError):
    """Raised when an account exceeds safe anti-ban cold DM limits."""

    def __init__(self, handle: str, limit: int):
        super().__init__(f"Account @{handle} has reached its daily limit of {limit} cold DMs.")
        self.handle = handle
        self.limit = limit
