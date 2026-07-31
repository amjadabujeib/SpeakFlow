"""Backward-compatible imports for the migrated authentication feature."""

from speakflow.features.auth.application.errors import (
    AuthEmailConflictError,
    AuthInvalidCredentialsError,
    AuthUnavailableError,
)
from speakflow.features.auth.infrastructure.service import (
    AuthService,
    auth_service,
)

__all__ = [
    "AuthEmailConflictError",
    "AuthInvalidCredentialsError",
    "AuthService",
    "AuthUnavailableError",
    "auth_service",
]
