import os
import time
from playwright.sync_api import sync_playwright

# ================= CONFIGURATION =================
USERNAME = "orlume51"
PASSWORD = "PKM9Ey$YbLUkTUH2uXx!"
IMAGE_PATH = os.path.abspath("orlume_logo.png")
CAPTION = "Hello from Orlume! 🌸✨"
SESSION_DIR = "./session/ig_session"
# =================================================


def post_to_instagram():
    if not os.path.exists(IMAGE_PATH):
        print(f"Error: File not found at {IMAGE_PATH}")
        return

    with sync_playwright() as p:
        print("Launching Chrome...")
        browser = p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            channel="chrome",
            headless=False,
            args=["--start-maximized"],
            no_viewport=True,
        )

        page = browser.pages[0]
        page.goto("https://www.instagram.com/")
        time.sleep(4)

        # 1. Handle Cookie Banner
        try:
            cookie_btn = page.get_by_role("button", name="Allow all cookies")
            if cookie_btn.is_visible():
                cookie_btn.click()
                time.sleep(2)
        except Exception:
            pass

        # 2. Check if we need to log in
        if page.locator('input[name="username"]').is_visible():
            print("Logging in...")
            page.locator('input[name="username"]').fill(USERNAME)
            page.locator('input[name="password"]').fill(PASSWORD)
            page.locator('button[type="submit"]').click()
            print("Waiting for home page...")

        # 3. Wait for the 'New post' (+) button
        new_post_btn = page.locator(
            'svg[aria-label="New post"], svg[aria-label="Create"]'
        ).first
        new_post_btn.wait_for(state="visible", timeout=60000)
        print("Logged in successfully!")

        # Dismiss "Turn on Notifications" popup if it appears
        for btn_text in ["Not Now", "Not now"]:
            try:
                not_now_btn = page.get_by_role(
                    "button", name=btn_text, exact=True
                )
                if not_now_btn.is_visible():
                    not_now_btn.click()
                    time.sleep(1)
            except Exception:
                pass

        # 4. Click the 'Create' / 'New post' button
        print("Opening create post modal...")
        new_post_btn.click()
        time.sleep(2)

        # If a sub-menu opens ("Post", "Live video"), click "Post"
        select_btn = page.get_by_role("button", name="Select from computer")
        if not select_btn.is_visible():
            post_submenu = (
                page.locator('svg[aria-label="Post"]')
                .or_(page.get_by_text("Post", exact=True))
                .first
            )
            if post_submenu.is_visible():
                post_submenu.click()
                time.sleep(1)

        # 5. Upload the Image
        print(f"Uploading {IMAGE_PATH}...")
        with page.expect_file_chooser() as fc_info:
            select_btn.click()

        file_chooser = fc_info.value
        file_chooser.set_files(IMAGE_PATH)
        time.sleep(2)

        # 6. Navigate through Crop and Filter screens
        print("Clicking through Next buttons...")
        page.get_by_role("button", name="Next").click()
        time.sleep(2)

        page.get_by_role("button", name="Next").click()
        time.sleep(2)

        # 7. Write the Caption (Updated for "Add a caption...")
        print("Writing caption...")
        caption_box = page.locator(
            'div[aria-label="Add a caption..."], div[aria-label="Write a caption..."], div[role="dialog"] div[role="textbox"]'
        ).first
        caption_box.click()
        time.sleep(1)
        page.keyboard.insert_text(CAPTION)
        time.sleep(2)

        # 8. Click Share
        print("Sharing post...")
        page.get_by_role("dialog").get_by_role(
            "button", name="Share", exact=True
        ).click()

        # 9. Wait for confirmation
        print("Waiting for upload to finish...")
        page.get_by_text("Your post has been shared.").or_(
            page.get_by_text("Post shared")
        ).first.wait_for(state="visible", timeout=60000)
        print("✅ Post uploaded successfully!")

        time.sleep(5)
        browser.close()


if __name__ == "__main__":
    post_to_instagram()