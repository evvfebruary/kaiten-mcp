"""Discovery MCP tools for spaces, boards, columns, and lanes."""

from __future__ import annotations

from typing import Any, cast

from mcp.server import MCPServer
from mcp.server.mcpserver import Context

from kaiten_mcp import api
from kaiten_mcp.tool_models import NamedList
from kaiten_mcp.tools._common import with_client


def register(mcp: MCPServer) -> None:
    @mcp.tool(
        name="list_spaces", description="List spaces (id, title) for discovering board targets."
    )
    async def list_spaces(ctx: Context) -> NamedList:
        async def _run(client: api.KaitenClient, settings: Any) -> dict[str, Any]:
            del settings
            spaces = await api.structure.list_spaces(client)
            items = [{"id": space.id, "title": space.title} for space in spaces]
            return {"items": items, "count": len(items)}

        return cast(
            NamedList,
            await with_client(
                ctx,
                "list_spaces",
                _run,
                arguments={},
                output_items_fn=lambda result: int(result.get("count", 0)),
            ),
        )

    @mcp.tool(name="list_boards", description="List boards in a space (id, title, space_id).")
    async def list_boards(space_id: int, ctx: Context) -> NamedList:
        async def _run(client: api.KaitenClient, settings: Any) -> dict[str, Any]:
            del settings
            boards = await api.structure.list_boards(client, space_id)
            items = [
                {"id": board.id, "title": board.title, "space_id": board.space_id or space_id}
                for board in boards
            ]
            return {"space_id": space_id, "items": items, "count": len(items)}

        return cast(
            NamedList,
            await with_client(
                ctx,
                "list_boards",
                _run,
                arguments={"space_id": space_id},
                input_items=1,
                output_items_fn=lambda result: int(result.get("count", 0)),
            ),
        )

    @mcp.tool(name="list_columns", description="List columns on a board (id, title, type, order).")
    async def list_columns(board_id: int, ctx: Context) -> NamedList:
        async def _run(client: api.KaitenClient, settings: Any) -> dict[str, Any]:
            del settings
            columns = await api.structure.list_columns(client, board_id)
            items = [
                {
                    "id": column.id,
                    "title": column.title,
                    "board_id": column.board_id or board_id,
                    "type": column.type,
                    "sort_order": column.sort_order,
                    "parent_column_id": column.column_id,
                }
                for column in columns
            ]
            return {"board_id": board_id, "items": items, "count": len(items)}

        return cast(
            NamedList,
            await with_client(
                ctx,
                "list_columns",
                _run,
                arguments={"board_id": board_id},
                input_items=1,
                output_items_fn=lambda result: int(result.get("count", 0)),
            ),
        )

    @mcp.tool(name="list_lanes", description="List lanes on a board (id, title, order).")
    async def list_lanes(board_id: int, ctx: Context) -> NamedList:
        async def _run(client: api.KaitenClient, settings: Any) -> dict[str, Any]:
            del settings
            lanes = await api.structure.list_lanes(client, board_id)
            items = [
                {
                    "id": lane.id,
                    "title": lane.title,
                    "board_id": lane.board_id or board_id,
                    "sort_order": lane.sort_order,
                    "condition": lane.condition,
                }
                for lane in lanes
            ]
            return {"board_id": board_id, "items": items, "count": len(items)}

        return cast(
            NamedList,
            await with_client(
                ctx,
                "list_lanes",
                _run,
                arguments={"board_id": board_id},
                input_items=1,
                output_items_fn=lambda result: int(result.get("count", 0)),
            ),
        )
