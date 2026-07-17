"""Tool package registration helpers."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from kaiten_mcp.tools import cards, comments, structure, tags


def register_all(mcp: FastMCP) -> None:
    cards.register(mcp)
    comments.register(mcp)
    tags.register(mcp)
    structure.register(mcp)
