"""Application composition for the SpeakFlow FastAPI service."""

from .factory import create_application, mount_versioned_aliases

__all__ = ["create_application", "mount_versioned_aliases"]
