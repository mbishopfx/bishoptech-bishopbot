from redis import Redis
from config import CONFIG


def _redis():
    return Redis.from_url(CONFIG["REDIS_URL"]) if CONFIG.get("REDIS_URL") else None


def set_last_session(user_key: str, session_id: str, ttl_seconds: int = 60 * 60 * 24):
    r = _redis()
    if not r:
        return False
    try:
        r.setex(f"wa:last_session:{user_key}", ttl_seconds, session_id)
        return True
    except Exception as e:
        print(f"⚠️ Failed to set last session mapping: {e}")
        return False


def get_last_session(user_key: str):
    r = _redis()
    if not r:
        return None
    try:
        v = r.get(f"wa:last_session:{user_key}")
        return v.decode("utf-8") if v else None
    except Exception as e:
        print(f"⚠️ Failed to get last session mapping: {e}")
        return None


def set_slack_thread_session(channel_id: str, thread_ts: str, session_id: str, ttl_seconds: int = 60 * 60 * 24):
    r = _redis()
    if not r or not channel_id or not thread_ts or not session_id:
        return False
    try:
        r.setex(f"slack:thread_session:{channel_id}:{thread_ts}", ttl_seconds, session_id)
        return True
    except Exception as e:
        print(f"⚠️ Failed to set Slack thread mapping: {e}")
        return False


def get_slack_thread_session(channel_id: str, thread_ts: str):
    r = _redis()
    if not r or not channel_id or not thread_ts:
        return None
    try:
        v = r.get(f"slack:thread_session:{channel_id}:{thread_ts}")
        return v.decode("utf-8") if v else None
    except Exception as e:
        print(f"⚠️ Failed to get Slack thread mapping: {e}")
        return None
