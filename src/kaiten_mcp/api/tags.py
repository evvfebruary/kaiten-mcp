"""Tag endpoint adapters."""

from __future__ import annotations

from typing import Any

from kaiten_mcp.api.client import KaitenClient
from kaiten_mcp.api.models import Tag


async def list_tags(
    client: KaitenClient,
    *,
    query: str | None = None,
    space_id: int | None = None,
    offset: int = 0,
    limit: int = 20,
) -> list[Tag]:
    params: dict[str, Any] = {}
    if query:
        params["query"] = query
    if space_id is not None:
        params["space_id"] = space_id
    raw = await client.get_paginated("/tags", params=params, offset=offset, limit=limit)
    return [Tag.model_validate(item) for item in raw if isinstance(item, dict)]


async def get_card_tags(client: KaitenClient, card_id: int) -> list[Tag]:
    data = await client.get(f"/cards/{card_id}/tags")
    if data is None:
        return []
    if not isinstance(data, list):
        raise TypeError("Expected tag list from Kaiten.")
    return [Tag.model_validate(item) for item in data if isinstance(item, dict)]


async def add_tag_to_card(client: KaitenClient, card_id: int, name: str) -> Tag:
    # Kaiten attaches tags by name, not by existing tag_id.
    data = await client.post(f"/cards/{card_id}/tags", json={"name": name})
    if not isinstance(data, dict):
        raise TypeError("Expected tag object from Kaiten.")
    return Tag.model_validate(data)


async def remove_tag_from_card(client: KaitenClient, card_id: int, tag_id: int) -> dict[str, Any]:
    data = await client.delete(f"/cards/{card_id}/tags/{tag_id}")
    if isinstance(data, dict):
        return data
    return {"id": tag_id}
