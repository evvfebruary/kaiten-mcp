"""Comment endpoint adapters."""

from __future__ import annotations

from typing import Any

from kaiten_mcp.api.client import KaitenClient
from kaiten_mcp.api.models import Comment


async def list_comments(client: KaitenClient, card_id: int) -> list[Comment]:
    data = await client.get(f"/cards/{card_id}/comments")
    if data is None:
        return []
    if not isinstance(data, list):
        raise TypeError("Expected comment list from Kaiten.")
    return [Comment.model_validate(item) for item in data if isinstance(item, dict)]


async def add_comment(client: KaitenClient, card_id: int, text: str) -> Comment:
    payload: dict[str, Any] = {"text": text}
    data = await client.post(f"/cards/{card_id}/comments", json=payload)
    if not isinstance(data, dict):
        raise TypeError("Expected comment object from Kaiten.")
    return Comment.model_validate(data)
