import os
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

load_dotenv()

ZENOTI_USER = os.getenv("MINER_USER")
ZENOTI_PASS = os.getenv("MINER_PASSWORD")
ADMIN_URL = "https://evolvemedspa.zenoti.com/Admin/Admin.aspx"


def login(page):
    print("Navigating to Zenoti admin...")
    page.goto(ADMIN_URL, wait_until="domcontentloaded")

    print("Waiting for IDS login redirect...")
    page.wait_for_url("**/Account/Login**", timeout=30000)

    print("Login page loaded. Filling credentials...")
    username_input = page.wait_for_selector(
        "input[name='Username'], input[name='username'], #Username, input[type='email'], input[name='Email']",
        timeout=15000,
    )
    username_input.fill(ZENOTI_USER)

    password_input = page.wait_for_selector(
        "input[name='Password'], input[name='password'], #Password, input[type='password']",
        timeout=5000,
    )
    password_input.fill(ZENOTI_PASS)

    print("Submitting login...")
    submit = page.wait_for_selector(
        "button[type='submit'], input[type='submit'], button:has-text('Log'), button:has-text('Sign')",
        timeout=5000,
    )
    submit.click()

    print("Waiting for admin page after login...")
    page.wait_for_url("**/Admin/**", timeout=30000)
    print("Login successful!")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()

        try:
            login(page)

            # DEBUG: pause here so you can see what's on screen
            print("Logged in. Browser will stay open 30s for inspection...")
            page.wait_for_timeout(30000)

        except PlaywrightTimeout as e:
            print(f"Timeout: {e}")
            # Screenshot for debugging
            page.screenshot(path="debug_screenshot.png")
            print("Screenshot saved to debug_screenshot.png")
        except Exception as e:
            print(f"Error: {e}")
            page.screenshot(path="debug_screenshot.png")
            print("Screenshot saved to debug_screenshot.png")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
