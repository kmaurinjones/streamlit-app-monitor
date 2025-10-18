"""
Streamlit App Monitor - Automated app wakeup script.

This script monitors Streamlit apps and automatically wakes them up if they're asleep.
It runs headlessly and sends email reports after each check.

Features:
- Detects if apps are asleep by checking for wakeup button
- Automatically clicks wakeup button for sleeping apps
- Sends detailed email reports with timestamps
- Runs in headless mode (suitable for cron/scheduling)
"""

# Standard library imports
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from zoneinfo import ZoneInfo

# third-party imports
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright


def check_and_wake_app(url: str, actually_click: bool = False):
    """
    Check if a Streamlit app is asleep and optionally wake it up.

    Args:
        url: The Streamlit app URL to check
        actually_click: If True, actually click the wakeup button. If False, just report.

    Returns:
        dict with status information
    """

    with sync_playwright() as p:
        # Launch Chromium in headless mode (optimized for Raspberry Pi)
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print(f"\n{'='*80}")
        print(f"Checking app: {url}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}")

        try:
            # Navigate to the page with appropriate timeout
            print("→ Loading page...")
            page.goto(url, wait_until="networkidle", timeout=60000)

            # Wait for dynamic content to load
            page.wait_for_timeout(3000)
            print("→ Page loaded successfully")

            # Check for the wakeup button (primary indicator of asleep state)
            wakeup_button = page.query_selector('[data-testid="wakeup-button-viewer"]')

            if wakeup_button:
                # App is ASLEEP
                print("\n⚠️  APP STATUS: ASLEEP")
                print(f"   Found wakeup button with text: '{wakeup_button.inner_text()}'")

                if actually_click:
                    print("\n→ Clicking wakeup button...")
                    wakeup_button.click()
                    print("✓ Button clicked!")

                    # Wait for the app to start waking up
                    page.wait_for_timeout(5000)
                    print("→ Waiting for app to wake up...")

                    # Check if the button is gone (indicating wake process started)
                    wakeup_button_after = page.query_selector('[data-testid="wakeup-button-viewer"]')
                    if wakeup_button_after is None:
                        print("✓ App wake-up process initiated successfully!")
                        result = {
                            "url": url,
                            "status": "woken_up",
                            "action": "clicked_wakeup_button",
                            "timestamp": datetime.now().isoformat()
                        }
                    else:
                        print("⚠️  Wakeup button still present - wake process may have failed")
                        result = {
                            "url": url,
                            "status": "asleep",
                            "action": "click_attempted_but_failed",
                            "timestamp": datetime.now().isoformat()
                        }
                else:
                    print("\n→ [TEST MODE] Would click wakeup button here")
                    print("   (actually_click=False, so skipping click)")
                    result = {
                        "url": url,
                        "status": "asleep",
                        "action": "would_click_button",
                        "timestamp": datetime.now().isoformat()
                    }

            else:
                # App is AWAKE
                print("\n✓ APP STATUS: AWAKE")

                # Additional verification: check for app creator avatar
                creator_avatar = page.query_selector('[data-testid="appCreatorAvatar"]')
                if creator_avatar:
                    print("   Confirmed: App creator avatar found")

                # Check page title
                title = page.title()
                print(f"   Page title: '{title}'")

                print("\n→ No action needed - app is already running")

                result = {
                    "url": url,
                    "status": "awake",
                    "action": "no_action_needed",
                    "timestamp": datetime.now().isoformat(),
                    "page_title": title
                }

        except Exception as e:
            print(f"\n❌ ERROR: {str(e)}")
            result = {
                "url": url,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

        finally:
            browser.close()

        print(f"\n{'='*80}\n")
        return result


def load_urls_from_file(file_path: str = "app_urls.txt") -> list[str]:
    """
    Load URLs from a text file, one URL per line.
    Strips whitespace and ignores empty lines.

    Args:
        file_path: Path to the file containing URLs

    Returns:
        List of URLs
    """
    urls = []
    url_file = Path(file_path)

    if not url_file.exists():
        raise FileNotFoundError(f"URL file not found: {file_path}")

    with open(url_file, 'r') as f:
        for line in f:
            url = line.strip()
            if url:  # Ignore empty lines
                urls.append(url)

    return urls


def send_email_report(results: list[dict], completion_time: datetime):
    """
    Send email report with script results.

    Args:
        results: List of result dictionaries from check_and_wake_app
        completion_time: Datetime when script completed
    """
    # Load environment variables
    load_dotenv()

    gmail_user = os.getenv("GMAIL_USER")
    gmail_app_password = os.getenv("GMAIL_APP_PASSWORD")

    if not gmail_user or not gmail_app_password:
        print("\n⚠️  WARNING: Email credentials not found in .env file")
        print("   Skipping email notification")
        return

    # Get timezone (EDT/EST based on system)
    local_tz = ZoneInfo("America/New_York")
    completion_time_local = completion_time.astimezone(local_tz)
    timezone_abbr = completion_time_local.strftime("%Z")

    # Format completion time
    completion_str = completion_time_local.strftime(f"%Y-%m-%d %H:%M:%S {timezone_abbr}")

    # Build email body
    email_body = f"Playwright Script Completed at {completion_str}:\n"
    email_body += "-" * 53 + "\n\n"

    # Successes section
    email_body += "Successes:\n"
    # Count all non-error results as successes (awake, asleep, woken_up)
    successes = [r for r in results if r['status'] != 'error']

    if successes:
        for result in successes:
            timestamp = datetime.fromisoformat(result['timestamp']).astimezone(local_tz)
            timestamp_str = timestamp.strftime(f"%Y-%m-%d %H:%M:%S {timezone_abbr}")
            email_body += f"- [{timestamp_str}] Loaded {result['url']}\n"

            # Add indented note if app was asleep
            if result['status'] in ['asleep', 'woken_up']:
                if result['status'] == 'asleep':
                    # App was asleep but we didn't click (test mode)
                    email_body += "    → App asleep -> wake-up button not clicked (test mode)\n"
                else:
                    # App was asleep and we clicked the button
                    email_body += "    → App asleep -> wake-up button clicked and should be awake at next check\n"
    else:
        email_body += "- No successes.\n"

    # Failures section
    email_body += "\nFailures:\n"
    failures = [r for r in results if r['status'] == 'error']

    if failures:
        for result in failures:
            timestamp = datetime.fromisoformat(result['timestamp']).astimezone(local_tz)
            timestamp_str = timestamp.strftime(f"%Y-%m-%d %H:%M:%S {timezone_abbr}")
            error_msg = result.get('error', 'Unknown error')
            email_body += f"- [{timestamp_str}] Failed to load {result['url']}: {error_msg}\n"
    else:
        email_body += "- No failures.\n"

    # Create email message
    msg = MIMEMultipart()
    msg['From'] = gmail_user
    msg['To'] = gmail_user
    msg['Subject'] = f"Streamlit App Monitor Report - {completion_str}"

    msg.attach(MIMEText(email_body, 'plain'))

    try:
        # Connect to Gmail SMTP server
        print("\n→ Sending email report...")
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(gmail_user, gmail_app_password)

        # Send email
        server.send_message(msg)
        server.quit()

        print(f"✓ Email report sent to {gmail_user}")

    except Exception as e:
        print(f"❌ Failed to send email: {str(e)}")


def main():
    """
    Main function to monitor and wake up Streamlit apps from app_urls.txt.
    """

    print("\n" + "="*80)
    print("STREAMLIT APP MONITOR")
    print("="*80)
    print("Checking app states and waking sleeping apps...")
    print("="*80)

    # Load URLs from file
    try:
        urls = load_urls_from_file("app_urls.txt")
        print(f"\nLoaded {len(urls)} URLs from app_urls.txt")
    except FileNotFoundError as e:
        print(f"\n❌ ERROR: {e}")
        print("Please create app_urls.txt with one URL per line")
        return

    # Check all apps and wake them if needed
    results = []

    for i, url in enumerate(urls, 1):
        print(f"\nAPP {i}/{len(urls)}")
        result = check_and_wake_app(url, actually_click=True)
        results.append(result)

    # Summary
    print("\n" + "="*80)
    print("MONITORING SUMMARY")
    print("="*80)

    # Count statistics
    awake_count = sum(1 for r in results if r['status'] == 'awake')
    asleep_count = sum(1 for r in results if r['status'] == 'asleep')
    error_count = sum(1 for r in results if r['status'] == 'error')

    print(f"\nTotal Apps Checked: {len(results)}")
    print(f"  ✓ Awake: {awake_count}")
    print(f"  ⚠️  Asleep: {asleep_count}")
    print(f"  ❌ Errors: {error_count}")

    print("\nDetailed Results:")
    for i, result in enumerate(results, 1):
        print(f"\n{i}. {result['url']}")
        print(f"   Status: {result['status'].upper()}")
        print(f"   Action: {result['action']}")
        if 'page_title' in result:
            print(f"   Title: {result['page_title']}")
        if 'error' in result:
            print(f"   Error: {result['error']}")

    print("\n" + "="*80 + "\n")

    # Send email report
    completion_time = datetime.now()
    send_email_report(results, completion_time)


if __name__ == "__main__":
    main()
