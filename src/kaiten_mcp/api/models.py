"""Focused Kaiten response models (extra fields ignored)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class KaitenModel(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class NamedRef(KaitenModel):
    id: int | None = None
    title: str | None = None
    name: str | None = None


class Tag(KaitenModel):
    id: int
    name: str
    color: int | None = None
    archived: bool | None = None


class Comment(KaitenModel):
    id: int
    text: str = ""
    card_id: int | None = None
    author_id: int | None = None
    created: str | None = None
    updated: str | None = None
    edited: bool | None = None


class Space(KaitenModel):
    id: int
    title: str
    uid: str | None = None


class Board(KaitenModel):
    id: int
    title: str
    space_id: int | None = None
    uid: str | None = None


class Column(KaitenModel):
    id: int
    title: str
    board_id: int | None = None
    type: int | None = None
    sort_order: float | None = None
    column_id: int | None = None


class Lane(KaitenModel):
    id: int
    title: str
    board_id: int | None = None
    sort_order: float | None = None
    condition: int | None = None


class Card(KaitenModel):
    id: int
    title: str
    description: str | None = None
    board_id: int | None = None
    column_id: int | None = None
    lane_id: int | None = None
    space_id: int | None = None
    owner_id: int | None = None
    responsible_id: int | None = None
    type_id: int | None = None
    state: int | None = None
    condition: int | None = None
    sort_order: float | None = None
    due_date: str | None = None
    created: str | None = None
    updated: str | None = None
    external_id: str | None = None
    properties: dict[str, Any] | None = None
    tags: list[Tag] = Field(default_factory=list)
    board: NamedRef | None = None
    column: NamedRef | None = None
    lane: NamedRef | None = None
    owner: NamedRef | None = None
