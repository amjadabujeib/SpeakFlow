"""Load SpeakFlow's local runtime configuration consistently."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


BACKEND_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_ROOT.parent
ENV_PATH = PROJECT_ROOT / ".env"
LOCAL_MODEL_ROOT = BACKEND_ROOT / ".models"


def load_runtime_env() -> Path:
    """Load the project .env without overriding explicitly exported values."""
    load_dotenv(ENV_PATH, override=False)
    nltk_data = LOCAL_MODEL_ROOT / "nltk_data"
    if nltk_data.is_dir():
        existing = os.environ.get("NLTK_DATA")
        paths = [str(nltk_data)]
        if existing:
            paths.append(existing)
        os.environ["NLTK_DATA"] = os.pathsep.join(paths)
    return ENV_PATH
