"""Prepare the dedicated evvbmstu fixture. Preview by default; --apply writes."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import shlex
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import httpx

ORIGIN = "https://evvbmstu.kaiten.ru"
ROOT = ORIGIN + "/api/v1"
SPACE = 937553
PREFIX = "kaiten-mcp-fixture-v1"
BOARDS = {"demo": "MCP Demo", "scenarios": "MCP Scenarios", "integration": "MCP Integration"}
COLUMNS = [("To Do", 1), ("In Progress", 2), ("Done", 3)]


def credentials(env: dict[str, str]) -> str:
    """Validate destination before creating a client carrying a credential."""
    if env.get("KAITEN_WORKSPACE_SLUG") != "evvbmstu":
        raise ValueError("KAITEN_WORKSPACE_SLUG must be evvbmstu")
    if env.get("KAITEN_BASE_URL", "").rstrip("/") not in {"", ROOT}:
        raise ValueError("KAITEN_BASE_URL must be unset or the demo API root")
    token = env.get("KAITEN_API_TOKEN", "").strip()
    if not token:
        raise ValueError("KAITEN_API_TOKEN is required")
    return token


def seed_cards(kind: str, today: date) -> list[dict[str, Any]]:
    titles = [
        "Add a password visibility toggle",
        "Document account recovery",
        "Improve keyboard navigation",
        "Clarify login error messages",
        "Check mobile layout",
        "Publish the onboarding guide",
    ]
    count = 6 if kind == "demo" else 25 if kind == "scenarios" else 0
    cards = []
    for i in range(count):
        title = titles[i % len(titles)]
        if kind == "demo":
            title = "Kaiten demo: " + title
        else:
            title = "Kaiten scenario: " + ("Review login flow" if i < 2 else f"{i + 1:02}: {title}")
        description = (
            f"Improve the sample application's login experience: {titles[i % len(titles)].lower()}."
            "\n\nAcceptance criteria:\n"
            "- The change works with keyboard-only navigation.\n"
            "- Existing form input is preserved.\n"
            "- The behavior is documented with a reproducible example.\n\n"
            "Fictional fixture data; no customer information."
        )
        if kind == "scenarios" and i == 2:
            description = ""
        if kind == "scenarios" and i == 3:
            description = "Detailed fictional requirement for truncation testing.\n" * 300
        card = {
            "external_id": f"{PREFIX}:{kind}:card:{i + 1}",
            "title": title,
            "description": description,
            "column_index": i % 3,
        }
        if i % 3 != 2:
            delta = -7 if i % 3 == 0 else 7
            card["due_date"] = (today + timedelta(days=delta)).isoformat() + "T12:00:00Z"
        cards.append(card)
    return cards


class Fixture:
    def __init__(self, client: httpx.Client, output: Path, *, apply: bool):
        if str(client.base_url).rstrip("/") != ROOT or client.follow_redirects:
            raise ValueError("Client must target the demo API without redirects")
        self.client, self.output, self.apply = client, output, apply
        self.journal = output / "demo-fixture-state.json"
        self.state = json.loads(self.journal.read_text()) if self.journal.exists() else {}
        if self.state.get("pending"):
            raise ValueError("Unresolved write in demo-fixture-state.json; inspect before resuming")
        self.done = self.state.setdefault("done", {})
        self.actions: list[str] = []

    def save(self):
        self.output.mkdir(parents=True, exist_ok=True)
        temporary = self.journal.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.state, indent=2) + "\n")
        temporary.replace(self.journal)

    def get(self, path: str, **params):
        response = self.client.get(path, params=params)
        if response.status_code != 200:
            raise ValueError(f"GET {path}: HTTP {response.status_code}")
        return response.json()

    def rows(self, path: str, **params) -> list[dict[str, Any]]:
        result = []
        for offset in range(0, 100000, 100):
            page = self.get(path, **params, offset=offset, limit=100)
            if not isinstance(page, list):
                raise ValueError(f"Expected list from {path}")
            result.extend(page)
            if len(page) < 100:
                return result
        raise ValueError(f"Pagination did not end: {path}")

    def post(self, key: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.actions.append(f"create {key}")
        if not self.apply:
            return {**payload, "id": -len(self.actions)}
        # Persist before sending: a timeout or interruption must not lead to a blind retry.
        self.state["pending"] = {"key": key, "path": path}
        self.save()
        response = self.client.post(path, json=payload)
        if response.status_code not in {200, 201}:
            raise ValueError(f"POST {path}: HTTP {response.status_code}; inspect pending write")
        result = response.json()
        if not isinstance(result, dict) or not isinstance(result.get("id"), int):
            raise ValueError(f"POST {path}: missing ID; inspect pending write")
        self.done[key] = result["id"]
        self.state.pop("pending")
        self.save()
        return result

    def ensure(self, key, path, payload, existing):
        matches = [x for x in existing if x.get("external_id") == key]
        if len(matches) > 1:
            raise ValueError(f"Duplicate external_id: {key}")
        if matches:
            self.actions.append(f"reuse {key}")
            return matches[0]
        if key in self.done:
            raise ValueError(f"Previously created object missing or identity changed: {key}")
        if any(x.get("title") == payload["title"] for x in existing):
            raise ValueError(f"Unowned title conflict: {payload['title']}")
        return self.post(key, path, {**payload, "external_id": key})

    def run(self, today: date) -> dict[str, Any]:
        spaces = self.rows("/spaces")
        if not any(x["id"] == SPACE for x in spaces):
            raise ValueError("Expected demo space is not accessible")
        boards_path = f"/spaces/{SPACE}/boards"
        boards = [self.get(f"{boards_path}/{x['id']}") for x in self.rows(boards_path)]
        # Include archived cards and cards moved to another board. Deleted/hidden objects
        # are protected by the durable receipt: missing identities stop preparation.
        all_cards = list(
            {
                x["id"]: x for condition in (1, 2) for x in self.rows("/cards", condition=condition)
            }.values()
        )
        report: dict[str, Any] = {"origin": ORIGIN, "space_id": SPACE, "boards": {}}
        for kind, title in BOARDS.items():
            key = f"{PREFIX}:{kind}"
            board = self.ensure(
                key,
                boards_path,
                {
                    "title": title,
                    "columns": [{"title": t, "type": v} for t, v in COLUMNS],
                    "lanes": [{"title": "Default"}],
                },
                boards,
            )
            bid = board["id"]
            if bid > 0:
                columns = self.get(f"/boards/{bid}/columns")
                lanes = self.get(f"/boards/{bid}/lanes")
            else:
                columns = [
                    {"id": -i - 1, "title": t, "type": v} for i, (t, v) in enumerate(COLUMNS)
                ]
                lanes = [{"id": -1, "title": "Default"}]
            resolved = []
            for name, column_type in COLUMNS:
                matches = [x for x in columns if x["title"] == name]
                if len(matches) != 1 or matches[0].get("type") != column_type:
                    raise ValueError(
                        f"Unexpected columns on {title}; preserve and inspect manually"
                    )
                resolved.append(matches[0]["id"])
            if len(lanes) != 1:
                raise ValueError(f"Expected one lane on {title}; preserve and inspect manually")
            info = {
                "id": bid,
                "url": f"{ORIGIN}/space/{SPACE}/boards?board_id={bid}",
                "columns": dict(zip((x[0] for x in COLUMNS), resolved, strict=True)),
                "lane_id": lanes[0]["id"],
                "cards": [],
            }
            report["boards"][kind] = info
            for seed in seed_cards(kind, today):
                ci = seed.pop("column_index")
                ck = seed["external_id"]
                # Managed duplicate titles are intentional in the scenarios board.
                candidates = [
                    x
                    for x in all_cards
                    if x.get("external_id") == ck
                    or (
                        x.get("board_id") == bid
                        and not str(x.get("external_id", "")).startswith(PREFIX + ":")
                    )
                ]
                card = self.ensure(
                    ck,
                    "/cards",
                    {
                        **seed,
                        "board_id": bid,
                        "column_id": resolved[ci],
                        "lane_id": lanes[0]["id"],
                    },
                    candidates,
                )
                cid = card["id"]
                info["cards"].append({"id": cid, "external_id": ck, "url": f"{ORIGIN}/{cid}"})
                # A durable receipt preserves subsequent manual comment/tag edits.
                for suffix, body in [
                    ("tags", {"name": "mcp-demo" if kind == "demo" else "mcp-scenario"}),
                    ("comments", {"text": f"Fixture note [{ck}]: ready for review."}),
                ]:
                    action = f"{ck}:{suffix}"
                    if action in self.done:
                        continue
                    existing = self.rows(f"/cards/{cid}/{suffix}") if cid > 0 else []
                    field = "name" if suffix == "tags" else "text"
                    matches = [x for x in existing if x.get(field) == body[field]]
                    if len(matches) > 1:
                        raise ValueError(f"Duplicate fixture {suffix} on card {cid}")
                    if matches:
                        if self.apply:
                            self.done[action] = matches[0]["id"]
                            self.save()
                    else:
                        self.post(action, f"/cards/{cid}/{suffix}", body)
        # Kaiten's tag list omits unused tags. Anchor the live-test tag to a permanent
        # demo card so it stays discoverable after each temporary live card is deleted.
        anchor = report["boards"]["demo"]["cards"][0]["id"]
        key = "integration-tag-anchor"
        attached = self.rows(f"/cards/{anchor}/tags") if anchor > 0 else []
        tags = [x for x in attached if x.get("name") == "mcp-test"]
        if len(tags) > 1:
            raise ValueError("Ambiguous mcp-test tag")
        if tags:
            tag = tags[0]
            if self.apply:
                self.done[key] = tag["id"]
                self.save()
        elif key in self.done:
            raise ValueError("Live-test tag anchor was removed; inspect before restoring")
        else:
            tag = self.post(key, f"/cards/{anchor}/tags", {"name": "mcp-test"})
        report["tag_id"] = tag["id"]
        report["actions"] = self.actions
        if self.apply:
            self.output.mkdir(parents=True, exist_ok=True)
            (self.output / "demo-fixture.json").write_text(json.dumps(report, indent=2) + "\n")
            integration = report["boards"]["integration"]
            values = {
                "SPACE_ID": SPACE,
                "BOARD_ID": integration["id"],
                "COLUMN_ID": integration["columns"]["To Do"],
                "TARGET_COLUMN_ID": integration["columns"]["In Progress"],
                "LANE_ID": integration["lane_id"],
                "TAG_ID": tag["id"],
                "TAG_NAME": "mcp-test",
            }
            (self.output / "demo-test.env").write_text(
                "".join(
                    f"export KAITEN_TEST_{k}={shlex.quote(str(v))}\n" for k, v in values.items()
                )
            )
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    output = Path(__file__).resolve().parents[1] / "reports"
    try:
        token = credentials(dict(os.environ))
        # One local writer across worktrees; remote concurrent preparation is unsupported.
        lock = Path.home() / ".config/kaiten-mcp/demo-fixture.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        with lock.open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with httpx.Client(
                base_url=ROOT,
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
                follow_redirects=False,
            ) as client:
                fixture = Fixture(client, output, apply=args.apply)
                report = fixture.run(date.today())
        print("Applied" if args.apply else "Preview only; pass --apply to create")
        for kind, info in report["boards"].items():
            location = info["url"] if info["id"] > 0 else "new board (preview)"
            print(f"{BOARDS[kind]}: {len(info['cards'])} seed cards; {location}")
        print(f"Planned/executed writes: {sum(x.startswith('create ') for x in report['actions'])}")
    except (ValueError, httpx.HTTPError, BlockingIOError) as exc:
        # HTTP exceptions may contain request details; never print them or response bodies.
        print(str(exc) if isinstance(exc, ValueError) else type(exc).__name__)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
