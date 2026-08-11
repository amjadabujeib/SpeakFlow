"""Bounded operational probes for administrator reporting."""

import requests

from speakflow.features.learning_plan.engine.config import OLLAMA_BASE_URL


def ollama_status() -> str:
    try:
        response = requests.get(
            f"{OLLAMA_BASE_URL.rstrip('/')}/api/tags",
            timeout=2,
        )
        response.raise_for_status()
        return "healthy"
    except requests.RequestException:
        return "error"
