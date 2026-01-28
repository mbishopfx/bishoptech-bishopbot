import time
from services import google_service, rag_service
from utils import auth_utils

def refresh():
    print("🔄 Refreshing Knowledge Base...")
    creds = auth_utils.get_credentials()
    if not creds:
        print("❌ Could not get credentials.")
        return

    try:
        emails = google_service.fetch_all_gmail(creds)
        calendar = google_service.fetch_all_calendar(creds)
        drive = google_service.fetch_all_drive(creds)
        
        all_docs = emails + calendar + drive
        
        # Simple deduplication by content
        existing_content = {doc["content"] for doc in rag_service.vector_store.documents}
        new_docs = [doc for doc in all_docs if doc["content"] not in existing_content]
        
        if new_docs:
            rag_service.vector_store.add_documents(new_docs)
            print(f"✅ Knowledge Base updated: {len(new_docs)} new items.")
        else:
            print("ℹ️ Knowledge Base is already up to date.")
    except Exception as e:
        print(f"❌ Refresh Error: {e}")

def refresh_loop():
    """Loop to be run in a background thread."""
    while True:
        refresh()
        # print("💤 Knowledge refresh sleeping for 1 hour...")
        time.sleep(3600)

if __name__ == "__main__":
    refresh_loop()