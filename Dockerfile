# Lupus Ex Machina — production image.
#
# Two stages: Node builds the front end, Python serves everything. The final
# image carries no Node runtime, no node_modules and no front-end sources.
#
# Base images are pinned to a minor version rather than :latest, so a rebuild
# months from now produces the same thing.

# --- Stage 1: build the front end --------------------------------------------
FROM node:22-alpine AS frontend-build

WORKDIR /build

# Dependency manifests first: this layer is only invalidated when they change,
# not on every source edit.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# --- Stage 2: runtime --------------------------------------------------------
FROM python:3.13-slim AS runtime

COPY --from=ghcr.io/astral-sh/uv:0.10.11 /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app/backend

# Same ordering rule as above: lockfile, then install, then sources.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/src ./src
RUN uv sync --frozen --no-dev

WORKDIR /app
COPY --from=frontend-build /build/dist ./frontend/dist
COPY assets ./assets

# The container layout differs from a checkout, so the paths are explicit.
# Everything else keeps its default. No secret is ever baked in here.
ENV LUPUS_HOST=0.0.0.0 \
    LUPUS_PORT=8000 \
    LUPUS_FRONTEND_DIST=/app/frontend/dist \
    LUPUS_MODELS_DIR=/app/assets

RUN useradd --create-home --uid 1001 lupus && chown -R lupus:lupus /app
USER lupus

EXPOSE 8000

# No curl in the slim image; Python is already there and honours $LUPUS_PORT.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; \
urllib.request.urlopen(f\"http://127.0.0.1:{os.environ['LUPUS_PORT']}/health\").read()"]

CMD ["lupus-ex-machina"]
