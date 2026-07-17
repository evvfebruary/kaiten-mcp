"""Structured logging setup with secret redaction and payload summaries."""

from __future__ import annotations

import json
import logging
import re
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

SECRET_KEYS = frozenset(
    {
        "authorization",
        "token",
        "api_token",
        "apitoken",
        "access_token",
        "refresh_token",
        "password",
        "secret",
        "bearer",
        "kaiten_api_token",
    }
)
_BEARER_RE = re.compile(r"(Bearer\s+)(\S+)", re.IGNORECASE)
_CONFIGURED = False


class StructuredFormatter(logging.Formatter):
    """Emit one JSON object per log line for easy grep/jq inspection."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extras = getattr(record, "structured", None)
        if isinstance(extras, dict):
            payload["data"] = extras
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str, separators=(",", ":"))


class TextStructuredFormatter(logging.Formatter):
    """Human-readable logs with a trailing JSON data block when present."""

    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extras = getattr(record, "structured", None)
        if isinstance(extras, dict) and extras:
            encoded = json.dumps(extras, ensure_ascii=False, default=str, separators=(",", ":"))
            return f"{base} | {encoded}"
        return base


def configure_logging(
    *,
    level: str = "INFO",
    fmt: str = "text",
    force: bool = False,
) -> None:
    """Configure root kaiten_mcp logging to stderr (stdio-safe)."""
    global _CONFIGURED
    if _CONFIGURED and not force:
        return

    normalized = level.upper()
    log_level = getattr(logging, normalized, logging.INFO)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        StructuredFormatter() if fmt.lower() == "json" else TextStructuredFormatter()
    )

    root = logging.getLogger("kaiten_mcp")
    root.handlers.clear()
    root.setLevel(log_level)
    root.addHandler(handler)
    root.propagate = False

    # Keep noisy HTTP client logs quieter unless DEBUG.
    logging.getLogger("httpx").setLevel(logging.WARNING if log_level > logging.DEBUG else log_level)
    logging.getLogger("httpcore").setLevel(
        logging.WARNING if log_level > logging.DEBUG else log_level
    )
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    if not name.startswith("kaiten_mcp"):
        name = f"kaiten_mcp.{name}"
    return logging.getLogger(name)


def log_event(
    logger: logging.Logger,
    level: int,
    message: str,
    **data: Any,
) -> None:
    """Log a message with structured fields under record.structured."""
    logger.log(level, message, extra={"structured": redact(data)})


def redact(value: Any, *, depth: int = 0) -> Any:
    """Recursively redact secrets and truncate oversized strings."""
    if depth > 6:
        return "…"
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            key_str = str(key)
            if key_str.lower().replace("-", "_") in SECRET_KEYS:
                out[key_str] = "[REDACTED]"
            else:
                out[key_str] = redact(item, depth=depth + 1)
        return out
    if isinstance(value, list):
        if len(value) > 20:
            return [redact(item, depth=depth + 1) for item in value[:20]] + [
                f"…(+{len(value) - 20} more)"
            ]
        return [redact(item, depth=depth + 1) for item in value]
    if isinstance(value, tuple):
        return [redact(item, depth=depth + 1) for item in value]
    if isinstance(value, str):
        redacted = _BEARER_RE.sub(r"\1[REDACTED]", value)
        if len(redacted) > 500:
            return redacted[:497] + "…"
        return redacted
    return value


def summarize_payload(value: Any, *, max_items: int = 5) -> dict[str, Any]:
    """Describe response/result structure without dumping full bodies."""
    if value is None:
        return {"type": "null"}
    if isinstance(value, Mapping):
        keys = sorted(str(key) for key in value)
        summary: dict[str, Any] = {
            "type": "object",
            "keys": keys[:30],
            "key_count": len(keys),
        }
        if "count" in value:
            summary["count"] = value.get("count")
        if "has_more" in value:
            summary["has_more"] = value.get("has_more")
        if "next_offset" in value:
            summary["next_offset"] = value.get("next_offset")
        if "id" in value:
            summary["id"] = value.get("id")
        items = value.get("items")
        if isinstance(items, list):
            summary["items"] = _summarize_sequence(items, max_items=max_items)
        return summary
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return {
            "type": "array",
            **_summarize_sequence(list(value), max_items=max_items),
        }
    if isinstance(value, str):
        return {"type": "string", "chars": len(value)}
    if isinstance(value, (int, float, bool)):
        return {"type": type(value).__name__, "value": value}
    return {"type": type(value).__name__}


def _summarize_sequence(items: list[Any], *, max_items: int) -> dict[str, Any]:
    preview: list[Any] = []
    for item in items[:max_items]:
        if isinstance(item, Mapping):
            preview.append(
                {
                    key: item.get(key)
                    for key in ("id", "title", "name", "board_id", "column_id", "state", "url")
                    if key in item
                }
            )
        else:
            preview.append(redact(item))
    return {
        "item_count": len(items),
        "preview": preview,
    }


def token_fingerprint(token: str) -> str:
    """Non-reversible short marker so multi-user logs can be correlated."""
    if not token:
        return "missing"
    suffix = token[-4:] if len(token) >= 4 else "****"
    return f"len={len(token)}:…{suffix}"
