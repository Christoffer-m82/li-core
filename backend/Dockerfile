FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

RUN groupadd --system li && useradd --system --gid li --home-dir /app li
WORKDIR /app

COPY backend/pyproject.toml ./
COPY backend/app ./app
COPY agents /agents
RUN pip install --upgrade pip && pip install .

USER li
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips='*' --no-access-log"]
