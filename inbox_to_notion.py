import os
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import threading
import requests
import json
from dotenv import load_dotenv
import urllib.parse
import time
import imaplib
import email
from email.header import decode_header

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from openai import OpenAI

load_dotenv()
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DB_ID = os.getenv("NOTION_DATABASE_ID")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS") 
IMAP_SERVER = "imap.gmail.com" 

slack_app = App(token=SLACK_BOT_TOKEN)
openai_client = OpenAI(api_key=OPENAI_API_KEY)
whatsapp_client = Flask(__name__)

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def generate_texts(raw_input):
    """
    Takes text and expands it into a task using AI. 
    """
    print(f"Processing text with AI: {raw_input[:50]}") 

    system_prompt = """
    You are a Task Expansion Agent. 
    Your goal is to convert raw unstructured text (email, chat, or command) into a clear, actionable task.

    OUTPUT GUIDELINES:
    1. Name: concise, action-oriented, and clear (e.g., "Fix login bug" instead of "The login isn't working")
    2. Description: concise, structured, and descriptive
       - Use a professional but human tone.
       - Use standard bullet points (• or -) for lists
       - DO NOT use em dashes (—)
       - Summarize the "What" and the "Why" clearly. 
    3. Priority: Assign strictly based on REVENUE IMPACT:
       - "High": Directly impacts sales, active customers, or immediate money (e.g., Server Down, Client Complaint, Contract Sign)
       - "Medium": Enables future revenue or team productivity (e.g., Roadmap planning, Internal Syncs, Hiring)
       - "Low": Administrative, maintenance, or tasks with no direct financial link (e.g., Office supplies, Organizing files)

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
        return {"name": raw_input[:20], "description": "AI Failed", "priority": "N/A"}

def push_to_notion(task_name, description, priority, source_link=None):
    properties = {
        "Task": {"title": [{"text": {"content": task_name}}]},
        "Description": {"rich_text": [{"text": {"content": description}}]},
        "Priority": {"select": {"name": priority}},
    }

    if source_link and source_link.startswith("http"):
        properties["Source URL"] = {"url": source_link}

    payload = {"parent": {"database_id": NOTION_DB_ID}, "properties": properties}

    try:
        r = requests.post(
            "https://api.notion.com/v1/pages",
            headers=headers,
            json=payload, 
            timeout=20,
        )

        print(f"🧾 Notion status={r.status_code}")
        if r.status_code in (200, 201):
            data = r.json()
            print(f"Notion created: {data.get('url')}")
            return data.get("url")

        print(f"Notion error body: {r.text}")
        return None

    except Exception as e:
        print(f"Notion exception: {e}")
        return None

@whatsapp_client.route("/whatsapp", methods=['POST'])
def whatsapp_extraction():
    incoming_msg = request.values.get('Body', '').strip()
    sender = request.values.get('From', '')
    print(f"WhatsApp from {sender}: {incoming_msg}")

    resp = MessagingResponse()
    if not incoming_msg:
        resp.message("Empty message received.")
        return str(resp)

    try:
        ai_result = generate_texts(incoming_msg)
        print("AI result:", ai_result)
    except Exception as e:
        print("AI crashed with error:", e)
        resp.message("AI failed before saving to Notion.")
        return str(resp)

    notion_url = push_to_notion(
        ai_result.get("name", incoming_msg),
        ai_result.get("description", "WhatsApp"),
        ai_result.get("priority", "Medium"),
        "https://web.whatsapp.com/"
    )

    resp.message(f"Saved to Notion\n{notion_url}" if notion_url else "❌ Notion Error (check server logs)")
    return str(resp)


def email_extraction():
    """
    Checks the NotesTracker label for emails, processes them,
    moves them back to the Inbox, and removes the label.
    """
    while True:
        try:
            mail = imaplib.IMAP4_SSL(IMAP_SERVER)
            mail.login(EMAIL_USER, EMAIL_PASS)
            
            # Select the source folder
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
                            
                            # 1. Decode Subject
                            subject, encoding = decode_header(msg["Subject"])[0]
                            if isinstance(subject, bytes):
                                subject = subject.decode(encoding or "utf-8")
                            
                            clean_subject = subject.replace("Fwd:", "").replace("FW:", "").strip()

                            # 2. Get Deep Link back to Email
                            raw_msg_id = msg.get("Message-ID", "").strip()
                            if raw_msg_id:
                                clean_id = raw_msg_id.strip("<>")
                                encoded_id = urllib.parse.quote(clean_id)
                                email_link = f"https://mail.google.com/mail/u/2/#search/rfc822msgid%3A{encoded_id}"
                            else:
                                email_link = "https://mail.google.com/mail/u/2/#inbox"

                            # 3. Get Body for AI context
                            body = ""
                            if msg.is_multipart():
                                for part in msg.walk():
                                    if part.get_content_type() == "text/plain":
                                        body = part.get_payload(decode=True).decode()
                                        break
                            else:
                                body = msg.get_payload(decode=True).decode()

                            ai_result = generate_texts(f"Email Subject: {clean_subject}\nBody: {body[:3000]}")
                            
                            # 5. Push to Notion 
                            push_to_notion(
                                ai_result.get("name", clean_subject), 
                                ai_result.get("description", "Imported from Email thread"), 
                                ai_result.get("priority", "Medium"),
                                email_link 
                            )
                            
                            mail.copy(e_id, "INBOX")
                            mail.store(e_id, '+FLAGS', '\\Deleted')
                            
                # Permanently remove the email from 'NotesTracker' (it's safe in INBOX now)
                mail.expunge() 
                mail.close() 
            
            mail.logout()
            
        except Exception as e:
            print(f"Email Loop Error: {e}")
        
        time.sleep(30)

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    print(f"   - Flask Server listening on Port {port}...")
    whatsapp_client.run(host='0.0.0.0', port=port, use_reloader=False)

@slack_app.command("/notion")
def slack_extraction(ack, body, respond):
    ack()
    user_text = body.get("text", "").strip()
    respond(f"Processing: {user_text}...")
    
    ai_result = generate_texts(user_text)
    push_to_notion(
        ai_result.get("name", user_text), 
        ai_result.get("description", "Slack Command"), 
        ai_result.get("priority", "Medium"), 
        "https://slack.com"
    )

if __name__ == "__main__":
    # 1. Start Email Thread
    print("    Starting Email Watcher")
    email_thread = threading.Thread(target=email_extraction)
    email_thread.daemon = True
    email_thread.start()

    # 2. Start WhatsApp Thread
    print("    Starting WhatsApp Server")
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # 3. Start Slack Listener (Blocks the Main Thread)
    print("    Starting Slack Mode")
    SocketModeHandler(slack_app, SLACK_APP_TOKEN).start()
