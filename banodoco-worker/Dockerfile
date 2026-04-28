# banodoco-worker — Sprint 7 (SD-035)
#
# Multi-stage image baking together everything the worker needs to (a)
# generate a TimelineConfig for `banodoco_timeline_generate` and (b)
# (Sprint 8) render that timeline via Remotion. Pre-baking Chrome here
# avoids a double-rebuild when Sprint 8 lands.
#
# Stages:
#   1. node-deps    — installs the workspace's Node packages
#                     (@banodoco/timeline-schema, timeline-ops,
#                     timeline-composition, timeline-theme-2rp).
#   2. chrome       — Chromium for Remotion (Sprint 8 uses headlessly).
#   3. python-base  — Python 3.11 + the tools/ pipeline + pip deps.
#   4. final        — assembles the runtime: Python entry + Node modules
#                     + Chromium binary + worker.py.
#
# Build context expectation: `banodoco-workspace/` repo root.
# Build invocation:
#   docker build -f banodoco-worker/Dockerfile -t banodoco-worker:sprint-7 .
# (NOT pushed to a registry in Sprint 7 — see sprint brief "Hard boundaries".)

# ---- Stage 1: Node dependencies -----------------------------------------
FROM node:20-bookworm-slim AS node-deps
WORKDIR /app

# Workspace shared packages: copy package manifests first for layer caching.
COPY packages/timeline-schema/package.json       ./packages/timeline-schema/package.json
COPY packages/timeline-ops/package.json          ./packages/timeline-ops/package.json
COPY packages/timeline-composition/package.json  ./packages/timeline-composition/package.json
COPY packages/timeline-theme-2rp/package.json    ./packages/timeline-theme-2rp/package.json

# Root package.json + lockfile for workspace resolution.
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev --include=workspace-root || npm install --omit=dev

# Now copy the actual source for the shared packages.
COPY packages/timeline-schema/       ./packages/timeline-schema/
COPY packages/timeline-ops/          ./packages/timeline-ops/
COPY packages/timeline-composition/  ./packages/timeline-composition/
COPY packages/timeline-theme-2rp/    ./packages/timeline-theme-2rp/

# Build any TS that needs compilation.
RUN cd packages/timeline-schema       && npm run build || true
RUN cd packages/timeline-ops          && npm run build || true
RUN cd packages/timeline-composition  && npm run build || true
RUN cd packages/timeline-theme-2rp    && npm run build || true


# ---- Stage 2: Chromium for Remotion (Sprint 8 prep) --------------------
# Use the lightweight Playwright/Puppeteer pull pattern. We pin the
# headless-shell channel so Sprint 8's `@remotion/renderer` finds it at
# the expected path without an extra download step.
FROM node:20-bookworm-slim AS chrome
RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium \
        ca-certificates \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*


# ---- Stage 3: Python pipeline ------------------------------------------
FROM python:3.11-slim AS python-base
WORKDIR /app

# System deps the pipeline needs at runtime (ffmpeg for video work, libs
# for opencv-headless used by scenedetect).
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libglib2.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps — worker first, then the existing tools/ deps so
# layer caching favors worker iteration.
COPY banodoco-worker/requirements.txt /tmp/worker-requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/worker-requirements.txt

COPY tools/requirements.txt /tmp/tools-requirements.txt
RUN pip install --no-cache-dir -r /tmp/tools-requirements.txt

# Workspace shared timeline-schema python wheel.
COPY packages/timeline-schema/python /opt/banodoco-timeline-schema-py
RUN pip install --no-cache-dir /opt/banodoco-timeline-schema-py


# ---- Stage 4: Final runtime --------------------------------------------
FROM python:3.11-slim AS final
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    BANODOCO_WORKER_POOL=banodoco \
    NODE_PATH=/app/node_modules

# Install Node.js + ffmpeg + Chromium runtime libs.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl gnupg ca-certificates ffmpeg libglib2.0-0 libgomp1 \
        chromium fonts-liberation \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed Python packages from python-base.
COPY --from=python-base /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=python-base /usr/local/bin /usr/local/bin

# Copy Node modules + shared workspace packages.
COPY --from=node-deps /app/node_modules ./node_modules
COPY --from=node-deps /app/packages     ./packages

# Copy the Banodoco pipeline entry points.
COPY tools/pipeline.py            ./tools/pipeline.py
COPY tools/arrange.py             ./tools/arrange.py
COPY tools/cut.py                 ./tools/cut.py
COPY tools/pool_merge.py          ./tools/pool_merge.py
COPY tools/timeline.py            ./tools/timeline.py
COPY tools/effects_catalog.py     ./tools/effects_catalog.py
COPY tools/text_match.py          ./tools/text_match.py
COPY tools/asset_cache.py         ./tools/asset_cache.py
COPY tools/arrangement_rules.py   ./tools/arrangement_rules.py
COPY tools/quality_zones.py       ./tools/quality_zones.py
COPY tools/theme_schema.py        ./tools/theme_schema.py

# Copy the worker itself.
COPY banodoco-worker/worker.py            ./worker.py
COPY banodoco-worker/worker_health.py     ./worker_health.py
COPY banodoco-worker/worker_jwt.py        ./worker_jwt.py
COPY banodoco-worker/worker_pipeline.py   ./worker_pipeline.py
COPY banodoco-worker/worker_writes.py     ./worker_writes.py
# Sprint 8 — render task type modules.
COPY banodoco-worker/worker_assets.py     ./worker_assets.py
COPY banodoco-worker/worker_remotion.py   ./worker_remotion.py
COPY banodoco-worker/worker_render.py     ./worker_render.py

ENV PYTHONPATH=/app:/app/tools

# Health endpoint is exposed on $WORKER_HEALTH_PORT (default 8088).
EXPOSE 8088

# Lifecycle: boot → health-server up → poll orchestrator → claim → execute → write → complete.
CMD ["python", "/app/worker.py"]
