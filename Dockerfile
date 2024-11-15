FROM ghcr.io/astral-sh/uv:python3.12-alpine

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Create a non-root user without a group
RUN adduser -S appuser

# Add poppler utils for pdftotext
RUN apk add --no-cache poppler-utils

# Copy the script and uv config
COPY webserver.py /app/webserver.py
COPY uv.lock /app/uv.lock
COPY pyproject.toml /app/pyproject.toml

# Install the project's dependencies using the lockfile and settings
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Switch to non-root user
USER appuser

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

# Run this when a container is started
CMD ["hypercorn", "--bind", "0.0.0.0:8888", "webserver:app"]
