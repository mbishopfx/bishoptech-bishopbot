import os
import asyncio
import aiohttp
from config import CONFIG

GITHUB_API_URL = "https://api.github.com"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
SLACK_NOTIFICATIONS_CHANNEL = os.getenv("SLACK_NOTIFICATIONS_CHANNEL")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")

async def send_slack_message(session, text):
    """Utility to send a slack message using the bot token."""
    if not SLACK_BOT_TOKEN or not SLACK_NOTIFICATIONS_CHANNEL:
        print(f"⚠️ Cannot send Slack message (missing token/channel): {text}")
        return
    
    try:
        url = "https://slack.com/api/chat.postMessage"
        headers = {
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {
            "channel": SLACK_NOTIFICATIONS_CHANNEL,
            "text": text
        }
        async with session.post(url, headers=headers, json=payload) as resp:
            data = await resp.json()
            if not data.get("ok"):
                print(f"❌ Slack API Error: {data}")
    except Exception as e:
        print(f"❌ Error sending Slack message: {e}")

async def get_repos(session):
    """Fetch all repos for the authenticated user, handling pagination."""
    repos = []
    page = 1
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    
    while True:
        url = f"{GITHUB_API_URL}/user/repos?sort=updated&per_page=100&page={page}"
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    print(f"❌ Error fetching repos: {resp.status} {text}")
                    break
                data = await resp.json()
                if not data:
                    break
                repos.extend(data)
                if len(data) < 100:
                    break
                page += 1
        except Exception as e:
            print(f"❌ Exception fetching repos: {e}")
            break
    
    return repos

async def get_latest_commit(session, repo_full_name, default_branch="main"):
    """Get the latest commit hash for a repo."""
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    url = f"{GITHUB_API_URL}/repos/{repo_full_name}/commits/{default_branch}"
    
    try:
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data['sha'], data['commit']['message']
            
            # Fallback to master if main fails
            if default_branch == "main":
                return await get_latest_commit(session, repo_full_name, default_branch="master")
    except Exception as e:
        print(f"❌ Error fetching commit for {repo_full_name}: {e}")
    
    return None, None

async def check_repo_batch(session, repos, last_known_commits):
    """Check a batch of repos concurrently for new commits."""
    new_commits = []
    
    async def check_single(repo):
        name = repo['full_name']
        branch = repo.get('default_branch', 'main')
        current_sha, message = await get_latest_commit(session, name, branch)
        
        if current_sha and current_sha != last_known_commits.get(name):
            # Check if it was just initialized
            if name not in last_known_commits:
                return (name, current_sha, None)  # Just initialize, no notification
            return (name, current_sha, message)  # New commit!
        
        return None
    
    # Process repos in batches of 10 to avoid rate limits
    batch_size = 10
    for i in range(0, len(repos), batch_size):
        batch = repos[i:i+batch_size]
        tasks = [check_single(repo) for repo in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                print(f"❌ Batch check error: {result}")
            elif result:
                new_commits.append(result)
        
        # Small delay between batches to be nice to the API
        if i + batch_size < len(repos):
            await asyncio.sleep(1)
    
    return new_commits

async def monitor_commits():
    """Main async monitoring loop."""
    print("🕵️ Starting GitHub Commit Monitor (Async)...")
    
    async with aiohttp.ClientSession() as session:
        await send_slack_message(session, "🚀 *GitHub Monitor Online* (Railway - Async)\nMonitoring repositories for activity.")
        
        last_known_commits = {}
        
        # Initialize
        print("🔄 Initializing repo list...")
        repos = await get_repos(session)
        print(f"📊 Found {len(repos)} repositories.")
        
        # Get initial commit states
        init_results = await check_repo_batch(session, repos, last_known_commits)
        for name, sha, _ in init_results:
            if sha:
                last_known_commits[name] = sha
        
        print(f"✅ Initialized {len(last_known_commits)} repos with current commits.")
        print("🚀 Monitoring for new commits...")
        
        while True:
            try:
                repos = await get_repos(session)
                new_commits = await check_repo_batch(session, repos, last_known_commits)
                
                for name, sha, message in new_commits:
                    last_known_commits[name] = sha
                    
                    if message:  # Only notify if there's a message (not init)
                        print(f"🆕 New commit in {name}: {message}")
                        slack_msg = f"📦 *New Progress Detected in {name}*\n> {message}\n_Gemini CLI progression log updated._"
                        await send_slack_message(session, slack_msg)
                
                # Non-blocking sleep - this is the key improvement
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                print("🛑 Monitor cancelled, shutting down gracefully...")
                break
            except Exception as e:
                print(f"❌ Error in monitor: {e}")
                await asyncio.sleep(30)  # Wait before retrying

def run_monitor():
    """Entry point that runs the async monitor."""
    try:
        asyncio.run(monitor_commits())
    except KeyboardInterrupt:
        print("\n🛑 GitHub Monitor stopped by user.")

if __name__ == "__main__":
    if not GITHUB_TOKEN:
        print("❌ Error: GITHUB_TOKEN not found in .env")
    else:
        run_monitor()
