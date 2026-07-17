"""Endpoint adapter tests."""

from __future__ import annotations

import httpx
import pytest
import respx

from kaiten_mcp.api import cards, comments, structure, tags
from kaiten_mcp.api.client import KaitenClient
from kaiten_mcp.config import get_settings


@pytest.mark.asyncio
@respx.mock
async def test_create_and_move_card() -> None:
    respx.post("https://test-tenant.kaiten.ru/api/v1/cards").mock(
        return_value=httpx.Response(
            200,
            json={"id": 10, "title": "New", "board_id": 2, "column_id": 3},
        )
    )
    respx.patch("https://test-tenant.kaiten.ru/api/v1/cards/10").mock(
        return_value=httpx.Response(
            200,
            json={"id": 10, "title": "New", "board_id": 2, "column_id": 4, "lane_id": 5},
        )
    )
    async with KaitenClient("token", settings=get_settings()) as client:
        created = await cards.create_card(client, {"title": "New", "board_id": 2})
        moved = await cards.move_card(client, 10, column_id=4, lane_id=5)
    assert created.id == 10
    assert moved.column_id == 4
    assert moved.lane_id == 5


@pytest.mark.asyncio
@respx.mock
async def test_list_cards_ignores_extra_nested_fields() -> None:
    respx.get("https://test-tenant.kaiten.ru/api/v1/cards").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": 1,
                    "title": "Task",
                    "board_id": 2,
                    "unknown_field": {"huge": "blob"},
                    "attacments": [{"id": 99}],
                    "tags": [{"id": 7, "name": "bug"}],
                }
            ],
        )
    )
    async with KaitenClient("token", settings=get_settings()) as client:
        result = await cards.list_cards(client, limit=20)
    assert result[0].id == 1
    assert result[0].tags[0].name == "bug"


@pytest.mark.asyncio
@respx.mock
async def test_tag_attach_by_name_remove_by_id() -> None:
    post = respx.post("https://test-tenant.kaiten.ru/api/v1/cards/1/tags").mock(
        return_value=httpx.Response(200, json={"id": 3, "name": "urgent"})
    )
    delete = respx.delete("https://test-tenant.kaiten.ru/api/v1/cards/1/tags/3").mock(
        return_value=httpx.Response(200, json={"id": 3})
    )
    async with KaitenClient("token", settings=get_settings()) as client:
        attached = await tags.add_tag_to_card(client, 1, "urgent")
        removed = await tags.remove_tag_from_card(client, 1, 3)
    assert attached.name == "urgent"
    assert removed["id"] == 3
    assert post.calls.last.request.content == b'{"name":"urgent"}'
    assert delete.called


@pytest.mark.asyncio
@respx.mock
async def test_comments_and_structure() -> None:
    respx.get("https://test-tenant.kaiten.ru/api/v1/cards/1/comments").mock(
        return_value=httpx.Response(200, json=[{"id": 1, "text": "hi", "card_id": 1}])
    )
    respx.post("https://test-tenant.kaiten.ru/api/v1/cards/1/comments").mock(
        return_value=httpx.Response(200, json={"id": 2, "text": "new", "card_id": 1})
    )
    respx.get("https://test-tenant.kaiten.ru/api/v1/spaces").mock(
        return_value=httpx.Response(200, json=[{"id": 1, "title": "Main"}])
    )
    respx.get("https://test-tenant.kaiten.ru/api/v1/spaces/1/boards").mock(
        return_value=httpx.Response(200, json=[{"id": 2, "title": "Dev", "space_id": 1}])
    )
    respx.get("https://test-tenant.kaiten.ru/api/v1/boards/2/columns").mock(
        return_value=httpx.Response(200, json=[{"id": 3, "title": "Todo", "type": 1}])
    )
    respx.get("https://test-tenant.kaiten.ru/api/v1/boards/2/lanes").mock(
        return_value=httpx.Response(200, json=[{"id": 4, "title": "Default"}])
    )
    async with KaitenClient("token", settings=get_settings()) as client:
        listed = await comments.list_comments(client, 1)
        added = await comments.add_comment(client, 1, "new")
        spaces = await structure.list_spaces(client)
        boards = await structure.list_boards(client, 1)
        columns = await structure.list_columns(client, 2)
        lanes = await structure.list_lanes(client, 2)
    assert listed[0].text == "hi"
    assert added.id == 2
    assert spaces[0].title == "Main"
    assert boards[0].id == 2
    assert columns[0].type == 1
    assert lanes[0].id == 4
