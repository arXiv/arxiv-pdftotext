FROM alpine:3.20

# Create a non-root user without a group
RUN adduser -S appuser
# Adapted from: https://github.com/frol/docker-alpine-python3/blob/master/Dockerfile
RUN apk add --no-cache poppler-utils python3 py3-pip bash

# Create a virtual environment
RUN python3 -m venv /venv && \
    # Install package management tools
    /venv/bin/pip3 install --no-cache-dir --upgrade pip setuptools && \
    # Install application dependencies
    /venv/bin/pip3 install --no-cache-dir \
    flask==3.0.3 \
    gunicorn==23.0.0 && \
    # Remove cache
    rm -rf /root/.cache

# Copy the script
COPY webserver.py /webserver.py

# Switch to non-root user
USER appuser
# Run this when a container is started
CMD ["/venv/bin/gunicorn", "--bind", "0.0.0.0:8888", "webserver:app"]
