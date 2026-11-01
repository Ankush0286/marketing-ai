"""
Centralized DOM selectors for Instagram Web automation.
Prioritizes semantic aria-labels, button roles, and form names over dynamic CSS classes.
"""

# Cookie Banners & Security Checkpoints
COOKIE_ALLOW_BUTTON = 'button:has-text("Allow all cookies"), button:has-text("Allow essential and optional cookies")'
POPUP_NOT_NOW_BUTTONS = ["Not Now", "Not now", "Cancel"]

# Login Form
LOGIN_USERNAME_INPUT = 'input[name="username"]'
LOGIN_PASSWORD_INPUT = 'input[name="password"]'
LOGIN_SUBMIT_BUTTON = 'button[type="submit"]'

# Navigation Bar
NAV_CREATE_BUTTON = 'svg[aria-label="New post"], svg[aria-label="Create"]'
NAV_DIRECT_MESSAGES = 'svg[aria-label="Direct"], svg[aria-label="Messenger"]'
NAV_SEARCH_BUTTON = 'svg[aria-label="Search"]'
NAV_PROFILE_LINK = 'a[href*="/direct/"], a[role="link"]:has(img[alt*="profile picture"])'

# Post Creation Modal Flow
CREATE_POST_SUBMENU_ITEM = 'svg[aria-label="Post"], [role="menuitem"]:has-text("Post"), button:has-text("Post")'
SELECT_FROM_COMPUTER_BUTTON = 'button:has-text("Select from computer")'
NEXT_BUTTON = 'button:has-text("Next"), div[role="button"]:has-text("Next")'
SHARE_BUTTON = '[role="dialog"] button:has-text("Share"), [role="dialog"] div[role="button"]:has-text("Share")'
CAPTION_TEXTAREA = (
    'div[aria-label="Add a caption..."], '
    'div[aria-label="Write a caption..."], '
    '[role="dialog"] div[role="textbox"]'
)
POST_SUCCESS_INDICATORS = [
    "Your post has been shared.",
    "Post shared",
    "Post created",
]

# Direct Messages (DM) Flow
PROFILE_MESSAGE_BUTTON = (
    'header button:has-text("Message"), '
    'header div[role="button"]:has-text("Message"), '
    'button:has-text("Message")'
)
DM_INPUT_TEXTBOX = (
    'div[aria-label="Message"], '
    'div[role="textbox"][contenteditable="true"]'
)

# Profile Scraping & Grid
PROFILE_POST_LINKS = 'article a[href^="/p/"], a[href^="/p/"], a[href^="/reel/"]'
PROFILE_HEADER_STATS = "header section ul li"
