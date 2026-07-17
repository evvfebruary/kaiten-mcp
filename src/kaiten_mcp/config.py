"""Validated application settings."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Self

from pydantic import Field, HttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_WORKSPACE_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


class Settings(BaseSettings):
    """Runtime configuration for the Kaiten MCP server."""

    model_config = SettingsConfigDict(
        env_prefix="KAITEN_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    workspace_slug: str | None = Field(
        default=None,
        description=(
            "Kaiten workspace slug used to build https://{slug}.kaiten.ru/api/v1. "
            "Required unless KAITEN_BASE_URL is set."
        ),
    )
    base_url: HttpUrl | None = Field(
        default=None,
        description=(
            "Explicit Kaiten REST API root override (custom/on-prem domains). "
            "When set, takes precedence over KAITEN_WORKSPACE_SLUG. "
            "Prefer /api/v1 over /api/latest."
        ),
    )
    host: str = Field(default="127.0.0.1", description="Streamable HTTP bind host.")
    port: int = Field(default=8000, ge=1, le=65535, description="Streamable HTTP bind port.")
    log_level: str = Field(default="INFO", description="Application log level.")
    log_format: str = Field(
        default="text",
        description="Log format: text (human) or json (structured one-line events).",
    )
    log_bodies: bool = Field(
        default=False,
        description="Include compact redacted request/result previews in logs.",
    )
    enable_metrics: bool = Field(
        default=False,
        description="Emit opt-in payload metrics without logging secrets or bodies.",
    )
    request_timeout_seconds: float = Field(default=30.0, gt=0)
    max_retries: int = Field(default=3, ge=0, le=8)
    default_page_size: int = Field(default=20, ge=1, le=100)
    max_page_size: int = Field(default=100, ge=1, le=100)
    max_description_chars: int = Field(default=4_000, ge=256, le=32_768)
    max_comment_chars: int = Field(default=2_000, ge=128, le=4_096)
    max_list_item_title_chars: int = Field(default=160, ge=32, le=512)

    @field_validator("workspace_slug", mode="before")
    @classmethod
    def normalize_workspace_slug(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            return stripped.lower()
        return value

    @field_validator("workspace_slug")
    @classmethod
    def validate_workspace_slug(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _WORKSPACE_SLUG_RE.fullmatch(value):
            raise ValueError(
                "KAITEN_WORKSPACE_SLUG must be a DNS-safe label: "
                "1-63 chars, lowercase letters/digits/hyphens, "
                "and must not start or end with a hyphen."
            )
        return value

    @model_validator(mode="after")
    def resolve_base_url(self) -> Self:
        if self.base_url is not None:
            return self
        if self.workspace_slug:
            # Mutate in place — model_copy is not supported from __init__ validators.
            object.__setattr__(
                self,
                "base_url",
                HttpUrl(f"https://{self.workspace_slug}.kaiten.ru/api/v1"),
            )
            return self
        raise ValueError(
            "Configure a Kaiten instance: set KAITEN_WORKSPACE_SLUG "
            "(e.g. 'acme' for https://acme.kaiten.ru) or KAITEN_BASE_URL "
            "for a custom API root."
        )

    @property
    def api_root(self) -> str:
        if self.base_url is None:  # pragma: no cover - guarded by resolve_base_url
            raise RuntimeError("KAITEN_BASE_URL is not configured")
        return str(self.base_url).rstrip("/")

    @property
    def company_origin(self) -> str:
        # https://acme.kaiten.ru/api/v1 -> https://acme.kaiten.ru
        root = self.api_root
        marker = "/api/"
        idx = root.find(marker)
        if idx == -1:
            return root
        return root[:idx]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
