"""Compact, token-efficient presentation of Kaiten data for MCP tools."""

from __future__ import annotations

from typing import Any

from kaiten_mcp.api.models import Card, Comment, Tag
from kaiten_mcp.config import Settings, get_settings


def truncate_text(value: str | None, limit: int) -> tuple[str | None, bool]:
    if value is None:
        return None, False
    if len(value) <= limit:
        return value, False
    return value[: max(limit - 1, 0)] + "…", True


def task_url(card_id: int, *, settings: Settings | None = None) -> str:
    cfg = settings or get_settings()
    return f"{cfg.company_origin}/{card_id}"


def _named(value: Any) -> str | None:
    if value is None:
        return None
    title = getattr(value, "title", None) or getattr(value, "name", None)
    if isinstance(title, str) and title.strip():
        return title
    return None


def summarize_card(card: Card, *, settings: Settings | None = None) -> dict[str, Any]:
    cfg = settings or get_settings()
    title, title_truncated = truncate_text(card.title, cfg.max_list_item_title_chars)
    tags = [{"id": tag.id, "name": tag.name} for tag in card.tags[:5]]
    payload: dict[str, Any] = {
        "id": card.id,
        "title": title,
        "board_id": card.board_id,
        "column_id": card.column_id,
        "lane_id": card.lane_id,
        "state": card.state,
        "condition": card.condition,
        "due_date": card.due_date,
        "owner_id": card.owner_id,
        "url": task_url(card.id, settings=cfg),
    }
    board_name = _named(card.board)
    column_name = _named(card.column)
    lane_name = _named(card.lane)
    if board_name:
        payload["board"] = board_name
    if column_name:
        payload["column"] = column_name
    if lane_name:
        payload["lane"] = lane_name
    if tags:
        payload["tags"] = tags
    if title_truncated:
        payload["truncated"] = True
    return {key: value for key, value in payload.items() if value is not None}


def detail_card(
    card: Card,
    *,
    include_description: bool = False,
    settings: Settings | None = None,
) -> dict[str, Any]:
    cfg = settings or get_settings()
    summary = summarize_card(card, settings=cfg)
    summary.update(
        {
            "type_id": card.type_id,
            "responsible_id": card.responsible_id,
            "external_id": card.external_id,
            "created": card.created,
            "updated": card.updated,
            "sort_order": card.sort_order,
            "properties": card.properties or {},
        }
    )
    if include_description:
        description, truncated = truncate_text(card.description, cfg.max_description_chars)
        summary["description"] = description
        if truncated:
            summary["description_truncated"] = True
            summary["description_chars"] = len(card.description or "")
    return {key: value for key, value in summary.items() if value is not None}


def mutation_result(
    card: Card,
    *,
    changed: dict[str, Any],
    settings: Settings | None = None,
) -> dict[str, Any]:
    cfg = settings or get_settings()
    return {
        "id": card.id,
        "title": card.title,
        "url": task_url(card.id, settings=cfg),
        "changed": changed,
        "location": {
            "board_id": card.board_id,
            "column_id": card.column_id,
            "lane_id": card.lane_id,
            "sort_order": card.sort_order,
        },
    }


def paginated(
    items: list[Any],
    *,
    offset: int,
    limit: int,
    requested_limit: int,
) -> dict[str, Any]:
    has_more = len(items) >= requested_limit
    next_offset = offset + len(items) if has_more else None
    return {
        "items": items,
        "count": len(items),
        "offset": offset,
        "limit": limit,
        "has_more": has_more,
        "next_offset": next_offset,
    }


def summarize_tag(tag: Tag) -> dict[str, Any]:
    return {"id": tag.id, "name": tag.name, "color": tag.color, "archived": tag.archived}


def summarize_comment(
    comment: Comment,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    cfg = settings or get_settings()
    text, truncated = truncate_text(comment.text, cfg.max_comment_chars)
    payload: dict[str, Any] = {
        "id": comment.id,
        "card_id": comment.card_id,
        "author_id": comment.author_id,
        "created": comment.created,
        "text": text,
    }
    if truncated:
        payload["truncated"] = True
        payload["text_chars"] = len(comment.text)
    return payload


def clamp_limit(limit: int | None, settings: Settings | None = None) -> int:
    cfg = settings or get_settings()
    if limit is None:
        return cfg.default_page_size
    return min(max(limit, 1), cfg.max_page_size)
