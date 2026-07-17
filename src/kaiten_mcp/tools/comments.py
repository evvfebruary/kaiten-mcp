"""Comment MCP tools."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from kaiten_mcp import api
from kaiten_mcp.presentation import summarize_comment
from kaiten_mcp.tools._common import with_client


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="add_comment",
        description="Add a comment to a task. Max useful body is truncated for context.",
    )
    async def add_comment(card_id: int, text: str, ctx: Context) -> dict[str, Any]:
        if not text.strip():
            raise ValueError("Comment text must not be empty.")

        async def _run(client: api.KaitenClient, settings: Any) -> dict[str, Any]:
            comment = await api.comments.add_comment(client, card_id, text)
            return summarize_comment(comment, settings=settings)

        return await with_client(
            ctx,
            "add_comment",
            _run,
            arguments={"card_id": card_id, "text_chars": len(text)},
            input_items=1,
            truncated_fn=lambda result: bool(result.get("truncated")),
        )

    @mcp.tool(
        name="list_comments", description="List comments for a task with compact truncated bodies."
    )
    async def list_comments(card_id: int, ctx: Context) -> dict[str, Any]:
        async def _run(client: api.KaitenClient, settings: Any) -> dict[str, Any]:
            comments = await api.comments.list_comments(client, card_id)
            items = [summarize_comment(comment, settings=settings) for comment in comments]
            return {
                "card_id": card_id,
                "items": items,
                "count": len(items),
            }

        return await with_client(
            ctx,
            "list_comments",
            _run,
            arguments={"card_id": card_id},
            input_items=1,
            output_items_fn=lambda result: int(result.get("count", 0)),
            truncated_fn=lambda result: any(
                item.get("truncated") for item in result.get("items", [])
            ),
        )
