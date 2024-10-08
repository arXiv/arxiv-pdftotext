FROM alpine:3.20
# Adapted from: https://github.com/frol/docker-alpine-python3/blob/master/Dockerfile
RUN apk add --no-cache poppler-utils python3 py3-pip bash
# Create a virtual environment
RUN python3 -m venv /venv
# Install packages in the virtual environment
RUN /venv/bin/pip3 install --upgrade pip setuptools flask
# Remove cache
RUN rm -r /root/.cache
# Copy the script
COPY webserver.py /webserver.py
# Run this when a container is started
CMD ["/venv/bin/python3", "/webserver.py"]
