FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
WORKDIR /app
COPY native-gateway/pyproject.toml ./
COPY native-gateway/app ./app
RUN pip install --no-cache-dir . && useradd --create-home --uid 10002 linative
USER linative
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --no-access-log"]
