"""Card/task MCP tools."""

from __future__ import annotations

from typing import Any, cast

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError

from kaiten_mcp import api
from kaiten_mcp.presentation import (
    clamp_limit,
    detail_card,
    mutation_result,
    paginated,
    summarize_card,
)
from kaiten_mcp.tool_models import MutationResult, TaskPage, TaskResult
from kaiten_mcp.tools._common import with_client


def register(mcp: MCPServer) -> None:
    @mcp.tool(
        name="create_task", description="Create a Kaiten task/card. Requires title and board_id."
    )
    async def create_task(
        title: str,
        board_id: int,
        ctx: Context,
        column_id: int | None = None,
        lane_id: int | None = None,
        description: str | None = None,
        owner_id: int | None = None,
        responsible_id: int | None = None,
        due_date: str | None = None,
        type_id: int | None = None,
        external_id: str | None = None,
        position: int | None = None,
    ) -> MutationResult:
        payload: dict[str, Any] = {"title": title, "board_id": board_id}
        optional = {
            "column_id": column_id,
            "lane_id": lane_id,
            "description": description,
            "owner_id": owner_id,
            "responsible_id": responsible_id,
            "due_date": due_date,
            "type_id": type_id,
            "external_id": external_id,
            "position": position,
        }
        payload.update({key: value for key, value in optional.items() if value is not None})

        async def _run(client: api.KaitenClient, settings: Any) -> dict[str, Any]:
            card = await api.cards.create_card(client, payload)
            return mutation_result(card, changed={"created": True, **payload}, settings=settings)

        return cast(
            MutationResult,
            await with_client(
                ctx,
                "create_task",
                _run,
                arguments=payload,
                input_items=1,
            ),
        )

    @mcp.tool(
        name="get_task", description="Get one task. Set include_description=true for body text."
    )
    async def get_task(
        card_id: int,
        ctx: Context,
        include_description: bool = False,
    ) -> TaskResult:
        async def _run(client: api.KaitenClient, settings: Any) -> dict[str, Any]:
            card = await api.cards.get_card(
                client,
                card_id,
                include_description=include_description,
            )
            return detail_card(card, include_description=include_description, settings=settings)

        return cast(
            TaskResult,
            await with_client(
                ctx,
                "get_task",
                _run,
                arguments={"card_id": card_id, "include_description": include_description},
                input_items=1,
                truncated_fn=lambda result: bool(result.get("description_truncated")),
            ),
        )

    @mcp.tool(
        name="list_tasks",
        description="List tasks with filters. Default page 20 (max 100). Compact summaries only.",
    )
    async def list_tasks(
        ctx: Context,
        query: str | None = None,
        space_id: int | None = None,
        board_id: int | None = None,
        column_id: int | None = None,
        lane_id: int | None = None,
        owner_id: int | None = None,
        responsible_id: int | None = None,
        states: str | None = None,
        tag: str | None = None,
        external_id: str | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> TaskPage:
        async def _run(client: api.KaitenClient, settings: Any) -> dict[str, Any]:
            page_size = clamp_limit(limit, settings)
            filters = {
                "query": query,
                "space_id": space_id,
                "board_id": board_id,
                "column_id": column_id,
                "lane_id": lane_id,
                "owner_id": owner_id,
                "responsible_id": responsible_id,
                "states": states,
                "tag": tag,
                "external_id": external_id,
            }
            clean = {key: value for key, value in filters.items() if value is not None}
            cards = await api.cards.list_cards(
                client,
                filters=clean,
                offset=max(offset, 0),
                limit=page_size,
                include_description=False,
            )
            items = [summarize_card(card, settings=settings) for card in cards]
            return paginated(
                items,
                offset=max(offset, 0),
                limit=page_size,
                requested_limit=page_size,
            )

        return cast(
            TaskPage,
            await with_client(
                ctx,
                "list_tasks",
                _run,
                arguments={
                    "query": query,
                    "space_id": space_id,
                    "board_id": board_id,
                    "column_id": column_id,
                    "lane_id": lane_id,
                    "owner_id": owner_id,
                    "responsible_id": responsible_id,
                    "states": states,
                    "tag": tag,
                    "external_id": external_id,
                    "offset": offset,
                    "limit": limit,
                },
                output_items_fn=lambda result: int(result.get("count", 0)),
                truncated_fn=lambda result: any(
                    item.get("truncated") for item in result.get("items", [])
                ),
            ),
        )

    @mcp.tool(
        name="update_task",
        description=(
            "Update card fields via PATCH. "
            "condition: 1=live, 2=archived, 3=deleted. "
            "Workflow status (queued/in-progress/done) comes from the column — use move_task. "
            "Responsible is set only on create_task."
        ),
    )
    async def update_task(
        card_id: int,
        ctx: Context,
        title: str | None = None,
        description: str | None = None,
        owner_id: int | None = None,
        due_date: str | None = None,
        type_id: int | None = None,
        condition: int | None = None,
        external_id: str | None = None,
        properties: dict[str, Any] | None = None,
    ) -> MutationResult:
        if condition is not None and condition not in {1, 2, 3}:
            raise ToolError("condition must be 1 (live), 2 (archived), or 3 (deleted).")

        payload: dict[str, Any] = {
            "title": title,
            "description": description,
            "owner_id": owner_id,
            "due_date": due_date,
            "type_id": type_id,
            "condition": condition,
            "external_id": external_id,
            "properties": properties,
        }
        clean = {key: value for key, value in payload.items() if value is not None}
        if not clean:
            raise ToolError("update_task requires at least one field to change.")

        async def _run(client: api.KaitenClient, settings: Any) -> dict[str, Any]:
            card = await api.cards.update_card(client, card_id, clean)
            return mutation_result(card, changed=clean, settings=settings)

        return cast(
            MutationResult,
            await with_client(
                ctx,
                "update_task",
                _run,
                arguments={"card_id": card_id, **clean},
                input_items=1,
            ),
        )

    @mcp.tool(
        name="move_task",
        description="Move a task via Kaiten card PATCH (board/column/lane/sort/prev_card_id).",
    )
    async def move_task(
        card_id: int,
        ctx: Context,
        board_id: int | None = None,
        column_id: int | None = None,
        lane_id: int | None = None,
        sort_order: float | None = None,
        prev_card_id: int | None = None,
    ) -> MutationResult:
        if all(value is None for value in (board_id, column_id, lane_id, sort_order, prev_card_id)):
            raise ToolError("move_task requires at least one location field.")

        async def _run(client: api.KaitenClient, settings: Any) -> dict[str, Any]:
            card = await api.cards.move_card(
                client,
                card_id,
                board_id=board_id,
                column_id=column_id,
                lane_id=lane_id,
                sort_order=sort_order,
                prev_card_id=prev_card_id,
            )
            changed = {
                key: value
                for key, value in {
                    "board_id": board_id,
                    "column_id": column_id,
                    "lane_id": lane_id,
                    "sort_order": sort_order,
                    "prev_card_id": prev_card_id,
                }.items()
                if value is not None
            }
            return mutation_result(card, changed=changed, settings=settings)

        return cast(
            MutationResult,
            await with_client(
                ctx,
                "move_task",
                _run,
                arguments={
                    "card_id": card_id,
                    "board_id": board_id,
                    "column_id": column_id,
                    "lane_id": lane_id,
                    "sort_order": sort_order,
                    "prev_card_id": prev_card_id,
                },
                input_items=1,
            ),
        )
