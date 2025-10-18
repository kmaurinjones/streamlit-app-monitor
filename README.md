# Streamlit App Monitor

Automated monitoring script that keeps your Streamlit apps awake by detecting sleeping apps and clicking their wakeup buttons.

## Features

- Headless browser automation with Playwright
- Detects sleeping apps by checking for wakeup button
- Automatically wakes up sleeping apps
- Sends email reports after each check
- Timezone-aware timestamps (EDT/EST)
- Designed for scheduled execution (cron/systemd)

## How It Works

The script:
1. Reads app URLs from `app_urls.txt`
2. Visits each app in a headless browser
3. Checks if the app is asleep (wakeup button present)
4. Clicks the wakeup button if needed
5. Sends an email report with results

## Setup

### 1. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone and Setup

```bash
git clone <your-repo-url>
cd keep-streamlit-apps-alive

# Create virtual environment and install dependencies
uv venv
uv sync

# Install Playwright browser
uv run playwright install chromium
```

### 3. Configure Email

Create a `.env` file with your Gmail credentials:

```bash
cp .env.example .env
```

Edit `.env` and add:
```
GMAIL_USER=your-email@gmail.com
GMAIL_APP_PASSWORD=your-16-char-app-password
```

See [EMAIL_SETUP.md](EMAIL_SETUP.md) for instructions on generating a Gmail App Password.

### 4. Add Your Apps

Create `app_urls.txt` from the example file:

```bash
cp app_urls.txt.example app_urls.txt
```

Edit `app_urls.txt` and add your Streamlit app URLs, one per line:
```
https://your-app1.streamlit.app/
https://your-app2.streamlit.app/
https://your-app3.streamlit.app/
```

**Note:** `app_urls.txt` is gitignored to keep your app list private.

### 5. Test

```bash
uv run python streamlit_app_monitor.py
```

## Scheduling

### On Raspberry Pi (cron)

Edit crontab:
```bash
crontab -e
```

Add this line to run at 6am, 12pm, and 6pm daily:
```cron
0 6,12,18 * * * cd /path/to/keep-streamlit-apps-alive && uv run python streamlit_app_monitor.py >> cron.log 2>&1
```

### On macOS/Linux (systemd)

Create a timer unit or use cron similar to Raspberry Pi.

## Email Report Format

```
Playwright Script Completed at 2025-10-18 12:02:17 EDT:
-----------------------------------------------------

Successes:
- [2025-10-18 12:00:19 EDT] Loaded https://app1.streamlit.app/
- [2025-10-18 12:00:35 EDT] Loaded https://app2.streamlit.app/
    � App asleep -> wake-up button clicked and should be awake at next check

Failures:
- No failures.
```

## Files

- `streamlit_app_monitor.py` - Main monitoring script
- `app_urls.txt` - List of Streamlit app URLs to monitor (gitignored)
- `app_urls.txt.example` - Template for app URLs
- `.env` - Email credentials (gitignored)
- `.env.example` - Template for credentials
- `EMAIL_SETUP.md` - Gmail App Password setup guide

## Requirements

- Python 3.11+
- Playwright
- Gmail account with App Password enabled

## Security

- Never commit `.env` to git (already in `.gitignore`)
- Use Gmail App Passwords instead of your main password
- Revoke App Passwords from Google Account settings if needed

## License

MIT
