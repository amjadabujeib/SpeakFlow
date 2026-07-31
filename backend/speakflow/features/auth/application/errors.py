class AuthInvalidCredentialsError(RuntimeError):
    pass


class AuthEmailConflictError(RuntimeError):
    pass


class AuthUnavailableError(RuntimeError):
    pass
