# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
COPY benchmarks ./benchmarks

RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim-bookworm AS runtime

ARG VERSION=0.0.0
ARG REVISION=unknown

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    KAITEN_HOST=0.0.0.0 \
    KAITEN_PORT=8000

LABEL org.opencontainers.image.title="kaiten-mcp" \
    org.opencontainers.image.description="MCP server for Kaiten tasks and kanban boards" \
    org.opencontainers.image.source="https://github.com/evvfebruary/kaiten-mcp" \
    org.opencontainers.image.url="https://github.com/evvfebruary/kaiten-mcp" \
    org.opencontainers.image.licenses="MIT" \
    org.opencontainers.image.version="${VERSION}" \
    org.opencontainers.image.revision="${REVISION}" \
    io.modelcontextprotocol.server.name="io.github.evvfebruary/kaiten-mcp"

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/pyproject.toml /app/README.md /app/

EXPOSE 8000
USER nobody
CMD ["kaiten-mcp", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8000"]
