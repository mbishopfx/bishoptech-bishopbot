import os
import time
import requests
from config import CONFIG

GITHUB_API_URL = "https://api.github.com"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
SLACK_NOTIFICATIONS_CHANNEL = os.getenv("SLACK_NOTIFICATIONS_CHANNEL")

def get_repos():
    """Fetch all repos for the authenticated user, handling pagination."""
    repos = []
    page = 1
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    while True:
        url = f"{GITHUB_API_URL}/user/repos?sort=updated&per_page=100&page={page}"
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"❌ Error fetching repos: {response.status_code} {response.text}")
            break
        data = response.json()
        if not data:
            break
        repos.extend(data)
        if len(data) < 100:
            break
        page += 1
    return repos

def get_latest_commit(repo_full_name, default_branch="main"):
    """Get the latest commit hash for a repo."""
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    url = f"{GITHUB_API_URL}/repos/{repo_full_name}/commits/{default_branch}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()['sha'], response.json()['commit']['message']
    
    # Fallback to master if main fails and we haven't tried master
    if default_branch == "main":
        return get_latest_commit(repo_full_name, default_branch="master")
        
    return None, None

def monitor_commits():
    print("🕵️ Starting GitHub Commit Monitor...")
    if not SLACK_NOTIFICATIONS_CHANNEL:
        print("⚠️ Warning: SLACK_NOTIFICATIONS_CHANNEL not set. Messages will only be printed to console.")
    
    last_known_commits = {}
    
    # Initialize
    print("🔄 Initializing repo list...")
    repos = get_repos()
    print(f"📊 Found {len(repos)} repositories.")
    for repo in repos:
        name = repo['full_name']
        branch = repo.get('default_branch', 'main')
        sha, _ = get_latest_commit(name, branch)
        if sha:
            last_known_commits[name] = sha
    
    print("🚀 Monitoring for new commits...")
    while True:
        try:
            repos = get_repos()
            for repo in repos:
                name = repo['full_name']
                branch = repo.get('default_branch', 'main')
                current_sha, message = get_latest_commit(name, branch)
                
                if current_sha and current_sha != last_known_commits.get(name):
                    # Check if it was just initialized
                    if name not in last_known_commits:
                        last_known_commits[name] = current_sha
                        continue

                    print(f"🆕 New commit in {name}: {message}")
                    
                    # Notify Slack
                    slack_msg = f"📦 *New Progress Detected in {name}*\n> {message}\n_Gemini CLI progression log updated._"
                    
                    if SLACK_NOTIFICATIONS_CHANNEL:
                        try:
                            # Avoid circular import by using app client directly if possible or creating a small client
                            from slack_bolt import App
                            slack_app = App(token=os.getenv("SLACK_BOT_TOKEN"))
                            slack_app.client.chat_postMessage(channel=SLACK_NOTIFICATIONS_CHANNEL, text=slack_msg)
                        except Exception as slack_err:
                            print(f"❌ Slack notification failed: {slack_err}")
                    
                    last_known_commits[name] = current_sha
            
            time.sleep(60) # Poll every minute
        except Exception as e:
            print(f"❌ Error in monitor: {e}")
            time.sleep(30) # Wait before retrying

if __name__ == "__main__":
    if not GITHUB_TOKEN:
        print("❌ Error: GITHUB_TOKEN not found in .env")
    else:
        monitor_commits()