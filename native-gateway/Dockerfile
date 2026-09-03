FROM python:3.12.14-slim-trixie@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea AS builder

# uv 0.12.9, pinned to the official multi-platform image digest.
COPY --from=ghcr.io/astral-sh/uv@sha256:8b940d3a9d65bed080436972241af2e21c84b5e8c9193f7014ed71479ee795ff /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app
COPY native-gateway/pyproject.toml native-gateway/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

FROM python:3.12.14-slim-trixie@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PORT=8080

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY native-gateway/app ./app
RUN useradd --create-home --uid 10002 linative
USER linative
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --no-access-log"]
