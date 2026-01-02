import os
import requests
import json
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

# Initialize Clients
app = App(token=SLACK_BOT_TOKEN)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Headers for Notion
headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

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

    OUTPUT JSON ONLY:
    {"name": "...", "description": "...", "priority": "..."}
    """

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

def push_to_notion(task_name, description, priority):
    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "Task": {"title": [{"text": {"content": task_name}}]},
            "Description": {"rich_text": [{"text": {"content": description}}]},
            "Priority": {"select": {"name": priority}}
        }
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
        print(f"Error: {e}")
        return None

# --- NEW SLACK HANDLER ---
@app.command("/notion")
def handle_command(ack, body, client, respond):
    ack()
    
    user_text = body.get("text", "").strip()
    user_id = body["user_id"]

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

    # Notion Save
    notion_url = push_to_notion(final_task, final_desc, final_prio)

    # 4. Push to Notion
    notion_url = push_to_notion(final_task, final_desc, final_prio)
    print(f"Notion URL: {notion_url}")


if __name__ == "__main__":
    print("Tracker Bot is running")
    SocketModeHandler(app, SLACK_APP_TOKEN).start()