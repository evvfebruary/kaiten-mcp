"""Settings and instance-configuration tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kaiten_mcp.config import Settings, get_settings


def test_workspace_slug_derives_api_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KAITEN_BASE_URL", raising=False)
    monkeypatch.setenv("KAITEN_WORKSPACE_SLUG", "Acme-Corp")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.workspace_slug == "acme-corp"
    assert settings.api_root == "https://acme-corp.kaiten.ru/api/v1"
    assert settings.company_origin == "https://acme-corp.kaiten.ru"


@pytest.mark.parametrize(
    ("slug", "expected_origin"),
    [
        ("acme", "https://acme.kaiten.ru"),
        ("my-team", "https://my-team.kaiten.ru"),
        ("a1", "https://a1.kaiten.ru"),
        ("tenant2024", "https://tenant2024.kaiten.ru"),
    ],
)
def test_valid_workspace_slugs(
    monkeypatch: pytest.MonkeyPatch,
    slug: str,
    expected_origin: str,
) -> None:
    monkeypatch.delenv("KAITEN_BASE_URL", raising=False)
    monkeypatch.setenv("KAITEN_WORKSPACE_SLUG", slug)
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.company_origin == expected_origin
    assert settings.api_root == f"{expected_origin}/api/v1"


@pytest.mark.parametrize(
    "slug",
    [
        "-bad",
        "bad-",
        "Bad_Underscore",
        "has.dot",
        "has space",
        "x" * 64,
    ],
)
def test_invalid_workspace_slugs_rejected(
    monkeypatch: pytest.MonkeyPatch,
    slug: str,
) -> None:
    monkeypatch.delenv("KAITEN_BASE_URL", raising=False)
    monkeypatch.setenv("KAITEN_WORKSPACE_SLUG", slug)
    get_settings.cache_clear()
    with pytest.raises(ValidationError, match="DNS-safe"):
        Settings()


def test_missing_instance_config_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KAITEN_WORKSPACE_SLUG", raising=False)
    monkeypatch.delenv("KAITEN_BASE_URL", raising=False)
    get_settings.cache_clear()
    with pytest.raises(ValidationError, match="KAITEN_WORKSPACE_SLUG"):
        Settings()


def test_blank_workspace_slug_treated_as_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KAITEN_WORKSPACE_SLUG", "   ")
    monkeypatch.delenv("KAITEN_BASE_URL", raising=False)
    get_settings.cache_clear()
    with pytest.raises(ValidationError, match="KAITEN_WORKSPACE_SLUG"):
        Settings()


def test_custom_base_url_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KAITEN_WORKSPACE_SLUG", raising=False)
    monkeypatch.setenv("KAITEN_BASE_URL", "https://kaiten.example.com/api/v1/")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.api_root == "https://kaiten.example.com/api/v1"
    assert settings.company_origin == "https://kaiten.example.com"


def test_base_url_takes_precedence_over_slug(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KAITEN_WORKSPACE_SLUG", "ignored-slug")
    monkeypatch.setenv("KAITEN_BASE_URL", "https://kaiten.internal.example/api/v1")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.workspace_slug == "ignored-slug"
    assert settings.api_root == "https://kaiten.internal.example/api/v1"
    assert settings.company_origin == "https://kaiten.internal.example"


def test_company_origin_strips_api_latest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KAITEN_WORKSPACE_SLUG", raising=False)
    monkeypatch.setenv("KAITEN_BASE_URL", "https://slug.kaiten.ru/api/latest")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.api_root == "https://slug.kaiten.ru/api/latest"
    assert settings.company_origin == "https://slug.kaiten.ru"


def test_company_origin_without_api_marker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KAITEN_WORKSPACE_SLUG", raising=False)
    monkeypatch.setenv("KAITEN_BASE_URL", "https://kaiten.example.com/v1")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.company_origin == "https://kaiten.example.com/v1"
