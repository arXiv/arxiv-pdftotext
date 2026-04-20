#!/usr/bin/env python3
"""Webserver-version of pdftotext (poppler utils) and pdf2txt (pdfminer.six)."""

import logging
import shutil
import socket
import sys
import os

import anyio.to_thread
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from contextlib import asynccontextmanager

from config import get_config, Config, ProgramEntry
from api import text_extraction_router

from subprocess import TimeoutExpired
from exceptions import (
    BadRequest,
    ExtractionFailure,
)

logger = logging.getLogger(__name__)


def detect_programs(config: Config) -> list[ProgramEntry]:
    """Scans the system for extraction program binaries defined in config. Sorts by priority."""
    found = []
    for k, v in config.program_configs.items():
        if shutil.which(v.name) or (v.path and os.path.exists(v.path)):
            found.append(v)
        else:
            logger.warning(f"Program {v.name} not found at path: {v.path}")

    return sorted(found, key=lambda x: x.priority)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App setup which runs once at startup."""
    config = get_config()

    # get threadpool capacity
    limiter = anyio.to_thread.current_default_thread_limiter()
    logger.info(f"Threadpool capacity: {limiter.total_tokens}")

    logger.info("Accepted buckets: %s", config.accepted_buckets)

    app.state.programs = detect_programs(config)

    if not app.state.programs:
        logger.critical("No extraction engines found!")
        sys.exit(1)

    logger.info(f"Engines detected: {[prog.name for prog in app.state.programs]}")

    yield


def add_exception_handlers(app: FastAPI):
    @app.exception_handler(BadRequest)
    async def bad_request_handler(request: Request, exc: BadRequest):
        return JSONResponse(status_code=400, content={"detail": "Bad request"})

    @app.exception_handler(TimeoutExpired)
    async def timeout_handler(request: Request, exc: TimeoutExpired):
        return JSONResponse(status_code=504, content={"detail": "Timeout expired"})

    @app.exception_handler(ExtractionFailure)
    async def failure_handler(request: Request, exc: ExtractionFailure):
        return JSONResponse(status_code=422, content={"detail": "Extraction failed"})


app = FastAPI(lifespan=lifespan)
app.include_router(text_extraction_router)
add_exception_handlers(app)


@app.get("/", response_class=HTMLResponse)
async def healthcheck() -> str:
    """Health check endpoint."""
    return "<h1>All good!</h1>"


if __name__ == "__main__":
    host = "0.0.0.0"
    port = 8888
    ip = socket.gethostbyname(socket.gethostname())
    print("start listening:", ip, host + ":" + str(port), file=sys.stderr)
