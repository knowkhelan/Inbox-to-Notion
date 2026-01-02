# Inbox-to-Notion
Turn scattered messages into real tasks. Inbox-to-Notion pulls one-line work items from Slack, Outlook, Teams, and WhatsApp, enriches them with AI-generated titles, descriptions, and priorities, and syncs everything into a single Notion task hub.

## 🚀 Deployment (Render.com)

This project is optimized for the **Render Free Tier**. Because Render "sleeps" free instances after 15 minutes of inactivity, we use a heartbeat strategy to keep the listeners active.

### 1. Render Configuration

* **Service Type:** Web Service
* **Runtime:** `Python 3`
* **Build Command:** `pip install -r requirements.txt`
* **Start Command:** `python main.py`
* **Environment Variables:** Add all keys from your `.env` file to the Render Dashboard under **Environment**.

### 2. Staying Online (The Heartbeat)

To ensure the Slack Socket Mode and Email threads don't die:

1. **UptimeRobot Setup:** Create a "HTTP(s)" monitor at [UptimeRobot.com](https://uptimerobot.com).
2. **Point to:** `https://your-render-app-name.onrender.com/whatsapp` (Note: Even though this is the WhatsApp endpoint, a GET/POST ping here will keep the container awake).
3. **Interval:** Set to every **5 minutes**.

---

## 🛠 Connection Guide

### 1. Notion Connection

1. Create an integration at [developers.notion.com](https://developers.notion.com).
2. **Important:** Go to your Database page → `...` → **Add Connections** → Select your app.
3. Ensure your database has these columns: `Task` (Title), `Description` (Text), `Priority` (Select), and `Source URL` (URL).

### 2. WhatsApp (via Twilio)

1. In your Twilio Console, set your **Sandbox Webhook** to: `https://your-render-app-name.onrender.com/whatsapp`.
2. Ensure the method is set to `POST`.

### 3. Slack (via Socket Mode)

1. Enable **Socket Mode** in your Slack App settings.
2. Under **Slash Commands**, create `/notion`.
3. Because this uses `SocketModeHandler`, you **do not** need to provide a Request URL to Slack; the app reaches out to Slack from Render.

### 4. Gmail (NotesTracker)

1. In Gmail, create a Label exactly named `NotesTracker`.
2. Go to Google Account Settings → Security → **App Passwords**.
3. Generate a 16-character password for "Mail". Use this as your `EMAIL_PASS`.
4. The bot only processes **unread** emails moved into the `NotesTracker` label.

---

## 🏗 System Architecture

The application runs three concurrent processes to handle real-time data:

| Component | Method | Purpose |
| --- | --- | --- |
| **Flask Server** | Webhook (Port 5000) | Listens for WhatsApp messages and UptimeBot pings. |
| **Email Watcher** | IMAP (Threaded) | Scans Gmail `NotesTracker` label for new tasks. |
| **Slack Listener** | Socket Mode | Processes `/notion` slash commands without needing a public static IP. |
| **AI Engine** | GPT-4o-mini | Handles JSON-structured task expansion. |

---

## 📄 Environment Variables Reference

| Key | Description |
| --- | --- |
| `OPENAI_API_KEY` | Your OpenAI API Secret. |
| `NOTION_TOKEN` | Internal Integration Token. |
| `NOTION_DATABASE_ID` | The long string in your Notion DB URL. |
| `SLACK_BOT_TOKEN` | `xoxb-...` (Bot User OAuth Token). |
| `SLACK_APP_TOKEN` | `xapp-...` (Socket Mode App Token). |
| `EMAIL_USER` | Your Gmail address. |
| `EMAIL_PASS` | Your 16-character Google App Password. |
