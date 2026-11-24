# syntax=docker/dockerfile:1
# ── fanic_bot image ──────────────────────────────────────────────────────────
# Multi-stage: build deps in an uv builder, run as non-root.

FROM ghcr.io/astral-sh/uv:0.6.17 AS uv-base

# Builder stage: install locked deps into a venv.
FROM python:3.12-slim AS builder
COPY --from=uv-base /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_CACHE_DIR=/tmp/.uv-cache
WORKDIR /app
# Build deps needed for asyncpg / pydantic-core wheels if wheels are unavailable
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/tmp/.uv-cache \
    uv sync --frozen --no-dev --no-install-project

# Runtime stage: minimal, non-root.
FROM python:3.12-slim AS runtime
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1
COPY --from=builder /app/.venv /app/.venv
COPY app ./app
COPY locales ./locales
# alembic + migrations are added at M1; keep the dir present for now.
COPY .env.example ./.env.example
USER 10001:10001
EXPOSE 8080
CMD ["python", "-m", "app.main"]
