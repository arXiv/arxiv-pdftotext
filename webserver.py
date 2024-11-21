#!/usr/bin/env python3
"""Webserver-version of pdftotext (poppler utils) and pdf2txt (pdfminer.six)."""

import logging
import os
import shutil
import socket
import sys
import tempfile
from subprocess import PIPE, Popen

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from google.cloud import storage
from google.cloud.storage.blob import Blob
from starlette.background import BackgroundTask

CGROUPNAME = "pdftotext"

PARAM2PROGRAM_DEFAULTS = {
    "pdftotext": "pdftotext",
    "pdf2txt": "pdf2txt.py",
}
PARAM2PROGRAM_FOUND = {}

load_dotenv()
# list of buckets like
# ACCEPTED_BUCKETS=foo-bar-baz,another-bucket
# would accept gs://foo-bar-baz/...
# if NOT set, *ALL* buckets are allowed!
ACCEPTED_BUCKETS_STRING = os.getenv("ACCEPTED_BUCKETS")
if ACCEPTED_BUCKETS_STRING is None:
    ACCEPTED_BUCKETS = None
else:
    ACCEPTED_BUCKETS = [bucket.lower() for bucket in ACCEPTED_BUCKETS_STRING.split(",")]

app = FastAPI()

for k, v in PARAM2PROGRAM_DEFAULTS.items():
    if shutil.which(v) is not None:
        PARAM2PROGRAM_FOUND[k] = v


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


def convert_file(temp_dir: str, file_path_in: str, mode: str, params: str):
    """Convert the given PDF files to text."""
    file_path_out = file_path_in + ".txt"
    if mode not in PARAM2PROGRAM_FOUND.keys():
        raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}")
    cmd = ["cgexec", "-g", f"memory:{CGROUPNAME}", PARAM2PROGRAM_FOUND[mode]]

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
    out, err = p.communicate()
    logging.debug(f"stdout={out}, stderr={err}")
    logging.debug("Conversion process finished")

    if p.returncode == 0:
        return FileResponse(file_path_out, background=BackgroundTask(shutil.rmtree, temp_dir))
    else:
        shutil.rmtree(temp_dir)
        raise HTTPException(status_code=500, detail=f"Failed to execute '{mode}' process:\n\n" + err.decode("utf-8"))


@app.get("/", response_class=HTMLResponse)
def healthcheck() -> str:
    """Health check endpoint."""
    return "<h1>All good!</h1>"


@app.post("/from_bucket")
def handle_file_from_bucket(uri: str, mode: str = "pdftotext", params: str = ""):
    """Entry point for API call to convert pdf via bucket url to text."""
    check_input_file(uri)
    temp_dir = tempfile.mkdtemp()
    try:
        client = storage.Client()
        blob = Blob.from_string(uri, client=client)
        file_path_in = os.path.join(temp_dir, os.path.basename(blob.name))
        blob.download_to_filename(file_path_in)
    except Exception as e:
        return f"Failed to obtain file from bucket: {e}", 500
    return convert_file(temp_dir, file_path_in, mode, params)


@app.post("/")
def handle_file(file: UploadFile = File(...), mode: str = "pdftotext", params: str = ""):
    """Entry point for API call to convert pdf to text."""
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

    return convert_file(temp_dir, file_path_in, mode, params)


if __name__ == "__main__":
    host = "0.0.0.0"
    port = 8888
    ip = socket.gethostbyname(socket.gethostname())
    print("start listening:", ip, host + ":" + str(port), file=sys.stderr)
