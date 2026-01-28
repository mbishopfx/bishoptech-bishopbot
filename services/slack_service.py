import requests
import json

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
