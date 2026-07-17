"""Benchmark budget regression tests."""

from __future__ import annotations

from kaiten_mcp.benchmark import BASELINE_PATH, assert_within_budget, run_benchmark


def test_payload_budgets() -> None:
    import json

    report = run_benchmark()
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    assert_within_budget(report, baseline)
    assert report["compact_versus_raw"]["reduction_ratio"] >= baseline["min_reduction_ratio"]
