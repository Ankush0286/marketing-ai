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


class TriggerActionType(str, enum.Enum):
    """Action executed when an incoming post matches a trigger rule."""

    AUTO_REPLY = "auto_reply"
    STAGE_DRAFT = "stage_draft"
    NOTIFY_ONLY = "notify_only"
    DISPATCH_DM = "dispatch_dm"


class TriggerMatchStatus(str, enum.Enum):
    """Lifecycle state of an intercepted conversation or tweet."""

    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    DISPATCHED = "dispatched"
    IGNORED = "ignored"
    FAILED = "failed"


class LeadStage(str, enum.Enum):
    """CRM relationship stage of an influencer or prospect."""

    DISCOVERED = "discovered"
    QUALIFIED = "qualified"
    CONTACTED = "contacted"
    REPLIED = "replied"
    CONVERTED = "converted"
    UNRESPONSIVE = "unresponsive"
    DO_NOT_CONTACT = "do_not_contact"


class LeadTier(str, enum.Enum):
    """Audience sizing categorization."""

    NANO = "nano"        # 1k - 10k
    MICRO = "micro"      # 10k - 50k
    MID = "mid"          # 50k - 200k
    MACRO = "macro"      # 200k - 1M
    MEGA = "mega"        # 1M+


class OutreachChannel(str, enum.Enum):
    """Medium used for cold outreach message delivery."""

    DM = "dm"
    EMAIL = "email"


class OutreachMessageStatus(str, enum.Enum):
    """Human-in-the-loop cold DM delivery state machine."""

    DRAFT = "draft"
    STAGED = "staged"            # Waiting for human review
    APPROVED = "approved"        # Human approved for dispatch
    REJECTED = "rejected"        # Dismissed by human
    DISPATCHED = "dispatched"    # Delivered by platform adapter
    FAILED = "failed"
