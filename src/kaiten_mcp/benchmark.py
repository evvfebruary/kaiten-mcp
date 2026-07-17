"""Benchmark helpers and CLI for MCP payload budgets."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from pydantic import HttpUrl

from kaiten_mcp.api.models import Card, Comment, Tag
from kaiten_mcp.config import Settings
from kaiten_mcp.metrics import estimate_tokens, measure_payload
from kaiten_mcp.presentation import (
    detail_card,
    mutation_result,
    paginated,
    summarize_card,
    summarize_comment,
    summarize_tag,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "benchmarks" / "fixtures"
BASELINE_PATH = ROOT / "benchmarks" / "baseline.json"

# Deterministic settings so benchmarks do not require a live workspace env.
_BENCHMARK_SETTINGS = Settings(base_url=HttpUrl("https://benchmark.kaiten.ru/api/v1"))


def _load_raw_cards() -> list[dict[str, Any]]:
    raw = json.loads((FIXTURES / "cards_raw.json").read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise TypeError("cards_raw.json must contain a list")
    return [item for item in raw if isinstance(item, dict)]


def _load_cards() -> list[Card]:
    return [Card.model_validate(item) for item in _load_raw_cards()]


def _workflow_payloads() -> dict[str, Any]:
    raw_cards = _load_raw_cards()
    cards = [Card.model_validate(item) for item in raw_cards]
    settings = _BENCHMARK_SETTINGS
    list_items = [summarize_card(card, settings=settings) for card in cards[:20]]
    list_payload = paginated(list_items, offset=0, limit=20, requested_limit=20)
    detail = detail_card(cards[0], include_description=True, settings=settings)
    detail_compact = detail_card(cards[0], include_description=False, settings=settings)
    moved = mutation_result(cards[0], changed={"column_id": 4}, settings=settings)
    comments = [
        summarize_comment(
            Comment(id=1, text="Looks good", card_id=cards[0].id),
            settings=settings,
        ),
        summarize_comment(
            Comment(id=2, text="c" * 2500, card_id=cards[0].id),
            settings=settings,
        ),
    ]
    tags = [summarize_tag(Tag(id=1, name="bug")), summarize_tag(Tag(id=2, name="mcp"))]
    discovery = {
        "spaces": {"items": [{"id": 1, "title": "Main"}], "count": 1},
        "boards": {"items": [{"id": 2, "title": "Dev", "space_id": 1}], "count": 1},
        "columns": {"items": [{"id": 3, "title": "Todo", "type": 1}], "count": 1},
        "lanes": {"items": [{"id": 4, "title": "Default"}], "count": 1},
    }
    return {
        "list_tasks": list_payload,
        "get_task": detail_compact,
        "get_task_with_description": detail,
        "move_task": moved,
        "list_comments": {"card_id": cards[0].id, "items": comments, "count": len(comments)},
        "list_tags": {"items": tags, "count": len(tags)},
        "discovery": discovery,
        # Compare against full upstream-shaped fixtures, not model-stripped dumps.
        "raw_cards_sample": raw_cards[:20],
    }


def _measure(name: str, payload: Any) -> dict[str, Any]:
    started = time.perf_counter()
    output_bytes, output_chars, text = measure_payload(payload)
    low, high = estimate_tokens(text)
    duration_ms = (time.perf_counter() - started) * 1000
    return {
        "tool": name,
        "output_bytes": output_bytes,
        "output_chars": output_chars,
        "estimated_tokens_low": low,
        "estimated_tokens_high": high,
        "duration_ms": round(duration_ms, 3),
    }


def run_benchmark() -> dict[str, Any]:
    payloads = _workflow_payloads()
    per_tool = {
        name: _measure(name, payload)
        for name, payload in payloads.items()
        if name != "raw_cards_sample"
    }
    raw = _measure("raw_cards_sample", payloads["raw_cards_sample"])
    compact = per_tool["list_tasks"]
    reduction = {
        "raw_bytes": raw["output_bytes"],
        "compact_bytes": compact["output_bytes"],
        "bytes_saved": raw["output_bytes"] - compact["output_bytes"],
        "reduction_ratio": round(1 - (compact["output_bytes"] / max(raw["output_bytes"], 1)), 4),
    }
    workflow = {
        "tools": ["discovery", "list_tasks", "get_task", "move_task", "list_comments", "list_tags"],
        "output_bytes": sum(
            per_tool[name]["output_bytes"]
            for name in (
                "discovery",
                "list_tasks",
                "get_task",
                "move_task",
                "list_comments",
                "list_tags",
            )
        ),
        "estimated_tokens_high": sum(
            per_tool[name]["estimated_tokens_high"]
            for name in (
                "discovery",
                "list_tasks",
                "get_task",
                "move_task",
                "list_comments",
                "list_tags",
            )
        ),
    }
    return {
        "per_tool": per_tool,
        "workflow": workflow,
        "compact_versus_raw": reduction,
    }


def assert_within_budget(report: dict[str, Any], baseline: dict[str, Any]) -> None:
    budgets = baseline["budgets"]
    for tool, metrics in report["per_tool"].items():
        if tool not in budgets:
            continue
        budget = budgets[tool]
        if metrics["output_bytes"] > budget["max_output_bytes"]:
            raise AssertionError(
                f"{tool} exceeded byte budget: "
                f"{metrics['output_bytes']} > {budget['max_output_bytes']}"
            )
        if metrics["estimated_tokens_high"] > budget["max_estimated_tokens_high"]:
            raise AssertionError(
                f"{tool} exceeded token estimate budget: "
                f"{metrics['estimated_tokens_high']} > {budget['max_estimated_tokens_high']}"
            )
    workflow_budget = budgets["workflow"]
    if report["workflow"]["output_bytes"] > workflow_budget["max_output_bytes"]:
        raise AssertionError("workflow exceeded byte budget")
    if report["workflow"]["estimated_tokens_high"] > workflow_budget["max_estimated_tokens_high"]:
        raise AssertionError("workflow exceeded token estimate budget")
    if report["compact_versus_raw"]["reduction_ratio"] < baseline["min_reduction_ratio"]:
        raise AssertionError("compact-versus-raw reduction dropped below baseline")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run Kaiten MCP payload benchmarks")
    parser.add_argument("--check", action="store_true", help="Fail if budgets are exceeded")
    parser.add_argument("--write-baseline", action="store_true", help="Rewrite baseline budgets")
    args = parser.parse_args(argv)

    report = run_benchmark()
    print(json.dumps(report, indent=2, sort_keys=True))

    if args.write_baseline:
        baseline = {
            "min_reduction_ratio": max(
                0.35,
                round(report["compact_versus_raw"]["reduction_ratio"] - 0.05, 4),
            ),
            "budgets": {
                name: {
                    "max_output_bytes": int(metrics["output_bytes"] * 1.5) + 256,
                    "max_estimated_tokens_high": int(metrics["estimated_tokens_high"] * 1.5) + 64,
                }
                for name, metrics in report["per_tool"].items()
            },
        }
        baseline["budgets"]["workflow"] = {
            "max_output_bytes": int(report["workflow"]["output_bytes"] * 1.5) + 512,
            "max_estimated_tokens_high": int(report["workflow"]["estimated_tokens_high"] * 1.5)
            + 128,
        }
        BASELINE_PATH.write_text(
            json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"Wrote {BASELINE_PATH}")
        return

    if args.check:
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        assert_within_budget(report, baseline)
        print("Benchmark budgets OK")


if __name__ == "__main__":
    main()
