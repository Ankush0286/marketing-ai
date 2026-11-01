import enum


class PlatformType(str, enum.Enum):
    """Supported social media and communication platforms."""

    TWITTER = "twitter"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    EMAIL = "email"


class AccountStatus(str, enum.Enum):
    """Operational health status of a connected profile."""

    ACTIVE = "active"
    NEEDS_REAUTH = "needs_reauth"
    RATE_LIMITED = "rate_limited"
    DISCONNECTED = "disconnected"
    SUSPENDED = "suspended"


class AuthMethod(str, enum.Enum):
    """Authentication mechanism utilized for platform interactions."""

    API_KEYS = "api_keys"
    BROWSER_SESSION = "browser_session"
    HYBRID = "hybrid"


class CampaignStatus(str, enum.Enum):
    """High-level lifecycle state of a marketing campaign."""

    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class PostStatus(str, enum.Enum):
    """Execution state machine for individual scheduled posts."""

    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PostContentType(str, enum.Enum):
    """Type of payload format dispatched to the target platform."""

    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    CAROUSEL = "carousel"
    THREAD = "thread"
