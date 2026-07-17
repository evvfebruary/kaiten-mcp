"""Server factory and tool registration tests."""

from __future__ import annotations

import pytest
from pydantic import HttpUrl

from kaiten_mcp.config import Settings
from kaiten_mcp.server import create_server


@pytest.mark.asyncio
async def test_server_registers_expected_tools() -> None:
    server = create_server()
    tools = await server.list_tools()
    names = sorted(tool.name for tool in tools)
    expected = {
        "add_comment",
        "add_tag_to_task",
        "create_task",
        "get_task",
        "get_task_tags",
        "list_boards",
        "list_columns",
        "list_comments",
        "list_lanes",
        "list_spaces",
        "list_tags",
        "list_tasks",
        "move_task",
        "remove_tag_from_task",
        "update_task",
    }
    assert expected.issubset(set(names))
    # Keep schemas concise: tool descriptions should stay short.
    assert all(len(tool.description or "") < 200 for tool in tools)


def test_server_instructions_reflect_configured_origin() -> None:
    server = create_server()
    assert "test-tenant.kaiten.ru" in (server.instructions or "")


def test_server_instructions_use_custom_base_url() -> None:
    settings = Settings(base_url=HttpUrl("https://kaiten.example.com/api/v1"))
    server = create_server(settings)
    assert "kaiten.example.com" in (server.instructions or "")
    assert "booleanoptimization" not in (server.instructions or "")
