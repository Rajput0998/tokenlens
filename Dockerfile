# TokenLens Multi-Stage Dockerfile
# Build arg: VARIANT=slim (no ML, <300MB) or VARIANT=full (with ML + React, <800MB)
ARG VARIANT=slim

# ============================================================
# Stage 1: Python base
# ============================================================
FROM python:3.12-slim AS python-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN groupadd -r tokenlens && useradd -r -g tokenlens -d /app tokenlens
WORKDIR /app

# ============================================================
# Stage 2: Builder
# ============================================================
FROM python-base AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --prefix=/install .

# ============================================================
# Stage 3: Builder with ML dependencies
# ============================================================
FROM builder AS builder-full

RUN pip install --prefix=/install ".[ml,api,tui]"

# ============================================================
# Stage 4: Slim image (no ML)
# ============================================================
FROM python-base AS slim

COPY --from=builder /install /usr/local
COPY src/ src/

RUN mkdir -p /data && chown tokenlens:tokenlens /data

USER tokenlens

ENV TOKENLENS_GENERAL__DATA_DIR=/data

VOLUME ["/data"]
EXPOSE 7890

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD tokenlens status --short || exit 1

ENTRYPOINT ["tokenlens"]
CMD ["agent", "start", "--foreground"]

# ============================================================
# Stage 5: Full image (with ML + API)
# ============================================================
FROM python-base AS full

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder-full /install /usr/local
COPY src/ src/

RUN mkdir -p /data && chown tokenlens:tokenlens /data

USER tokenlens

ENV TOKENLENS_GENERAL__DATA_DIR=/data

VOLUME ["/data"]
EXPOSE 7890

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD tokenlens status --short || exit 1

ENTRYPOINT ["tokenlens"]
CMD ["agent", "start", "--foreground"]
