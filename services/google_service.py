from googleapiclient.discovery import build
import base64
from datetime import datetime, timedelta, timezone

def fetch_all_gmail(creds, max_results=100, after_timestamp=None):
    """
    Fetch Gmail messages. If after_timestamp is provided, only fetch messages
    received after that time (ISO format string or datetime).
    """
    service = build('gmail', 'v1', credentials=creds)
    
    # Build query with date filter if provided
    query = None
    if after_timestamp:
        if isinstance(after_timestamp, str):
            after_timestamp = datetime.fromisoformat(after_timestamp.replace('Z', '+00:00'))
        # Gmail uses epoch seconds for after: query
        epoch_seconds = int(after_timestamp.timestamp())
        query = f"after:{epoch_seconds}"
    
    results = service.users().messages().list(
        userId='me', 
        maxResults=max_results,
        q=query
    ).execute()
    messages = results.get('messages', [])
    
    docs = []
    for msg in messages:
        m = service.users().messages().get(userId='me', id=msg['id']).execute()
        snippet = m.get('snippet', '')
        payload = m.get('payload', {})
        headers = payload.get('headers', [])
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
        internal_date = m.get('internalDate', '0')
        
        content = f"Subject: {subject}\nFrom: {sender}\nSnippet: {snippet}"
        docs.append({
            "content": content, 
            "metadata": {
                "id": msg['id'], 
                "type": "gmail", 
                "subject": subject,
                "timestamp": internal_date
            }
        })
    return docs

def fetch_all_calendar(creds, max_results=50, after_timestamp=None):
    """
    Fetch Calendar events. If after_timestamp is provided, only fetch events
    that start after that time.
    """
    service = build('calendar', 'v3', credentials=creds)
    
    # Use provided timestamp or default to now
    if after_timestamp:
        if isinstance(after_timestamp, str):
            time_min = after_timestamp
        else:
            time_min = after_timestamp.isoformat() + 'Z'
    else:
        time_min = datetime.utcnow().isoformat() + 'Z'
    
    events_result = service.events().list(
        calendarId='primary', 
        timeMin=time_min,
        maxResults=max_results, 
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])
    
    docs = []
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        summary = event.get('summary', 'No Title')
        description = event.get('description', '')
        updated = event.get('updated', '')
        
        content = f"Event: {summary}\nStart: {start}\nDescription: {description}"
        docs.append({
            "content": content, 
            "metadata": {
                "id": event.get('id'), 
                "type": "calendar", 
                "summary": summary,
                "updated": updated
            }
        })
    return docs

def fetch_all_drive(creds, max_results=50, after_timestamp=None):
    """
    Fetch Drive files. If after_timestamp is provided, only fetch files
    modified after that time.
    """
    service = build('drive', 'v3', credentials=creds)
    
    # Build query with date filter if provided
    query = None
    if after_timestamp:
        if isinstance(after_timestamp, str):
            modified_time = after_timestamp
        else:
            modified_time = after_timestamp.isoformat()
        query = f"modifiedTime > '{modified_time}'"
    
    results = service.files().list(
        pageSize=max_results, 
        fields="nextPageToken, files(id, name, mimeType, description, modifiedTime)",
        q=query
    ).execute()
    items = results.get('files', [])
    
    docs = []
    for item in items:
        content = f"File Name: {item['name']}\nType: {item['mimeType']}\nDescription: {item.get('description', 'N/A')}"
        docs.append({
            "content": content, 
            "metadata": {
                "id": item['id'], 
                "type": "drive", 
                "name": item['name'],
                "modifiedTime": item.get('modifiedTime', '')
            }
        })
    return docs