# Phinan Finance Suite - Production Dockerfile
# Multi-stage build for smaller image

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

# Initialize Reflex only (frontend built at runtime to pick up API_URL)
RUN reflex init

#######################################
# FINAL STAGE
#######################################
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1

# Install Node.js (required by Reflex at runtime)
RUN apt-get update && apt-get install -y \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create data directory for DuckDB
RUN mkdir -p /app/data

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --from=builder /app /app

# Expose ports
EXPOSE 3000 8000

# Run migrations and start application
# Running as root to allow Railway volume writes
CMD ["python", "scripts/start.py"]
