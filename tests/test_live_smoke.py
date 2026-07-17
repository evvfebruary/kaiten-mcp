"""Opt-in live smoke test against the configured Kaiten tenant."""

from __future__ import annotations

import os

import pytest

from kaiten_mcp.api.client import KaitenClient
from kaiten_mcp.config import get_settings

pytestmark = pytest.mark.live


@pytest.mark.asyncio
async def test_live_list_spaces() -> None:
    token = os.environ.get("KAITEN_API_TOKEN", "").strip()
    if not token:
        pytest.skip("KAITEN_API_TOKEN is required for live tests")

    async with KaitenClient(token, settings=get_settings()) as client:
        spaces = await client.get("/spaces")
    assert isinstance(spaces, list)
