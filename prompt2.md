## Expanded Listener Logic

The listener is the core of the Slack integration, handling incoming slash commands (e.g., `/cli`) and orchestrating the workflow. It's built using Slack Bolt's event-driven framework, which verifies requests, acknowledges them immediately (to comply with Slack's 3-second timeout), and processes asynchronously if needed. The logic ensures secure, reliable handling with confirmations, verbose outputs, and error logging.

### Detailed Workflow Steps
1. **Incoming Slack Message**: User sends a slash command like `/cli open the xyz folder and change the header to say xyz`. This hits the webhook endpoint (exposed via ngrok locally).
2. **Verification and ACK**: Bolt verifies the signing secret to prevent unauthorized requests. It sends an immediate ACK (empty response) to Slack, then replies with a confirmation message ("Command received, processing...") to the user via `say()`.
3. **Command Parsing**: Extract the command text (e.g., body["text"]). Use `utils/command_parser.py` to break it down if complex (e.g., identify project dir, action type).
4. **Call to Gemini CLI**: Forward the parsed input to the Gemini service, which generates executable code (bash/Python). This is the "bash 'gemini [input message]'" equivalent—actually a Python call to Gemini API prompting for code generation.
5. **Execution**: Run the generated code in a safe shell environment (via `shell_service.py`), limiting to `PROJECT_ROOT_DIR` to avoid system risks.
6. **Git Integration**: After execution, check for changes, commit with a descriptive message (derived from input), and push to origin. If no repo exists, init one.
7. **Slack Reply**: 
   - Success: Send verbose output (stdout + key logs) as a threaded reply.
   - Failure: Send error message + link to log file (stored in `./logs/`).
8. **Asynchronous Handling**: For long-running tasks (e.g., large file edits or CrewAI integrations), use Bolt's `respond()` for delayed replies or Python's `threading` to background process.
9. **Error Resilience**: Catch exceptions at each step, log verbosely, and reply with failure details. Include retry logic for transient API errors (e.g., Gemini rate limits).
10. **Scalability**: Listener is modular—new commands (e.g., `/research`) register similarly. For high volume, could add queuing (e.g., Celery, but keep local for now).

### Security Considerations
- Rate limit commands per user (track via Slack user_id).
- Sanitize inputs to prevent injection (e.g., validate generated code before exec).
- OAuth for Google features: Listener triggers auth flow if tokens expired.
- Local Only: No cloud; ngrok for dev, but could use localtunnel or similar.

## Expanded Gemini CLI Shell

The "Gemini CLI Shell" is a custom Python-based interface that interprets natural language commands via Google's Gemini API into executable actions. It's not a traditional bash CLI but a smart, AI-powered shell for file/project ops, callable via Slack. It supports editing files, creating/changing projects, and integrates with added features like CrewAI research or Firecrawl audits. The shell is "verbose" on output, meaning it captures and returns detailed execution logs.

### Key Components and Logic
- **Input Interpretation**: Gemini API is prompted to convert NL (natural language) to code. E.g., Prompt: "Generate safe Python code to: {input}. Limit to dir {PROJECT_ROOT_DIR}. Output only code in a runnable block."
- **Execution Environment**: Uses `subprocess` or `exec` in a sandbox (e.g., restricted globals/locals). Supports bash-like commands via `os.system` if generated as shell scripts.
- **Statefulness**: Maintains session state per Slack thread (e.g., current working dir tracked in memory or Redis for local persistence).
- **Integration Points**:
  - **Git**: Post-execution, auto-commit/push.
  - **Google Workspace**: If command involves (e.g., "pull emails and add to file"), use OAuth'd services.
  - **CrewAI/Firecrawl**: Commands like "research topic and edit file" parse to call research handlers, then apply results to file ops.
  - **Fallbacks**: Use OpenAI/Gemini fallback in generation if primary fails.
- **Verbose Output**: Capture stdout/stderr, format as code blocks in Slack replies. Include diffs for file changes.
- **Failure Handling**: On errors, rollback changes (if possible), log full traceback, and reply with "Failure: {error}. Log: {path}".
- **Scalability**: Extend by adding prompt templates in `gemini_service.py` for new action types (e.g., "build new project" → scaffold dirs/files). Tools from CrewAI can be invoked in generated code.
- **Local CLI Mode**: For non-Slack use, add a `cli.py` entry point: `python cli.py "command"` → Same logic without Slack.

## Updated Project Structure (Minimal Changes for Expansion)

Added details to existing files; new `cli.py` for direct shell access.

```
slack-cli-gemini/
├── app.py                  # Listener registration
├── cli.py                  # New: Direct CLI entry for Gemini shell (non-Slack)
├── config.py
├── requirements.txt
├── .env.example
├── README.md               # Add listener/CLI docs
├── logs/
├── agents/
│   ├── research_agents.py
│   └── audit_agents.py
├── handlers/
│   ├── cli_handler.py      # Expanded: Detailed parsing/execution
│   ├── ... (others)
├── services/
│   ├── gemini_service.py   # Expanded: Advanced prompting for CLI
│   ├── shell_service.py    # Expanded: Sandbox exec with state
│   ├── ... (others)
├── tools/
│   ├── ... (existing)
├── utils/
│   ├── logger.py
│   ├── command_parser.py   # Expanded: NL parsing helpers
│   ├── ... (others)
└── tests/
    ├── ... (add listener/CLI tests)
```

## Updated Code Skeletons

### app.py (Listener Expansions)
```python
# ... existing imports ...

from slack_bolt import App, Say
from slack_bolt.adapter.socket_mode import SocketModeHandler
import threading  # For async processing

app = App(...)  # Existing

@app.command("/cli")
def cli_listener(ack, body, say: Say):
    ack()
    say("Command received, processing...")
    
    # Async process to avoid timeout
    def process_command():
        response = handle_cli_command(body["text"])
        if response["success"]:
            say(f"Success:\n```\n{response['output']}\n```")  # Verbose output
        else:
            say(f"Failure: {response['error']}. Log: {response['log']}")
    
    threading.Thread(target=process_command).start()

# ... other commands/main ...
```

### cli.py (New: Direct Gemini CLI Shell)
```python
import sys
import services.gemini_service as gemini
import services.shell_service as shell
import services.git_service as git
import utils.logger as logger

def main(input_text):
    try:
        generated_code = gemini.generate_command(input_text)
        exec_result = shell.execute(generated_code)
        project_dir = shell.get_project_dir_from_input(input_text)  # Assume parser
        git.commit_and_push(project_dir, f"CLI: {input_text}")
        print(f"Success: {exec_result}")  # Verbose to console
        return True
    except Exception as e:
        log_path = logger.log_error(str(e))
        print(f"Failure: {e}. Log: {log_path}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        input_text = " ".join(sys.argv[1:])
        main(input_text)
    else:
        print("Usage: python cli.py 'your command'")
```

### handlers/cli_handler.py (Expansions)
```python
# ... imports ...

def handle_cli_command(input_text):
    try:
        # Parse for specifics (e.g., dir, action)
        parsed = command_parser.parse(input_text)  # e.g., {'dir': 'xyz', 'action': 'change header'}
        
        # Gemini call
        generated_code = gemini.generate_command(input_text, context=parsed)
        
        # Execute with state (e.g., cwd)
        exec_result = shell.execute(generated_code, cwd=parsed.get('dir'))
        
        # Git
        git.commit_and_push(parsed['dir'], f"Changes from: {input_text}")
        
        # Verbose: Include diffs
        diffs = git.get_diffs(parsed['dir'])
        output = f"Exec: {exec_result}\nDiffs: {diffs}"
        
        logger.log_success(output)
        return {"success": True, "output": output}
    except Exception as e:
        # Rollback if critical
        # git.rollback(parsed['dir'])
        log_path = logger.log_error(str(e))
        return {"success": False, "error": str(e), "log": log_path}
```

### services/gemini_service.py (Expansions)
```python
# ... existing ...

def generate_command(input_text, context=None):
    prompt = f"Interpret as CLI command: {input_text}. Generate Python/bash code. Use context: {context}. Safe, limited to {CONFIG['PROJECT_ROOT_DIR']}. Output: ```language\ncode\n```"
    response = model.generate_content(prompt)
    code = extract_code(response.text)  # Parse block
    return code

def extract_code(text):
    # Logic to pull code from response (e.g., regex for ```)
    return text.split('```')[1] if '```' in text else text
```

### services/shell_service.py (Expansions)
```python
import subprocess
import os
from config import CONFIG

CURRENT_STATE = {}  # e.g., {'cwd': CONFIG['PROJECT_ROOT_DIR']}

def execute(code, cwd=None):
    cwd = cwd or CURRENT_STATE['cwd']
    if code.startswith('bash'):
        # Run as shell
        result = subprocess.run(code[4:], shell=True, cwd=cwd, capture_output=True, text=True)
        output = f"stdout: {result.stdout}\nstderr: {result.stderr}"
    else:
        # Python exec in sandbox
        safe_globals = {'__builtins__': {}}  # Restricted
        exec(code, safe_globals)
        output = "Executed Python code."  # Capture prints if needed
    CURRENT_STATE['cwd'] = cwd  # Update state
    return output

def get_project_dir_from_input(input_text):
    # Simple parse or use Gemini for extraction
    return CONFIG['PROJECT_ROOT_DIR'] + '/xyz'  # Example
```

### utils/command_parser.py (Expansions)
```python
def parse(input_text):
    # Basic NL parse; could use OpenAI/Gemini for better
    # e.g., regex or simple split
    parts = input_text.split()
    dir_index = parts.index('folder') if 'folder' in parts else None
    return {'dir': parts[dir_index + 1] if dir_index else None, 'action': ' '.join(parts)}
```

This expansion deepens the listener and CLI shell for robustness and usability. Test the direct `cli.py` locally, then integrate with Slack. For further tweaks (e.g., advanced parsing), provide examples!