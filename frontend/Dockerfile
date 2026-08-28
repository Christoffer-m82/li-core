FROM python:3.12-slim AS builder
WORKDIR /build
COPY frontend/pyproject.toml .
COPY frontend/app ./app
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
WORKDIR /app
COPY --from=builder /install /usr/local
COPY frontend/app ./app
COPY frontend/static ./static
RUN useradd --create-home --uid 10001 liweb && chown -R liweb:liweb /app
USER liweb
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
