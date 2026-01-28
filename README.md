# Slack-Integrated Gemini CLI Shell

This tool allows you to interact with your local development environment via Slack using natural language.

## Features
- **NL to Code**: Uses Gemini 1.5 Pro to translate English commands into Bash or Python.
- **Auto-Git**: Automatically commits changes to your repository after each command.
- **Verbose Logging**: Detailed execution logs stored in `logs/`.
- **Async Execution**: Handles long-running commands without timing out Slack.

## Setup Instructions

1. **Clone the Repository**
2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Configure Environment**:
   - Copy `.env.example` to `.env`.
   - Fill in your `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, `SLACK_APP_TOKEN` (for Socket Mode), and `GEMINI_API_KEY`.
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
In Slack, type:
`/cli open the project folder and update the README header to say 'Hello World'`

The bot will:
1. Confirm receipt.
2. Generate the code.
3. Execute it.
4. Commit the changes.
5. Reply with the verbose output.
