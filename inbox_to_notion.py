import os
import requests
import json
import time
import threading
import imaplib
import email
from email.header import decode_header
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from openai import OpenAI

# 1. Setup Environment
load_dotenv()
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DB_ID = os.getenv("NOTION_DATABASE_ID")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Email Config (Add these to your .env file!)
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS") 
IMAP_SERVER = "imap.gmail.com" #Change to outlook.office365.com if using Outlook

# Initialize Clients
app = App(token=SLACK_BOT_TOKEN)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Headers for Notion
headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# --- AI AGENT ---
def generate_texts(raw_input):
    """
    Takes text (Slack command or Email body) and expands it into a task.
    """
    print(f"AI Processing: {raw_input[:50]}...") # Print first 50 chars for debug

    system_prompt = """
    You are a Task Expansion Agent. 
    The user will give you a short command OR a full email body.
    
    YOUR JOB:
    1. Name: Create a professional Task Title. 
       - If Email: Ignore "Fwd:", "Re:", and signatures. Extract the core request.
    2. Description: EXTRAPOLATE the likely workflow.
       - Structure with concise bullets (Context, Action Plan).
    3. Priority: Infer High/Medium/Low based on urgency words. Default to Medium.

    OUTPUT JSON ONLY:
    {"name": "...", "description": "...", "priority": "..."}
    """

    try:
        completion = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Input: {raw_input}"}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        print(f"AI Error: {e}")
        return {"name": raw_input[:20], "description": "AI Failed", "priority": "Medium"}

# --- NOTION API ---
def push_to_notion(task_name, description, priority, source_link=None):
    # Base properties
    properties = {
        "Task": {"title": [{"text": {"content": task_name}}]},
        "Description": {"rich_text": [{"text": {"content": description}}]},
        "Priority": {"select": {"name": priority}},
    }
    
    # Only add Source URL if it's a valid link (Notion validates this strictly)
    if source_link and source_link.startswith("http"):
        properties["Source URL"] = {"url": source_link}

    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": properties
    }
    
    try:
        response = requests.post(
            "https://api.notion.com/v1/pages", 
            headers=headers, 
            data=json.dumps(payload)
        )
        if response.status_code == 200:
            return response.json()['url']
        else:
            print(f"Notion Error: {response.text}")
            return None
    except Exception as e:
        print(f"Connection Error: {e}")
        return None

# --- EMAIL WATCHER ---
def check_email_and_sync():
    """
    Checks specific folder for emails, processes them, and moves to Trash.
    """
    while True:
        try:
            # print("📧 Checking Email Folder...") # Uncomment to debug loop
            mail = imaplib.IMAP4_SSL(IMAP_SERVER)
            mail.login(EMAIL_USER, EMAIL_PASS)
            
            # Select Folder - ENSURE THIS MATCHES YOUR GMAIL LABEL
            status, _ = mail.select("NotesTracker") 

            if status == 'OK':
                # Search for ALL emails in this folder
                _, messages = mail.search(None, 'ALL')
                email_ids = messages[0].split()

                for e_id in email_ids:
                    _, msg_data = mail.fetch(e_id, "(RFC822)")
                    for response_part in msg_data:
                        if isinstance(response_part, tuple):
                            msg = email.message_from_bytes(response_part[1])
                            
                            # Decode Subject
                            subject, encoding = decode_header(msg["Subject"])[0]
                            if isinstance(subject, bytes):
                                subject = subject.decode(encoding or "utf-8")
                            
                            # Clean Subject
                            clean_subject = subject.replace("Fwd:", "").replace("FW:", "").strip()
                            print(f"Email Found: {clean_subject}")

                            # Get Body
                            body = ""
                            if msg.is_multipart():
                                for part in msg.walk():
                                    if part.get_content_type() == "text/plain":
                                        body = part.get_payload(decode=True).decode()
                                        break
                            else:
                                body = msg.get_payload(decode=True).decode()

                            # Process with AI
                            ai_result = generate_texts(f"Email Subject: {clean_subject}\nBody: {body[:1000]}")
                            
                            # Push to Notion 
                            push_to_notion(
                                ai_result.get("name", clean_subject), 
                                ai_result.get("description", ai_result.get("description", "Imported from Email")), 
                                ai_result.get("priority", "Medium"),
                                source_link="https://mail.google.com/mail/#label/NotesTracker" 
                            )
                            
                            print(f"Synced Email: {clean_subject}")

                            # Move to Trash (Prevent duplicate processing)
                            mail.store(e_id, '+FLAGS', '\\Deleted')
                
                mail.expunge() # Permanently remove deleted items
                mail.close() # Close folder safely
            
            mail.logout()
            
        except Exception as e:
            print(f"Email Loop Error: {e}")
        
        # Wait 60 seconds before checking again
        time.sleep(60)

# --- SLACK HANDLER ---
@app.command("/notion")
def handle_command(ack, body, respond):
    ack()
    
    user_text = body.get("text", "").strip()
    channel_id = body.get("channel_id")  
    slack_link = f"https://slack.com/app_redirect?channel={channel_id}" 

    if not user_text:
        respond("Please provide text. Example: `/notion Fix bug on homepage`")
        return

    respond(f"Adding: *{user_text}* to the Notion database")

    # AI Processing
    ai_result = generate_texts(user_text)
    
    # Push to Notion
    notion_url = push_to_notion(
        ai_result.get("name", user_text), 
        ai_result.get("description", "No description generated."), 
        ai_result.get("priority", "Medium"), 
        slack_link
    )    
    
    if notion_url:
        print(f"Synced Slack: {user_text}")
    else:
        respond("Failed to create task in Notion.")

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    print("Tracker Bot is running (Slack + Email Watcher)")
    
    # Start Email Thread in Background
    email_thread = threading.Thread(target=check_email_and_sync)
    email_thread.daemon = True # Ensures thread dies when main app quits
    email_thread.start()

    # Start Slack Listener (Blocks main thread)
    SocketModeHandler(app, SLACK_APP_TOKEN).start()