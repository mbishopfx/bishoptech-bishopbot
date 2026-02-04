import os
import sys
import time
import uuid
import threading
import subprocess
from services import shell_service, slack_service
from config import CONFIG

# Global dictionary to track active sessions
# session_id -> {window_id, thread, response_url, user_id, last_output, active}
SESSIONS = {}

class TerminalSessionManager:
    @staticmethod
    def start_session(user_id, response_url, initial_command, plan_text="", tasks=None, agent_mode="gemini"):
        """Starts a new Gemini session in a terminal and kicks off monitoring."""
        session_id = str(uuid.uuid4())[:8]
        
        # 1. Start the actual terminal window
        window_id = shell_service.start_terminal_session()
        
        if not window_id:
            print(f"❌ Failed to start terminal for session {session_id}")
            return None

        # 2. Wait for Gemini to initialize
        time.sleep(10)
        
        # 3. Send initial command
        shell_service.send_input_to_terminal(initial_command, window_id=window_id)
        
        # 4. Store session info
        SESSIONS[session_id] = {
            "window_id": window_id,
            "response_url": response_url,
            "user_id": user_id,
            "last_output": "",
            "active": True,
            "start_time": time.time(),
            "last_poll_time": time.time()
        }
        SESSIONS[session_id]["plan_text"] = plan_text
        SESSIONS[session_id]["tasks"] = tasks or []
        SESSIONS[session_id]["agent_mode"] = agent_mode
        SESSIONS[session_id]["current_task_index"] = 0
        
        # 5. Start background polling thread
        thread = threading.Thread(
            target=TerminalSessionManager._poll_loop, 
            args=(session_id,), 
            daemon=True
        )
        SESSIONS[session_id]["thread"] = thread
        thread.start()
        
        if plan_text:
            plan_header = f"🧭 {agent_mode.capitalize()} plan for session `{session_id}`"
            TerminalSessionManager.send_status_to_slack(session_id, plan_text, header_override=plan_header)
        
        return session_id

    @staticmethod
    def _poll_loop(session_id):
        """Background thread that polls terminal output and posts to Slack."""
        print(f"🧵 Polling thread started for session {session_id}")
        
        timeout = 1800  # 30 minutes
        poll_interval = 40  # 40 seconds
        
        while session_id in SESSIONS and SESSIONS[session_id]["active"]:
            session = SESSIONS[session_id]
            
            # Check for timeout
            if time.time() - session["start_time"] > timeout:
                TerminalSessionManager.send_status_to_slack(session_id, "⏰ *Session Timeout:* Closing terminal session after 30 minutes.")
                TerminalSessionManager.close_session(session_id)
                break
            
            # Capture output
            current_output = TerminalSessionManager.get_terminal_contents(session["window_id"])
            
            # If output has changed significantly, or every few polls, report to Slack
            if current_output and current_output != session["last_output"]:
                # Check for common interaction prompts
                needs_input = any(prompt in current_output.lower() for prompt in ["proceed?", "y/n", "enter", "confirm"])
                
                TerminalSessionManager.send_status_to_slack(session_id, current_output, needs_input=needs_input)
                session["last_output"] = current_output
                session["last_poll_time"] = time.time()
            
            time.sleep(poll_interval)
        
        print(f"🧵 Polling thread exiting for session {session_id}")

    @staticmethod
    def get_terminal_contents(window_id):
        """Uses AppleScript to get the current visible text in the terminal window."""
        if sys.platform != "darwin":
            return "Terminal capture only supported on macOS"
            
        try:
            # Get the text contents of the specific window
            script = f'tell application "Terminal" to get contents of window id {window_id}'
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=True)
            full_text = result.stdout.strip()
            
            # Usually we only want the last ~15 lines to show progress without flooding Slack
            lines = full_text.splitlines()
            if len(lines) > 15:
                # Filter out empty lines at the end
                last_lines = [line for line in lines[-15:] if line.strip()]
                return "\n".join(last_lines)
            return full_text
        except Exception as e:
            print(f"⚠️ Error capturing terminal {window_id}: {e}")
            return None

    @staticmethod
    def send_status_to_slack(session_id, output, needs_input=False, header_override=None):
        """Sends a status update to Slack with optional interactive buttons."""
        session = SESSIONS.get(session_id)
        if not session:
            return
            
        header = header_override or f"🤖 *Gemini Session `{session_id}` Status Update*"
        if needs_input:
            header += " ⚠️ *ACTION REQUIRED*"
            
        # Format the output in a code block
        formatted_output = f"```\n{output}\n```"
        
        blocks = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": header}
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": formatted_output}
            }
        ]
        
        # Add buttons if interaction is likely needed
        if needs_input or True: # Always add buttons for control
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✅ Yes / Enter"},
                        "value": f"{session_id}:ENTER",
                        "action_id": "cli_input_enter"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "❌ No"},
                        "value": f"{session_id}:N",
                        "action_id": "cli_input_no"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "🛑 Stop Session"},
                        "style": "danger",
                        "value": f"{session_id}:STOP",
                        "action_id": "cli_stop"
                    }
                ]
            })
            
        slack_service.send_delayed_message(session["response_url"], header, blocks=blocks)

    @staticmethod
    def send_input(session_id, input_text):
        """Sends input to the active terminal session."""
        session = SESSIONS.get(session_id)
        if not session or not session["active"]:
            return False
            
        if input_text == "ENTER":
            # Just send a return key
            return shell_service.send_input_to_terminal("", window_id=session["window_id"])
        elif input_text == "N":
            return shell_service.send_input_to_terminal("n", window_id=session["window_id"])
        elif input_text == "Y":
            return shell_service.send_input_to_terminal("y", window_id=session["window_id"])
        else:
            return shell_service.send_input_to_terminal(input_text, window_id=session["window_id"])

    @staticmethod
    def close_session(session_id):
        """Closes a session and flags it as inactive."""
        session = SESSIONS.get(session_id)
        if session:
            session["active"] = False
            # We don't necessarily want to hard-kill the terminal window automatically
            # but we could if needed. For now just stop polling.
            print(f"✅ Session {session_id} closed.")
            return True
        return False
