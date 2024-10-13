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

# Install the project's dependencies using the lockfile and settings
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Copy the script
COPY webserver.py /app/webserver.py

# Switch to non-root user
USER appuser

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

# Run this when a container is started
CMD ["gunicorn", "--bind", "0.0.0.0:8888", "webserver:app"]
