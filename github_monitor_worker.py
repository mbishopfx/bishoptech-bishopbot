import os
import asyncio
import aiohttp
from config import CONFIG

GITHUB_API_URL = "https://api.github.com"
GITHUB_TOKEN = CONFIG.get("GITHUB_TOKEN")
SLACK_NOTIFICATIONS_CHANNEL = CONFIG.get("SLACK_NOTIFICATIONS_CHANNEL")
SLACK_BOT_TOKEN = CONFIG.get("SLACK_BOT_TOKEN")

async def send_slack_message(session, text):
    """Utility to send a slack message using the bot token."""
    if not SLACK_BOT_TOKEN or not SLACK_NOTIFICATIONS_CHANNEL:
        print(f"⚠️ Cannot send Slack message (missing token/channel): {text}")
        print(f"DEBUG: SLACK_BOT_TOKEN is {'Set' if SLACK_BOT_TOKEN else 'None'}")
        print(f"DEBUG: SLACK_NOTIFICATIONS_CHANNEL is {'Set' if SLACK_NOTIFICATIONS_CHANNEL else 'None'}")
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
            else:
                print(f"📡 Slack Notification Sent: {text[:50]}...")
    except Exception as e:
        print(f"❌ Error sending Slack message: {e}")

async def get_repos(session):
    """Fetch all repos for the authenticated user, handling pagination."""
    repos = []
    page = 1
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    
    if not GITHUB_TOKEN:
        print("❌ Error: GITHUB_TOKEN is not set in environment or CONFIG.")
        return []

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
            if resp.status == 404 and default_branch == "main":
                return await get_latest_commit(session, repo_full_name, default_branch="master")
            
            if resp.status != 200:
                # Silently fail for individual repos to avoid flooding logs
                return None, None
    except Exception as e:
        # print(f"❌ Error fetching commit for {repo_full_name}: {e}")
        pass
    
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
    total_repos = len(repos)
    for i in range(0, total_repos, batch_size):
        batch = repos[i:i+batch_size]
        tasks = [check_single(repo) for repo in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                print(f"❌ Batch check error: {result}")
            elif result:
                new_commits.append(result)
        
        # Small delay between batches to be nice to the API
        if i + batch_size < total_repos:
            await asyncio.sleep(0.5)
    
    return new_commits

async def monitor_commits():
    """Main async monitoring loop."""
    print("🕵️ Starting GitHub Commit Monitor (Async)...")
    print(f"DEBUG: GITHUB_TOKEN present: {bool(GITHUB_TOKEN)}")
    print(f"DEBUG: SLACK_CHANNEL present: {bool(SLACK_NOTIFICATIONS_CHANNEL)}")
    
    async with aiohttp.ClientSession() as session:
        await send_slack_message(session, "🚀 *GitHub Monitor Online* (Railway - Async)\nMonitoring repositories for activity.")
        
        last_known_commits = {}
        
        # Initialize
        print("🔄 Initializing repo list...")
        repos = await get_repos(session)
        print(f"📊 Found {len(repos)} repositories.")
        
        if not repos:
            print("⚠️ No repositories found. Check GITHUB_TOKEN permissions.")
        
        # Get initial commit states
        init_results = await check_repo_batch(session, repos, last_known_commits)
        for name, sha, _ in init_results:
            if sha:
                last_known_commits[name] = sha
        
        print(f"✅ Initialized {len(last_known_commits)} repos with current commits.")
        print("🚀 Monitoring for new commits...")
        
        while True:
            try:
                loop_start = asyncio.get_event_loop().time()
                print(f"⏱️ Running check loop at {asyncio.get_event_loop().time()}...")
                
                repos = await get_repos(session)
                if repos:
                    new_commits = await check_repo_batch(session, repos, last_known_commits)
                    
                    found_new = False
                    for name, sha, message in new_commits:
                        last_known_commits[name] = sha
                        
                        if message:  # Only notify if there's a message (not init)
                            found_new = True
                            print(f"🆕 New commit in {name}: {message}")
                            slack_msg = f"📦 *New Progress Detected in {name}*\n> {message}\n_Gemini CLI progression log updated._"
                            await send_slack_message(session, slack_msg)
                    
                    if not found_new:
                        print("😴 No new commits this cycle.")
                else:
                    print("⚠️ Repos list empty, skipping batch check.")

                # Non-blocking sleep 
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                print("🛑 Monitor cancelled, shutting down gracefully...")
                break
            except Exception as e:
                print(f"❌ Error in monitor loop: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(30)  # Wait before retrying

def run_monitor():
    """Entry point that runs the async monitor."""
    try:
        asyncio.run(monitor_commits())
    except KeyboardInterrupt:
        print("\n🛑 GitHub Monitor stopped by user.")

if __name__ == "__main__":
    run_monitor()
