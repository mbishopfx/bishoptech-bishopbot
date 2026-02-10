import os
# Fix for macOS fork() issue with Objective-C libraries
os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"

import time
from redis import Redis
from rq import Worker, Queue, Connection, SimpleWorker
from config import CONFIG
from handlers import cli_handler, google_handler, research_handler
from services.reply_service import send as send_delayed_message
from services.terminal_session_manager import TerminalSessionManager

def process_task(command, input_text, response_url, user_id):
    """
    This function runs LOCALLY on your machine.
    It takes the task from Redis, runs the logic, and posts back to Slack.
    """
    print(f"🛠️ Processing {command} for {user_id}: {input_text}")
    
    try:
        if command == "/cli":
            # Pass user_id to handle_cli_command
            result = cli_handler.handle_cli_command(input_text, response_url=response_url, user_id=user_id)
        elif command == "/codex":
            result = cli_handler.handle_cli_command(input_text, response_url=response_url, user_id=user_id, mode="codex")
        elif command in ["/google", "/gmail", "/drive", "/calendar", "/meet"]:
            result = google_handler.handle_google_command(input_text, command=command)
        elif command == "/research":
            result = research_handler.handle_research_command(input_text)
        else:
            result = {"success": False, "error": "Unknown command"}

        # Format message for Slack if it's NOT a CLI command (CLI command handles its own feedback via sessions)
        if command not in ["/cli", "/codex"]:
            if result["success"]:
                msg = f"✅ *Success ({command})*\n```\n{result.get('output', 'Success')}\n```"
            else:
                msg = f"❌ *Error ({command})*\n{result.get('error', 'Unknown Error')}"
            
            # Send result back via response_url
            send_delayed_message(response_url, msg)
            
        print(f"✅ Finished {command}")

    except Exception as e:
        error_msg = f"💥 *Crash in Local Worker:* {str(e)}"
        send_delayed_message(response_url, error_msg)
        print(error_msg)

def process_terminal_input(session_id, input_text, user_id, response_url):
    """
    Handles interactive terminal input from Slack buttons.
    """
    print(f"⌨️ Sending terminal input to session {session_id}: {input_text}")
    
    if input_text == "STATUS":
        snap = TerminalSessionManager.snapshot(session_id)
        msg = f"📟 Session `{session_id}` status:\n```\n{snap or '(no output)'}\n```"
        send_delayed_message(response_url, msg)
        return

    if input_text == "STOP":
        success = TerminalSessionManager.close_session(session_id)
        msg = f"🛑 *Gemini Session `{session_id}` Stopped* by <@{user_id}>"
    else:
        success = TerminalSessionManager.send_input(session_id, input_text)
        msg = f"⌨️ Sent `{input_text}` to session `{session_id}`" if success else f"❌ Failed to send input to session `{session_id}`"

    send_delayed_message(response_url, msg)

if __name__ == '__main__':
    # Start the knowledge refresh in the background
    import threading
    from refresh_knowledge import refresh_loop
    refresh_thread = threading.Thread(target=refresh_loop, daemon=True)
    refresh_thread.start()
    print("🧠 Background Knowledge Refresh started (1h interval)")

    # Connect to the SAME Redis as Railway
    try:
        conn = Redis.from_url(CONFIG["REDIS_URL"])
        with Connection(conn):
            # Use SimpleWorker on macOS to avoid fork() issues
            worker_class = SimpleWorker if os.uname().sysname == 'Darwin' else Worker
            worker = worker_class([Queue(CONFIG["TASK_QUEUE_NAME"])])
            print(f"🤖 BishopBot Local Worker ({worker_class.__name__}) started on queue: {CONFIG['TASK_QUEUE_NAME']}")
            print("Listening for commands from Railway/Redis...")
            worker.work()
    except Exception as e:
        print(f"Failed to start worker: {e}")
        print("Check if REDIS_URL is correct in your .env")
