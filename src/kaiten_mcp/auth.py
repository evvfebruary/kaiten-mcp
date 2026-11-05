"""Request-scoped Kaiten credential resolution."""

from __future__ import annotations

import os
from contextvars import ContextVar
from typing import Any, Protocol


class _HasHeaders(Protocol):
    def get(self, key: str, default: str | None = None) -> str | None: ...


class _HasRequest(Protocol):
    @property
    def headers(self) -> _HasHeaders: ...


class _HasRequestContext(Protocol):
    @property
    def request(self) -> _HasRequest | None: ...


class AuthContext(Protocol):
    @property
    def request_context(self) -> _HasRequestContext: ...


_TOKEN_ENV = "KAITEN_API_TOKEN"
_token_override: ContextVar[str | None] = ContextVar("kaiten_token_override", default=None)


class AuthError(Exception):
    """Raised when no usable Kaiten API token is available."""


def set_token_override(token: str | None) -> None:
    """Set a request-scoped token override (used by tests and HTTP middleware)."""
    _token_override.set(token)


def clear_token_override() -> None:
    _token_override.set(None)


def _token_from_authorization_header(value: str | None) -> str | None:
    if not value:
        return None
    parts = value.strip().split(None, 1)
    if len(parts) != 2:
        return None
    scheme, token = parts
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _token_from_context(ctx: AuthContext | Any | None) -> str | None:
    if ctx is None:
        return None
    try:
        request = ctx.request_context.request
    except (AttributeError, LookupError, ValueError):
        return None
    if request is None:
        return None
    headers = getattr(request, "headers", None)
    if headers is None:
        return None
    auth_header = headers.get("authorization") or headers.get("Authorization")
    return _token_from_authorization_header(auth_header)


def resolve_token(ctx: AuthContext | Any | None = None) -> str:
    """Resolve the caller's Kaiten token without logging or persisting it.

    Order:
    1. Explicit request-scoped override
    2. HTTP Authorization: Bearer <token>
    3. KAITEN_API_TOKEN environment variable (stdio only; never for HTTP requests)
    """
    override = _token_override.get()
    if override:
        return override

    header_token = _token_from_context(ctx)
    if header_token:
        return header_token

    try:
        request = ctx.request_context.request if ctx is not None else None
    except (AttributeError, LookupError, ValueError):
        request = None
    if request is not None:
        raise AuthError("Missing Kaiten API token: HTTP requires Authorization: Bearer <token>.")

    env_token = os.environ.get(_TOKEN_ENV, "").strip()
    if env_token:
        return env_token

    raise AuthError(
        "Missing Kaiten API token. Set KAITEN_API_TOKEN for stdio, "
        "or send Authorization: Bearer <token> for Streamable HTTP."
    )
