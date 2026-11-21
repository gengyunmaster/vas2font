FROM ghcr.io/astral-sh/uv:0.11.15 AS uv

FROM node:24-bookworm-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run lint && npm run build

FROM node:24-bookworm-slim AS node_dependencies
WORKDIR /worker
COPY src/vas2font/node/package.json src/vas2font/node/package-lock.json ./
RUN npm ci --omit=dev

FROM python:3.12-slim AS backend
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
RUN uv sync --locked --no-editable && uv run ruff check src && uv run ruff format --check src
RUN uv sync --locked --no-dev --no-editable

FROM python:3.12-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends libstdc++6 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=backend /app/.venv/ /app/.venv/
COPY --from=node:24-bookworm-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=node_dependencies /worker/node_modules/ /app/.venv/lib/python3.12/site-packages/vas2font/node/node_modules/
COPY alembic.ini ./
COPY migrations/ ./migrations/
COPY --from=frontend /app/frontend/dist/ /app/frontend/dist/
RUN useradd --create-home --uid 10001 app
ENV PATH="/app/.venv/bin:$PATH" \
    DATABASE_URL="postgresql+asyncpg://vas2font:vas2font@db:5432/vas2font" \
    FRONTEND_DIST="/app/frontend/dist" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')" || exit 1
CMD ["sh", "-c", "alembic upgrade head && uvicorn vas2font.api.app:app --host 0.0.0.0 --port 8000"]
