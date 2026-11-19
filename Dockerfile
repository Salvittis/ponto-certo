# syntax=docker/dockerfile:1
FROM python:3.12-alpine@sha256:c5ba3deef00c7758561a0f03c26f44f10589263d40e732b8748e0d1f38f6dd89
ARG APP_REVISION=development
LABEL org.opencontainers.image.source="https://github.com/Salvittis/ponto-certo" \
      org.opencontainers.image.title="Ponto Certo API" \
      org.opencontainers.image.revision=$APP_REVISION
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    APP_REVISION=$APP_REVISION PORT=8000
WORKDIR /app
RUN apk upgrade --no-cache \
    && addgroup -g 10001 pontocerto \
    && adduser -D -H -u 10001 -G pontocerto -s /sbin/nologin pontocerto
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY --chown=10001:10001 app/ ./app/
COPY --chown=10001:10001 base/ ./base/
COPY --chown=10001:10001 dados/fixtures/ ./dados/fixtures/
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
