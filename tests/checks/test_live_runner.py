"""Exercise the complete live lifecycle against a stateful fake, including cleanup failures."""

import json

import httpx
import pytest
import respx

from kaiten_mcp.checks.live import LiveConfig, board_lock, run_live
from kaiten_mcp.checks.registry import CONTRACTS
from kaiten_mcp.config import get_settings

CONFIG = LiveConfig(1, 2, 3, 5, 4, 8, "mcp-test")


@pytest.mark.parametrize("failure", [None, "move", "cleanup", "preflight"])
@respx.mock
async def test_lifecycle_and_cleanup(failure, monkeypatch):
    monkeypatch.setenv("KAITEN_API_TOKEN", "live-test-token")
    get_settings().max_retries = 0
    card = {}
    comments = []
    tags = []
    deleted = []

    def handle(request):
        path = request.url.path.removeprefix("/api/v1")
        method = request.method
        payload = json.loads(request.content) if request.content else {}
        if path == "/spaces":
            result = [{"id": 1, "title": "Test"}]
        elif path == "/spaces/1/boards":
            result = [{"id": 2, "title": "Test"}]
        elif path == "/boards/2/columns":
            result = [{"id": 3, "title": "Todo"}, {"id": 5, "title": "Done"}]
        elif path == "/boards/2/lanes":
            result = [{"id": 4, "title": "Test"}]
        elif path == "/tags":
            result = [] if failure == "preflight" else [{"id": 8, "name": "mcp-test"}]
        elif path == "/cards" and method == "POST":
            card.update(id=11, **payload)
            result = card
        elif path == "/cards":
            result = [card]
        elif path == "/cards/11" and method == "DELETE":
            deleted.append(11)
            return httpx.Response(503 if failure == "cleanup" else 204)
        elif path == "/cards/11":
            if failure == "move" and "column_id" in payload:
                return httpx.Response(403, json={"message": "no"})
            card.update(payload)
            result = card
        elif path == "/cards/11/comments":
            if method == "POST":
                comments.append({"id": 9, "card_id": 11, **payload})
                result = comments[-1]
            else:
                result = comments
        elif path == "/cards/11/tags/8":
            tags.clear()
            result = {"id": 8}
        elif path == "/cards/11/tags":
            if method == "POST":
                tags.append({"id": 8, "name": payload["name"]})
                result = tags[-1]
            else:
                result = tags
        else:
            raise AssertionError(f"Unexpected request: {method} {path}")
        return httpx.Response(200, json=result)

    respx.route().mock(side_effect=handle)
    result = await run_live(CONFIG)
    assert result["status"] == ("passed" if failure is None else "failed")
    assert deleted == ([] if failure == "preflight" else [11])
    assert "live-test-token" not in json.dumps(result)
    if failure is None:
        assert {row["name"] for row in result["tools"] if row["status"] == "passed"} == set(
            CONTRACTS
        )
    elif failure == "cleanup":
        assert result["cleanup"] == {"status": "failed", "card_id": 11, "error_type": "KaitenError"}
    elif failure == "move":
        assert result["cleanup"]["status"] == "passed"
        assert (
            next(row for row in result["tools"] if row["name"] == "add_comment")["status"]
            == "skipped"
        )


def test_live_requires_explicit_configuration():
    with pytest.raises(ValueError, match="KAITEN_API_TOKEN"):
        LiveConfig.from_env()


def test_board_lock_blocks_overlapping_run():
    with (
        board_lock(CONFIG),
        pytest.raises(ValueError, match="Another local live run"),
        board_lock(CONFIG),
    ):
        pass
