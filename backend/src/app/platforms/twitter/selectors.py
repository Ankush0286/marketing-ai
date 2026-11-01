"""
Centralized DOM selectors for Twitter / X Web automation.
Prioritizes official data-testid attributes, semantic button roles, and form names.
"""

# Cookie Banners & Modal Dismissals
COOKIE_ACCEPT_BUTTON = 'button:has-text("Accept all cookies"), [role="button"]:has-text("Refuse non-essential cookies")'
CLOSE_MODAL_BUTTON = 'button[data-testid="app-bar-close"], div[data-testid="app-bar-close"]'

# Multi-Step Login Flow
LOGIN_USERNAME_INPUT = 'input[autocomplete="username"], input[name="text"]'
LOGIN_NEXT_BUTTON = 'button:has-text("Next"), div[role="button"]:has-text("Next")'
LOGIN_PASSWORD_INPUT = 'input[name="password"]'
LOGIN_SUBMIT_BUTTON = 'button[data-testid="LoginForm_Login_Button"], button:has-text("Log in"), div[role="button"]:has-text("Log in")'
LOGIN_UNUSUAL_ACTIVITY_INPUT = 'input[data-testid="ocfEnterTextTextInput"]'

# Navigation & Home Verification
HOME_NAV_ICON = 'a[data-testid="AppTabBar_Home_Link"]'
PROFILE_NAV_ICON = 'a[data-testid="AppTabBar_Profile_Link"]'

# Tweet / Post Compose Box
TWEET_TEXTAREA = (
    'div[data-testid="tweetTextarea_0"], '
    'div[role="textbox"][data-testid^="tweetTextarea_"]'
)
TWEET_FILE_INPUT = 'input[data-testid="fileInput"]'
TWEET_SUBMIT_BUTTON = (
    'button[data-testid="tweetButtonInline"], '
    'button[data-testid="tweetButton"]'
)
TWEET_POSTED_TOAST = 'div[data-testid="toast"]'

# Direct Messages (DM) Flow
PROFILE_DM_BUTTON = (
    'button[data-testid="sendDMFromProfile"], '
    'div[data-testid="sendDMFromProfile"]'
)
DM_TEXTAREA = (
    'div[data-testid="dmComposerTextInput"], '
    'div[role="textbox"][aria-label="Start a new message"]'
)
DM_SEND_BUTTON = 'button[data-testid="dmComposerSendButton"]'

# Profile & Timeline Scraping
TWEET_ARTICLE = 'article[data-testid="tweet"]'
TWEET_TEXT = 'div[data-testid="tweetText"]'
TWEET_STATUS_LINK = 'a[href*="/status/"]'
TWEET_TIME = "time"
