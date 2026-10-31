import enum


class PlatformType(str, enum.Enum):
    TWITTER = "twitter"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    EMAIL = "email"

class AccountStatus(str, enum.Enum):
    ACTIVE = "active"
    NEEDS_REAUTH = "needs_reauth"  
    RATE_LIMITED = "rate_limited" 
    DISCONNECTED = "disconnected"
    SUSPENDED = "suspended"

class AuthMethod(str, enum.Enum):
    API_KEYS = "api_keys"         
    BROWSER_SESSION = "browser_session" 
    HYBRID = "hybrid"

