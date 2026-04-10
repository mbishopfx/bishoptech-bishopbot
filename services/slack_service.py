import requests
import json
from config import CONFIG


def is_slack_target(target):
    return bool(target and str(target).strip().startswith("slack:"))


def parse_slack_target(target):
    raw = str(target or "").strip()
    if not raw.startswith("slack:"):
        return None, None
    parts = raw.split(":", 2)
    channel_id = parts[1] if len(parts) > 1 else None
    thread_ts = parts[2] if len(parts) > 2 else None
    return channel_id, thread_ts

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


def post_message(text, channel=None, blocks=None, thread_ts=None):
    channel = channel or CONFIG.get("SLACK_NOTIFICATIONS_CHANNEL")
    if not channel:
        print("⚠️ No SLACK_NOTIFICATIONS_CHANNEL configured; skipping channel message.")
        return None

    payload = {"channel": channel, "text": text}
    if blocks:
        payload["blocks"] = blocks
    if thread_ts:
        payload["thread_ts"] = thread_ts

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
            return None
        data = response.json()
        if not data.get("ok"):
            print(f"Error sending channel message: {data}")
            return None
        return data
    except Exception as e:
        print(f"Error sending channel message: {e}")
        return None


def send_channel_message(text, channel=None, blocks=None):
    return bool(post_message(text, channel=channel, blocks=blocks))


def send_target_message(target, text, blocks=None):
    channel_id, thread_ts = parse_slack_target(target)
    if not channel_id:
        return False
    return post_message(text, channel=channel_id, blocks=blocks, thread_ts=thread_ts)
