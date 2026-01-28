import os
import time
import requests
from config import CONFIG
from services.slack_service import send_delayed_message

GITHUB_API_URL = "https://api.github.com"
# You'll need to add GITHUB_TOKEN to your .env
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

def get_repos():
    """Fetch all repos for the authenticated user."""
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.get(f"{GITHUB_API_URL}/user/repos?sort=updated", headers=headers)
    return response.json() if response.status_code == 200 else []

def get_latest_commit(repo_full_name):
    """Get the latest commit hash for a repo."""
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.get(f"{GITHUB_API_URL}/repos/{repo_full_name}/commits/main", headers=headers)
    if response.status_code == 200:
        return response.json()['sha'], response.json()['commit']['message']
    return None, None

def monitor_commits():
    print("🕵️ Starting GitHub Commit Monitor...")
    last_known_commits = {}
    
    # Initialize
    repos = get_repos()
    for repo in repos:
        name = repo['full_name']
        sha, _ = get_latest_commit(name)
        if sha:
            last_known_commits[name] = sha

    while True:
        try:
            repos = get_repos()
            for repo in repos:
                name = repo['full_name']
                current_sha, message = get_latest_commit(name)
                
                if current_sha and current_sha != last_known_commits.get(name):
                    print(f"🆕 New commit in {name}: {message}")
                    
                    # Notify Slack
                    slack_msg = f"📦 *New Progress Detected in {name}*\n> {message}\n_Gemini CLI progression log updated._"
                    # Note: We need a generic channel or the specific response_url. 
                    # For a monitor, we usually post to a default channel ID.
                    # We'll use a placeholder for SLACK_NOTIFICATIONS_CHANNEL
                    channel_id = os.getenv("SLACK_NOTIFICATIONS_CHANNEL")
                    if channel_id:
                        from services.slack_service import send_delayed_message
                        # Use requests directly or Bolt app to post
                        from app import app
                        try:
                            app.client.chat_postMessage(channel=channel_id, text=slack_msg)
                        except Exception as slack_err:
                            print(f"Slack notification failed: {slack_err}")
                    
                    last_known_commits[name] = current_sha
            
            time.sleep(60) # Poll every minute
        except Exception as e:
            print(f"Error in monitor: {e}")
            time.sleep(30) # Wait before retrying

if __name__ == "__main__":
    if not GITHUB_TOKEN:
        print("❌ Error: GITHUB_TOKEN not found in .env")
    else:
        monitor_commits()
