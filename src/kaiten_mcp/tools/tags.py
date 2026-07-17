"""Tag MCP tools."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from kaiten_mcp import api
from kaiten_mcp.presentation import clamp_limit, paginated, summarize_tag
from kaiten_mcp.tools._common import with_client


def register(mcp: FastMCP) -> None:
    @mcp.tool(name="list_tags", description="List company/space tags (paginated, compact).")
    async def list_tags(
        ctx: Context,
        query: str | None = None,
        space_id: int | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> dict[str, Any]:
        async def _run(client: api.KaitenClient, settings: Any) -> dict[str, Any]:
            page_size = clamp_limit(limit, settings)
            tags = await api.tags.list_tags(
                client,
                query=query,
                space_id=space_id,
                offset=max(offset, 0),
                limit=page_size,
            )
            items = [summarize_tag(tag) for tag in tags]
            return paginated(
                items,
                offset=max(offset, 0),
                limit=page_size,
                requested_limit=page_size,
            )

        return await with_client(
            ctx,
            "list_tags",
            _run,
            arguments={
                "query": query,
                "space_id": space_id,
                "offset": offset,
                "limit": limit,
            },
            output_items_fn=lambda result: int(result.get("count", 0)),
        )

    @mcp.tool(name="get_task_tags", description="List tags attached to a task.")
    async def get_task_tags(card_id: int, ctx: Context) -> dict[str, Any]:
        async def _run(client: api.KaitenClient, settings: Any) -> dict[str, Any]:
            del settings
            tags = await api.tags.get_card_tags(client, card_id)
            items = [summarize_tag(tag) for tag in tags]
            return {"card_id": card_id, "items": items, "count": len(items)}

        return await with_client(
            ctx,
            "get_task_tags",
            _run,
            arguments={"card_id": card_id},
            input_items=1,
            output_items_fn=lambda result: int(result.get("count", 0)),
        )

    @mcp.tool(
        name="add_tag_to_task",
        description="Attach a tag by name (Kaiten API uses name, not tag_id, for attach).",
    )
    async def add_tag_to_task(card_id: int, name: str, ctx: Context) -> dict[str, Any]:
        if not name.strip():
            raise ValueError("Tag name must not be empty.")

        async def _run(client: api.KaitenClient, settings: Any) -> dict[str, Any]:
            del settings
            tag = await api.tags.add_tag_to_card(client, card_id, name.strip())
            return {"card_id": card_id, "tag": summarize_tag(tag)}

        return await with_client(
            ctx,
            "add_tag_to_task",
            _run,
            arguments={"card_id": card_id, "name": name},
            input_items=1,
        )

    @mcp.tool(
        name="remove_tag_from_task",
        description="Remove a tag from a task by tag_id (Kaiten delete uses tag_id).",
    )
    async def remove_tag_from_task(card_id: int, tag_id: int, ctx: Context) -> dict[str, Any]:
        async def _run(client: api.KaitenClient, settings: Any) -> dict[str, Any]:
            del settings
            result = await api.tags.remove_tag_from_card(client, card_id, tag_id)
            return {"card_id": card_id, "removed_tag_id": result.get("id", tag_id)}

        return await with_client(
            ctx,
            "remove_tag_from_task",
            _run,
            arguments={"card_id": card_id, "tag_id": tag_id},
            input_items=1,
        )
