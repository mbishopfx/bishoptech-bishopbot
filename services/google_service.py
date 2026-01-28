from googleapiclient.discovery import build
import base64

def fetch_all_gmail(creds, max_results=100):
    service = build('gmail', 'v1', credentials=creds)
    results = service.users().messages().list(userId='me', maxResults=max_results).execute()
    messages = results.get('messages', [])
    
    docs = []
    for msg in messages:
        m = service.users().messages().get(userId='me', id=msg['id']).execute()
        snippet = m.get('snippet', '')
        payload = m.get('payload', {})
        headers = payload.get('headers', [])
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
        
        content = f"Subject: {subject}\nFrom: {sender}\nSnippet: {snippet}"
        docs.append({"content": content, "metadata": {"id": msg['id'], "type": "gmail", "subject": subject}})
    return docs

def fetch_all_calendar(creds, max_results=50):
    service = build('calendar', 'v3', credentials=creds)
    from datetime import datetime, timedelta
    now = datetime.utcnow().isoformat() + 'Z'
    events_result = service.events().list(calendarId='primary', timeMin=now,
                                        maxResults=max_results, singleEvents=True,
                                        orderBy='startTime').execute()
    events = events_result.get('items', [])
    
    docs = []
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        summary = event.get('summary', 'No Title')
        description = event.get('description', '')
        content = f"Event: {summary}\nStart: {start}\nDescription: {description}"
        docs.append({"content": content, "metadata": {"id": event.get('id'), "type": "calendar", "summary": summary}})
    return docs

def fetch_all_drive(creds, max_results=50):
    service = build('drive', 'v3', credentials=creds)
    results = service.files().list(
        pageSize=max_results, fields="nextPageToken, files(id, name, mimeType, description)").execute()
    items = results.get('files', [])
    
    docs = []
    for item in items:
        content = f"File Name: {item['name']}\nType: {item['mimeType']}\nDescription: {item.get('description', 'N/A')}"
        docs.append({"content": content, "metadata": {"id": item['id'], "type": "drive", "name": item['name']}})
    return docs