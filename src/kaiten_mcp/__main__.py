"""CLI entrypoint for stdio and Streamable HTTP transports."""

from __future__ import annotations

import argparse
import logging
from typing import Literal

from kaiten_mcp.config import get_settings
from kaiten_mcp.logging_utils import configure_logging, get_logger, log_event
from kaiten_mcp.server import create_server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Kaiten MCP server")
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
        help="MCP transport (stdio for Cursor/Claude Code; streamable-http for remote).",
    )
    parser.add_argument("--host", default=None, help="Override KAITEN_HOST for HTTP mode.")
    parser.add_argument(
        "--port", type=int, default=None, help="Override KAITEN_PORT for HTTP mode."
    )
    parser.add_argument(
        "--log-format",
        choices=("text", "json"),
        default=None,
        help="Override KAITEN_LOG_FORMAT (text|json).",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    settings = get_settings()
    if args.host:
        settings.host = args.host
    if args.port:
        settings.port = args.port
    if args.log_format:
        settings.log_format = args.log_format

    configure_logging(level=settings.log_level, fmt=settings.log_format, force=True)
    logger = get_logger("startup")
    log_event(
        logger,
        logging.INFO,
        "server_starting",
        transport=args.transport,
        host=settings.host,
        port=settings.port,
        api_root=settings.api_root,
        log_level=settings.log_level,
        log_format=settings.log_format,
        log_bodies=settings.log_bodies,
        enable_metrics=settings.enable_metrics,
    )

    server = create_server(settings)
    transport: Literal["stdio", "streamable-http"] = args.transport
    if transport == "stdio":
        server.run(transport=transport)
    else:
        server.run(
            transport=transport,
            host=settings.host,
            port=settings.port,
            stateless_http=True,
            streamable_http_path="/mcp",
        )


if __name__ == "__main__":
    main()
