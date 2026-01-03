# Phinan Finance Suite - Production Dockerfile
# Multi-stage build with Caddy for static serving

#######################################
# BUILDER STAGE - Heavy compilation here
#######################################
FROM python:3.11-slim AS builder

# Build argument for API URL (needed for frontend to find backend)
ARG API_URL
ENV REFLEX_API_URL=${API_URL}

# Install build-time dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    unzip \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Initialize Reflex and PRE-BUILD frontend (memory-intensive, but only at build time)
RUN reflex init && reflex export --frontend-only --no-zip && \
    echo "=== Checking export output ===" && \
    ls -la .web/ && \
    ls -la .web/build/ 2>/dev/null || echo "No .web/build/" && \
    ls -la .web/build/client/ 2>/dev/null || echo "No .web/build/client/" && \
    ls -la .web/_static/ 2>/dev/null || echo "No .web/_static/"

#######################################
# FINAL STAGE - Minimal runtime
#######################################
FROM python:3.11-slim

# Runtime environment with memory optimization
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    MALLOC_ARENA_MAX=2 \
    PYTHONMALLOC=malloc

# Install Caddy (for reverse proxy) and minimal runtime deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    caddy \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create data directory for DuckDB
RUN mkdir -p /app/data /srv

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy pre-built static frontend CONTENTS to /srv (served by Caddy)
COPY --from=builder /app/.web/build/client/ /srv/

# Copy application code (without .web to save space)
COPY --from=builder /app /app

# Copy Caddyfile
COPY Caddyfile /etc/caddy/Caddyfile

# Expose the single port (Caddy handles routing)
EXPOSE 8080

# Start Caddy and backend-only (NO runtime compilation!)
CMD caddy start --config /etc/caddy/Caddyfile && \
    python scripts/start.py
