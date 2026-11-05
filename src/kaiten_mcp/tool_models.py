"""Public compact tool output contracts; optional fields stay absent on the wire."""

from typing import Any, NotRequired, Required

from typing_extensions import TypedDict


class MetricsResult(TypedDict, total=False):
    _metrics: dict[str, Any]


class NamedItem(TypedDict, total=False):
    id: Required[int]
    title: Required[str]
    space_id: int | None
    board_id: int | None
    type: int | None
    sort_order: float | None
    condition: int | None
    parent_column_id: int | None


class TagItem(TypedDict):
    id: int
    name: str
    color: NotRequired[int | None]
    archived: NotRequired[bool | None]


class CommentResult(MetricsResult):
    id: int
    text: str | None
    card_id: int | None
    author_id: int | None
    created: str | None
    truncated: NotRequired[bool]
    text_chars: NotRequired[int]


class TaskResult(MetricsResult, total=False):
    id: Required[int]
    title: Required[str]
    url: Required[str]
    board_id: int
    column_id: int
    lane_id: int
    state: int
    condition: int
    due_date: str
    owner_id: int
    board: str
    column: str
    lane: str
    tags: list[TagItem]
    truncated: bool
    type_id: int
    responsible_id: int
    external_id: str
    created: str
    updated: str
    sort_order: float
    properties: dict[str, Any]
    description: str
    description_truncated: bool
    description_chars: int


class ItemList[T](MetricsResult):
    items: list[T]
    count: int
    card_id: NotRequired[int]


class Page[T](ItemList[T]):
    offset: int
    limit: int
    has_more: bool
    next_offset: int | None


class Location(TypedDict):
    board_id: int | None
    column_id: int | None
    lane_id: int | None
    sort_order: float | None


class MutationResult(MetricsResult):
    id: int
    title: str
    url: str
    changed: dict[str, Any]
    location: Location


class TagAdded(MetricsResult):
    card_id: int
    tag: TagItem


class TagRemoved(MetricsResult):
    card_id: int
    removed_tag_id: int


class NamedList(ItemList[NamedItem]):
    space_id: NotRequired[int]
    board_id: NotRequired[int]


class TagList(ItemList[TagItem]):
    pass


class CommentList(ItemList[CommentResult]):
    pass


class TaskPage(Page[TaskResult]):
    pass


class TagPage(Page[TagItem]):
    pass
