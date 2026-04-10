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
    """Uses System Events to paste input into a SPECIFIC Terminal window."""
    if sys.platform == "darwin":
        try:
            # Put the text into the clipboard
            process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
            process.communicate(input=input_text.encode('utf-8'))
            
            # Target the specific window ID we captured earlier.
            target = f"window id {window_id}" if window_id else "front window"
            
            # AppleScript to focus window and paste
            script = f'''
            tell application "Terminal"
                activate
                try
                    if exists ({target}) then
                        set index of {target} to 1
                    else
                        set index of front window to 1
                    end if
                on error
                    set index of front window to 1
                end try
            end tell
            delay 0.5
            tell application "System Events"
                tell process "Terminal"
                    -- Paste from clipboard
                    keystroke "v" using {{command down}}
                    delay 0.2
                    -- Press Return
                    key code 36
                end tell
            end tell
            '''
            subprocess.run(["osascript", "-e", script], check=True)
            return True
        except Exception as e:
            print(f"Error sending to terminal: {e}")
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
