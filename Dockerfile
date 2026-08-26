# ---------- builder ----------
FROM python:3.11-slim AS builder
WORKDIR /app
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /app/
# CPU-only torch keeps the image ~2GB smaller than the default CUDA build.
RUN pip wheel --wheel-dir /wheels \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements.txt

# ---------- runtime ----------
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    HF_HOME=/home/appuser/.cache/huggingface \
    TRANSFORMERS_NO_TF=1
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
RUN adduser --disabled-password --gecos "" appuser

COPY --from=builder /wheels /wheels
COPY requirements.txt /app/
RUN pip install --no-index --find-links=/wheels -r requirements.txt && rm -rf /wheels

COPY src/ ./src/
COPY README.md ./

# The FAISS index (26MB) and fine-tuned model (88MB) are NOT baked into the
# image. They are build artifacts, not source. docker-compose mounts them from
# the host at ./data and ./models -- see docker-compose.yml.
RUN mkdir -p /app/data /app/models /app/logs && chown -R appuser:appuser /app

USER appuser
EXPOSE 8000
# Hits /health, which is liveness-only and does not touch the index.
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1
CMD ["uvicorn","src.app.main:app","--host","0.0.0.0","--port","8000"]
