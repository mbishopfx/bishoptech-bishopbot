import os
import json
import time
from datetime import datetime, timezone
from services import google_service, rag_service, slack_service
from utils import auth_utils

SYNC_STATE_FILE = "sync_state.json"

def load_sync_state():
    """Load the last sync timestamp from disk."""
    if os.path.exists(SYNC_STATE_FILE):
        try:
            with open(SYNC_STATE_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Could not load sync state: {e}")
    return {"last_sync": None}

def save_sync_state(state):
    """Save the sync state to disk."""
    try:
        with open(SYNC_STATE_FILE, 'w') as f:
            json.dump(state, f)
    except Exception as e:
        print(f"⚠️ Could not save sync state: {e}")

def refresh():
    """Refresh the knowledge base, fetching only new items since last sync."""
    print("🔄 Refreshing Knowledge Base...")
    
    creds = auth_utils.get_credentials()
    if not creds:
        print("❌ Could not get credentials.")
        return

    try:
        # Load last sync timestamp
        sync_state = load_sync_state()
        last_sync = sync_state.get("last_sync")
        
        if last_sync:
            print(f"📅 Fetching items since: {last_sync}")
        else:
            print("📅 First sync - fetching all items")
        
        # Record current time BEFORE fetching (to avoid missing items)
        current_time = datetime.now(timezone.utc).isoformat()
        
        # Fetch with timestamp filter
        emails = google_service.fetch_all_gmail(creds, after_timestamp=last_sync)
        calendar = google_service.fetch_all_calendar(creds, after_timestamp=last_sync)
        drive = google_service.fetch_all_drive(creds, after_timestamp=last_sync)
        
        all_docs = emails + calendar + drive
        
        if not all_docs:
            print("ℹ️ No new items found since last sync.")
            # Update sync time even if no new items
            sync_state["last_sync"] = current_time
            save_sync_state(sync_state)
            return
        
        # Deduplicate by ID (more reliable than content)
        existing_ids = {doc["metadata"].get("id") for doc in rag_service.vector_store.documents}
        new_docs = [doc for doc in all_docs if doc["metadata"].get("id") not in existing_ids]
        
        if new_docs:
            rag_service.vector_store.add_documents(new_docs)
            print(f"✅ Knowledge Base updated: {len(new_docs)} new items indexed.")
            _notify_new_docs(new_docs)
        else:
            print("ℹ️ All fetched items already existed in knowledge base.")
        
        # Update sync timestamp
        sync_state["last_sync"] = current_time
        save_sync_state(sync_state)
        print(f"💾 Sync state saved: {current_time}")
        
    except Exception as e:
        print(f"❌ Refresh Error: {e}")


def _notify_new_docs(new_docs):
    drive_docs = [doc for doc in new_docs if doc["metadata"].get("type") == "drive"]
    meet_events = [
        doc for doc in new_docs
        if doc["metadata"].get("type") == "calendar"
        and doc["metadata"].get("meetLink")
    ]

    if not drive_docs and not meet_events:
        return

    lines = []
    if drive_docs:
        lines.append(f"📁 *New Drive files:* {len(drive_docs)}")
        for doc in drive_docs[:10]:
            name = doc["metadata"].get("name", "Unnamed")
            lines.append(f"• {name}")
        if len(drive_docs) > 10:
            lines.append(f"• …and {len(drive_docs) - 10} more")

    if meet_events:
        lines.append(f"📅 *New Meet events:* {len(meet_events)}")
        for doc in meet_events[:10]:
            summary = doc["metadata"].get("summary", "No Title")
            link = doc["metadata"].get("meetLink", "")
            if link:
                lines.append(f"• {summary} — {link}")
            else:
                lines.append(f"• {summary}")
        if len(meet_events) > 10:
            lines.append(f"• …and {len(meet_events) - 10} more")

    slack_service.send_channel_message("\n".join(lines))

def refresh_loop():
    """Loop to be run in a background thread. Runs every 1 hour."""
    while True:
        refresh()
        print("💤 Knowledge refresh sleeping for 1 hour...")
        time.sleep(3600)  # 1 hour

if __name__ == "__main__":
    refresh_loop()
