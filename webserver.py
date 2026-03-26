#!/usr/bin/env python3
"""Webserver-version of pdftotext (poppler utils) and pdf2txt (pdfminer.six)."""

import logging
import os
import shutil
import signal
import socket
import sys
import tempfile
from collections import namedtuple
from subprocess import PIPE, Popen, TimeoutExpired

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from google.cloud import storage  # type: ignore
from google.cloud.storage.blob import Blob  # type: ignore
from starlette.background import BackgroundTask

CGROUPNAME: str = "pdftotext"

ProgramEntry = namedtuple("ProgramEntry", ["priority", "progname"])
PARAM2PROGRAM_DEFAULTS: dict[str, ProgramEntry] = {
    "pdftotext": ProgramEntry(10, "pdftotext"),
    "pdf2txt": ProgramEntry(20, "/app/.venv/bin/pdf2txt.py"),  # this one is not in PATH, set explicitly!
}
PARAM2PROGRAM_FOUND: dict[str, ProgramEntry] = {}


load_dotenv()
# list of buckets like
# ACCEPTED_BUCKETS=foo-bar-baz,another-bucket
# would accept gs://foo-bar-baz/...
# if NOT set, *ALL* buckets are allowed!
ACCEPTED_BUCKETS_STRING: str | None = os.getenv("ACCEPTED_BUCKETS")
ACCEPTED_BUCKETS: list[str] | None = None
if ACCEPTED_BUCKETS_STRING is None:
    ACCEPTED_BUCKETS = None
else:
    ACCEPTED_BUCKETS = [bucket.lower() for bucket in ACCEPTED_BUCKETS_STRING.split(",")]

for k, v in PARAM2PROGRAM_DEFAULTS.items():
    logging.debug(f"Testing for {v.progname}")
    if shutil.which(v.progname) is not None:
        logging.debug(f"{v.progname} found")
        PARAM2PROGRAM_FOUND[k] = v
    else:
        logging.warning(f"{v.progname} not found")

logging.info("ACCEPTED_BUCKETS: %s", ACCEPTED_BUCKETS)
logging.info("PARAM2PROGRAM_FOUND: %s", PARAM2PROGRAM_FOUND)
app = FastAPI()


def check_input_file(uri: str) -> None:
    """Check if input file satisfies acceptability conditions."""
    # check for .pdf extension
    uri_lower = uri.lower()
    if not uri_lower.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Input file is not a PDF file")
    if uri_lower.startswith("gs://"):
        if ACCEPTED_BUCKETS is not None:
            # get bucket from uri
            bucket_name = uri_lower.split("/")[2]
            if bucket_name not in ACCEPTED_BUCKETS:
                raise HTTPException(status_code=400, detail="Input bucket not found in ACCEPTED_BUCKETS")


def convert_file(temp_dir: str, file_path_in: str, mode: str, convert_timeout: int, params: str) -> FileResponse:
    """Convert the given PDF files to text."""
    file_path_out: str = file_path_in + ".txt"
    logging.debug(f"Entering convert_file: PARAM2PROGRAM_FOUND.keys: {PARAM2PROGRAM_FOUND.keys()}")
    if mode not in PARAM2PROGRAM_FOUND.keys() and mode != "auto":
        raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}")

    modes_to_be_tried: list[str] = []
    if mode == "auto":
        # add the keys sorted according to their priority
        modes_to_be_tried.extend([k for k, v in sorted(PARAM2PROGRAM_FOUND.items(), key=lambda k_v: k_v[1].priority)])
    elif mode in PARAM2PROGRAM_FOUND.keys():
        modes_to_be_tried.append(mode)
    # no else needed, already checked above

    logging.debug(f"mode={mode} prog_to_be_tried={modes_to_be_tried}")

    for mode in modes_to_be_tried:
        cmd: list[str] = ["cgexec", "-g", f"memory:{CGROUPNAME}", PARAM2PROGRAM_FOUND[mode].progname]

        logging.debug("mode=%s file_path_in=%s file_path_out=%s params=%s", mode, file_path_in, file_path_out, params)
        if params:
            cmd.extend(params.split())
        if mode == "pdf2txt":
            cmd.extend(["--outfile", file_path_out, file_path_in])
        elif mode == "pdftotext":
            cmd.extend([file_path_in, file_path_out])
        else:
            raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}")

        logging.debug(f"Running {cmd}")
        p = Popen(cmd, stdout=PIPE, stderr=PIPE)
        logging.debug("Starting conversion process")
        try:
            out, err = p.communicate(timeout=convert_timeout)
        except TimeoutExpired:
            logging.warning(f"Conversion with mode {mode} timed out after {convert_timeout}secs")
            p.kill()
            out, err = p.communicate()

        logging.debug(f"stdout={out.decode('utf-8')}, stderr={err.decode('utf-8')}")
        logging.debug("Conversion process finished")

        if p.returncode == 0:
            return FileResponse(file_path_out, background=BackgroundTask(shutil.rmtree, temp_dir))
        elif p.returncode < 0:
            logging.warning(f"Conversion with mode {mode} was killed with {signal.Signals(-p.returncode).name}.")
        else:
            logging.warning(f"Conversion with mode {mode} failed, exitcode: {p.returncode}: {err.decode('utf-8')}")

    # if we are still here, all modes have failed
    shutil.rmtree(temp_dir)
    raise HTTPException(status_code=500, detail=f"Failed to convert {os.path.basename(file_path_in)}")


@app.get("/", response_class=HTMLResponse)
def healthcheck() -> str:
    """Health check endpoint."""
    return "<h1>All good!</h1>"


@app.post("/from_bucket")
def handle_file_from_bucket(uri: str, mode: str = "auto", convert_timeout: int = 180, params: str = "") -> FileResponse:
    """Entry point for API call to convert pdf via bucket url to text."""
    check_input_file(uri)
    temp_dir = tempfile.mkdtemp()
    try:
        client = storage.Client()
        blob = Blob.from_string(uri, client=client)
        file_path_in = os.path.join(temp_dir, os.path.basename(blob.name))
        blob.download_to_filename(file_path_in)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to obtain file from bucket: {e}")
    return convert_file(temp_dir, file_path_in, mode, convert_timeout, params)


@app.post("/")
def handle_file(
    file: UploadFile = File(...), mode: str = "auto", convert_timeout: int = 180, params: str = ""
) -> FileResponse:
    """Entry point for API call to convert pdf to text."""
    if file.filename is None:
        raise HTTPException(status_code=400, detail="No filename provided.")
    check_input_file(file.filename)
    temp_dir = tempfile.mkdtemp()
    file_path_in = os.path.join(temp_dir, file.filename)
    try:
        with open(file_path_in, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception:
        raise HTTPException(status_code=500, detail="Something went wrong")
    finally:
        file.file.close()

    return convert_file(temp_dir, file_path_in, mode, convert_timeout, params)


if __name__ == "__main__":
    host = "0.0.0.0"
    port = 8888
    ip = socket.gethostbyname(socket.gethostname())
    print("start listening:", ip, host + ":" + str(port), file=sys.stderr)
