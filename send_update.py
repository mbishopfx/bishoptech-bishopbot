import os
import sys
import json
import urllib.request

# Hardcoded for the standalone tool as requested
SLACK_BOT_TOKEN = "xoxb-9440980605828-10406902778304-nPSk2ZTzW9uOsg7r08awqsmz"
SLACK_NOTIFICATIONS_CHANNEL = "C09CYUULMEY"

def send_slack_message(message):
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
        print("Usage: python3 send_update.py <message>")
        sys.exit(1)
        
    msg = sys.argv[1]
    if send_slack_message(msg):
        print("Successfully sent update to Slack.")
    else:
        sys.exit(1)
