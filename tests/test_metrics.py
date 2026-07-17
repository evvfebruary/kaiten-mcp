"""Payload metrics helpers."""

from __future__ import annotations

from kaiten_mcp.metrics import estimate_tokens, measure_payload, record_tool_metrics


def test_estimate_and_measure_payload() -> None:
    payload = {"items": [{"id": 1, "title": "Task"}], "count": 1}
    output_bytes, output_chars, text = measure_payload(payload)
    assert output_bytes > 0
    assert output_chars == len(text)
    low, high = estimate_tokens(text)
    assert low <= high


def test_record_tool_metrics_without_body_logging() -> None:
    metrics = record_tool_metrics(
        enabled=False,
        tool="list_tasks",
        duration_ms=12.5,
        kaiten_requests=1,
        input_items=0,
        output_items=20,
        payload={"items": [{"id": i} for i in range(20)], "count": 20},
        truncated=False,
    )
    assert metrics.tool == "list_tasks"
    assert metrics.output_items == 20
    assert metrics.estimated_tokens_low <= metrics.estimated_tokens_high
