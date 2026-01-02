import os
import requests
import json
from dotenv import load_dotenv

# Slack Imports
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# OpenAI Import
from openai import OpenAI

<<<<<<< Updated upstream
=======
# WhatsApp/Flask Imports
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

>>>>>>> Stashed changes
load_dotenv()

# --- CONFIGURATION ---
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DB_ID = os.getenv("NOTION_DATABASE_ID")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

<<<<<<< Updated upstream
# Initialize Clients
app = App(token=SLACK_BOT_TOKEN)
=======
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS") 
IMAP_SERVER = "imap.gmail.com" 

# --- INITIALIZE CLIENTS ---
# 1. Slack Client
slack_app = App(token=SLACK_BOT_TOKEN)

# 2. OpenAI Client
>>>>>>> Stashed changes
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# 3. Flask Client (For WhatsApp) - Renamed to flask_app to avoid conflict
flask_app = Flask(__name__)

# Headers for Notion
headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

<<<<<<< Updated upstream
def generate_texts(raw_input):
    """
    Takes a short sentence and expands it into a full task spec.
    """
    print(f"AI Expanding: {raw_input}")

    system_prompt = """
    You are a Task Expansion Agent. 
    The user will give you a short, often vague command (e.g., "Fix header").
    
    YOUR JOB:
    1. Name: Create a professional, clear Task Title.
    2. Description: EXTRAPOLATE the likely workflow. If the input is sparse, assume standard professional steps (Investigate -> Fix -> Test). 
       - Structure the description with concise bullets (Context, Action Plan, deliverables).
    3. Priority: Infer High/Medium/Low based on urgency words (crash, error, urgent = High). Default to Medium.

=======
# --- SHARED FUNCTIONS (AI & NOTION) ---
def generate_texts(raw_input):
    """
    Takes text and expands it into a task using AI.
    """
    print(f"AI Processing: {raw_input[:50]}...") 

    system_prompt = """
    You are a Task Expansion Agent. 
>>>>>>> Stashed changes
    OUTPUT JSON ONLY:
    {"name": "...", "description": "...", "priority": "..."}
    """

<<<<<<< Updated upstream
    completion = openai_client.chat.completions.create(
        model="gpt-4o-mini", # Using mini is faster/cheaper for this
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Command: {raw_input}"}
        ],
        response_format={"type": "json_object"}
    )
    
    ai_data = json.loads(completion.choices[0].message.content)
        
    # Print for your debugging
    # print(f"AI Generated: {ai_data}")
    return ai_data


# NEW (Added source_link argument)
def push_to_notion(task_name, description, priority, source_link):
    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "Task": {"title": [{"text": {"content": task_name}}]},
            "Description": {"rich_text": [{"text": {"content": description}}]},
            "Priority": {"select": {"name": priority}},
            
            # NEW: This block maps the link to your new Notion column
            "Source URL": {"url": source_link} 
        }
    }
    
=======
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

def push_to_notion(task_name, description, priority, source_link=None):
    properties = {
        "Task": {"title": [{"text": {"content": task_name}}]},
        "Description": {"rich_text": [{"text": {"content": description}}]},
        "Priority": {"select": {"name": priority}},
    }

    if source_link and source_link.startswith("http"):
        properties["Source URL"] = {"url": source_link}

    payload = {"parent": {"database_id": NOTION_DB_ID}, "properties": properties}

>>>>>>> Stashed changes
    try:
        r = requests.post(
            "https://api.notion.com/v1/pages",
            headers=headers,
            json=payload,  # <— use json= (cleaner than data=json.dumps)
            timeout=20,
        )
<<<<<<< Updated upstream
        if response.status_code == 200:
            return response.json()['url']
        else:
            print(f"Notion Error: {response.text}")
            return None
    except Exception as e:
        print(f"Error: {e}")
        return None

# --- NEW SLACK HANDLER ---
@app.command("/notion")
def handle_command(ack, body, client, respond):
=======

        print(f"🧾 Notion status={r.status_code}")
        if r.status_code in (200, 201):
            data = r.json()
            print(f"✅ Notion created: {data.get('url')}")
            return data.get("url")

        print(f"❌ Notion error body: {r.text}")
        return None

    except Exception as e:
        print(f"❌ Notion exception: {e}")
        return None
    

@flask_app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    incoming_msg = request.values.get('Body', '').strip()
    sender = request.values.get('From', '')
    print(f"📩 WhatsApp from {sender}: {incoming_msg}")

    resp = MessagingResponse()
    if not incoming_msg:
        resp.message("Empty message received.")
        return str(resp)

    try:
        ai_result = generate_texts(incoming_msg)
        print("🧠 AI result:", ai_result)
    except Exception as e:
        print("❌ AI crashed:", e)
        resp.message("AI failed before saving to Notion.")
        return str(resp)

    notion_url = push_to_notion(
        ai_result.get("name", incoming_msg),
        ai_result.get("description", "WhatsApp"),
        ai_result.get("priority", "Medium"),
        "https://web.whatsapp.com/"
    )

    resp.message(f"✅ Saved to Notion\n{notion_url}" if notion_url else "❌ Notion Error (check server logs)")
    return str(resp)


# --- MODULE 1: EMAIL WATCHER (Background Thread) ---
def check_email_and_sync():
    """
    Checks specific folder for emails, processes them, and moves to Trash.
    """
    while True:
        try:
            if not EMAIL_USER: return # Safety check
            
            mail = imaplib.IMAP4_SSL(IMAP_SERVER)
            mail.login(EMAIL_USER, EMAIL_PASS)
            status, _ = mail.select("NotesTracker") 

            if status == 'OK':
                _, messages = mail.search(None, 'ALL')
                email_ids = messages[0].split()

                for e_id in email_ids:
                    _, msg_data = mail.fetch(e_id, "(RFC822)")
                    for response_part in msg_data:
                        if isinstance(response_part, tuple):
                            msg = email.message_from_bytes(response_part[1])
                            subject, encoding = decode_header(msg["Subject"])[0]
                            if isinstance(subject, bytes):
                                subject = subject.decode(encoding or "utf-8")
                            
                            clean_subject = subject.replace("Fwd:", "").strip()
                            print(f"📧 Email Found: {clean_subject}")

                            # Process
                            ai_result = generate_texts(clean_subject)
                            push_to_notion(
                                ai_result.get("name", clean_subject), 
                                ai_result.get("description", "Imported from Email"), 
                                ai_result.get("priority", "Medium"),
                                "https://mail.google.com" 
                            )
                            
                            # Delete
                            mail.store(e_id, '+FLAGS', '\\Deleted')
                
                mail.expunge()
                mail.close()
            mail.logout()
        except Exception as e:
            print(f"Email Loop Error: {e}")
        
        time.sleep(60)

def run_flask():
    print("   - Flask Server listening on Port 5050...")
    flask_app.run(host='0.0.0.0', port=5050, use_reloader=False)


# --- MODULE 3: SLACK HANDLER (Main Thread) ---
@slack_app.command("/notion")
def handle_slack_command(ack, body, respond):
>>>>>>> Stashed changes
    ack()
    user_text = body.get("text", "").strip()
<<<<<<< Updated upstream
    user_id = body["user_id"]

    channel_id = body.get("channel_id")  # <--- Added this
    slack_link = f"https://slack.com/app_redirect?channel={channel_id}" # <--- Formatted into a URL

    # Handle empty input
    if not user_text:
        respond("Please provide text. Example: `/notion Fix bug on homepage`")
        return

    # 2. Send a temporary "Working" message (Visible only to user)
    respond(f"Adding: *{user_text}* to the Notion database")

    # 3. AI Processing
    ai_result = generate_texts(user_text)
    
    # 1. Title
    final_task = ai_result.get("name", user_text)

    # 2. Description
    if "description" in ai_result:
        final_desc = ai_result["description"]
    else:
        final_desc = "No description generated."

    # 3. Priority
    if "priority" in ai_result:
        final_prio = ai_result["priority"]
    else:
        final_prio = "Medium"

    notion_url = push_to_notion(final_task, final_desc, final_prio, slack_link)    
    print(f"Notion URL: {notion_url}")

=======
    respond(f"Processing: {user_text}...")
    
    ai_result = generate_texts(user_text)
    push_to_notion(
        ai_result.get("name", user_text), 
        ai_result.get("description", "Slack Command"), 
        ai_result.get("priority", "Medium"), 
        "https://slack.com"
    )
>>>>>>> Stashed changes

if __name__ == "__main__":
<<<<<<< Updated upstream
    print("Tracker Bot is running")
    SocketModeHandler(app, SLACK_APP_TOKEN).start()
=======
    print("🚀 STARTING UNIVERSAL INBOX BOT...")
    
    # 1. Start Email Thread
    print("   - Starting Email Watcher...")
    email_thread = threading.Thread(target=check_email_and_sync)
    email_thread.daemon = True
    email_thread.start()

    # 2. Start WhatsApp (Flask) Thread
    print("   - Starting WhatsApp Server (Port 5000)...")
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # 3. Start Slack Listener (Blocks the Main Thread)
    print("   - Starting Slack Socket Mode...")
    print("✅ ALL SYSTEMS GO!")
    SocketModeHandler(slack_app, SLACK_APP_TOKEN).start()
>>>>>>> Stashed changes
