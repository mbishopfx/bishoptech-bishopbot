import os
# Fix for macOS fork() issue with Objective-C libraries
os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from redis import Redis
from rq import Queue
from config import CONFIG

# Initialize Redis and Queue
redis_conn = Redis.from_url(CONFIG["REDIS_URL"])
q = Queue(CONFIG["TASK_QUEUE_NAME"], connection=redis_conn)

# Initialize the Bolt app
app = App(token=CONFIG["SLACK_BOT_TOKEN"])

def enqueue_task(command, body, say):
    user_input = body.get("text", "")
    user_id = body["user_id"]
    response_url = body["response_url"]
    
    # Immediately acknowledge to user
    say(f"📨 <@{user_id}>, task queued for local machine: `{command} {user_input}`")
    
    # Push to Redis
    q.enqueue(
        'local_worker.process_task', 
        command=command, 
        input_text=user_input, 
        response_url=response_url,
        user_id=user_id
    )

@app.command("/cli")
def cli_handler(ack, body, say):
    ack()
    enqueue_task("/cli", body, say)

@app.command("/gmail")
def gmail_handler(ack, body, say):
    ack()
    enqueue_task("/gmail", body, say)

@app.command("/drive")
def drive_handler(ack, body, say):
    ack()
    enqueue_task("/drive", body, say)

@app.command("/calendar")
def calendar_handler(ack, body, say):
    ack()
    enqueue_task("/calendar", body, say)

@app.command("/meet")
def meet_handler(ack, body, say):
    ack()
    enqueue_task("/meet", body, say)

@app.command("/research")
def research_handler(ack, body, say):
    ack()
    enqueue_task("/research", body, say)

@app.command("/google")
def google_handler(ack, body, say):
    ack()
    enqueue_task("/google", body, say)

# --- Interactive Button Handlers ---

@app.action("cli_input_enter")
def handle_cli_enter(ack, body, say):
    ack()
    _enqueue_cli_input(body, "ENTER")

@app.action("cli_input_no")
def handle_cli_no(ack, body, say):
    ack()
    _enqueue_cli_input(body, "N")

@app.action("cli_stop")
def handle_cli_stop(ack, body, say):
    ack()
    _enqueue_cli_input(body, "STOP")

def _enqueue_cli_input(body, input_type):
    """Auxiliary to enqueue inputs from interactive buttons."""
    # body["actions"][0]["value"] contains "session_id:TYPE"
    full_value = body["actions"][0]["value"]
    session_id, _ = full_value.split(":")
    user_id = body["user"]["id"]
    response_url = body["response_url"]
    
    # Push a special terminal input task to Redis
    q.enqueue(
        'local_worker.process_terminal_input',
        session_id=session_id,
        input_text=input_type,
        user_id=user_id,
        response_url=response_url
    )

if __name__ == "__main__":
    # Start the app using Socket Mode
    handler = SocketModeHandler(app, CONFIG["SLACK_APP_TOKEN"])
    handler.start()