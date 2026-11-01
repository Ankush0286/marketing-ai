from uuid import UUID

from app.common.exceptions import AppError, ConflictError, NotFoundError


class CampaignNotFoundError(NotFoundError):
    """Raised when a campaign ID does not exist."""

    def __init__(self, campaign_id: UUID | str):
        super().__init__(f"Campaign with ID '{campaign_id}' was not found.")
        self.campaign_id = campaign_id


class PostNotFoundError(NotFoundError):
    """Raised when a scheduled post ID does not exist."""

    def __init__(self, post_id: UUID | str):
        super().__init__(f"Scheduled post with ID '{post_id}' was not found.")
        self.post_id = post_id


class CampaignInactiveError(AppError):
    """Raised when trying to queue posts under an archived, paused, or completed campaign."""

    def __init__(self, campaign_id: UUID | str, status: str):
        super().__init__(
            f"Cannot queue posts for campaign '{campaign_id}' because its status is '{status}'."
        )
        self.campaign_id = campaign_id
        self.status = status


class InvalidPostScheduleError(AppError):
    """Raised when schedule timestamp is in the past or outside campaign date boundaries."""

    def __init__(self, message: str = "Invalid post schedule timestamp provided."):
        super().__init__(message)


class PostAlreadyPublishedError(ConflictError):
    """Raised when attempting to modify, reschedule, or delete an already published post."""

    def __init__(self, post_id: UUID | str):
        super().__init__(
            f"Post '{post_id}' has already been published and cannot be modified."
        )
        self.post_id = post_id
