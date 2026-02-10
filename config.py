import os
from dotenv import load_dotenv

load_dotenv()

CONFIG = {
    "SLACK_BOT_TOKEN": os.getenv("SLACK_BOT_TOKEN"),
    "SLACK_APP_TOKEN": os.getenv("SLACK_APP_TOKEN"),
    "SLACK_SIGNING_SECRET": os.getenv("SLACK_SIGNING_SECRET"),
    "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY"),
    "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
    "FIRECRAWL_API_KEY": os.getenv("FIRECRAWL_API_KEY"),
    "PRIMARY_LLM": os.getenv("PRIMARY_LLM", "gemini"),
    "SECONDARY_LLM": os.getenv("SECONDARY_LLM", "openai"),
    "PROJECT_ROOT_DIR": os.getenv("PROJECT_ROOT_DIR", os.getcwd()),
    "REDIS_URL": os.getenv("REDIS_URL"),
    "TASK_QUEUE_NAME": os.getenv("TASK_QUEUE_NAME", "bishopbot_tasks"),
    "GITHUB_TOKEN": os.getenv("GITHUB_TOKEN"),
    "SLACK_NOTIFICATIONS_CHANNEL": os.getenv("SLACK_NOTIFICATIONS_CHANNEL"),
    "GEMINI_CLI_ARGS": os.getenv("GEMINI_CLI_ARGS", "--yolo"),
    "GOOGLE_CLIENT_SECRETS_PATH": os.getenv("GOOGLE_CLIENT_SECRETS_PATH", "client_secrets.json"),

    # Terminal session tuning
    "TERMINAL_BOOT_DELAY_SECONDS": os.getenv("TERMINAL_BOOT_DELAY_SECONDS", "7"),
    "TERMINAL_POLL_INTERVAL_SECONDS": os.getenv("TERMINAL_POLL_INTERVAL_SECONDS", "40"),
    "TERMINAL_TAIL_LINES_SLACK": os.getenv("TERMINAL_TAIL_LINES_SLACK", "15"),
    "TERMINAL_TAIL_LINES_WHATSAPP": os.getenv("TERMINAL_TAIL_LINES_WHATSAPP", "40"),

    # WhatsApp Cloud API (Meta)
    "WHATSAPP_ENABLED": os.getenv("WHATSAPP_ENABLED", "false"),
    "WHATSAPP_DEBUG": os.getenv("WHATSAPP_DEBUG", "false"),
    "WHATSAPP_VERIFY_TOKEN": os.getenv("WHATSAPP_VERIFY_TOKEN"),
    "WHATSAPP_ACCESS_TOKEN": os.getenv("WHATSAPP_ACCESS_TOKEN"),
    "WHATSAPP_PHONE_NUMBER_ID": os.getenv("WHATSAPP_PHONE_NUMBER_ID"),
    # Optional: webhook signature verification (X-Hub-Signature-256)
    "WHATSAPP_APP_SECRET": os.getenv("WHATSAPP_APP_SECRET"),
}
