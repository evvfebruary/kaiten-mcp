"""Explicit inventory connecting public tools to Kaiten API contracts."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Contract:
    method: str
    path: str
    docs: str
    arguments: dict[str, Any]
    response: Any
    query: dict[str, str] | None = None
    body: dict[str, Any] | None = None


CARD = {"id": 11, "title": "Contract", "board_id": 2, "column_id": 3, "lane_id": 4}
TAG = {"id": 8, "name": "mcp-test"}
COMMENT = {"id": 9, "card_id": 11, "text": "contract"}
CONTRACTS = {
    "list_spaces": Contract(
        "GET", "/spaces", "/spaces/retrieve-list-of-spaces", {}, [{"id": 1, "title": "Test"}]
    ),
    "list_boards": Contract(
        "GET",
        "/spaces/1/boards",
        "/space-boards/get-list-of-boards",
        {"space_id": 1},
        [{"id": 2, "title": "Test", "space_id": 1}],
    ),
    "list_columns": Contract(
        "GET",
        "/boards/2/columns",
        "/columns/get-list-of-columns",
        {"board_id": 2},
        [{"id": 3, "title": "Todo"}],
    ),
    "list_lanes": Contract(
        "GET",
        "/boards/2/lanes",
        "/lanes/get-list-of-lanes",
        {"board_id": 2},
        [{"id": 4, "title": "Test"}],
    ),
    "create_task": Contract(
        "POST",
        "/cards",
        "/cards/create-new-card",
        {"title": "Contract", "board_id": 2},
        CARD,
        body={"title": "Contract", "board_id": 2},
    ),
    "get_task": Contract("GET", "/cards/11", "/cards/retrieve-card", {"card_id": 11}, CARD),
    "list_tasks": Contract(
        "GET",
        "/cards",
        "/cards/retrieve-card-list",
        {"board_id": 2},
        [CARD],
        query={"board_id": "2", "offset": "0", "limit": "20"},
    ),
    "update_task": Contract(
        "PATCH",
        "/cards/11",
        "/cards/update-card",
        {"card_id": 11, "title": "Contract"},
        CARD,
        body={"title": "Contract"},
    ),
    "move_task": Contract(
        "PATCH",
        "/cards/11",
        "/cards/update-card",
        {"card_id": 11, "column_id": 3},
        CARD,
        body={"column_id": 3},
    ),
    "add_comment": Contract(
        "POST",
        "/cards/11/comments",
        "/card-comments/add-comment",
        {"card_id": 11, "text": "contract"},
        COMMENT,
        body={"text": "contract"},
    ),
    "list_comments": Contract(
        "GET",
        "/cards/11/comments",
        "/card-comments/retrieve-card-comments",
        {"card_id": 11},
        [COMMENT],
    ),
    "list_tags": Contract(
        "GET",
        "/tags",
        "/tags/retrieve-list-of-tags",
        {},
        [TAG],
        query={"offset": "0", "limit": "20"},
    ),
    "get_task_tags": Contract(
        "GET", "/cards/11/tags", "/card-tags/rertrieve-list-of-tags", {"card_id": 11}, [TAG]
    ),
    "add_tag_to_task": Contract(
        "POST",
        "/cards/11/tags",
        "/card-tags/add-tag",
        {"card_id": 11, "name": "mcp-test"},
        TAG,
        body={"name": "mcp-test"},
    ),
    "remove_tag_from_task": Contract(
        "DELETE",
        "/cards/11/tags/8",
        "/card-tags/remove-tag-from-card",
        {"card_id": 11, "tag_id": 8},
        {"id": 8},
    ),
}
READ_TOOLS = frozenset(name for name, contract in CONTRACTS.items() if contract.method == "GET")
