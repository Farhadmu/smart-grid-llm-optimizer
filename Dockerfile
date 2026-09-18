# Multi-stage production Dockerfile for GridWise Optimization Service
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock .
RUN pip install --no-cache-dir --user -r requirements.lock

# Final runtime image
FROM python:3.11-slim AS runner

WORKDIR /app

# Install curl for container health check
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Copy application source and public assets
COPY --chown=appuser:appuser app/ app/
COPY --chown=appuser:appuser docs/ docs/
COPY --chown=appuser:appuser scripts/ scripts/
COPY --chown=appuser:appuser frontend/ frontend/

USER appuser

ENV HOST=0.0.0.0
ENV PORT=8000
EXPOSE 8000

# Health check dynamically verifies GET /health on configured port
HEALTHCHECK --interval=5s --timeout=3s --start-period=5s --retries=3 \
    CMD sh -c 'curl -f http://localhost:${PORT:-8000}/health || exit 1'

CMD ["sh", "-c", "uvicorn app.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000}"]
