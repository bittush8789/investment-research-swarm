# ==============================================================================
# Investment Research Swarm — Production Multi-Stage Dockerfile
# ==============================================================================

# Build Stage
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


# Final Runtime Stage
FROM python:3.12-slim AS runner

# Security: Create non-privileged system user
RUN groupadd -g 10001 appgroup && \
    useradd -u 10000 -g appgroup -s /bin/bash -m appuser

WORKDIR /app

# Install runtime dependencies including curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copy application source code
COPY --chown=appuser:appgroup app /app/app
COPY --chown=appuser:appgroup frontend /app/frontend

# Switch to non-root user
USER appuser

# Expose API port
EXPOSE 8000

# Container Health Check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Production Entrypoint with Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
