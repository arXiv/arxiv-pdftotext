#!/usr/bin/env python3
"""Webserver-version of pdftotext (poppler utils) and pdf2txt (pdfminer.six)."""

import logging
import os
import shutil
import socket
import sys
import tempfile
from subprocess import PIPE, Popen

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

PARAM2PROGRAM_DEFAULTS = {
    "pdftotext": "pdftotext",
    "pdf2txt": "pdf2txt.py",
}
PARAM2PROGRAM_FOUND = {}

app = FastAPI()

for k, v in PARAM2PROGRAM_DEFAULTS.items():
    if shutil.which(v) is not None:
        PARAM2PROGRAM_FOUND[k] = v


@app.get("/")
def healthcheck() -> str:
    """Health check endpoint."""
    return "<h1>All good!</h1>"


@app.post("/")
def handle_file(file: UploadFile = File(...), mode: str = "pdftotext", params: str = ""):
    """Entry point for API call to convert pdf to text."""
    temp_dir = tempfile.mkdtemp()
    file_path_in = os.path.join(temp_dir, file.filename)
    if not file_path_in.lower().endswith(".pdf"):
        return f"Only .pdf files are allowed (file_path_in={file_path_in})", 400
    try:
        with open(file_path_in, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception:
        raise HTTPException(status_code=500, detail="Something went wrong")
    finally:
        file.file.close()

    file_path_out = file_path_in + ".txt"
    if mode not in PARAM2PROGRAM_FOUND.keys():
        return f"Program for mode {mode} not found", 400
    cmd = PARAM2PROGRAM_FOUND[mode]

    logging.debug("mode=%s file_path_in=%s file_path_out=%s params=%s", mode, file_path_in, file_path_out, params)
    args = []
    if params:
        args = params.split()
    if mode == "pdf2txt":
        args.extend(["--outfile", file_path_out, file_path_in])
    elif mode == "pdftotext":
        args.extend([file_path_in, file_path_out])
    else:
        return f"Invalid mode: {mode}", 400

    logging.debug(f"Running {[cmd, *args]}")
    p = Popen([cmd, *args], stdout=PIPE, stderr=PIPE)
    logging.debug("Starting conversion process")
    out, err = p.communicate()
    logging.debug(f"stdout={out}, stderr={err}")
    print("Conversion process finished")

    if p.returncode == 0:
        return FileResponse(file_path_out, background=BackgroundTask(shutil.rmtree, temp_dir))
    else:
        shutil.rmtree(temp_dir)
        return f"Failed to execute '{mode}' process:\n\n" + err.decode("utf-8"), 500


if __name__ == "__main__":
    host = "0.0.0.0"
    port = 8888
    ip = socket.gethostbyname(socket.gethostname())
    print("start listening:", ip, host + ":" + str(port), file=sys.stderr)
