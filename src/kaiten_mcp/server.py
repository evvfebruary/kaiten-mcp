"""FastMCP application factory."""

from __future__ import annotations

import logging
from typing import Literal

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from kaiten_mcp import __version__
from kaiten_mcp.config import Settings, get_settings
from kaiten_mcp.logging_utils import configure_logging, get_logger, log_event
from kaiten_mcp.tools import register_all

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def _log_level(value: str) -> LogLevel:
    normalized = value.upper()
    allowed: dict[str, LogLevel] = {
        "DEBUG": "DEBUG",
        "INFO": "INFO",
        "WARNING": "WARNING",
        "ERROR": "ERROR",
        "CRITICAL": "CRITICAL",
    }
    return allowed.get(normalized, "INFO")


def create_server(settings: Settings | None = None) -> FastMCP:
    cfg = settings or get_settings()
    configure_logging(level=cfg.log_level, fmt=cfg.log_format)
    logger = get_logger("server")
    origin = cfg.company_origin.removeprefix("https://").removeprefix("http://")
    mcp = FastMCP(
        name="kaiten-mcp",
        instructions=(
            f"Kaiten task MCP for {origin}. "
            "Discover spaces/boards/columns/lanes first, then create/update/move tasks. "
            "Responses are compact by default; request descriptions explicitly."
        ),
        host=cfg.host,
        port=cfg.port,
        streamable_http_path="/mcp",
        stateless_http=True,
        log_level=_log_level(cfg.log_level),
    )
    register_all(mcp)
    log_event(
        logger,
        logging.INFO,
        "server_created",
        version=__version__,
        company_origin=cfg.company_origin,
        streamable_http_path="/mcp",
        healthz_path="/healthz",
    )

    @mcp.custom_route("/healthz", methods=["GET"])
    async def healthz(_request: Request) -> Response:
        return JSONResponse({"status": "ok", "version": __version__})

    return mcp


# Lazy module-level server for `mcp run` style launches.
# Avoids requiring instance env vars at import time (e.g. during test collection).
_mcp: FastMCP | None = None


def __getattr__(name: str) -> FastMCP:
    global _mcp
    if name == "mcp":
        if _mcp is None:
            _mcp = create_server()
        return _mcp
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
