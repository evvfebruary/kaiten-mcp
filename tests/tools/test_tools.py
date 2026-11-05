"""MCP tool adapter tests with mocked Kaiten HTTP."""

from __future__ import annotations

import httpx
import pytest
import respx
from mcp.types import CallToolResult

from kaiten_mcp.auth import set_token_override
from kaiten_mcp.server import create_server


async def _call(tool_name: str, arguments: dict) -> dict:
    server = create_server()
    result = await server.call_tool(tool_name, arguments)
    assert isinstance(result, CallToolResult)
    if result.is_error:
        raise ValueError(str(result.content))
    assert result.structured_content is not None
    return result.structured_content


@pytest.mark.asyncio
@respx.mock
async def test_list_tasks_compact_default_page(api_token: str) -> None:
    del api_token
    cards = [
        {
            "id": i,
            "title": f"Task {i}",
            "description": "IGNORE ME",
            "board_id": 1,
            "column_id": 2,
            "board": {"id": 1, "title": "Dev"},
            "column": {"id": 2, "title": "Todo"},
            "tags": [{"id": 1, "name": "bug"}],
            "files": [{"id": 99, "url": "https://example/file"}],
        }
        for i in range(1, 21)
    ]
    respx.get("https://test-tenant.kaiten.ru/api/v1/cards").mock(
        return_value=httpx.Response(200, json=cards)
    )
    result = await _call("list_tasks", {"board_id": 1})
    assert result["count"] == 20
    assert result["has_more"] is True
    assert result["next_offset"] == 20
    assert "description" not in result["items"][0]
    assert "files" not in result["items"][0]
    assert result["items"][0]["url"].endswith("/1")


@pytest.mark.asyncio
@respx.mock
async def test_create_update_move_and_tags(api_token: str) -> None:
    del api_token
    respx.post("https://test-tenant.kaiten.ru/api/v1/cards").mock(
        return_value=httpx.Response(
            200,
            json={"id": 11, "title": "Created", "board_id": 2, "column_id": 3},
        )
    )
    respx.patch("https://test-tenant.kaiten.ru/api/v1/cards/11").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": 11,
                "title": "Updated",
                "board_id": 2,
                "column_id": 4,
                "description": "body",
            },
        )
    )
    respx.post("https://test-tenant.kaiten.ru/api/v1/cards/11/tags").mock(
        return_value=httpx.Response(200, json={"id": 8, "name": "mcp"})
    )
    respx.delete("https://test-tenant.kaiten.ru/api/v1/cards/11/tags/8").mock(
        return_value=httpx.Response(200, json={"id": 8})
    )

    created = await _call("create_task", {"title": "Created", "board_id": 2, "column_id": 3})
    assert created["id"] == 11
    assert "changed" in created
    assert "description" not in created

    updated = await _call("update_task", {"card_id": 11, "title": "Updated"})
    assert updated["changed"]["title"] == "Updated"

    archived = await _call("update_task", {"card_id": 11, "condition": 2})
    assert archived["changed"]["condition"] == 2

    with pytest.raises(Exception, match="condition must be"):
        await _call("update_task", {"card_id": 11, "condition": 9})

    moved = await _call("move_task", {"card_id": 11, "column_id": 4})
    assert moved["changed"]["column_id"] == 4

    tagged = await _call("add_tag_to_task", {"card_id": 11, "name": "mcp"})
    assert tagged["tag"]["name"] == "mcp"
    removed = await _call("remove_tag_from_task", {"card_id": 11, "tag_id": 8})
    assert removed["removed_tag_id"] == 8


@pytest.mark.asyncio
@respx.mock
async def test_get_task_description_flag_and_comments(api_token: str) -> None:
    del api_token
    respx.get("https://test-tenant.kaiten.ru/api/v1/cards/5").mock(
        return_value=httpx.Response(
            200,
            json={"id": 5, "title": "Detail", "description": "hello", "board_id": 1},
        )
    )
    respx.get("https://test-tenant.kaiten.ru/api/v1/cards/5/comments").mock(
        return_value=httpx.Response(
            200,
            json=[{"id": 1, "text": "c" * 5000, "card_id": 5}],
        )
    )
    respx.post("https://test-tenant.kaiten.ru/api/v1/cards/5/comments").mock(
        return_value=httpx.Response(200, json={"id": 2, "text": "note", "card_id": 5})
    )

    compact = await _call("get_task", {"card_id": 5})
    assert "description" not in compact
    detailed = await _call("get_task", {"card_id": 5, "include_description": True})
    assert detailed["description"] == "hello"

    comments = await _call("list_comments", {"card_id": 5})
    assert comments["items"][0]["truncated"] is True
    added = await _call("add_comment", {"card_id": 5, "text": "note"})
    assert added["text"] == "note"


@pytest.mark.asyncio
@respx.mock
async def test_discovery_tools(api_token: str) -> None:
    del api_token
    respx.get("https://test-tenant.kaiten.ru/api/v1/spaces").mock(
        return_value=httpx.Response(200, json=[{"id": 1, "title": "Main", "extra": "nope"}])
    )
    respx.get("https://test-tenant.kaiten.ru/api/v1/spaces/1/boards").mock(
        return_value=httpx.Response(200, json=[{"id": 2, "title": "Board", "space_id": 1}])
    )
    respx.get("https://test-tenant.kaiten.ru/api/v1/boards/2/columns").mock(
        return_value=httpx.Response(200, json=[{"id": 3, "title": "Todo", "type": 1}])
    )
    respx.get("https://test-tenant.kaiten.ru/api/v1/boards/2/lanes").mock(
        return_value=httpx.Response(200, json=[{"id": 4, "title": "Lane"}])
    )
    respx.get("https://test-tenant.kaiten.ru/api/v1/tags").mock(
        return_value=httpx.Response(200, json=[{"id": 9, "name": "bug"}])
    )

    spaces = await _call("list_spaces", {})
    assert set(spaces["items"][0]) == {"id", "title"}
    boards = await _call("list_boards", {"space_id": 1})
    assert boards["count"] == 1
    assert boards["space_id"] == 1
    columns = await _call("list_columns", {"board_id": 2})
    assert columns["items"][0]["type"] == 1
    assert columns["board_id"] == 2
    assert "parent_column_id" in columns["items"][0]
    lanes = await _call("list_lanes", {"board_id": 2})
    assert lanes["items"][0]["id"] == 4
    assert lanes["board_id"] == 2
    tags = await _call("list_tags", {})
    assert tags["items"][0]["name"] == "bug"


@pytest.mark.asyncio
async def test_tool_requires_token() -> None:
    with pytest.raises(Exception, match="Missing Kaiten API token"):
        await _call("list_spaces", {})


@pytest.mark.asyncio
@respx.mock
async def test_permission_error_is_concise(api_token: str) -> None:
    del api_token
    respx.get("https://test-tenant.kaiten.ru/api/v1/spaces").mock(
        return_value=httpx.Response(403, json={"message": "forbidden"})
    )
    with pytest.raises(Exception, match="denied"):
        await _call("list_spaces", {})


@pytest.mark.asyncio
@respx.mock
async def test_metrics_opt_in_does_not_embed_secrets(
    api_token: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_token_override(api_token)
    monkeypatch.setenv("KAITEN_ENABLE_METRICS", "true")
    from kaiten_mcp.config import get_settings

    get_settings.cache_clear()
    respx.get("https://test-tenant.kaiten.ru/api/v1/spaces").mock(
        return_value=httpx.Response(200, json=[{"id": 1, "title": "Main"}])
    )
    result = await _call("list_spaces", {})
    assert "_metrics" in result
    assert "test-kaiten-token" not in str(result["_metrics"])
    assert result["_metrics"]["tool"] == "list_spaces"
