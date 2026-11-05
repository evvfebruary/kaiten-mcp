"""Opt-in cloud lifecycle. Only cards created by this run may be deleted."""

from __future__ import annotations

import asyncio
import fcntl
import hashlib
import os
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp import Client

from kaiten_mcp.api.client import KaitenClient
from kaiten_mcp.checks.registry import CONTRACTS
from kaiten_mcp.config import get_settings
from kaiten_mcp.server import create_server


@dataclass(frozen=True)
class LiveConfig:
    space_id: int
    board_id: int
    column_id: int
    target_column_id: int
    lane_id: int
    tag_id: int
    tag_name: str

    @classmethod
    def from_env(cls) -> LiveConfig:
        values: dict[str, Any] = {}
        if not os.environ.get("KAITEN_API_TOKEN", "").strip():
            raise ValueError("KAITEN_API_TOKEN is required")
        for field in cls.__dataclass_fields__:
            key = "KAITEN_TEST_" + field.upper()
            value = os.environ.get(key, "").strip()
            if not value:
                raise ValueError(f"{key} is required")
            if field.endswith("_id"):
                if not value.isdigit() or int(value) <= 0:
                    raise ValueError(f"{key} must be a positive integer")
                values[field] = int(value)
            else:
                values[field] = value
        if values["column_id"] == values["target_column_id"]:
            raise ValueError("Test source and target columns must differ")
        get_settings()  # Validate tenant before any requests.
        return cls(**values)


@contextmanager
def board_lock(config: LiveConfig):
    key = f"{get_settings().api_root}:{config.board_id}"
    digest = hashlib.sha256(key.encode()).hexdigest()[:24]
    path = Path(tempfile.gettempdir()) / f"kaiten-mcp-live-{digest}.lock"
    with path.open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("Another local live run is using this board") from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


async def run_live(config: LiveConfig) -> dict[str, Any]:
    run_id = uuid.uuid4().hex
    rows = {name: {"name": name, "status": "skipped"} for name in sorted(CONTRACTS)}
    cleanup: dict[str, Any] = {"status": "skipped"}
    card_id: int | None = None
    failed = False
    stage = "preflight"
    with board_lock(config):
        async with Client(create_server(), read_timeout_seconds=60) as mcp:

            async def call(tool_name: str, **arguments: Any) -> dict[str, Any]:
                nonlocal stage
                stage = tool_name
                await asyncio.sleep(0.1)  # Bound the test's request rate.
                result = await mcp.call_tool(tool_name, arguments)
                require(not result.is_error, f"Tool {tool_name} failed")
                require(
                    result.structured_content is not None,
                    f"Tool {tool_name} omitted structured output",
                )
                rows[tool_name]["status"] = "passed"
                return result.structured_content or {}

            try:
                spaces = await call("list_spaces")
                require(
                    any(x["id"] == config.space_id for x in spaces["items"]), "Test space missing"
                )
                boards = await call("list_boards", space_id=config.space_id)
                require(
                    any(x["id"] == config.board_id for x in boards["items"]), "Test board missing"
                )
                columns = await call("list_columns", board_id=config.board_id)
                ids = {x["id"] for x in columns["items"]}
                require({config.column_id, config.target_column_id} <= ids, "Test columns missing")
                lanes = await call("list_lanes", board_id=config.board_id)
                require(any(x["id"] == config.lane_id for x in lanes["items"]), "Test lane missing")
                tags = await call("list_tags", query=config.tag_name, limit=100)
                require(
                    any(
                        x["id"] == config.tag_id and x["name"] == config.tag_name
                        for x in tags["items"]
                    ),
                    "Existing test tag missing or not on first page",
                )
                title = "mcp-check-" + run_id
                created = await call(
                    "create_task",
                    title=title,
                    board_id=config.board_id,
                    column_id=config.column_id,
                    lane_id=config.lane_id,
                )
                card_id = created["id"]
                read = await call("get_task", card_id=card_id)
                require(
                    read["title"] == title and read["board_id"] == config.board_id,
                    "Created card does not match",
                )
                found = await call("list_tasks", board_id=config.board_id, query=title, limit=100)
                require(any(x["id"] == card_id for x in found["items"]), "Created card not found")
                await call("update_task", card_id=card_id, title=title + "-updated")
                require(
                    (await call("get_task", card_id=card_id))["title"] == title + "-updated",
                    "Updated title did not persist",
                )
                await call("move_task", card_id=card_id, column_id=config.target_column_id)
                require(
                    (await call("get_task", card_id=card_id))["column_id"]
                    == config.target_column_id,
                    "Move did not persist",
                )
                comment = await call("add_comment", card_id=card_id, text="mcp-check " + run_id)
                comments = await call("list_comments", card_id=card_id)
                require(
                    any(
                        x["id"] == comment["id"] and run_id in x["text"] for x in comments["items"]
                    ),
                    "Comment did not persist",
                )
                attached = await call("add_tag_to_task", card_id=card_id, name=config.tag_name)
                require(attached["tag"]["id"] == config.tag_id, "Unexpected test tag ID")
                tags = await call("get_task_tags", card_id=card_id)
                require(any(x["id"] == config.tag_id for x in tags["items"]), "Tag did not persist")
                await call("remove_tag_from_task", card_id=card_id, tag_id=config.tag_id)
                tags = await call("get_task_tags", card_id=card_id)
                require(all(x["id"] != config.tag_id for x in tags["items"]), "Tag was not removed")
            except Exception as exc:
                failed = True
                rows[stage] = {"name": stage, "status": "failed", "error_type": type(exc).__name__}
            finally:
                if card_id is not None:
                    cleanup = {"status": "failed", "card_id": card_id}
                    try:
                        async with KaitenClient(os.environ["KAITEN_API_TOKEN"]) as api:
                            await api.delete(f"/cards/{card_id}")
                        cleanup["status"] = "passed"
                    except Exception as exc:
                        failed = True
                        cleanup["error_type"] = type(exc).__name__
    failed = failed or any(row["status"] != "passed" for row in rows.values())
    return {
        "status": "failed" if failed else "passed",
        "run_id": run_id,
        "tools": list(rows.values()),
        "cleanup": cleanup,
    }
