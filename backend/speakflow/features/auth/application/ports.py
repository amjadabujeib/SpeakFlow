from __future__ import annotations

from typing import Protocol

from speakflow.features.auth.domain import AuthenticatedUser, IssuedSession


class SignUpCommand(Protocol):
    email: str
    password: str
    display_name: str


class SignInCommand(Protocol):
    email: str
    password: str


class GuestSessionCommand(Protocol):
    display_name: str


class AuthenticationPort(Protocol):
    def sign_up(self, command: SignUpCommand) -> IssuedSession: ...

    def sign_in(self, command: SignInCommand) -> IssuedSession: ...

    def create_guest(self, command: GuestSessionCommand) -> IssuedSession: ...

    def authenticate(self, token: str) -> AuthenticatedUser: ...

    def sign_out(self, token: str) -> None: ...
