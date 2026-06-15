# Load .env once at import time so any module that imports `common.*` sees
# LLM_BACKEND, ANTHROPIC_API_KEY, etc. without needing to import dotenv itself.
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_REPO_ROOT / ".env", override=False)
