import subprocess
import os
import sys
import io
import time
from contextlib import redirect_stdout, redirect_stderr
from config import CONFIG

def run(code, cwd=None):
    if cwd is None:
        cwd = CONFIG["PROJECT_ROOT_DIR"]
    
    # Simple heuristic to determine if it's bash or python
    if code.strip().startswith("#!") or any(code.strip().startswith(cmd) for cmd in ["ls ", "cd ", "mkdir ", "git ", "cat ", "grep ", "rm ", "cp ", "mv "]):
        return run_bash(code, cwd)
    else:
        return run_python(code, cwd)

def start_terminal_session(cwd=None):
    if cwd is None:
        cwd = CONFIG["PROJECT_ROOT_DIR"]
    
    if sys.platform == "darwin":
        try:
            # Open Terminal, start Gemini, and return the unique window ID
            script = f'''
            tell application "Terminal"
                activate
                set newWin to do script "cd {cwd} && gemini"
                delay 1
                return id of window 1
            end tell
            '''
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=True)
            window_id = result.stdout.strip()
            return window_id
        except Exception as e:
            print(f"Error starting terminal: {e}")
            return None
    return None

def run_bash(code, cwd):
    try:
        result = subprocess.run(code, shell=True, cwd=cwd, capture_output=True, text=True, check=True)
        return f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    except subprocess.CalledProcessError as e:
        return f"FAILED with exit code {e.returncode}\nSTDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}"

def send_input_to_terminal(input_text, window_id=None):
    """Uses System Events to type input into a SPECIFIC Terminal window."""
    if sys.platform == "darwin":
        try:
            # Escape double quotes by breaking the string and inserting the 'quote' constant
            # This is the most reliable way to handle nested quotes in AppleScript
            escaped_input = input_text.replace('"', '" & quote & "')
            
            # Target the specific window ID we captured earlier
            target = f"window id {window_id}" if window_id else "window 1"
            
            script = f'''
            tell application "Terminal"
                activate
                set index of {target} to 1
            end tell
            delay 0.5
            tell application "System Events"
                tell process "Terminal"
                    keystroke "{escaped_input}"
                    delay 0.1
                    key code 36 -- Return key
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