# Slack-Integrated Gemini CLI Shell

This tool allows you to interact with your local development environment via Slack using natural language.

## Features
- **NL to Code**: Uses Gemini 1.5 Pro to translate English commands into Bash or Python.
- **Auto-Git**: Automatically commits changes to your repository after each command.
- **Verbose Logging**: Detailed execution logs stored in `logs/`.
- **Async Execution**: Handles long-running commands without timing out Slack.
- **YOLO automation**: Gemini launches with `--yolo` and executes the generated plan atomically so you can build, test, and push without manual prompts.
- **Task planning**: Each slash command produces a numbered task list that is posted back to Slack before execution; the CLI runs each step sequentially and reports progress.
- **Dual agents**: `/cli` uses the default Gemini-focused workflow, while `/codex` calls the same infrastructure but with Codex-style guidance for situations where you prefer a different reasoning voice.

## Setup Instructions

1. **Clone the Repository**
2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Configure Environment**:
   - Copy `.env.example` to `.env`.
   - Fill in your `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, `SLACK_APP_TOKEN` (for Socket Mode), and `GEMINI_API_KEY`.
   - (Optional) Set `GEMINI_CLI_ARGS` if you need to pass extra flags to the Gemini CLI; it defaults to `--yolo`.
4. **Run the App**:
   ```bash
   python app.py
   ```
5. **Slack Configuration**:
   - Create a Slack App at `api.slack.com`.
   - Enable **Socket Mode**.
   - Under **Slash Commands**, create `/cli`.
   - Install the app to your workspace.

## Usage
In Slack, run either `/cli` or `/codex` followed by a request (Codex mode uses a softer reasoning tone but still runs Gemini under the hood):

```
/cli open the project folder, run the tests, bump the version, and push the tag
/codex scaffold a new Next.js API route that returns the current timestamp and document it
```

The bot now:
1. Refines your request with GPT-4o.
2. Builds a numbered task list, posts it back to Slack, and starts Gemini with your preferred agent mode.
3. Gemini (running with `--yolo`) executes each task sequentially, runs `git status`, commits, and pushes any changes.
4. You receive periodic updates every 40 seconds plus a session summary when the work completes.
