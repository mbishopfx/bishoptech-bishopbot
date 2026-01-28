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
}
