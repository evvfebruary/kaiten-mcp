"""Stateful API checks for fixture creation and safe resumption."""

import importlib.util
import json
from datetime import date
from pathlib import Path

import httpx
import pytest

spec = importlib.util.spec_from_file_location(
    "prepare_demo", Path(__file__).resolve().parents[2] / "scripts/prepare_demo.py"
)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class API:
    def __init__(self):
        self.boards = []
        self.cards = []
        self.tags = []
        self.extras = {}
        self.writes = 0
        self.serial = 100
        self.fail_at = None

    def new(self, payload):
        self.serial += 1
        return {**payload, "id": self.serial}

    def handle(self, request):
        path = request.url.path.removeprefix("/api/v1")
        data = json.loads(request.content) if request.content else {}
        post = request.method == "POST"
        if post:
            self.writes += 1
        if path == "/spaces":
            result = [{"id": module.SPACE, "title": "Main"}]
        elif path == f"/spaces/{module.SPACE}/boards":
            if post:
                board = self.new(data)
                board["columns"] = [self.new(x) for x in data["columns"]]
                board["lanes"] = [self.new(x) for x in data["lanes"]]
                self.boards.append(board)
                result = board
            else:
                result = self.boards
        elif path.startswith(f"/spaces/{module.SPACE}/boards/"):
            result = next(x for x in self.boards if x["id"] == int(path.split("/")[-1]))
        elif path.startswith("/boards/"):
            board = next(x for x in self.boards if x["id"] == int(path.split("/")[2]))
            result = board[path.split("/")[-1]]
        elif path == "/cards":
            if post:
                result = self.new(data)
                self.cards.append(result)
            else:
                result = self.cards
        elif path == "/tags":
            if post:
                result = self.new(data)
                self.tags.append(result)
            else:
                attached = {
                    x["id"] for k, rows in self.extras.items() if k.endswith("/tags") for x in rows
                }
                result = [x for x in self.tags if x["id"] in attached]
        elif path.startswith("/cards/"):
            rows = self.extras.setdefault(path, [])
            if post:
                if path.endswith("/tags"):
                    result = next((x for x in self.tags if x["name"] == data["name"]), None)
                    if result is None:
                        result = self.new(data)
                        self.tags.append(result)
                else:
                    result = self.new(data)
                rows.append(result)
            else:
                result = rows
        else:
            raise AssertionError(path)
        if post and self.writes == self.fail_at:
            raise httpx.ReadTimeout("response lost after server committed", request=request)
        if isinstance(result, list):
            offset = int(request.url.params.get("offset", 0))
            limit = int(request.url.params.get("limit", 100))
            result = result[offset : offset + limit]
        return httpx.Response(200, json=result)


def run(api, tmp_path, apply=True):
    with httpx.Client(base_url=module.ROOT, transport=httpx.MockTransport(api.handle)) as client:
        return module.Fixture(client, tmp_path, apply=apply).run(date(2026, 11, 6))


def test_preview_and_repeat_preserve_changes(tmp_path):
    api = API()
    run(api, tmp_path, apply=False)
    assert api.writes == 0
    assert not list(tmp_path.iterdir())
    report = run(api, tmp_path)
    assert len(api.boards) == 3
    assert len(api.cards) == 31
    assert len({c["external_id"] for c in api.cards}) == 31
    assert len(report["boards"]["scenarios"]["cards"]) == 25
    api.cards[0].update(title="User edited", description="Preserve me", board_id=999)
    api.extras[
        next(k for k in api.extras if k.endswith("/comments"))
    ].clear()  # Manual removal must remain removed.
    writes = api.writes
    run(api, tmp_path)
    assert api.writes == writes
    assert api.cards[0]["description"] == "Preserve me"
    assert api.cards[0]["board_id"] == 999
    assert "TOKEN" not in (tmp_path / "demo-test.env").read_text()


def test_partial_stand_is_completed(tmp_path):
    api = API()
    run(api, tmp_path)
    # Simulate a successfully checkpointed run that ended after its first board/card.
    api.boards = api.boards[:1]
    api.cards = api.cards[:1]
    api.extras = {k: v for k, v in api.extras.items() if f"/{api.cards[0]['id']}/" in k}
    state = json.loads((tmp_path / "demo-fixture-state.json").read_text())
    state["done"] = {
        k: v
        for k, v in state["done"].items()
        if k == f"{module.PREFIX}:demo"
        or k.startswith(f"{module.PREFIX}:demo:card:1:")
        or k == f"{module.PREFIX}:demo:card:1"
    }
    (tmp_path / "demo-fixture-state.json").write_text(json.dumps(state))
    run(api, tmp_path)
    assert len(api.boards) == 3
    assert len(api.cards) == 31


def test_conflict_stops_before_writes(tmp_path):
    api = API()
    api.boards = [{"id": 1, "title": "MCP Demo"}]
    with pytest.raises(ValueError, match="Unowned title conflict"):
        run(api, tmp_path)
    assert api.writes == 0


def test_lost_response_blocks_retry(tmp_path):
    api = API()
    api.fail_at = 1
    with pytest.raises(httpx.ReadTimeout):
        run(api, tmp_path)
    assert len(api.boards) == 1
    with pytest.raises(ValueError, match="Unresolved write"):
        run(api, tmp_path)
    assert api.writes == 1


@pytest.mark.parametrize("slug,url", [("production", ""), ("evvbmstu", "https://evil.example")])
def test_wrong_account_rejected(slug, url):
    with pytest.raises(ValueError):
        module.credentials(
            {"KAITEN_WORKSPACE_SLUG": slug, "KAITEN_BASE_URL": url, "KAITEN_API_TOKEN": "secret"}
        )


def test_duplicate_identity_rejected(tmp_path):
    api = API()
    run(api, tmp_path)
    api.cards.append({**api.cards[0], "id": 9999})
    with pytest.raises(ValueError, match="Duplicate external_id"):
        run(api, tmp_path)


def test_integration_tag_is_discoverable_without_live_cards(tmp_path):
    api = API()
    report = run(api, tmp_path)
    with httpx.Client(base_url=module.ROOT, transport=httpx.MockTransport(api.handle)) as client:
        visible = client.get("/tags").json()
    assert any(x["id"] == report["tag_id"] for x in visible)
    assert not [x for x in api.cards if x["board_id"] == report["boards"]["integration"]["id"]]
