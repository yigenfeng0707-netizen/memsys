import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

LLM_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai-next.com/v1").rstrip("/")
LLM_API_KEY = os.environ.get("OPENAI_API_KEY", "")
CHAT_MODEL = os.environ.get("CHAT_MODEL", "gpt-4o-mini")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "text-embedding-3-small")
EMBED_DIM = int(os.environ.get("EMBED_DIM", "1536"))

EMBED_BASE_URL = os.environ.get("EMBED_BASE_URL", LLM_BASE_URL).rstrip("/")
EMBED_API_KEY = os.environ.get("EMBED_API_KEY", LLM_API_KEY)

NO_THINKING = os.environ.get("MEMSYS_NO_THINKING", "").strip()
DISABLE_THINKING = NO_THINKING

DB_PATH = Path(os.environ.get("MEMSYS_DB", BASE_DIR / "data" / "memories.db"))
AUTH_TOKEN = os.environ.get("MEMSYS_AUTH_TOKEN", "").strip()
PORT = int(os.environ.get("MEMSYS_PORT", "8790"))

CHUNK_MAX_CHARS = 1500
VECTOR_CANDIDATES = 200
KEYWORD_CANDIDATES = 200
RRF_K = 60
RESULT_CAP = int(os.environ.get("MEMSYS_RESULT_CAP", "0"))
CHUNKS_ENABLED = os.environ.get("MEMSYS_CHUNKS", "1") == "1"
TRIM_CHUNK_LINES = int(os.environ.get("MEMSYS_TRIM_LINES", "0"))
DEBUG_LOG = os.environ.get("MEMSYS_DEBUG", "0") == "1"

EXTRACT_FACTS = os.environ.get("MEMSYS_EXTRACT_FACTS", "1") == "1"
DEDUP_THRESHOLD = float(os.environ.get("MEMSYS_DEDUP_SIM", "0.97"))
CONFLICT_LOW = float(os.environ.get("MEMSYS_CONFLICT_LOW", "0.55"))
CONFLICT_HIGH = float(os.environ.get("MEMSYS_CONFLICT_HIGH", "0.97"))
MAX_CONFLICT_JUDGES_PER_ADD = 12
MAX_FACTS_PER_ADD = 40
