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

# Build argument for API URL (needed at runtime for backend config)
ARG API_URL

# Runtime environment with aggressive memory optimization
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    # Memory allocator tuning
    MALLOC_ARENA_MAX=2 \
    PYTHONMALLOC=malloc \
    MALLOC_TRIM_THRESHOLD_=131072 \
    MALLOC_MMAP_THRESHOLD_=131072 \
    # Database path
    PHINAN_DATABASE__PATH=/data/phinan.duckdb \
    # Limit thread spawning for NumPy/OpenBLAS/MKL/SciPy (Railway has process limits)
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    OMP_NUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1 \
    VECLIB_MAXIMUM_THREADS=1 \
    # Disable lazy imports that might trigger heavy loading
    PHINAN_AI_SERVICES_ENABLE_SENTIMENT=false \
    PHINAN_AI_SERVICES_ENABLE_VOLATILITY=false \
    PHINAN_AI_SERVICES_ENABLE_EMBEDDINGS=false

# Build argument for runtime API URL
ARG API_URL
ENV API_URL=${API_URL}

# Install Caddy (for reverse proxy) and minimal runtime deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    caddy \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create data directories for DuckDB and static assets
RUN mkdir -p /app/data /data /srv

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy pre-built static frontend CONTENTS to /srv (served by Caddy)
COPY --from=builder /app/.web/build/client/ /srv/

# Copy application code EXCLUDING .web (which is huge with node_modules)
# The .web directory is not needed at runtime - Caddy serves static files from /srv
COPY --from=builder /app/phinan /app/phinan
COPY --from=builder /app/assets /app/assets
COPY --from=builder /app/rxconfig.py /app/rxconfig.py
COPY --from=builder /app/requirements.txt /app/requirements.txt
COPY --from=builder /app/migrations /app/migrations
COPY --from=builder /app/scripts /app/scripts

# Copy Caddyfile
COPY Caddyfile /etc/caddy/Caddyfile

# Copy entrypoint script and fix Windows line endings (CRLF -> LF)
COPY scripts/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN sed -i 's/\r$//' /usr/local/bin/entrypoint.sh && chmod +x /usr/local/bin/entrypoint.sh

# Expose the single port (Caddy handles routing)
EXPOSE 8080

# Start Caddy and backend with supervision
CMD ["/usr/local/bin/entrypoint.sh"]
