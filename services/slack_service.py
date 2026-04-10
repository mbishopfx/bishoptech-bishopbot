import requests
import json
from config import CONFIG

def send_delayed_message(response_url, text, blocks=None):
    """
    Sends a message back to Slack using the response_url provided by the slash command.
    Used by the local worker after completing long-running tasks.
    """
    payload = {
        "text": text,
        "replace_original": False,
        "response_type": "in_channel" # or "ephemeral"
    }
    
    if blocks:
        payload["blocks"] = blocks
        
    try:
        response = requests.post(
            response_url, 
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'}
        )
        return response.status_code == 200
    except Exception as e:
        print(f"Error sending delayed message: {e}")
        return False


def send_channel_message(text, channel=None, blocks=None):
    channel = channel or CONFIG.get("SLACK_NOTIFICATIONS_CHANNEL")
    if not channel:
        print("⚠️ No SLACK_NOTIFICATIONS_CHANNEL configured; skipping channel message.")
        return False

    payload = {"channel": channel, "text": text}
    if blocks:
        payload["blocks"] = blocks

    try:
        response = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {CONFIG.get('SLACK_BOT_TOKEN')}",
            },
            data=json.dumps(payload),
            timeout=10,
        )
        if response.status_code != 200:
            print(f"Error sending channel message: {response.status_code} {response.text}")
            return False
        data = response.json()
        if not data.get("ok"):
            print(f"Error sending channel message: {data}")
            return False
        return True
    except Exception as e:
        print(f"Error sending channel message: {e}")
        return False
