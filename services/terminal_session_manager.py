import os
import sys
import time
import uuid
import threading
import subprocess
from services import shell_service, reply_service, session_link_service
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
        try:
            boot_delay = int(str(CONFIG.get("TERMINAL_BOOT_DELAY_SECONDS", "7")))
        except Exception:
            boot_delay = 7
        time.sleep(max(0, boot_delay))
        
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

        # Keep a per-user "last session" pointer (used by WhatsApp controls like !enter).
        if user_id and session_id:
            session_link_service.set_last_session(str(user_id), session_id)
        
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
        try:
            poll_interval = int(str(CONFIG.get("TERMINAL_POLL_INTERVAL_SECONDS", "40")))
        except Exception:
            poll_interval = 40
        
        while session_id in SESSIONS and SESSIONS[session_id]["active"]:
            session = SESSIONS[session_id]
            
            # Check for timeout
            if time.time() - session["start_time"] > timeout:
                TerminalSessionManager.send_status_to_slack(session_id, "⏰ *Session Timeout:* Closing terminal session after 30 minutes.")
                TerminalSessionManager.close_session(session_id)
                break
            
            # Capture output
            current_output = TerminalSessionManager.get_terminal_contents(
                session["window_id"],
                tail_lines=TerminalSessionManager._tail_lines_for_target(session.get("response_url")),
            )
            
            # If output has changed significantly, or every few polls, report to Slack
            if current_output and current_output != session["last_output"]:
                # Check for common interaction prompts
                needs_input = any(prompt in current_output.lower() for prompt in ["proceed?", "y/n", "enter", "confirm"])
                
                TerminalSessionManager.send_status_to_slack(session_id, current_output, needs_input=needs_input)
                session["last_output"] = current_output
                session["last_poll_time"] = time.time()
            
            time.sleep(max(5, poll_interval))
        
        print(f"🧵 Polling thread exiting for session {session_id}")

    @staticmethod
    def _tail_lines_for_target(target):
        try:
            if reply_service.is_whatsapp_target(target):
                return int(str(CONFIG.get("TERMINAL_TAIL_LINES_WHATSAPP", "40")))
            return int(str(CONFIG.get("TERMINAL_TAIL_LINES_SLACK", "15")))
        except Exception:
            return 15

    @staticmethod
    def get_terminal_contents(window_id, tail_lines=15):
        """Uses AppleScript to get the current visible text in the terminal window."""
        if sys.platform != "darwin":
            return "Terminal capture only supported on macOS"
            
        try:
            # Get the text contents of the specific window
            script = f'tell application "Terminal" to get contents of window id {window_id}'
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=True)
            full_text = result.stdout.strip()
            
            # Tail output to avoid flooding chat.
            lines = full_text.splitlines()
            if tail_lines and len(lines) > tail_lines:
                # Filter out empty lines at the end.
                last_lines = [line for line in lines[-tail_lines:] if line.strip()]
                return "\n".join(last_lines)
            return full_text
        except Exception as e:
            print(f"⚠️ Error capturing terminal {window_id}: {e}")
            return None

    @staticmethod
    def send_status_to_slack(session_id, output, needs_input=False, header_override=None):
        """Sends a status update to Slack (response_url) or WhatsApp (whatsapp:<wa_id>)."""
        session = SESSIONS.get(session_id)
        if not session:
            return
            
        header = header_override or f"🤖 *Gemini Session `{session_id}` Status Update*"
        if needs_input:
            header += " ⚠️ *ACTION REQUIRED*"
            
        # Format the output in a code block
        formatted_output = f"```\n{output}\n```"

        target = session.get("response_url")
        if reply_service.is_whatsapp_target(target):
            msg = f"{header}\n{formatted_output}"
            if needs_input:
                msg += f"\n\nControls: !enter {session_id} | !n {session_id} | !y {session_id} | !stop {session_id}"
            reply_service.send(target, msg)
            return
        
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
            
        reply_service.send(target, header, blocks=blocks)

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
    def snapshot(session_id):
        """Capture current tailed output for a session (useful for manual status requests)."""
        session = SESSIONS.get(session_id)
        if not session or not session.get("active"):
            return None
        return TerminalSessionManager.get_terminal_contents(
            session["window_id"],
            tail_lines=TerminalSessionManager._tail_lines_for_target(session.get("response_url")),
        )

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
