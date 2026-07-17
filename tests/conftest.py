"""Shared test fixtures."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from kaiten_mcp.auth import clear_token_override, set_token_override
from kaiten_mcp.config import Settings, get_settings

TEST_WORKSPACE_SLUG = "test-tenant"
TEST_API_ROOT = f"https://{TEST_WORKSPACE_SLUG}.kaiten.ru/api/v1"
TEST_COMPANY_ORIGIN = f"https://{TEST_WORKSPACE_SLUG}.kaiten.ru"


@pytest.fixture(autouse=True)
def _reset_settings_and_auth(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    get_settings.cache_clear()
    monkeypatch.setenv("KAITEN_WORKSPACE_SLUG", TEST_WORKSPACE_SLUG)
    monkeypatch.delenv("KAITEN_BASE_URL", raising=False)
    monkeypatch.setenv("KAITEN_ENABLE_METRICS", "false")
    monkeypatch.setenv("KAITEN_LOG_LEVEL", "WARNING")
    monkeypatch.setenv("KAITEN_LOG_FORMAT", "text")
    monkeypatch.setenv("KAITEN_LOG_BODIES", "false")
    monkeypatch.delenv("KAITEN_API_TOKEN", raising=False)
    clear_token_override()
    yield
    clear_token_override()
    get_settings.cache_clear()


@pytest.fixture
def settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()


@pytest.fixture
def api_token() -> str:
    token = "test-kaiten-token"
    set_token_override(token)
    return token
