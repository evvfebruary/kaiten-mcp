"""Opt-in MCP payload metrics without logging secrets or bodies."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from typing import Any

logger = logging.getLogger("kaiten_mcp.metrics")


@dataclass(slots=True)
class ToolMetrics:
    tool: str
    duration_ms: float
    kaiten_requests: int
    input_items: int
    output_items: int
    output_bytes: int
    output_chars: int
    truncated: bool
    estimated_tokens_low: int
    estimated_tokens_high: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def estimate_tokens(text: str) -> tuple[int, int]:
    """Cross-model estimate range from characters (not provider-exact).

    Rough heuristic: ~4 chars/token (Latin) to ~2 chars/token denser text.
    """
    chars = max(len(text), 0)
    low = max(chars // 4, 0)
    high = max((chars + 1) // 2, low)
    return low, high


def measure_payload(payload: Any) -> tuple[int, int, str]:
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
    return len(text.encode("utf-8")), len(text), text


def record_tool_metrics(
    *,
    enabled: bool,
    tool: str,
    duration_ms: float,
    kaiten_requests: int,
    input_items: int,
    output_items: int,
    payload: Any,
    truncated: bool = False,
) -> ToolMetrics:
    output_bytes, output_chars, text = measure_payload(payload)
    low, high = estimate_tokens(text)
    metrics = ToolMetrics(
        tool=tool,
        duration_ms=round(duration_ms, 2),
        kaiten_requests=kaiten_requests,
        input_items=input_items,
        output_items=output_items,
        output_bytes=output_bytes,
        output_chars=output_chars,
        truncated=truncated,
        estimated_tokens_low=low,
        estimated_tokens_high=high,
    )
    if enabled:
        # Never include token/body content — metrics only.
        from kaiten_mcp.logging_utils import log_event

        log_event(logger, logging.INFO, "tool_metrics", **metrics.as_dict())
    return metrics
