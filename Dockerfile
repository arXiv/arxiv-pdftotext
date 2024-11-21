FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
ARG USER_ID=1000

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Create a non-root user without a group
RUN adduser --system --uid $USER_ID appuser

# Add poppler utils for pdftotext
RUN apt-get update && apt install -y sudo cgroup-tools poppler-utils && rm -rf /var/lib/apt/lists/*

# Copy the script and uv config
COPY webserver.py /app/webserver.py
COPY uv.lock /app/uv.lock
COPY pyproject.toml /app/pyproject.toml
COPY run-me.sh /app/run-me.sh

# Install the project's dependencies using the lockfile and settings
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Switch to non-root user
# this is done in run-me.sh
# USER appuser

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

# Run this when a container is started
CMD ["/app/run-me.sh"]
