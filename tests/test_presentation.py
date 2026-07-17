"""Presentation compaction tests."""

from __future__ import annotations

import pytest
from pydantic import HttpUrl

from kaiten_mcp.api.models import Card, Comment
from kaiten_mcp.config import Settings, get_settings
from kaiten_mcp.presentation import (
    clamp_limit,
    detail_card,
    mutation_result,
    paginated,
    summarize_card,
    summarize_comment,
    task_url,
)


def test_summarize_card_omits_description_and_nested_bloat() -> None:
    card = Card(
        id=42,
        title="x" * 300,
        description="should not appear in summary",
        board_id=1,
        column_id=2,
        tags=[],
    )
    summary = summarize_card(card, settings=get_settings())
    assert "description" not in summary
    assert summary["url"] == "https://test-tenant.kaiten.ru/42"
    assert summary.get("truncated") is True
    assert len(summary["title"]) <= get_settings().max_list_item_title_chars


def test_task_url_respects_custom_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KAITEN_WORKSPACE_SLUG", raising=False)
    settings = Settings(base_url=HttpUrl("https://other-slug.kaiten.ru/api/v1"))
    assert task_url(99, settings=settings) == "https://other-slug.kaiten.ru/99"


def test_detail_card_description_opt_in_and_truncation() -> None:
    settings = get_settings()
    card = Card(id=1, title="T", description="d" * (settings.max_description_chars + 50))
    without = detail_card(card, include_description=False, settings=settings)
    with_desc = detail_card(card, include_description=True, settings=settings)
    assert "description" not in without
    assert with_desc["description_truncated"] is True
    assert len(with_desc["description"]) <= settings.max_description_chars


def test_paginated_defaults_and_mutation_compact() -> None:
    assert clamp_limit(None) == 20
    assert clamp_limit(500) == 100
    page = paginated([{"id": 1}] * 20, offset=0, limit=20, requested_limit=20)
    assert page["has_more"] is True
    assert page["next_offset"] == 20
    card = Card(id=5, title="Moved", board_id=1, column_id=2)
    result = mutation_result(card, changed={"column_id": 2})
    assert set(result) == {"id", "title", "url", "changed", "location"}


def test_comment_truncation() -> None:
    settings = get_settings()
    comment = Comment(id=1, text="c" * (settings.max_comment_chars + 10), card_id=9)
    payload = summarize_comment(comment, settings=settings)
    assert payload["truncated"] is True
    assert len(payload["text"]) <= settings.max_comment_chars
