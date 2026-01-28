import git
import os
from config import CONFIG

def sync_changes(message):
    repo_path = CONFIG["PROJECT_ROOT_DIR"]
    try:
        repo = git.Repo(repo_path)
    except git.exc.InvalidGitRepositoryError:
        repo = git.Repo.init(repo_path)
    
    # Check if there are changes to commit
    if repo.is_dirty(untracked_files=True):
        repo.git.add(A=True)
        commit_msg = f"Gemini CLI: {message}"
        repo.index.commit(commit_msg)
        
        # In a real scenario, you'd check for a remote before pushing
        # if repo.remotes:
        #     repo.remotes.origin.push()
        return "Changes committed."
    return "No changes detected."

def get_diffs():
    repo_path = CONFIG["PROJECT_ROOT_DIR"]
    try:
        repo = git.Repo(repo_path)
        return repo.git.diff('HEAD~1', 'HEAD')
    except Exception:
        return "Could not retrieve diffs."
