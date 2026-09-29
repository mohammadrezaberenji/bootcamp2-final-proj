FROM nexus.server:8083/library/python:3.12-slim

# Python/container runtime settings
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install curl for Docker HEALTHCHECK
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies separately for better Docker layer caching
COPY requirements.txt .

RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY . /app/backend

# Create and use a non-root user
RUN groupadd --gid 10001 app \
    && useradd \
       --uid 10001 \
       --gid app \
       --shell /usr/sbin/nologin \
       --create-home \
       app \
    && chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK \
    --interval=30s \
    --timeout=5s \
    --start-period=15s \
    --retries=3 \
    CMD curl --fail --silent http://localhost:8000/health/live || exit 1

CMD ["uvicorn", "backend.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--proxy-headers", \
     "--no-access-log"]
