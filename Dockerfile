# Phinan Finance Suite - Production Dockerfile
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create a non-root user and group
RUN addgroup --system app && adduser --system --ingroup app app

# Create data directory for DuckDB and set permissions
RUN mkdir -p /app/data && chown -R app:app /app/data

# Copy requirements first to leverage Docker cache
COPY --chown=app:app requirements.txt .

# Install dependencies (as root for system-wide install)
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy the rest of the application
COPY --chown=app:app . .

# Initialize Reflex and build frontend (needs write access to .web)
RUN reflex init && \
    reflex export --frontend-only --no-zip && \
    chown -R app:app /app

# Switch to non-root user
USER app

# Expose the ports
EXPOSE 3000 8000

# Run migrations and start the application
CMD ["python", "scripts/start.py"]
