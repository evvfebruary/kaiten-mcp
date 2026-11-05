"""Fail-closed snapshots of the official Kaiten documentation."""

from __future__ import annotations

import difflib
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

from kaiten_mcp.checks.registry import CONTRACTS

ORIGIN = "https://developers.kaiten.ru"


def catalog(html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    result = {}
    for link in soup.select("a[href]"):
        path = str(link.get("href", ""))
        text = link.get_text(" ", strip=True)
        if (
            path.startswith("/")
            and not path.startswith("//")
            and re.search(r"\b(GET|POST|PATCH|PUT|DELETE)$", text)
        ):
            result[path] = text
    if len(result) < 15:
        raise ValueError("Documentation catalog could not be parsed")
    return dict(sorted(result.items()))


def normalize(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".native-scroll-container.info")
    if content is None:
        raise ValueError("Documentation content selector no longer matches")
    for tag in content.select("script, style, button, input, svg"):
        tag.decompose()
    text = "\n".join(
        line.strip() for line in content.get_text("\n", strip=True).splitlines() if line.strip()
    )
    if len(text) < 100 or "Responses" not in text or "/api/" not in text:
        raise ValueError("Documentation endpoint content is incomplete")
    return text


def fetch_snapshot() -> dict[str, Any]:
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        response = client.get(ORIGIN)
        response.raise_for_status()
        index = catalog(response.text)
        pages = {}
        for path in sorted({contract.docs for contract in CONTRACTS.values()}):
            if path not in index:
                raise ValueError(f"Documented method disappeared from catalog: {path}")
            response = client.get(ORIGIN + path)
            response.raise_for_status()
            pages[path] = normalize(response.text)
    return {"source": ORIGIN, "catalog": index, "pages": pages}


def compare(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    if before.get("source") != ORIGIN or set(before.get("pages", {})) != {
        contract.docs for contract in CONTRACTS.values()
    }:
        raise ValueError("Baseline does not cover the current registry")
    changed = {}
    for path, old in before["pages"].items():
        new = after["pages"].get(path, "")
        if old != new:
            changed[path] = "\n".join(
                difflib.unified_diff(
                    old.splitlines(),
                    new.splitlines(),
                    fromfile=path + " (baseline)",
                    tofile=path + " (current)",
                    lineterm="",
                )
            )
    added = sorted(set(after["catalog"]) - set(before["catalog"]))
    removed = sorted(set(before["catalog"]) - set(after["catalog"]))
    modified = sorted(
        p
        for p in before["catalog"].keys() & after["catalog"].keys()
        if before["catalog"][p] != after["catalog"][p]
    )
    return {
        "status": "docs_changed" if changed else "passed",
        "changes": changed,
        "new_methods": added,
        "removed_methods": removed,
        "catalog_changes": modified,
    }
