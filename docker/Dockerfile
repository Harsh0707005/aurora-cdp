# Aurora CDP (aurora_cdp) runtime image: API + UI, job runner and CLI share this image.
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    AURORA_WORKSPACE=/data/aurora
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
COPY aurora_cdp ./aurora_cdp
RUN pip install --upgrade pip && pip install -e .
RUN mkdir -p /data/aurora /data/outputs && useradd -m aurora && chown -R aurora /data /app
USER aurora
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -fsS http://localhost:8000/health || exit 1
CMD ["uvicorn", "aurora_cdp.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
