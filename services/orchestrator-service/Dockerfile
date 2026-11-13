FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SERVICE_NAME=orchestrator-service \
    APP_VERSION=0.1.0

WORKDIR /app

COPY services/orchestrator-service/requirements.txt /tmp/requirements.txt

RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt

COPY shared/python/devsphere-common /tmp/devsphere-common

RUN python -m pip install --no-cache-dir /tmp/devsphere-common \
    && rm -rf /tmp/devsphere-common

COPY services/orchestrator-service/app ./app
COPY services/orchestrator-service/migrations ./migrations
COPY services/orchestrator-service/alembic.ini .

RUN mkdir -p /app/artifacts && chown -R 10001:10001 /app/artifacts

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
