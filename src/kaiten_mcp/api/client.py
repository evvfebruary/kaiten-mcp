"""Async Kaiten HTTP transport with retries and pagination."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import Mapping, Sequence
from typing import Any

import httpx

from kaiten_mcp.api.errors import KaitenError, KaitenRateLimitError, map_http_error
from kaiten_mcp.config import Settings, get_settings
from kaiten_mcp.logging_utils import log_event, summarize_payload, token_fingerprint

logger = logging.getLogger("kaiten_mcp.api.client")


class KaitenClient:
    """Thin async client for the tenant-scoped Kaiten REST API."""

    def __init__(
        self,
        token: str,
        *,
        settings: Settings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._token = token
        self._token_fp = token_fingerprint(token)
        self._request_count = 0
        self._client = httpx.AsyncClient(
            base_url=self._settings.api_root,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=self._settings.request_timeout_seconds,
            transport=transport,
        )

    @property
    def request_count(self) -> int:
        return self._request_count

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> KaitenClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Mapping[str, Any] | Sequence[Any] | None = None,
    ) -> Any:
        query = dict(params or {})
        # New integrations should send broken_api=false for stable integer IDs.
        query.setdefault("broken_api", "false")

        attempt = 0
        while True:
            self._request_count += 1
            started = time.perf_counter()
            try:
                response = await self._client.request(method, path, params=query, json=json)
            except httpx.TransportError as exc:
                duration_ms = (time.perf_counter() - started) * 1000
                log_event(
                    logger,
                    logging.WARNING,
                    "kaiten_transport_error",
                    method=method,
                    path=path,
                    attempt=attempt,
                    duration_ms=round(duration_ms, 2),
                    token_fp=self._token_fp,
                    error=str(exc),
                )
                if attempt >= self._settings.max_retries:
                    raise KaitenError(f"Kaiten transport error: {exc}") from exc
                await asyncio.sleep(self._backoff_seconds(attempt))
                attempt += 1
                continue

            duration_ms = (time.perf_counter() - started) * 1000
            if response.status_code == 429 and attempt < self._settings.max_retries:
                error = map_http_error(response)
                delay = self._rate_limit_delay(
                    error if isinstance(error, KaitenRateLimitError) else None
                )
                log_event(
                    logger,
                    logging.WARNING,
                    "kaiten_rate_limited",
                    method=method,
                    path=path,
                    status_code=response.status_code,
                    attempt=attempt,
                    retry_in_seconds=round(delay, 3),
                    duration_ms=round(duration_ms, 2),
                    token_fp=self._token_fp,
                )
                await asyncio.sleep(delay)
                attempt += 1
                continue

            if response.status_code >= 500 and attempt < self._settings.max_retries:
                log_event(
                    logger,
                    logging.WARNING,
                    "kaiten_server_error_retry",
                    method=method,
                    path=path,
                    status_code=response.status_code,
                    attempt=attempt,
                    duration_ms=round(duration_ms, 2),
                    token_fp=self._token_fp,
                )
                await asyncio.sleep(self._backoff_seconds(attempt))
                attempt += 1
                continue

            if response.status_code >= 400:
                log_event(
                    logger,
                    logging.ERROR,
                    "kaiten_request_failed",
                    method=method,
                    path=path,
                    status_code=response.status_code,
                    attempt=attempt,
                    duration_ms=round(duration_ms, 2),
                    token_fp=self._token_fp,
                    params=_safe_params(query),
                )
                raise map_http_error(response)

            payload: Any
            if response.status_code == 204 or not response.content:
                payload = None
            else:
                payload = response.json()

            event: dict[str, Any] = {
                "method": method,
                "path": path,
                "status_code": response.status_code,
                "attempt": attempt,
                "duration_ms": round(duration_ms, 2),
                "token_fp": self._token_fp,
                "params": _safe_params(query),
                "response": summarize_payload(payload),
                "response_bytes": len(response.content or b""),
            }
            if self._settings.log_bodies and json is not None:
                event["request_body"] = summarize_payload(json)
            log_event(logger, logging.INFO, "kaiten_request", **event)
            return payload

    async def get(self, path: str, *, params: Mapping[str, Any] | None = None) -> Any:
        return await self.request("GET", path, params=params)

    async def post(
        self,
        path: str,
        *,
        json: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> Any:
        return await self.request("POST", path, params=params, json=json)

    async def patch(
        self,
        path: str,
        *,
        json: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> Any:
        return await self.request("PATCH", path, params=params, json=json)

    async def delete(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> Any:
        return await self.request("DELETE", path, params=params)

    async def get_paginated(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> list[Any]:
        query = dict(params or {})
        query["offset"] = max(offset, 0)
        query["limit"] = min(max(limit, 1), self._settings.max_page_size)
        payload = await self.get(path, params=query)
        if payload is None:
            return []
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("data", "result", "items", "cards"):
                value = payload.get(key)
                if isinstance(value, list):
                    return value
        raise KaitenError("Unexpected paginated response shape from Kaiten.")

    def _backoff_seconds(self, attempt: int) -> float:
        base = min(2**attempt, 8)
        return base + random.uniform(0, 0.25)

    def _rate_limit_delay(self, error: KaitenRateLimitError | None) -> float:
        if error and error.retry_after is not None:
            return max(error.retry_after, 0.25)
        if error and error.reset_at is not None:
            return max(error.reset_at - time.time(), 0.25)
        return self._backoff_seconds(1)


def _safe_params(params: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): value for key, value in params.items() if str(key).lower() != "authorization"}
