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

    NANO = "nano"
    MICRO = "micro"
    MID = "mid"
    MACRO = "macro"
    MEGA = "mega"


class OutreachChannel(str, enum.Enum):
    """Medium used for cold outreach message delivery."""

    DM = "dm"
    EMAIL = "email"


class OutreachMessageStatus(str, enum.Enum):
    """Human-in-the-loop cold DM delivery state machine."""

    DRAFT = "draft"
    STAGED = "staged"
    APPROVED = "approved"
    REJECTED = "rejected"
    DISPATCHED = "dispatched"
    FAILED = "failed"


class ActivitySeverity(str, enum.Enum):
    """Severity classification for audit trail logs."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class ActivityType(str, enum.Enum):
    """Domain events tracked in the unified audit trail."""

    # Accounts
    ACCOUNT_CONNECTED = "account_connected"
    ACCOUNT_COOLDOWN_TRIGGERED = "account_cooldown_triggered"
    ACCOUNT_UPDATED = "account_updated"
    ACCOUNT_DELETED = "account_deleted"

    # Campaigns & Posts
    CAMPAIGN_CREATED = "campaign_created"
    POST_SCHEDULED = "post_scheduled"
    POST_PUBLISHED = "post_published"
    POST_FAILED = "post_failed"
    POST_CANCELLED = "post_cancelled"

    # Triggers & Monitoring
    TRIGGER_MATCHED = "trigger_matched"
    TRIGGER_APPROVED = "trigger_approved"
    TRIGGER_IGNORED = "trigger_ignored"

    # Outreach CRM
    LEAD_IMPORTED = "lead_imported"
    MESSAGE_STAGED = "message_staged"
    MESSAGE_APPROVED = "message_approved"
    MESSAGE_REJECTED = "message_rejected"
    MESSAGE_DISPATCHED = "message_dispatched"

    # System & Automation
    SYSTEM_REPLICA_SYNCED = "system_replica_synced"
    SYSTEM_QUOTA_RESET = "system_quota_reset"
    AGENT_TOOL_EXECUTED = "agent_tool_executed"
