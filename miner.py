import os
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "/app/pw-browsers"  # Must be before playwright import

from playwright.sync_api import sync_playwright
import json
import time
import random
import re
from datetime import date, timedelta
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path)

USERNAME = os.getenv("MINER_USER")
PASSWORD = os.getenv("MINER_PASSWORD")
ADMIN_URL = "https://evolvemedspa.zenoti.com/Admin/Admin.aspx"
COOKIES_FILE = os.path.join(os.path.dirname(__file__), "cookies.json")

if not USERNAME or not PASSWORD:
    raise ValueError("MINER_USER and MINER_PASSWORD must be set in the .env file.")

yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
START_DATE = yesterday
END_DATE = yesterday

IS_LOCAL = os.getenv("RAILWAY_ENVIRONMENT") is None


def create_browser_and_context(pw):
    launch_args = {
        "headless": True,
        "args": [
            "--start-maximized",
            "--disable-blink-features=AutomationControlled",
        ],
    }

    if not IS_LOCAL:
        launch_args["args"] += [
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ]

    # Always use chromium (no channel), works both local and Railway
    browser = pw.chromium.launch(**launch_args)

    context_args = {"no_viewport": True}
    if os.path.exists(COOKIES_FILE):
        print(f"Loading saved cookies from {COOKIES_FILE}")
        context_args["storage_state"] = COOKIES_FILE

    context = browser.new_context(**context_args)
    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        window.chrome = {runtime: {}};
    """)
    return browser, context


def save_cookies(context):
    context.storage_state(path=COOKIES_FILE)
    print(f"Cookies saved to {COOKIES_FILE}")


def needs_login(page):
    """Check if current page is login page or admin dashboard."""
    page.goto(ADMIN_URL, wait_until="domcontentloaded")
    time.sleep(3)
    current_url = page.url
    print(f"Current URL after navigation: {current_url}")
    if "Admin" in current_url and "Login" not in current_url and "Account" not in current_url:
        return False
    return True


def do_login(page):
    print(f"Current URL before login: {page.url}")
    print("Waiting for login page...")

    # Wait for either SSO or direct login page
    try:
        page.wait_for_url("**/Account/Login**", timeout=15000)
        print("Redirected to IDS login page.")
    except:
        current_url = page.url
        print(f"URL after wait: {current_url}")
        if "Admin" in current_url and "Login" not in current_url:
            print("Already logged in!")
            return

    username_sel = "input#Username, input[name='Username'], input[name='username'], input[type='email']"
    page.wait_for_selector(username_sel, state="visible", timeout=15000)
    print("Login page loaded.")

    page.locator(username_sel).first.click()
    page.locator(username_sel).first.press_sequentially(USERNAME, delay=50)
    time.sleep(random.uniform(0.5, 1.5))
    print("Username entered.")

    page.locator('#Password').click()
    page.locator('#Password').press_sequentially(PASSWORD, delay=50)
    time.sleep(random.uniform(0.5, 1.5))
    print("Password entered.")
    time.sleep(2)

    login_button = page.locator('#btnLogin')
    print("Waiting for login button...")
    login_button.click(timeout=60000)
    print("Login button clicked.")
    time.sleep(random.uniform(2.0, 3.0))

    page.wait_for_url("**/Admin/**", timeout=30000)
    print("Login successful!")


def wait_for_dashboard(page):
    try:
        page.locator('#menuLinkreports').wait_for(state='visible', timeout=60000)
        print("Dashboard loaded.")
    except Exception as e:
        print(f"Error: Dashboard menu not found. URL: {page.url}")
        raise e


def download_report(context, page, report_name, start_date, end_date):
    page.goto("https://evolvemedspa.zenoti.com/Admin/Reports/ReportsDashboard.aspx")
    page.wait_for_load_state("networkidle")
    time.sleep(3)
    print(f"Opening report: {report_name}")

    with context.expect_page() as new_page_info:
        page.locator('#gridReports span.report-name').get_by_text(report_name, exact=True).click()

    time.sleep(3)
    report_page = new_page_info.value
    report_page.wait_for_load_state("load")
    report_page.wait_for_load_state("networkidle")
    time.sleep(3)
    print(f"{report_name} report page loaded.")

    report_page.locator('#elm_dates').click()
    time.sleep(3)

    try:
        report_page.locator('li[data-range-key="Custom"]').click(timeout=5000)
    except:
        report_page.evaluate("document.querySelector('li[data-range-key=\"Custom\"]').click()")
    time.sleep(3)

    def select_calendar_date(rp, date_str, side):
        year, month, day = date_str.split('-')
        month_val = str(int(month) - 1)
        day_val = str(int(day))
        cal = f'.drp-calendar.{side}'

        rp.locator(f'{cal} .yearselect').first.select_option(year)
        time.sleep(1)
        rp.locator(f'{cal} .monthselect').first.select_option(month_val)
        time.sleep(1)
        rp.locator(f'{cal} td.available:not(.off)').filter(has_text=re.compile(f"^{day_val}$")).first.click()
        time.sleep(1)

    select_calendar_date(report_page, start_date, "left")
    time.sleep(2)
    select_calendar_date(report_page, end_date, "right")
    time.sleep(2)

    report_page.evaluate("document.querySelector('button.applyBtn').click()")
    time.sleep(3)
    print("Date range set.")

    print("Refreshing report...")
    report_page.locator('#btnRefresh').click()
    time.sleep(3)
    report_page.wait_for_load_state("networkidle", timeout=60000)
    time.sleep(3)

    print("Exporting report to CSV...")
    report_page.locator('#dropdownMenuLink').click()
    time.sleep(3)

    with report_page.expect_download() as download_info:
        report_page.locator('#export_csv').click()

    time.sleep(3)
    download = download_info.value
    safe_name = report_name.replace(" ", "_").lower()
    filename = f"{safe_name}_{start_date}_to_{end_date}.csv"
    download.save_as(filename)
    print(f"Downloaded: {filename}")

    report_page.close()
    time.sleep(3)
    page.bring_to_front()
    time.sleep(3)
    return filename


with sync_playwright() as p:
    browser, context = create_browser_and_context(p)
    page = context.new_page()

    try:
        if needs_login(page):
            print("No valid session. Logging in...")
            do_login(page)
            save_cookies(context)
        else:
            print("Session valid from saved cookies. Skipping login.")

        wait_for_dashboard(page)
        save_cookies(context)

        reports = ["Appointments", "Cost of Goods", "Attendance", "Sales-Accrual", "Sales-Cash"]
        for report in reports:
            download_report(context, page, report, START_DATE, END_DATE)
            save_cookies(context)

    except Exception as e:
        print(f"Error: {e}")
    finally:
        context.close()
        browser.close()