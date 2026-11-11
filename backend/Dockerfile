FROM python:3.12-slim

# Install uv from official binary
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /uvx /bin/

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Install dependencies first for layer caching
COPY pyproject.toml README.md ./
RUN uv sync --no-dev --no-install-project

# Copy source code and install project
COPY src/ src/
COPY tools/ tools/
RUN uv sync --no-dev

EXPOSE 8000

CMD ["sh", "-c", "uv run uvicorn fw.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

