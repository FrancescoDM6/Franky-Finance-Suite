# Phinan Finance Suite - Production Dockerfile
# Multi-stage build for smaller image

#######################################
# BUILDER STAGE
#######################################
FROM python:3.11-slim AS builder

# Build argument for API URL (passed from Railway)
ARG API_URL
ENV API_URL=${API_URL}

# Install build-time dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    unzip \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy application code
COPY . .

# Initialize and build Reflex frontend (uses API_URL from build arg)
RUN reflex init && reflex export --frontend-only --no-zip

#######################################
# FINAL STAGE
#######################################
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1

# Install Node.js and unzip (required by Reflex at runtime)
RUN apt-get update && apt-get install -y \
    curl \
    unzip \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create data directory for DuckDB
RUN mkdir -p /app/data

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code with pre-built frontend
COPY --from=builder /app /app

# Expose ports
EXPOSE 3000 8000

# Run migrations and start application
CMD ["python", "scripts/start.py"]
