# Use a lightweight python image matching local environment version
FROM python:3.12-slim AS builder

# Set shell and environment variables for optimized builds
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PYTHON_PREFERENCE=only-system

# Copy uv binary from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Install dependencies first using cache mounts for speed and efficiency
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Copy the rest of the application
COPY . .

# Sync the project itself
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


# Final stage to keep the production image tiny and secure
FROM python:3.12-slim

WORKDIR /app

# Copy the built virtual environment and application code
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/app /app/app

# Prepend virtual environment path to find uvicorn and python modules
ENV PATH="/app/.venv/bin:$PATH"

# Expose port (metadata only)
EXPOSE 8000

# Start command: Use absolute path to bypass $PATH issues, and sh -c to expand $PORT
CMD ["sh", "-c", "/app/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]