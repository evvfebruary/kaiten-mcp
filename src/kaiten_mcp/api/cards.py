"""Card/task endpoint adapters."""

from __future__ import annotations

from typing import Any

from kaiten_mcp.api.client import KaitenClient
from kaiten_mcp.api.models import Card


def _parse_card(payload: Any) -> Card:
    if not isinstance(payload, dict):
        raise TypeError("Expected card object from Kaiten.")
    return Card.model_validate(payload)


async def create_card(client: KaitenClient, payload: dict[str, Any]) -> Card:
    data = await client.post("/cards", json=payload)
    return _parse_card(data)


async def get_card(
    client: KaitenClient,
    card_id: int,
    *,
    include_description: bool = True,
) -> Card:
    params: dict[str, Any] = {}
    if include_description:
        params["additional_card_fields"] = "description"
    data = await client.get(f"/cards/{card_id}", params=params or None)
    return _parse_card(data)


async def list_cards(
    client: KaitenClient,
    *,
    filters: dict[str, Any] | None = None,
    offset: int = 0,
    limit: int = 20,
    include_description: bool = False,
) -> list[Card]:
    params = dict(filters or {})
    if include_description:
        params["additional_card_fields"] = "description"
    raw = await client.get_paginated("/cards", params=params, offset=offset, limit=limit)
    return [Card.model_validate(item) for item in raw]


async def update_card(client: KaitenClient, card_id: int, payload: dict[str, Any]) -> Card:
    data = await client.patch(f"/cards/{card_id}", json=payload)
    return _parse_card(data)


async def move_card(
    client: KaitenClient,
    card_id: int,
    *,
    board_id: int | None = None,
    column_id: int | None = None,
    lane_id: int | None = None,
    sort_order: float | None = None,
    prev_card_id: int | None = None,
) -> Card:
    payload: dict[str, Any] = {}
    if board_id is not None:
        payload["board_id"] = board_id
    if column_id is not None:
        payload["column_id"] = column_id
    if lane_id is not None:
        payload["lane_id"] = lane_id
    if sort_order is not None:
        payload["sort_order"] = sort_order
    if prev_card_id is not None:
        payload["prev_card_id"] = prev_card_id
    if not payload:
        raise ValueError("move_card requires at least one location field.")
    return await update_card(client, card_id, payload)
