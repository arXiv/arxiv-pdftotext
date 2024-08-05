FROM alpine:3.20
# Adapted from: https://github.com/frol/docker-alpine-python3/blob/master/Dockerfile
RUN apk add --no-cache poppler-utils python3 py3-pip bash && \
    pip3 install --break-system-packages --upgrade pip setuptools flask && \
    if [ ! -e /usr/bin/pip ]; then ln -s pip3 /usr/bin/pip ; fi && \
    if [[ ! -e /usr/bin/python ]]; then ln -sf /usr/bin/python3 /usr/bin/python; fi && \
    rm -r /root/.cache

COPY webserver.py /webserver.py

CMD ["/webserver.py"]
