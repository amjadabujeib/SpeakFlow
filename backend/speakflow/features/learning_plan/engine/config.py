from __future__ import annotations

import os
from pathlib import Path

from speakflow.config import PROJECT_ROOT, load_runtime_env
from speakflow.shared.groq_keys import configured_groq_api_keys

load_runtime_env()

DATA_ROOT = Path(os.environ.get("PLP_DATA_ROOT", ".local_data")).expanduser()
if not DATA_ROOT.is_absolute():
    DATA_ROOT = PROJECT_ROOT / DATA_ROOT
RAG_ROOT = DATA_ROOT / "rag"

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://english_tutor:english_tutor@127.0.0.1:5432/english_tutor",
)
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_EMBED_TIMEOUT_SECONDS = float(
    os.environ.get("OLLAMA_EMBED_TIMEOUT_SECONDS", "120")
)
GROQ_API_KEYS = configured_groq_api_keys()
GROQ_PLP_MODEL = os.environ.get("GROQ_PLP_MODEL", "openai/gpt-oss-120b")
OLLAMA_EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "embeddinggemma:latest")

SUPPORTED_LEVELS = ("A1", "A2", "B1", "B2")
LOCAL_GUEST_ID = "00000000-0000-0000-0000-000000000001"
EMBEDDING_DIMENSIONS = 768
