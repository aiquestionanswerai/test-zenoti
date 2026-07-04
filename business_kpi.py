import os

if os.getenv("RAILWAY_ENVIRONMENT"):
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "/app/pw-browsers"

from playwright.sync_api import sync_playwright
import json
import time
import random
import sys
import io
import csv
import calendar
from datetime import date, datetime, timedelta
from dotenv import load_dotenv

print("Imports done.", flush=True)

dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path)

USERNAME = os.getenv("MINER_USER")
PASSWORD = os.getenv("MINER_PASSWORD")
ADMIN_URL = "https://evolvemedspa.zenoti.com/Admin/Admin.aspx"
COOKIES_FILE = os.path.join(os.path.dirname(__file__), "cookies.json")

if not USERNAME or not PASSWORD:
    raise ValueError("MINER_USER and MINER_PASSWORD must be set in the .env file.")

IS_LOCAL = os.getenv("RAILWAY_ENVIRONMENT") is None
SCRIPT_DIR = os.path.dirname(__file__) or "."

START_YEAR = 2022
START_MONTH = 1


def generate_month_ranges(start_year, start_month):
    today = date.today()
    y, m = start_year, start_month
    while (y, m) <= (today.year, today.month):
        first_day = date(y, m, 1)
        last_day = date(y, m, calendar.monthrange(y, m)[1])
        if last_day > today:
            last_day = today
        yield first_day, last_day
        m += 1
        if m > 12:
            m = 1
            y += 1


def create_browser_and_context(pw):
    launch_args = {
        "headless": False,
        "args": [
            "--start-maximized",
            "--disable-blink-features=AutomationControlled",
        ],
    }

    if IS_LOCAL:
        launch_args["channel"] = "chrome"
    else:
        launch_args["args"] += [
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ]

    browser = pw.chromium.launch(**launch_args)

    context_args = {"no_viewport": True, "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"}
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
    print(f"Checking if login is needed. Current URL: {page.url}")
    page.goto(ADMIN_URL, wait_until="domcontentloaded")
    try:
        page.wait_for_url("**/Admin/**", timeout=10000)
        return False
    except:
        return True


def do_login(page):
    print(f"Current URL before login: {page.url}")

    username_sel = "input#Username, input[name='Username'], input[name='username'], input[type='email']"
    if not page.locator(username_sel).first.is_visible():
        print("Login form not visible, navigating to admin...")
        page.goto(ADMIN_URL, wait_until="networkidle")

    try:
        page.wait_for_selector(username_sel, state="visible", timeout=30000)
    except Exception as e:
        print(f"Login form not found. URL: {page.url}")
        print(f"Page title: {page.title()}")
        print(f"Page content preview: {page.content()[:1000]}")
        raise e
    print(f"Login page loaded. URL: {page.url}")

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
    try:
        login_button.click(timeout=10000)
    except:
        print("Button disabled (captcha pending). Forcing submit via JS...")
        page.evaluate("document.getElementById('btnLogin').removeAttribute('disabled')")
        page.evaluate("document.getElementById('btnLogin').click()")
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


def validate_csv(filepath):
    filename = os.path.basename(filepath)

    if not os.path.exists(filepath):
        raise Exception(f"File not found: {filename}")

    filesize = os.path.getsize(filepath)
    if filesize == 0:
        raise Exception(f"File is empty: {filename}")

    filesize_mb = filesize / (1024 * 1024)
    print(f"  File size: {filesize_mb:.2f} MB")

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        head = f.read(1024)

    if "<html" in head.lower() or "<!doctype" in head.lower():
        raise Exception(f"File is HTML, not CSV (possible error page): {filename}")

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        try:
            headers = next(reader)
        except StopIteration:
            raise Exception(f"CSV has no headers: {filename}")

        if len(headers) < 2:
            raise Exception(f"CSV has only {len(headers)} column(s), likely corrupt: {filename}")

        row_count = 0
        for row in reader:
            row_count += 1
            if row_count >= 5:
                break

        if row_count == 0:
            raise Exception(f"CSV has headers but no data rows: {filename}")

    print(f"  CSV valid: {len(headers)} columns, {row_count}+ data rows")
    return True


def open_business_kpi_report(context, page):
    page.goto("https://evolvemedspa.zenoti.com/Admin/Reports/ReportsDashboard.aspx")
    page.wait_for_load_state("networkidle", timeout=120000)
    time.sleep(5)
    print("Reports Dashboard loaded.")

    print("Clicking 'View All'...")
    page.evaluate('loadBookmarksViewAllGrid("Bookmarked")')
    time.sleep(5)

    print("Clicking 'Business KPI'...")
    with context.expect_page(timeout=120000) as new_page_info:
        page.evaluate("ReportsGrid_Row_Click(event,'business_kpi')")

    time.sleep(5)
    report_page = new_page_info.value
    report_page.wait_for_load_state("load", timeout=120000)
    report_page.wait_for_load_state("networkidle", timeout=120000)
    time.sleep(5)
    print("Business KPI report page loaded.")
    return report_page


def apply_business_kpi_filters(report_page):
    print("Applying Business KPI filters...")
    report_page.evaluate("""
        (function() {
            // Centers → All
            var cb = document.getElementById('elm_centers-zenoti-dropdown-options-all');
            if (cb && !cb.checked) cb.click();

            // Invoice Status → select All
            $('select[multiple]').each(function() {
                $(this).multiselect('selectAll', false);
            });

            // Uncheck 'Show Sales Including Tax'
            var taxCb = document.getElementById('elm_include_tax');
            if (taxCb && taxCb.checked) taxCb.click();
        })();
    """)
    time.sleep(2)
    print("Filters applied.")


def download_month(report_page, start_date, end_date):
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    month_label = start_date.strftime("%b %Y")
    print(f"\n--- Downloading: {month_label} ({start_str} to {end_str}) ---")

    report_page.evaluate(f"""
        (function() {{
            var picker = $('#elm_dates').data('daterangepicker');
            if (picker) {{
                var startDate = moment('{start_str}', 'YYYY-MM-DD');
                var endDate = moment('{end_str}', 'YYYY-MM-DD');
                picker.setStartDate(startDate);
                picker.setEndDate(endDate);
                picker.element.trigger('apply.daterangepicker', picker);
            }}
        }})();
    """)
    time.sleep(3)
    print("Date range set.")

    print("Refreshing report...")
    report_page.evaluate("document.querySelector('#btnRefresh').click()")
    time.sleep(5)
    report_page.wait_for_load_state("networkidle", timeout=300000)
    time.sleep(10)

    print("Exporting to CSV...")
    report_page.locator('#dropdownMenuLink').click()
    time.sleep(2)

    with report_page.expect_download(timeout=300000) as download_info:
        report_page.evaluate("document.querySelector('#export_csv').click()")

    time.sleep(15)
    download = download_info.value
    filename = os.path.join(SCRIPT_DIR, f"business_kpi_{start_str}_to_{end_str}.csv")
    download.save_as(filename)
    time.sleep(5)

    print(f"Validating: {filename}")
    validate_csv(filename)
    print(f"Downloaded: {filename}")
    return filename


print("Script starting...")
sys.stdout.flush()

LOG_FILENAME = os.path.join(SCRIPT_DIR, f"bkpi_logs_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.txt")
log_file = open(LOG_FILENAME, "w", encoding="utf-8")


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            s.write(data)
            s.flush()

    def flush(self):
        for s in self.streams:
            s.flush()


sys.stdout = Tee(sys.__stdout__, log_file)

with sync_playwright() as p:
    print("Playwright started.")
    browser, context = create_browser_and_context(p)
    print("Browser launched.")
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

        report_page = open_business_kpi_report(context, page)
        apply_business_kpi_filters(report_page)

        months = list(generate_month_ranges(START_YEAR, START_MONTH))
        succeeded = []
        failed = []

        for start_dt, end_dt in months:
            csv_path = os.path.join(SCRIPT_DIR, f"business_kpi_{start_dt.strftime('%Y-%m-%d')}_to_{end_dt.strftime('%Y-%m-%d')}.csv")
            if os.path.exists(csv_path):
                print(f"Skipping {start_dt.strftime('%b %Y')} — already downloaded.")
                succeeded.append(start_dt.strftime("%b %Y"))
                continue

            try:
                download_month(report_page, start_dt, end_dt)
                succeeded.append(start_dt.strftime("%b %Y"))
                save_cookies(context)
                time.sleep(5)
            except Exception as e:
                print(f"FAILED: {start_dt.strftime('%b %Y')} — {e}")
                failed.append((start_dt, end_dt, str(e)))
                time.sleep(5)

        if failed:
            print(f"\n--- Retrying {len(failed)} failed month(s) ---")
            retry_still_failed = []
            for start_dt, end_dt, prev_error in failed:
                try:
                    print(f"Retrying: {start_dt.strftime('%b %Y')}")
                    download_month(report_page, start_dt, end_dt)
                    succeeded.append(start_dt.strftime("%b %Y"))
                    save_cookies(context)
                    time.sleep(5)
                except Exception as e:
                    print(f"RETRY FAILED: {start_dt.strftime('%b %Y')} — {e}")
                    retry_still_failed.append((start_dt.strftime("%b %Y"), str(e)))
                    time.sleep(5)
            failed = retry_still_failed

        print(f"\n--- Summary ---")
        print(f"Succeeded: {len(succeeded)} months")
        if failed:
            print(f"Failed: {[m for m, _ in failed]}")

        report_page.close()
        time.sleep(2)

        print("Logging out...")
        page.bring_to_front()
        page.goto("https://evolvemedspa.zenoti.com/Admin/Reports/ReportsDashboard.aspx")
        page.wait_for_load_state("networkidle", timeout=60000)
        time.sleep(1)
        page.locator('#usernameBtn').click()
        time.sleep(1)
        page.locator('.userLogoutCls').click()
        time.sleep(5)
        print("Logged out.")

        if failed:
            raise Exception(f"Months failed after retry: {[m for m, _ in failed]}")

    except Exception as e:
        print(f"Error: {e}")
        raise
    finally:
        context.close()
        browser.close()

    sys.stdout = sys.__stdout__
    log_file.close()
    print(f"Log saved: {LOG_FILENAME}")
