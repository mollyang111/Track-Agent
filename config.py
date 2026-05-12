import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "deepseek-r1:7b")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))
WATCH_FOLDER_ID = os.getenv("WATCH_FOLDER_ID") or None
WEBHOOK_URL = os.getenv("WEBHOOK_URL") or None
CUSTOM_SCRIPT = os.getenv("CUSTOM_SCRIPT") or None
LOG_FILE = os.getenv("LOG_FILE", "state/changes.log")

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "track_agent")
