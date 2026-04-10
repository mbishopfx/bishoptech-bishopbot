import subprocess
import os
import sys
import io
from dataclasses import dataclass
from contextlib import redirect_stdout, redirect_stderr
from typing import Optional
from config import CONFIG
from services.runtime_adapters import get_runtime_adapter


@dataclass
class TerminalSnapshot:
    window_id: str
    exists: bool
    busy: bool
    contents: str = ""


def _config_truthy(key, default="false"):
    return str(CONFIG.get(key, default) or default).strip().lower() in {"1", "true", "yes", "on"}

def run(code, cwd=None):
    if cwd is None:
        cwd = CONFIG["PROJECT_ROOT_DIR"]
    
    # Simple heuristic to determine if it's bash or python
    if code.strip().startswith("#!") or any(code.strip().startswith(cmd) for cmd in ["ls ", "cd ", "mkdir ", "git ", "cat ", "grep ", "rm ", "cp ", "mv "]):
        return run_bash(code, cwd)
    else:
        return run_python(code, cwd)

def start_terminal_session(cwd=None, runtime="gemini", initial_prompt=None, launch_mode=None, state_file=None, output_file=None, startup_command=None):
    if cwd is None:
        cwd = CONFIG["PROJECT_ROOT_DIR"]

    adapter = get_runtime_adapter(runtime)

    if not adapter.is_available():
        print(f"Error starting {adapter.label} terminal: binary `{adapter.binary}` is not available on PATH")
        return None

    if sys.platform == "darwin":
        try:
            if startup_command is not None:
                launch_command = startup_command
            else:
                launch_command = adapter.launch_bootstrap_command(
                    cwd,
                    initial_prompt=initial_prompt,
                    launch_mode=launch_mode,
                    state_file=state_file,
                    output_file=output_file,
                )

            # We use single quotes for the 'osascript -e' wrapper,
            # so we must escape any single quotes in the AppleScript itself.
            # But here we are building the AppleScript string which will contain 
            # the launch_command inside double quotes. 
            # We need to escape double quotes inside launch_command.
            escaped_launch = launch_command.replace('"', '\\"')
            activate_line = "activate" if _config_truthy("TERMINAL_ACTIVATE_ON_LAUNCH") else ""

            script = f'''
            tell application "Terminal"
                {activate_line}
                set newTab to do script "{escaped_launch}"
                delay 2
                try
                    -- Try to get the window ID associated with the new tab
                    return id of (window of newTab)
                on error
                    -- Fallback to front window if that fails
                    return id of front window
                end try
            end tell
            '''
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=True)
            window_id = result.stdout.strip()
            return window_id
        except Exception as e:
            print(f"Error starting {adapter.label} terminal: {e}")
            return None
    return None

def run_bash(code, cwd):
    try:
        result = subprocess.run(code, shell=True, cwd=cwd, capture_output=True, text=True, check=True)
        return f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    except subprocess.CalledProcessError as e:
        return f"FAILED with exit code {e.returncode}\nSTDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}"


def get_terminal_snapshot(window_id=None):
    """Return terminal existence/busy state plus visible contents for a specific window."""
    if sys.platform != "darwin":
        return TerminalSnapshot(window_id=str(window_id or ""), exists=False, busy=False, contents="Terminal capture only supported on macOS")

    target = f"window id {window_id}" if window_id else "front window"
    script = f'''
    tell application "Terminal"
        if (count of windows) is 0 then
            return "exists:false\nbusy:false\ncontents:"
        end if

        if exists ({target}) then
            set targetWindow to {target}
            set tabBusy to false
            try
                set tabBusy to busy of selected tab of targetWindow
            end try

            set tabContents to ""
            try
                set tabContents to contents of selected tab of targetWindow
            on error
                try
                    set tabContents to contents of targetWindow
                end try
            end try

            return "exists:true\nbusy:" & (tabBusy as string) & "\ncontents:" & tabContents
        end if

        return "exists:false\nbusy:false\ncontents:"
    end tell
    '''

    try:
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=True)
        raw = result.stdout or ""
        exists = False
        busy = False
        contents = ""
        for line in raw.splitlines():
            if line.startswith("exists:"):
                exists = line.split(":", 1)[1].strip().lower() == "true"
            elif line.startswith("busy:"):
                busy = line.split(":", 1)[1].strip().lower() == "true"
            elif line.startswith("contents:"):
                contents = line.split(":", 1)[1]
            else:
                contents = f"{contents}\n{line}" if contents else line
        return TerminalSnapshot(window_id=str(window_id or ""), exists=exists, busy=busy, contents=contents.strip())
    except Exception as e:
        print(f"⚠️ Error capturing terminal snapshot {window_id}: {e}")
        return TerminalSnapshot(window_id=str(window_id or ""), exists=False, busy=False, contents="")


def get_terminal_tty(window_id=None) -> Optional[str]:
    if sys.platform != "darwin":
        return None

    target = f"window id {window_id}" if window_id else "front window"
    script = f'''
    tell application "Terminal"
        if exists ({target}) then
            try
                return tty of selected tab of {target}
            on error
                return ""
            end try
        end if
        return ""
    end tell
    '''

    try:
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=True)
        tty_path = (result.stdout or "").strip()
        return tty_path or None
    except Exception as e:
        print(f"⚠️ Error resolving terminal tty for {window_id}: {e}")
        return None


def _write_to_tty(tty_path: str, input_text: str, submit: bool) -> bool:
    payload = input_text or ""
    if submit:
        payload += "\r"
    if not payload:
        return True

    try:
        fd = os.open(tty_path, os.O_WRONLY | os.O_NOCTTY)
        try:
            os.write(fd, payload.encode("utf-8"))
        finally:
            os.close(fd)
        return True
    except Exception as e:
        print(f"⚠️ Error writing to tty {tty_path}: {e}")
        return False


def _send_input_via_terminal_ui(input_text: str, window_id=None, submit=True) -> bool:
    target = f"window id {window_id}" if window_id else "front window"
    keep_terminal_frontmost = _config_truthy("TERMINAL_ACTIVATE_ON_INPUT")
    previous_app = ""

    try:
        previous_app_result = subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "System Events" to get name of first application process whose frontmost is true',
            ],
            capture_output=True,
            text=True,
        )
        previous_app = (previous_app_result.stdout or "").strip()
    except Exception:
        previous_app = ""

    previous_clipboard = None
    needs_paste = bool(input_text)
    if needs_paste:
        try:
            previous_clipboard_result = subprocess.run(["pbpaste"], capture_output=True, text=True)
            previous_clipboard = previous_clipboard_result.stdout
        except Exception:
            previous_clipboard = None

        try:
            subprocess.run(["pbcopy"], input=input_text, text=True, check=True)
        except Exception as e:
            print(f"⚠️ Error preparing clipboard for Terminal input: {e}")
            return False

    activate_line = "activate"
    restore_line = ""
    if not keep_terminal_frontmost and previous_app and previous_app != "Terminal":
        escaped_previous_app = previous_app.replace('"', '\\"')
        restore_line = f'''
        delay 0.1
        tell application "{escaped_previous_app}"
            activate
        end tell
        '''

    script = f'''
    tell application "Terminal"
        {activate_line}
        try
            if exists ({target}) then
                set frontmost of {target} to true
            end if
        end try
    end tell
    delay 0.2
    tell application "System Events"
        tell process "Terminal"
            {'keystroke "v" using command down' if needs_paste else ''}
            {'delay 0.1' if needs_paste and submit else ''}
            {'key code 36' if submit else ''}
        end tell
    end tell
    {restore_line}
    '''

    try:
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error sending Terminal UI input (exit {result.returncode}): {result.stderr.strip()}")
            return False
        return True
    except Exception as e:
        print(f"Exception sending Terminal UI input: {e}")
        return False
    finally:
        if needs_paste and previous_clipboard is not None:
            try:
                subprocess.run(["pbcopy"], input=previous_clipboard, text=True, check=True)
            except Exception:
                pass


def send_input_to_terminal(input_text, window_id=None, tty_path=None, submit=True):
    """Send text to a terminal session, preferring direct tty writes when available."""
    if sys.platform == "darwin" and window_id and tty_path:
        return _send_input_via_terminal_ui(input_text, window_id=window_id, submit=submit)

    if tty_path:
        return _write_to_tty(tty_path, input_text, submit)

    if sys.platform == "darwin":
        try:
            # Escape double quotes for AppleScript string
            escaped_input = input_text.replace('"', '\\"')
            
            # Target the specific window ID we captured earlier.
            target = f"window id {window_id}" if window_id else "front window"
            if _config_truthy("TERMINAL_ACTIVATE_ON_INPUT"):
                script = f'''
                tell application "Terminal"
                    activate
                    try
                        if exists ({target}) then
                            set frontmost of {target} to true
                        end if
                    end try
                end tell
                delay 0.3
                tell application "System Events"
                    tell process "Terminal"
                        keystroke "{escaped_input}"
                        delay 0.1
                        {'key code 36 -- Return key' if submit else ''}
                    end tell
                end tell
                '''
            else:
                if not submit:
                    print("⚠️ Non-submitting terminal input requires a tty path; falling back is not available.")
                    return False
                script = f'''
                tell application "Terminal"
                    if exists ({target}) then
                        do script "{escaped_input}" in selected tab of {target}
                        return "ok"
                    end if
                end tell
                '''
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Error sending to terminal (exit {result.returncode}): {result.stderr.strip()}")
                return False
            return True
        except Exception as e:
            print(f"Exception sending to terminal: {e}")
            return False
    return False

def run_python(code, cwd):
    # Change directory to simulate cwd for python execution
    old_cwd = os.getcwd()
    os.chdir(cwd)
    
    stdout = io.StringIO()
    stderr = io.StringIO()
    
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            # Using a relatively safe dict for globals, but it's still local execution
            exec_globals = {"os": os, "sys": sys, "subprocess": subprocess}
            exec(code, exec_globals)
        return f"STDOUT:\n{stdout.getvalue()}\nSTDERR:\n{stderr.getvalue()}"
    except Exception as e:
        return f"PYTHON ERROR:\n{str(e)}\nSTDOUT:\n{stdout.getvalue()}\nSTDERR:\n{stderr.getvalue()}"
    finally:
        os.chdir(old_cwd)
