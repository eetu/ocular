# syntax=docker/dockerfile:1
#
# Container-ready, but NOT the v1 deploy path. ocular ships first as a native
# systemd service on the Pi (picamera2 talks to /dev/* directly — see
# tasks/ocular.py + tasks/camera.py in the raspi repo), because Pi-camera
# access inside a container needs libcamera device passthrough that isn't worth
# the bring-up cost yet. This image builds + serves the SPA and API today; the
# camera layer falls back to a synthetic source unless picamera2 + libcamera are
# present. Wiring libcamera into the image is the TODO for the quadlet cutover.

# --- Stage 1: build the Svelte SPA (platform-independent output) ---
FROM --platform=$BUILDPLATFORM node:24-alpine AS frontend-build
WORKDIR /app
COPY frontend/package.json frontend/yarn.lock frontend/.yarnrc.yml ./
RUN corepack enable && yarn install --immutable --network-timeout 1000000
COPY frontend/ .
RUN yarn build

# --- Stage 2: runtime (Python + uv) ---
FROM python:3.14-slim AS runner
WORKDIR /app
LABEL org.opencontainers.image.description="ocular — camera-vision app with a pluggable detector pipeline"
LABEL org.opencontainers.image.source="https://github.com/eetu/ocular"

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/src ./src
RUN uv sync --frozen --no-dev

COPY --from=frontend-build /app/dist ./dist

ENV PATH="/app/.venv/bin:$PATH"
ENV OCULAR_BIND=0.0.0.0:8099
ENV OCULAR_STATIC_DIR=/app/dist
ENV OCULAR_STATE_DIR=/data
ENV OCULAR_CONFIG=/data/config.json

EXPOSE 8099

CMD ["/app/.venv/bin/ocular"]
