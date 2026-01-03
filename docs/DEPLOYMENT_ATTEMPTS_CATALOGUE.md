# Railway Deployment Attempts - Complete Catalogue

**Project:** Phinan Finance Suite
**Target Platform:** Railway
**Period:** January 2-3, 2026
**Total Commits:** 27 deployment-related commits
**Status:** Active troubleshooting

---

## Table of Contents
1. [Overview](#overview)
2. [Chronological Attempts](#chronological-attempts)
3. [Key Configuration Evolution](#key-configuration-evolution)
4. [Technical Challenges Encountered](#technical-challenges-encountered)
5. [Current Configuration](#current-configuration)
6. [Lessons Learned](#lessons-learned)

---

## Overview

This document catalogues all attempted deployment methods for the Phinan Finance Suite on Railway. The app is a Reflex-based (Python → React) finance application with an AI assistant, using DuckDB for storage and Redis for session state.

### Core Challenges
- **Memory constraints** on Railway's free tier
- **Frontend compilation** at runtime consuming too much memory
- **Routing complexity** between static frontend and backend API
- **State management** across distributed deployments
- **Health check** configuration for Railway's deployment system

### Deployment Architecture Goal
- Frontend: Pre-compiled React app served as static files
- Backend: Python/Reflex API server
- Reverse Proxy: Caddy to route requests
- State: Redis for distributed session management
- Database: DuckDB (embedded, file-based)

---

## Chronological Attempts

### Attempt 1: Initial Railway Setup (Jan 2, 2026 - Commit 6e99b8d)
**Approach:** Basic Dockerfile with runtime compilation

**Configuration:**
```dockerfile
FROM python:3.11-slim
# Install dependencies
# Copy application
# Run: reflex init
# Exposed port for Railway
CMD ["reflex", "run", "--env", "prod"]
```

**railway.toml:**
```toml
[build]
builder = "DOCKERFILE"

[deploy]
healthcheckPath = "/"
healthcheckTimeout = 100
```

**Issues:**
- Runtime `reflex run` attempted to compile frontend on each deploy
- High memory usage during startup
- Health check failures due to slow startup

**Files Changed:** 11 files (Dockerfile, railway.toml, requirements, etc.)

---

### Attempt 2: Add Node.js for Frontend Build (Commit 789daa6)
**Approach:** Install Node.js in Dockerfile to support frontend compilation

**Changes:**
```dockerfile
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs
```

**Rationale:** Reflex requires Node.js to compile the React frontend

**Issues:**
- Still compiling at runtime
- Memory usage remained problematic
- Build times increased

---

### Attempt 3: Configure Reflex Cache Path (Commit 318ca65)
**Approach:** Set custom cache directory for non-root user

**Changes:**
```dockerfile
ENV HOME=/home/appuser
ENV REFLEX_DIR=/home/appuser/.reflex
```

**Issues:**
- Permission issues with cache directory
- Runtime compilation still happening

---

### Attempt 4: Docker Multi-Stage Build (Commit 01191ef)
**Approach:** Separate build and runtime stages to reduce image size

**Configuration:**
```dockerfile
# BUILDER STAGE
FROM python:3.11-slim AS builder
RUN reflex init && reflex export --frontend-only --no-zip

# FINAL STAGE
FROM python:3.11-slim
COPY --from=builder /app/.web/build /app/.web/build
```

**Benefits:**
- Smaller final image
- Frontend compiled during build (not runtime)

**Issues:**
- Still needed to figure out how to serve pre-built frontend
- Runtime command unclear

---

### Attempt 5: Non-Root User Security (Commit 44bfdf3)
**Approach:** Add security by running as non-root user

**Changes:**
```dockerfile
RUN useradd -m -u 1000 appuser
USER appuser
```

**Issues:**
- Permission errors with DuckDB database file
- Cache directory access issues
- Complexity without clear benefit on Railway

**Result:** Later reverted (see Attempt 9)

---

### Attempt 6: Add Production Startup Script (Commits f0a4c18, c5e3558, 3dfa96b, 5b701b8)
**Approach:** Create `scripts/start.py` to handle migrations and startup

**Initial Script:**
```python
def run_migrations():
    """Run database migrations."""
    from phinan.core.database import get_database_manager
    db = get_database_manager()
    db.initialize_schema()

def start_reflex():
    """Start Reflex in production mode."""
    subprocess.run(["reflex", "run", "--env", "prod"])

if __name__ == "__main__":
    run_migrations()
    start_reflex()
```

**Benefits:**
- Explicit migration step before app starts
- Clearer deployment process
- Better error handling

**Issues:**
- Still using `reflex run` (runtime compilation)
- Memory issues persisted

---

### Attempt 7: Update Health Check Configuration (Commits da92045, 0bdf257)
**Approach:** Adjust Railway health checks to account for slow startup

**railway.toml Changes:**
```toml
# Attempt 7a: Extend timeout
healthcheckPath = "/"
healthcheckTimeout = 300  # Increased from 100

# Attempt 7b: Disable health checks temporarily
# healthcheckPath = "/health/live"  # Commented out
```

**Rationale:** Give app more time to start up and compile

**Issues:**
- Treating symptom, not cause
- Still had memory/compilation issues

---

### Attempt 8: Pre-build Frontend with API_URL (Commit e7510b7)
**Approach:** Use Railway build argument to configure frontend at build time

**railway.toml:**
```toml
[build]
builder = "DOCKERFILE"
dockerfilePath = "Dockerfile"

[build.args]
API_URL = "https://phinan-finance-suite-production.up.railway.app"
```

**Dockerfile:**
```dockerfile
ARG API_URL
ENV REFLEX_API_URL=${API_URL}
RUN reflex init && reflex export --frontend-only --no-zip
```

**Benefits:**
- Frontend knows correct backend URL at build time
- Pre-compilation happening

**Issues:**
- Still needed to serve the pre-built files
- Unclear how to skip runtime compilation

---

### Attempt 9: Remove Non-Root User (Commit ff68e30)
**Approach:** Revert to root user to eliminate permission issues

**Rationale:**
- Railway containers are ephemeral
- Security benefit minimal in this context
- Simplifies debugging

**Result:** Improved, but core issues remained

---

### Attempt 10: Add Redis for State Management (Commit 1973a38)
**Approach:** Use Redis instead of disk-based state

**rxconfig.py:**
```python
redis_url = os.environ.get("REDIS_URL")

config = rx.Config(
    state_manager_mode="redis" if redis_url else "disk",
    redis_url=redis_url,
)
```

**requirements.txt:**
```
redis>=4.6.0
```

**Benefits:**
- Better for distributed deployments
- Avoids file permission issues
- Scales horizontally

**Issues:**
- Doesn't solve frontend compilation problem
- Added complexity

---

### Attempt 11: Introduce Caddy Reverse Proxy (Commits 6c94f73, c4a9fd1, 6a3c04f)
**Approach:** Use Caddy to serve static frontend and proxy backend requests

**Caddyfile (Initial):**
```caddyfile
:{$PORT}

reverse_proxy localhost:8000
file_server {
    root .web/build
}
```

**Dockerfile:**
```dockerfile
# Install Caddy
RUN apt-get install -y caddy

# Copy Caddyfile
COPY Caddyfile /etc/caddy/Caddyfile

# Start both Caddy and backend
CMD caddy start && reflex run --backend-only
```

**Benefits:**
- Separates frontend (static) from backend (API)
- Single port for Railway
- Proper routing

**Issues:**
- Routing configuration incomplete
- SPA fallback not configured
- Backend routes not properly defined

---

### Attempt 12: Switch to Uvicorn Direct Execution (Commit 9ef8a2a)
**Approach:** Skip `reflex run` and use `uvicorn` directly for backend

**scripts/start.py:**
```python
def start_reflex():
    """Start backend with Uvicorn."""
    cmd = [
        "uvicorn",
        "phinan.phinan:app",
        "--host", "0.0.0.0",
        "--port", "8000",
    ]
    env = os.environ.copy()
    env["REFLEX_ENV"] = "prod"
    env["__REFLEX_SKIP_COMPILE"] = "yes"

    subprocess.run(cmd, check=True, env=env)
```

**Benefits:**
- Direct backend execution (no runtime compilation)
- Lower memory footprint
- Faster startup

**Issues:**
- Needed to ensure frontend was properly served by Caddy

---

### Attempt 13: Fix Static File Copy Location (Commit a9323aa)
**Approach:** Correct the path where frontend files are copied

**Dockerfile:**
```dockerfile
# Copy pre-built frontend to /srv
COPY --from=builder /app/.web/build/client/ /srv/
```

**Caddyfile:**
```caddyfile
root * /srv
file_server
```

**Issue:** Ensuring correct paths for Caddy to find files

---

### Attempt 14: Refine Caddyfile Routing (Commits bf61408, 247dbfe, fa024f4)
**Approach:** Multiple iterations on Caddy routing configuration

**Attempt 14a (bf61408) - Add Logging:**
```caddyfile
:{$PORT}

log {
    output stdout
    level DEBUG
}

route {
    reverse_proxy /_event/* 127.0.0.1:8000
    reverse_proxy /ping 127.0.0.1:8000
    file_server {
        root .web/build
    }
}
```

**Attempt 14b (247dbfe) - Named Matchers:**
```caddyfile
@backend {
    path /_event/* /ping /_upload/*
}
reverse_proxy @backend 127.0.0.1:8000

@spa {
    not path /_event/* /ping /_upload/*
}
file_server @spa {
    root .web/build
    try_files {path} /index.html
}
```

**Attempt 14c (fa024f4) - Handle Blocks:**
```caddyfile
handle /_event/* {
    reverse_proxy 127.0.0.1:8000
}

handle /ping {
    reverse_proxy 127.0.0.1:8000
}

handle {
    root * /srv
    encode gzip
    try_files {path} /index.html
    file_server
}
```

**Progression:** Increasingly sophisticated routing to handle:
- Backend API routes (/_event/*, /ping, /_upload/*)
- Static files (CSS, JS, images)
- SPA fallback (redirect unknown routes to /index.html)

---

### Attempt 15: Simplify Caddyfile (Commit 8df4be0)
**Approach:** Consolidate routing with global root

**Caddyfile:**
```caddyfile
:{$PORT}

root * /srv

@backend {
    path /_event/* /ping /_upload/*
}
reverse_proxy @backend 127.0.0.1:8000

try_files {path} /index.html
file_server
```

**Benefits:**
- Cleaner configuration
- Easier to debug
- Maintains all functionality

---

### Attempt 16: Add Production Debug Logging (Commit 100f1c6)
**Approach:** Enhanced debugging in both Caddy and startup script

**Caddyfile:**
```caddyfile
log {
    output stdout
    level DEBUG
    format console
}
```

**scripts/start.py:**
```python
print(f"DEBUG: Railway PORT={port}")
print(f"DEBUG: Caddy should be listening on port {port}")
print("DEBUG: Backend will run on port 8000")
subprocess.run(["ls", "/srv"], check=False)
```

**Purpose:** Better visibility into what's happening during deployment

---

### Attempt 17: Add Test Endpoints (Commit 1ae912d)
**Approach:** Add simple endpoints to verify Caddy and routing work

**Caddyfile:**
```caddyfile
# Simple test endpoint - verify Caddy is working
respond /caddy-test "Caddy OK" 200
```

**Purpose:** Isolate whether issues are with Caddy, routing, or backend

---

### Attempt 18: Add Health Check Endpoint (Commit 8bc6a51) - CURRENT
**Approach:** Dedicated health endpoint that bypasses backend

**Caddyfile:**
```caddyfile
# Health check endpoint for Railway (bypasses backend)
respond /healthz "OK" 200
```

**railway.toml:**
```toml
[deploy]
healthcheckPath = "/healthz"
healthcheckTimeout = 300
```

**Benefits:**
- Railway can verify deployment without waiting for backend
- Faster health check response
- Separate concerns (infrastructure vs application health)

---

## Key Configuration Evolution

### Dockerfile Evolution

#### Phase 1: Simple Single-Stage (Commits 6e99b8d - f0a4c18)
```dockerfile
FROM python:3.11-slim
# Everything in one stage
CMD ["reflex", "run"]
```

#### Phase 2: Multi-Stage Build (Commits 01191ef - ff68e30)
```dockerfile
FROM python:3.11-slim AS builder
RUN reflex export --frontend-only

FROM python:3.11-slim
COPY --from=builder ...
CMD ["reflex", "run", "--backend-only"]
```

#### Phase 3: Multi-Stage + Caddy (Commits 6c94f73 - 9ef8a2a)
```dockerfile
FROM python:3.11-slim AS builder
RUN reflex export --frontend-only

FROM python:3.11-slim
RUN apt-get install caddy
COPY --from=builder ...
CMD caddy start && reflex run --backend-only
```

#### Phase 4: Multi-Stage + Caddy + Uvicorn Direct (Commits a9323aa - current)
```dockerfile
FROM python:3.11-slim AS builder
ARG API_URL
RUN reflex export --frontend-only
RUN ls -la .web/build/client/  # Verification

FROM python:3.11-slim
RUN apt-get install caddy
COPY --from=builder /app/.web/build/client/ /srv/
CMD caddy start && python scripts/start.py
```

### Railway Configuration Evolution

```toml
# Attempt 1-5: Basic configuration
[build]
builder = "DOCKERFILE"

[deploy]
healthcheckPath = "/"

# Attempt 6-7: Extended timeout
healthcheckTimeout = 300

# Attempt 8: Add build args
[build.args]
API_URL = "https://phinan-finance-suite-production.up.railway.app"

# Attempt 18 (Current): Custom health endpoint
[deploy]
healthcheckPath = "/healthz"
healthcheckTimeout = 300
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 3
```

### Startup Script Evolution

```python
# Version 1 (Commit c5e3558): Basic
run_migrations()
subprocess.run(["reflex", "run", "--env", "prod"])

# Version 2 (Commit 6c94f73): Backend-only
subprocess.run(["reflex", "run", "--backend-only", "--env", "prod"])

# Version 3 (Commit 9ef8a2a): Uvicorn direct
cmd = ["uvicorn", "phinan.phinan:app", "--host", "0.0.0.0", "--port", "8000"]
env["__REFLEX_SKIP_COMPILE"] = "yes"

# Version 4 (Current - Commit 100f1c6): With debug logging
print(f"DEBUG: Railway PORT={port}")
print(f"DEBUG: Checking /srv contents:")
subprocess.run(["ls", "/srv"], check=False)
```

---

## Technical Challenges Encountered

### 1. Frontend Compilation Memory Issues
**Problem:** Railway's free tier has limited memory; Reflex frontend compilation is memory-intensive

**Solutions Tried:**
- Runtime compilation with increased timeout ❌
- Multi-stage Docker build ✅
- Pre-compilation during build ✅
- Skip runtime compilation with `__REFLEX_SKIP_COMPILE` ✅

**Current Solution:** Build frontend in builder stage, copy to runtime, serve as static files

---

### 2. Routing Complexity
**Problem:** Single-page app (SPA) needs different handling than API routes

**Solutions Tried:**
- Simple `reverse_proxy` + `file_server` ❌
- Named matchers with `@backend` and `@spa` ✅
- Handle blocks for different route types ✅
- Global root with `try_files` fallback ✅

**Current Solution:** Caddy with matcher for backend routes, SPA fallback for frontend

---

### 3. State Management
**Problem:** Disk-based state doesn't work well in distributed/ephemeral containers

**Solutions Tried:**
- Default disk-based state ❌
- Redis with conditional configuration ✅

**Current Solution:** Redis for production, disk for development

---

### 4. Health Check Failures
**Problem:** Railway marks deployment as failed if health check doesn't respond quickly

**Solutions Tried:**
- Increase timeout from 100s → 300s ⚠️
- Disable health checks temporarily ❌
- Change to root path ❌
- Create dedicated `/healthz` endpoint ✅

**Current Solution:** Caddy responds immediately on `/healthz`, separate from backend

---

### 5. File Permissions
**Problem:** Non-root user had permission issues with database and cache

**Solutions Tried:**
- Configure custom home directory ❌
- Set REFLEX_DIR environment variable ❌
- Switch to root user ✅

**Current Solution:** Run as root (Railway containers are ephemeral, security less critical)

---

### 6. Static File Serving
**Problem:** Incorrect paths caused 404s for frontend assets

**Solutions Tried:**
- Copy to `.web/build` ❌
- Copy to `/app/.web/build/client/` ❌
- Copy to `/srv/` and set Caddy root ✅

**Current Solution:** Copy client files to `/srv/`, Caddy serves from there

---

### 7. Backend-Frontend Communication
**Problem:** Frontend needs to know backend URL at build time

**Solutions Tried:**
- Default localhost ❌
- Environment variable at runtime ❌
- Railway build argument passed to Docker ✅

**Current Solution:** `API_URL` build arg sets `REFLEX_API_URL` during frontend compilation

---

### 8. Debugging Deployed App
**Problem:** Limited visibility into what's happening in Railway deployment

**Solutions Tried:**
- Basic error messages ❌
- Add Caddy logging (DEBUG level) ✅
- Add startup script debug prints ✅
- Add test endpoints (`/caddy-test`) ✅
- List files during startup (`ls /srv`) ✅

**Current Solution:** Comprehensive logging at every stage

---

## Current Configuration

### Dockerfile (Multi-Stage with Caddy)
```dockerfile
# BUILDER STAGE
FROM python:3.11-slim AS builder
ARG API_URL
ENV REFLEX_API_URL=${API_URL}

# Install Node.js and dependencies
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs git curl unzip

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Build frontend
COPY . .
RUN reflex init && reflex export --frontend-only --no-zip

# FINAL STAGE
FROM python:3.11-slim

# Install Caddy
RUN apt-get update && apt-get install -y caddy

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Copy pre-built frontend
COPY --from=builder /app/.web/build/client/ /srv/

# Copy application code
COPY --from=builder /app /app

# Copy Caddy config
COPY Caddyfile /etc/caddy/Caddyfile

# Start Caddy and backend
CMD caddy start --config /etc/caddy/Caddyfile && python scripts/start.py
```

### Caddyfile
```caddyfile
:{$PORT}

# Debug logging
log {
    output stdout
    level DEBUG
    format console
}

# Test endpoints
respond /caddy-test "Caddy OK" 200
respond /healthz "OK" 200

# Set root for static files
root * /srv

# Compression
encode gzip

# Backend routes
@backend {
    path /_event/* /ping /_upload/* /health/* /api/*
}
reverse_proxy @backend 127.0.0.1:8000

# SPA fallback and static file serving
try_files {path} /index.html
file_server
```

### railway.toml
```toml
[build]
builder = "DOCKERFILE"
dockerfilePath = "Dockerfile"

[build.args]
API_URL = "https://phinan-finance-suite-production.up.railway.app"

[deploy]
healthcheckPath = "/healthz"
healthcheckTimeout = 300
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 3
```

### scripts/start.py
```python
#!/usr/bin/env python3
"""Production startup script."""

def run_migrations():
    """Run database migrations."""
    from phinan.core.database import get_database_manager
    db = get_database_manager()
    db.initialize_schema()

def start_reflex():
    """Start Reflex backend with Uvicorn."""
    port = os.environ.get("PORT", "NOT SET")
    print(f"DEBUG: Railway PORT={port}")
    print(f"DEBUG: Caddy listening on {port}")
    print("DEBUG: Backend on port 8000")
    print("DEBUG: /srv contents:")
    subprocess.run(["ls", "/srv"], check=False)

    cmd = ["uvicorn", "phinan.phinan:app", "--host", "0.0.0.0", "--port", "8000"]
    env = os.environ.copy()
    env["REFLEX_ENV"] = "prod"
    env["__REFLEX_SKIP_COMPILE"] = "yes"

    subprocess.run(cmd, check=True, env=env)

if __name__ == "__main__":
    run_migrations()
    start_reflex()
```

### rxconfig.py
```python
import reflex as rx

redis_url = os.environ.get("REDIS_URL")

config = rx.Config(
    app_name="phinan",
    api_url=os.environ.get("API_URL"),
    state_manager_mode="redis" if redis_url else "disk",
    redis_url=redis_url,
    cors_allowed_origins=[os.environ.get("API_URL")] if os.environ.get("API_URL") else ["*"],
)
```

---

## Lessons Learned

### What Worked

1. **Multi-Stage Docker Builds**
   - Separate heavy compilation from runtime
   - Smaller final images
   - Faster deployments

2. **Pre-Compilation Strategy**
   - Build frontend during Docker build
   - Serve as static files
   - Avoid runtime memory issues

3. **Caddy for Reverse Proxy**
   - Simple configuration
   - Handles routing well
   - Good logging
   - Native HTTPS support

4. **Direct Uvicorn Execution**
   - Skips Reflex's compilation checks
   - Lower overhead
   - Faster startup

5. **Redis for State**
   - Better for distributed deployments
   - Avoids file permission issues
   - Proper solution for production

6. **Dedicated Health Endpoint**
   - Fast response
   - Independent of backend
   - Better Railway integration

### What Didn't Work

1. **Runtime Compilation**
   - Too memory-intensive
   - Slow startup
   - Unreliable on Railway free tier

2. **Non-Root User**
   - Permission complications
   - Limited benefit in Railway context
   - Harder to debug

3. **Simple Reverse Proxy**
   - Doesn't handle SPA routing
   - 404s for frontend routes
   - Needs explicit routing rules

4. **Default Health Checks**
   - Root path too slow
   - Backend-dependent
   - Causes false failures

### Best Practices Discovered

1. **Build-Time Configuration**
   - Pass API_URL as build arg
   - Configure frontend at build time
   - Avoid runtime environment variables for frontend

2. **Explicit Route Matching**
   - Define backend routes explicitly
   - Use matchers for clarity
   - Document all routes

3. **Debug Logging Everywhere**
   - Log during Docker build
   - Log during startup
   - Log in Caddy
   - Essential for troubleshooting

4. **Verification Steps**
   - `ls` commands to verify file copying
   - Test endpoints for quick checks
   - Health endpoints separate from app logic

5. **Incremental Changes**
   - Small commits
   - Test each change
   - Easy to revert

---

## Next Steps for Troubleshooting

If current deployment still has issues, investigate:

1. **Frontend Build Verification**
   - Check if `/srv/` has all necessary files
   - Verify `index.html` exists
   - Check if assets are in correct locations

2. **Backend Connectivity**
   - Test if backend responds on port 8000
   - Check if Caddy can reach backend
   - Verify websocket connections for `/_event/*`

3. **Railway Logs**
   - Check build logs for errors
   - Review runtime logs
   - Monitor memory usage

4. **Caddy Configuration**
   - Test routing with `/caddy-test`
   - Check if backend routes match actual Reflex routes
   - Verify CORS settings

5. **Environment Variables**
   - Confirm `PORT` is set by Railway
   - Verify `API_URL` is correct
   - Check `REDIS_URL` if using Redis

---

## Summary Statistics

- **Total Commits:** 27 deployment-related
- **Configuration Files Modified:**
  - Dockerfile: 18 iterations
  - Caddyfile: 10 iterations
  - railway.toml: 8 iterations
  - scripts/start.py: 7 iterations
  - rxconfig.py: 2 iterations

- **Major Approaches:**
  1. Runtime compilation (abandoned)
  2. Multi-stage build (adopted)
  3. Caddy reverse proxy (adopted)
  4. Direct Uvicorn execution (adopted)
  5. Redis state management (adopted)

- **Time Investment:** ~2 days of iterative development
- **Key Learning:** Reflex's default `reflex run` is not suitable for memory-constrained production deployments

---

**Document Created:** January 3, 2026
**Last Updated:** January 3, 2026
**Branch:** `claude/document-deployment-attempts-chAvQ`
