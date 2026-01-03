# Phinan Finance Suite - Production Dockerfile
# Multi-stage build for smaller, more secure image

#######################################
# BUILDER STAGE
#######################################
FROM python:3.11-slim AS builder

# Install build-time dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy application code
COPY . .

# Initialize Reflex and build frontend
RUN reflex init && \
    reflex export --frontend-only --no-zip

#######################################
# FINAL STAGE
#######################################
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1

WORKDIR /app

# Create non-root user
RUN addgroup --system app && adduser --system --ingroup app app

# Create data directory for DuckDB
RUN mkdir -p /app/data && chown -R app:app /app/data

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code and built frontend
COPY --from=builder --chown=app:app /app /app

# Switch to non-root user
USER app

# Expose ports
EXPOSE 3000 8000

# Run migrations and start application
CMD ["python", "scripts/start.py"]
