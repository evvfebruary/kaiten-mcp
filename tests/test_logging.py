"""Logging helpers tests."""

from __future__ import annotations

import json
import logging

from kaiten_mcp.logging_utils import (
    StructuredFormatter,
    configure_logging,
    redact,
    summarize_payload,
    token_fingerprint,
)


def test_redact_secrets_and_bearer() -> None:
    payload = {
        "Authorization": "Bearer super-secret-token",
        "token": "abc",
        "title": "ok",
        "nested": {"access_token": "xyz", "id": 1},
    }
    redacted = redact(payload)
    assert redacted["Authorization"] == "[REDACTED]"
    assert redacted["token"] == "[REDACTED]"
    assert redacted["nested"]["access_token"] == "[REDACTED]"
    assert redacted["title"] == "ok"
    assert "Bearer [REDACTED]" in redact("Authorization: Bearer super-secret-token")


def test_summarize_payload_structure() -> None:
    summary = summarize_payload(
        {
            "items": [{"id": 1, "title": "A"}, {"id": 2, "title": "B"}],
            "count": 2,
            "has_more": False,
        }
    )
    assert summary["type"] == "object"
    assert summary["count"] == 2
    assert summary["items"]["item_count"] == 2
    assert summary["items"]["preview"][0]["id"] == 1


def test_json_formatter_emits_structured_data() -> None:
    configure_logging(level="INFO", fmt="json", force=True)
    record = logging.LogRecord(
        name="kaiten_mcp.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="tool_success",
        args=(),
        exc_info=None,
    )
    record.structured = {"tool": "list_spaces", "token": "len=4:…oken"}
    line = StructuredFormatter().format(record)
    payload = json.loads(line)
    assert payload["message"] == "tool_success"
    assert payload["data"]["tool"] == "list_spaces"
    assert token_fingerprint("abcd1234").endswith("1234")
