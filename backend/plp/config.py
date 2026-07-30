from __future__ import annotations

import os
from pathlib import Path

from runtime_env import PROJECT_ROOT, load_runtime_env


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
OLLAMA_PLP_MODEL = os.environ.get("OLLAMA_PLP_MODEL", "llama3.1:latest")
OLLAMA_PLP_NUM_CTX = int(os.environ.get("OLLAMA_PLP_NUM_CTX", "12288"))
OLLAMA_PLP_TIMEOUT_SECONDS = float(
    os.environ.get("OLLAMA_PLP_TIMEOUT_SECONDS", "900")
)
PLP_GENERATOR_PROVIDER = os.environ.get(
    "PLP_GENERATOR_PROVIDER", "groq"
).lower()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_PLP_MODEL = os.environ.get("GROQ_PLP_MODEL", "openai/gpt-oss-120b")
OLLAMA_EMBED_MODEL = os.environ.get(
    "OLLAMA_EMBED_MODEL", "embeddinggemma:latest"
)

SUPPORTED_LEVELS = ("A1", "A2", "B1", "B2")
LOCAL_GUEST_ID = "00000000-0000-0000-0000-000000000001"
GENERATOR_VERSION = "plp-v3-weekly-mission-2026-07-26"
CURATED_GENERATOR_VERSION = "plp-v2-curated-2026-07-17"
LEGACY_LLM_GENERATOR_VERSION = "plp-v2-lesson-writer-2026-07-17"
PLANNER_VERSION = "planner-v4-prerequisite-graph-2026-07-21"
WEEKLY_PROMPT_VERSION = "weekly-surface-v13-fixed-id-buckets-2026-07-26"
WEEKLY_SCHEMA_VERSION = "weekly-surface-schema-v7-fixed-id-buckets"
WEEKLY_COMPILER_VERSION = "weekly-compiler-v14-micro-listening-length-2026-07-26"
EMBEDDING_DIMENSIONS = 768
