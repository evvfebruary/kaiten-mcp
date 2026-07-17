"""Shared helpers for MCP tool adapters."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, cast

from mcp.server.fastmcp import Context

from kaiten_mcp.api.client import KaitenClient
from kaiten_mcp.api.errors import KaitenError
from kaiten_mcp.auth import AuthError, resolve_token
from kaiten_mcp.config import Settings, get_settings
from kaiten_mcp.logging_utils import log_event, summarize_payload, token_fingerprint
from kaiten_mcp.metrics import record_tool_metrics

logger = logging.getLogger("kaiten_mcp.tools")


async def with_client[T](
    ctx: Context | None,
    tool_name: str,
    operation: Callable[[KaitenClient, Settings], Awaitable[T]],
    *,
    arguments: Mapping[str, Any] | None = None,
    input_items: int = 0,
    output_items_fn: Callable[[T], int] | None = None,
    truncated_fn: Callable[[T], bool] | None = None,
) -> T:
    settings = get_settings()
    try:
        token = resolve_token(ctx)
    except AuthError as exc:
        log_event(logger, logging.ERROR, "tool_auth_missing", tool=tool_name)
        raise ValueError(str(exc)) from exc

    started = time.perf_counter()
    log_event(
        logger,
        logging.INFO,
        "tool_start",
        tool=tool_name,
        token_fp=token_fingerprint(token),
        arguments=dict(arguments or {}),
    )
    async with KaitenClient(token, settings=settings) as client:
        try:
            result = await operation(client, settings)
        except KaitenError as exc:
            duration_ms = (time.perf_counter() - started) * 1000
            log_event(
                logger,
                logging.ERROR,
                "tool_error",
                tool=tool_name,
                token_fp=token_fingerprint(token),
                duration_ms=round(duration_ms, 2),
                kaiten_requests=client.request_count,
                error=str(exc),
                status_code=exc.status_code,
            )
            raise ValueError(str(exc)) from exc
        except Exception as exc:
            duration_ms = (time.perf_counter() - started) * 1000
            log_event(
                logger,
                logging.ERROR,
                "tool_error",
                tool=tool_name,
                token_fp=token_fingerprint(token),
                duration_ms=round(duration_ms, 2),
                kaiten_requests=client.request_count,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise

    duration_ms = (time.perf_counter() - started) * 1000
    output_items = output_items_fn(result) if output_items_fn else 1
    truncated = truncated_fn(result) if truncated_fn else False
    metrics = record_tool_metrics(
        enabled=settings.enable_metrics,
        tool=tool_name,
        duration_ms=duration_ms,
        kaiten_requests=client.request_count,
        input_items=input_items,
        output_items=output_items,
        payload=result,
        truncated=truncated,
    )
    result_summary = summarize_payload(result)
    log_payload: dict[str, Any] = {
        "tool": tool_name,
        "token_fp": token_fingerprint(token),
        "duration_ms": round(duration_ms, 2),
        "kaiten_requests": client.request_count,
        "output_items": output_items,
        "truncated": truncated,
        "result": result_summary,
        "metrics": metrics.as_dict(),
    }
    if settings.log_bodies and isinstance(result, Mapping):
        from kaiten_mcp.logging_utils import redact

        result_payload = dict(cast(Mapping[str, Any], result))
        result_payload.pop("_metrics", None)
        log_payload["result_preview"] = redact(result_payload)
    log_event(logger, logging.INFO, "tool_success", **log_payload)

    if settings.enable_metrics and isinstance(result, Mapping):
        enriched = dict(cast(Mapping[str, Any], result))
        enriched["_metrics"] = metrics.as_dict()
        return cast(T, enriched)
    return result
