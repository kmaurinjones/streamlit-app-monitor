# Gmail App Password Setup

This guide shows how to create a Gmail App Password for the Streamlit App Monitor email notifications.

## Prerequisites

- Gmail account
- 2-Step Verification enabled on your Google account

## Steps

1. **Enable 2-Step Verification** (if not already enabled)
   - Go to https://myaccount.google.com/security
   - Find "2-Step Verification" and enable it
   - Follow the prompts to set it up

2. **Generate App Password**
   - Go to https://myaccount.google.com/apppasswords
   - You may need to sign in again
   - Select "Mail" as the app
   - Select "Other (Custom name)" as the device
   - Enter "Streamlit App Monitor" as the name
   - Click "Generate"

3. **Copy the 16-character password**
   - Google will display a 16-character password
   - Copy this password (spaces don't matter)

4. **Add to .env file**
   ```bash
   GMAIL_USER=your-email@gmail.com
   GMAIL_APP_PASSWORD=your-16-char-app-password
   ```

## Troubleshooting

**Can't find App Passwords option?**
- Ensure 2-Step Verification is enabled first
- Some Google Workspace accounts may have this disabled by admin

**Authentication fails?**
- Double-check the app password was copied correctly
- Ensure no extra spaces in the .env file
- Try generating a new app password

**Still having issues?**
- Check that SMTP access is enabled in Gmail settings
- Verify your account isn't blocking "less secure apps" (shouldn't be needed with App Passwords)

## Security Notes

- App Passwords bypass 2-Step Verification for specific apps
- Each app password can only be used for one app/device
- You can revoke app passwords anytime from https://myaccount.google.com/apppasswords
- Never commit your `.env` file to git (it's already in `.gitignore`)
