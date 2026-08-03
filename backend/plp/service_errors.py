"""Learning-plan service errors and operational policy constants."""

JOB_LEASE_SECONDS = 120
JOB_HEARTBEAT_SECONDS = 30
FAILURE_ENVELOPE_PREFIX = "__plp_failure_v1__:"
DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS = 90
PRONUNCIATION_PASS_ACCURACY = 85
PRONUNCIATION_PASS_COMPLETENESS = 90


class PlpUnavailableError(RuntimeError):
    pass


class PlpNotFoundError(RuntimeError):
    pass


class PlpConflictError(RuntimeError):
    pass


class PlpInvalidAttemptError(RuntimeError):
    pass
