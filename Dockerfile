FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

WORKDIR /srv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY app ./app

FROM python:3.13-slim-bookworm

WORKDIR /srv
RUN useradd --system --no-create-home appuser
COPY --from=builder /srv/.venv /srv/.venv
COPY app ./app
ENV PATH="/srv/.venv/bin:$PATH"
USER appuser
EXPOSE 8000

# PORT is honored for cloud platforms that inject it; defaults to 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
