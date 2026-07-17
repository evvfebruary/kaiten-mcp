"""Safe Kaiten API error types and mapping."""

from __future__ import annotations

from typing import Any

import httpx


class KaitenError(Exception):
    """Base error for upstream Kaiten failures."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class KaitenAuthError(KaitenError):
    """Invalid or missing credentials."""


class KaitenPermissionError(KaitenError):
    """Authenticated but forbidden."""


class KaitenNotFoundError(KaitenError):
    """Requested resource was not found."""


class KaitenRateLimitError(KaitenError):
    """Upstream rate limit exceeded."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 429,
        retry_after: float | None = None,
        reset_at: float | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code)
        self.retry_after = retry_after
        self.reset_at = reset_at


class KaitenValidationError(KaitenError):
    """Upstream rejected the request payload."""


def _extract_message(payload: Any, fallback: str) -> str:
    if isinstance(payload, str) and payload.strip():
        return payload.strip()[:500]
    if isinstance(payload, dict):
        for key in ("message", "error", "detail", "title"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:500]
        errors = payload.get("errors")
        if isinstance(errors, list) and errors:
            first = errors[0]
            if isinstance(first, str):
                return first[:500]
            if isinstance(first, dict):
                return str(first)[:500]
    return fallback


def map_http_error(response: httpx.Response) -> KaitenError:
    """Translate Kaiten HTTP errors into concise MCP-safe exceptions."""
    status = response.status_code
    try:
        payload: Any = response.json()
    except ValueError:
        payload = response.text

    message = _extract_message(payload, fallback=f"Kaiten API error ({status})")

    if status in {401}:
        return KaitenAuthError("Invalid Kaiten API token.", status_code=status)
    if status in {402, 403}:
        return KaitenPermissionError(
            f"Kaiten denied this action ({status}): {message}",
            status_code=status,
        )
    if status == 404:
        return KaitenNotFoundError(f"Kaiten resource not found: {message}", status_code=status)
    if status == 429:
        retry_after_raw = response.headers.get("Retry-After")
        reset_raw = response.headers.get("X-RateLimit-Reset")
        retry_after: float | None = None
        reset_at: float | None = None
        if retry_after_raw:
            try:
                retry_after = float(retry_after_raw)
            except ValueError:
                retry_after = None
        if reset_raw:
            try:
                reset_at = float(reset_raw)
            except ValueError:
                reset_at = None
        return KaitenRateLimitError(
            "Kaiten rate limit exceeded. Retry shortly.",
            retry_after=retry_after,
            reset_at=reset_at,
        )
    if 400 <= status < 500:
        return KaitenValidationError(f"Invalid Kaiten request: {message}", status_code=status)
    return KaitenError(f"Kaiten server error ({status}): {message}", status_code=status)
