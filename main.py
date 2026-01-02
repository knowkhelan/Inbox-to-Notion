import os
import requests
import json
from datetime import datetime
from dotenv import load_dotenv

# 1. Setup Environment
load_dotenv()
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DB_ID = os.getenv("NOTION_DATABASE_ID")

# 2. Define Headers for Notion API
headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"  # Ensure you use a supported API version
}


PROPERTIES_TO_ASK = {
    "Task": ("title", "Enter the task name: "),
    "Description": ("rich_text", "Enter a description: "),
}

def format_property(prop_type, value):
    """Helper to format data into Notion's specific JSON structure."""
    if not value: return None # Skip empty inputs

    if prop_type == "title":
        return {"title": [{"text": {"content": value}}]}
    
    elif prop_type == "rich_text":
        return {"rich_text": [{"text": {"content": value}}]}
    
    elif prop_type == "number":
        try:
            return {"number": float(value)}
        except ValueError:
            print(f"Warning: '{value}' is not a valid number. Skipping.")
            return None

    elif prop_type == "select":
        return {"select": {"name": value}}
    
    elif prop_type == "date":
        return {"date": {"start": value}} # Expects YYYY-MM-DD
    
    return None

def main():
    print("--- Adding New Entry to Notion ---")
    
    new_page_properties = {}

    # 3. Loop through configured properties and ask user for input
    for prop_name, (prop_type, prompt_text) in PROPERTIES_TO_ASK.items():
        user_input = input(prompt_text)
        
        formatted_data = format_property(prop_type, user_input)
        
        if formatted_data:
            new_page_properties[prop_name] = formatted_data

    # 4. Construct the Payload
    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": new_page_properties
    }

    # 5. Send to Notion
    try:
        response = requests.post(
            "https://api.notion.com/v1/pages", 
            headers=headers, 
            data=json.dumps(payload)
        )
        
        if response.status_code == 200:
            print("\nSuccess! Added to Notion.")
            print(f"Link: {response.json()['url']}")
        else:
            print(f"\nError {response.status_code}: {response.text}")

    except Exception as e:
        print(f"\nAn error occurred: {e}")

if __name__ == "__main__":
    main()