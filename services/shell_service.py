import subprocess
import os
import sys
import io
from dataclasses import dataclass
from contextlib import redirect_stdout, redirect_stderr
from config import CONFIG
from services.runtime_adapters import get_runtime_adapter


@dataclass
class TerminalSnapshot:
    window_id: str
    exists: bool
    busy: bool
    contents: str = ""

def run(code, cwd=None):
    if cwd is None:
        cwd = CONFIG["PROJECT_ROOT_DIR"]
    
    # Simple heuristic to determine if it's bash or python
    if code.strip().startswith("#!") or any(code.strip().startswith(cmd) for cmd in ["ls ", "cd ", "mkdir ", "git ", "cat ", "grep ", "rm ", "cp ", "mv "]):
        return run_bash(code, cwd)
    else:
        return run_python(code, cwd)

def start_terminal_session(cwd=None, runtime="gemini", initial_prompt=None, launch_mode=None, state_file=None, output_file=None):
    if cwd is None:
        cwd = CONFIG["PROJECT_ROOT_DIR"]

    adapter = get_runtime_adapter(runtime)

    if not adapter.is_available():
        print(f"Error starting {adapter.label} terminal: binary `{adapter.binary}` is not available on PATH")
        return None

    if sys.platform == "darwin":
        try:
            launch_command = adapter.launch_bootstrap_command(
                cwd,
                initial_prompt=initial_prompt,
                launch_mode=launch_mode,
                state_file=state_file,
                output_file=output_file,
            ).replace('"', '\\"')

            script = f'''
            tell application "Terminal"
                activate
                set newTab to do script "{launch_command}"
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


def send_input_to_terminal(input_text, window_id=None):
    """Uses Terminal's native 'do script' to send input to a SPECIFIC window and attempts to trigger execution."""
    if sys.platform == "darwin":
        try:
            # Escape double quotes for AppleScript string
            escaped_input = input_text.replace('"', '\\"')
            
            # Target the specific window ID we captured earlier.
            target = f"window id {window_id}" if window_id else "front window"
            
            # We use 'do script' which is usually for shell commands, but if we send it 
            # to a busy window, it can sometimes behave like stdin injection or at least
            # show up in the buffer. 
            # To ensure it EXECUTUES, we try to send a return key via System Events 
            # but with a more robust check.
            script = f'''
            tell application "Terminal"
                activate
                try
                    if exists ({target}) then
                        do script "{escaped_input}" in {target}
                    else
                        do script "{escaped_input}" in front window
                    end if
                on error err
                    log "Terminal Error: " & err
                end try
            end tell
            delay 0.2
            tell application "System Events"
                tell process "Terminal"
                    set frontmost to true
                    key code 36 -- Return key
                end tell
            end tell
            '''
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
            if result.returncode != 0:
                # If System Events fails (exit 1), we at least want to know IF the 'do script' part worked.
                # Often 'do script' works but 'System Events' fails due to permissions.
                print(f"Terminal input sent, but Return key might have failed (exit {result.returncode}): {result.stderr.strip()}")
                # We return True anyway if we suspect the text at least got into the buffer
                return result.returncode == 0 or "System Events" in result.stderr
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
