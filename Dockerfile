# ---------- builder ----------
FROM python:3.11-slim AS builder
WORKDIR /app
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /app/
RUN pip wheel --wheel-dir /wheels -r requirements.txt

# ---------- runtime ----------
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN adduser --disabled-password --gecos "" appuser
COPY --from=builder /wheels /wheels
COPY requirements.txt /app/
RUN pip install --no-index --find-links=/wheels -r requirements.txt && rm -rf /wheels
COPY src/ ./src/
COPY README.md ./
EXPOSE 8000
USER appuser
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD curl -f http://localhost:8000/health || exit 1
CMD ["uvicorn","src.app.main:app","--host","0.0.0.0","--port","8000"]
