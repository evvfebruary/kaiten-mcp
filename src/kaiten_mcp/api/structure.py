"""Space/board/column/lane discovery adapters."""

from __future__ import annotations

from kaiten_mcp.api.client import KaitenClient
from kaiten_mcp.api.models import Board, Column, Lane, Space


async def list_spaces(client: KaitenClient) -> list[Space]:
    data = await client.get_all("/spaces")
    if data is None:
        return []
    if not isinstance(data, list):
        raise TypeError("Expected space list from Kaiten.")
    return [Space.model_validate(item) for item in data]


async def list_boards(client: KaitenClient, space_id: int) -> list[Board]:
    data = await client.get(f"/spaces/{space_id}/boards")
    if data is None:
        return []
    if not isinstance(data, list):
        raise TypeError("Expected board list from Kaiten.")
    return [Board.model_validate(item) for item in data]


async def list_columns(client: KaitenClient, board_id: int) -> list[Column]:
    data = await client.get(f"/boards/{board_id}/columns")
    if data is None:
        return []
    if not isinstance(data, list):
        raise TypeError("Expected column list from Kaiten.")
    return [Column.model_validate(item) for item in data]


async def list_lanes(client: KaitenClient, board_id: int) -> list[Lane]:
    data = await client.get(f"/boards/{board_id}/lanes")
    if data is None:
        return []
    if not isinstance(data, list):
        raise TypeError("Expected lane list from Kaiten.")
    return [Lane.model_validate(item) for item in data]
