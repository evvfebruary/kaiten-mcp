"""Kaiten HTTP client tests."""

from __future__ import annotations

import httpx
import pytest
import respx

from kaiten_mcp.api.client import KaitenClient
from kaiten_mcp.api.errors import (
    KaitenAuthError,
    KaitenNotFoundError,
    KaitenPermissionError,
    KaitenRateLimitError,
    KaitenValidationError,
)
from kaiten_mcp.config import get_settings


@pytest.mark.asyncio
@respx.mock
async def test_client_sends_broken_api_false_and_bearer() -> None:
    route = respx.get("https://test-tenant.kaiten.ru/api/v1/spaces").mock(
        return_value=httpx.Response(200, json=[{"id": 1, "title": "Space"}])
    )
    async with KaitenClient("secret-token", settings=get_settings()) as client:
        data = await client.get("/spaces")
    assert data == [{"id": 1, "title": "Space"}]
    assert route.called
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer secret-token"
    assert "broken_api=false" in str(request.url)


@pytest.mark.asyncio
@respx.mock
async def test_client_maps_status_codes() -> None:
    cases = [
        (401, KaitenAuthError),
        (402, KaitenPermissionError),
        (403, KaitenPermissionError),
        (404, KaitenNotFoundError),
        (400, KaitenValidationError),
    ]
    for status, exc_type in cases:
        respx.get("https://test-tenant.kaiten.ru/api/v1/cards/1").mock(
            return_value=httpx.Response(status, json={"message": "nope"})
        )
        async with KaitenClient("token", settings=get_settings()) as client:
            with pytest.raises(exc_type):
                await client.get("/cards/1")


@pytest.mark.asyncio
@respx.mock
async def test_client_retries_429_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _no_sleep(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr("kaiten_mcp.api.client.asyncio.sleep", _no_sleep)
    route = respx.get("https://test-tenant.kaiten.ru/api/v1/tags").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "0"}, json={"message": "slow down"}),
            httpx.Response(200, json=[{"id": 9, "name": "bug"}]),
        ]
    )
    async with KaitenClient("token", settings=get_settings()) as client:
        data = await client.get("/tags")
    assert data == [{"id": 9, "name": "bug"}]
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_client_raises_after_exhausted_429(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    settings.max_retries = 1

    async def _no_sleep(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr("kaiten_mcp.api.client.asyncio.sleep", _no_sleep)
    respx.get("https://test-tenant.kaiten.ru/api/v1/tags").mock(
        return_value=httpx.Response(429, json={"message": "slow down"})
    )
    async with KaitenClient("token", settings=settings) as client:
        with pytest.raises(KaitenRateLimitError):
            await client.get("/tags")


@pytest.mark.asyncio
@respx.mock
async def test_get_paginated_clamps_limit() -> None:
    route = respx.get("https://test-tenant.kaiten.ru/api/v1/cards").mock(
        return_value=httpx.Response(200, json=[{"id": 1, "title": "A"}])
    )
    async with KaitenClient("token", settings=get_settings()) as client:
        items = await client.get_paginated("/cards", offset=0, limit=500)
    assert len(items) == 1
    assert "limit=100" in str(route.calls.last.request.url)


@pytest.mark.asyncio
@respx.mock
async def test_tokens_are_isolated_per_client() -> None:
    route = respx.get("https://test-tenant.kaiten.ru/api/v1/spaces").mock(
        return_value=httpx.Response(200, json=[])
    )
    async with KaitenClient("user-a", settings=get_settings()) as client_a:
        await client_a.get("/spaces")
    async with KaitenClient("user-b", settings=get_settings()) as client_b:
        await client_b.get("/spaces")
    assert route.calls[0].request.headers["Authorization"] == "Bearer user-a"
    assert route.calls[1].request.headers["Authorization"] == "Bearer user-b"
