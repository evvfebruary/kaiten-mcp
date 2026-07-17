"""Auth resolution tests."""

from __future__ import annotations

import pytest

from kaiten_mcp.auth import AuthError, clear_token_override, resolve_token, set_token_override


def test_resolve_token_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KAITEN_API_TOKEN", "env-token")
    assert resolve_token() == "env-token"


def test_resolve_token_override_beats_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KAITEN_API_TOKEN", "env-token")
    set_token_override("override-token")
    assert resolve_token() == "override-token"
    clear_token_override()


def test_missing_token_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KAITEN_API_TOKEN", raising=False)
    clear_token_override()
    with pytest.raises(AuthError, match="Missing Kaiten API token"):
        resolve_token()


def test_authorization_header_parser(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KAITEN_API_TOKEN", raising=False)
    clear_token_override()

    class _Headers:
        def __init__(self, data: dict[str, str]) -> None:
            self._data = {key.lower(): value for key, value in data.items()}

        def get(self, key: str, default: str | None = None) -> str | None:
            return self._data.get(key.lower(), default)

    class _Request:
        headers = _Headers({"Authorization": "Bearer header-token"})

    class _RequestContext:
        request = _Request()

    class _Ctx:
        request_context = _RequestContext()

    assert resolve_token(_Ctx()) == "header-token"
