# Backend image (api + worker share it). Same uv.lock as dev.
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim
RUN useradd --system --uid 10001 --create-home tss
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY alembic.ini ./
COPY alembic ./alembic
COPY config ./config
ENV PATH="/app/.venv/bin:$PATH" TSS_CONFIG_DIR=/app/config PYTHONUNBUFFERED=1
USER tss
EXPOSE 8000
CMD ["uvicorn", "tss.entrypoints.api:app", "--host", "0.0.0.0", "--port", "8000"]
