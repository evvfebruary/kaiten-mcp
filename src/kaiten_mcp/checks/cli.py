"""Local and CI check entrypoint; reports never contain live API response bodies."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from kaiten_mcp.checks.docs import compare, fetch_snapshot
from kaiten_mcp.checks.live import LiveConfig, run_live
from kaiten_mcp.config import get_settings
from kaiten_mcp.logging_utils import configure_logging

BAD = {"failed", "not_configured", "source_error", "docs_changed"}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Check Kaiten MCP locally or in CI")
    parser.add_argument("mode", choices=["offline", "docs", "live", "all"])
    parser.add_argument("--output", type=Path, default=Path("reports"))
    parser.add_argument("--baseline", type=Path, default=Path("checks/kaiten-docs.json"))
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Explicitly accept the current official documentation after review",
    )
    args = parser.parse_args(argv)
    if args.update_baseline and args.mode != "docs":
        parser.error("--update-baseline requires docs mode")
    args.output.mkdir(parents=True, exist_ok=True)
    results = {}
    modes = ["offline", "docs", "live"] if args.mode == "all" else [args.mode]
    for mode in modes:
        try:
            if mode == "offline":
                if not Path("tests/checks/test_contracts.py").is_file():
                    raise ValueError(
                        "Run offline checks from the repository root with dev dependencies"
                    )
                with (args.output / "pytest.log").open("w") as output:
                    completed = subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "pytest",
                            "-m",
                            "not live",
                            "--junitxml=" + str(args.output / "offline.xml"),
                        ],
                        stdout=output,
                        stderr=subprocess.STDOUT,
                        check=False,
                    )
                result = {"status": "passed" if completed.returncode == 0 else "failed"}
            elif mode == "docs":
                snapshot = fetch_snapshot()
                (args.output / "docs-current.json").write_text(
                    json.dumps(snapshot, indent=2) + "\n"
                )
                if args.update_baseline:
                    args.baseline.parent.mkdir(parents=True, exist_ok=True)
                    args.baseline.write_text(json.dumps(snapshot, indent=2) + "\n")
                    result = {"status": "passed", "baseline_updated": True}
                else:
                    result = compare(json.loads(args.baseline.read_text()), snapshot)
                    (args.output / "docs.diff").write_text("\n\n".join(result["changes"].values()))
            else:
                config = LiveConfig.from_env()
                # Prevent live card content and credentials entering artifacts or Actions logs.
                get_settings().log_level = "CRITICAL"
                get_settings().log_bodies = False
                configure_logging(level="CRITICAL", fmt="json", force=True)
                result = asyncio.run(run_live(config))
        except Exception as exc:
            result = {
                "status": "source_error"
                if mode == "docs"
                else ("not_configured" if isinstance(exc, ValueError) else "failed"),
                "error_type": type(exc).__name__,
            }
            # Only configuration errors are safe to show verbatim.
            if mode != "docs" and isinstance(exc, ValueError):
                result["detail"] = str(exc)
        results[mode] = result
        print(f"{mode:10} {result['status']}")
        if result.get("detail"):
            print(result["detail"])
    (args.output / "report.json").write_text(json.dumps(results, indent=2) + "\n")
    summary = "| Check | Status |\n|---|---|\n" + "".join(
        f"| {name} | {result['status']} |\n" for name, result in results.items()
    )
    (args.output / "summary.md").write_text(summary)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as stream:
            stream.write(summary)
    suite = ET.Element("testsuite", name="kaiten-mcp-check")
    for name, result in results.items():
        case = ET.SubElement(suite, "testcase", name=name)
        if result["status"] in BAD:
            ET.SubElement(case, "failure", message=str(result["status"]))
    ET.ElementTree(suite).write(args.output / "checks.xml", encoding="unicode")
    raise SystemExit(int(any(result["status"] in BAD for result in results.values())))


if __name__ == "__main__":
    main()
