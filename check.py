import os
import imaplib
import email
from email.header import decode_header
from dotenv import load_dotenv

# 1. Load Credentials
load_dotenv()
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
IMAP_SERVER = "imap.gmail.com"

def list_folder_contents():
    print(f"🔌 Connecting to {IMAP_SERVER} as {EMAIL_USER}...")
    
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_USER, EMAIL_PASS)
        
        # 2. Select the Folder
        folder_name = "NotesTracker"  # Ensure this matches exactly!
        status, messages = mail.select(folder_name)

        if status != 'OK':
            print(f"❌ CRITICAL ERROR: Could not find folder '{folder_name}'")
            print("   -> Tip: Check Gmail sidebar. Is it nested? Is it case-sensitive?")
            return

        # 3. Get total count
        total_emails = int(messages[0])
        print(f"📂 Folder '{folder_name}' selected.")
        print(f"📊 Total Emails Found: {total_emails}")
        print("-" * 40)

        if total_emails == 0:
            print("   (The folder is empty. Try forwarding an email to it first!)")
            return

        # 4. Fetch and Print Headers
        # We fetch the last 5 emails to avoid spamming the terminal if you have hundreds
        _, msg_ids = mail.search(None, 'ALL')
        id_list = msg_ids[0].split()
        
        # Show last 5 emails (most recent)
        for e_id in id_list[-5:]:
            _, msg_data = mail.fetch(e_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    # Decode Subject
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding or "utf-8")
                    
                    # Decode From
                    sender, encoding = decode_header(msg.get("From"))[0]
                    if isinstance(sender, bytes):
                        sender = sender.decode(encoding or "utf-8")

                    print(f"🆔 ID: {e_id.decode()} | 👤 From: {sender}")
                    print(f"   📩 Subject: {subject}")
                    print("-" * 40)

        mail.logout()
        print("✅ Done.")

    except Exception as e:
        print(f"⚠️ Error: {e}")

if __name__ == "__main__":
    list_folder_contents()