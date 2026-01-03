# Phinan Finance Suite - Production Dockerfile
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
# git is often needed for pip installing from git repositories
# curl/unzip are useful for healthchecks or downloading assets
RUN apt-get update && apt-get install -y \
    git \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create data directory for DuckDB (will be mounted as volume in Railway)
RUN mkdir -p /app/data

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy the rest of the application
COPY . .

# Initialize Reflex (creates .web directory)
# We use --loglevel debug to see any issues during build
RUN reflex init

# Build the frontend (exports to .web/_static)
RUN reflex export --frontend-only --no-zip

# Expose the ports
# Reflex defaults: 3000 (frontend), 8000 (backend)
EXPOSE 3000 8000

# Run migrations and start the application
CMD ["python", "scripts/start.py"]
