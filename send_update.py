import os
import sys
import json
import urllib.request

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_NOTIFICATIONS_CHANNEL = os.getenv("SLACK_NOTIFICATIONS_CHANNEL")

def send_slack_message(message):
    if not SLACK_BOT_TOKEN or not SLACK_NOTIFICATIONS_CHANNEL:
        print("Missing SLACK_BOT_TOKEN or SLACK_NOTIFICATIONS_CHANNEL in the environment.")
        return False

    url = "https://slack.com/api/chat.postMessage"
    headers = {
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        "Content-Type": "application/json; charset=utf-8"
    }
    payload = {
        "channel": SLACK_NOTIFICATIONS_CHANNEL,
        "text": message
    }
    
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            if res_data.get("ok"):
                return True
            else:
                print(f"Slack API Error: {res_data.get('error')}")
                return False
    except Exception as e:
        print(f"Error sending message: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: SLACK_BOT_TOKEN=... SLACK_NOTIFICATIONS_CHANNEL=... python3 send_update.py <message>")
        sys.exit(1)
        
    msg = sys.argv[1]
    if send_slack_message(msg):
        print("Successfully sent update to Slack.")
    else:
        sys.exit(1)
