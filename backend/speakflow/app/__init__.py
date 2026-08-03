"""Application composition for the SpeakFlow FastAPI service."""

from .factory import create_application

__all__ = ["create_application"]
