#!/usr/bin/env python3
"""Webserver-version of pdftotext (poppler utils) and pdf2txt (pdfminer.six)."""

import logging
import os
import shutil
import socket
import sys
import tempfile
from subprocess import PIPE, Popen, TimeoutExpired

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from google.cloud import storage
from google.cloud.storage.blob import Blob
from starlette.background import BackgroundTask

from config import config, ProgramEntry

PROGRAMS_FOUND: dict[str, ProgramEntry] = {}

for k, v in config.program_configs.items():
    logging.debug(f"Testing for {v.progname}")
    if shutil.which(v.progname) is not None:
        logging.debug(f"{v.progname} found")
        PROGRAMS_FOUND[k] = v
    else:
        logging.warning(f"{v.progname} not found")

logging.info("ACCEPTED_BUCKETS: %s", config.accepted_buckets)
logging.info("PROGRAMS_FOUND: %s", PROGRAMS_FOUND)

app = FastAPI()


def check_input_file(uri: str) -> None:
    uri_lower = uri.lower()

    if not uri_lower.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Input file is not a PDF file")

    if uri_lower.startswith("gs://") and config.accepted_buckets is not None:
        bucket_name = uri_lower.split("/")[2]

        if bucket_name not in config.accepted_buckets:
            raise HTTPException(
                status_code=400, detail="Input bucket not found in ACCEPTED_BUCKETS"
            )


def get_ordered_list_of_modes(mode: str) -> list[str]:
    if mode == "auto":
        return [
            k for k, v in sorted(PROGRAMS_FOUND.items(), key=lambda x: x[1].priority)
        ]
    elif mode in PROGRAMS_FOUND:
        return [mode]
    else:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}")


def get_command_for_mode(
    mode: str, progname: str, file_in: str, file_out: str, params: str
) -> list[str]:
    base = ["cgexec", "-g", f"memory:{config.cgroup_name}", progname]

    if params:
        base.extend(params.split())

    if mode == "pdf2txt":
        return [*base, "--outfile", file_out, file_in]
    elif mode == "pdftotext":
        return [*base, file_in, file_out]
    else:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}")


def convert_file(
    temp_dir: str, file_path_in: str, mode: str, convert_timeout: int, params: str
) -> FileResponse:
    file_path_out = f"{file_path_in}.txt"

    modes = get_ordered_list_of_modes(mode)

    for current_mode in modes:
        prog = PROGRAMS_FOUND[current_mode]
        cmd = get_command_for_mode(
            current_mode, prog.progname, file_path_in, file_path_out, params
        )

        try:
            logging.debug(f"Running: {' '.join(cmd)}")
            p = Popen(cmd, stdout=PIPE, stderr=PIPE)
            out, err = p.communicate(timeout=convert_timeout)

            if p.returncode == 0:
                return FileResponse(
                    file_path_out, background=BackgroundTask(shutil.rmtree, temp_dir)
                )
            logging.warning(
                f"{current_mode} failed with code {p.returncode}: {err.decode().strip()}"
            )
        except TimeoutExpired:
            p.kill()
            logging.warning(f"{current_mode} timed out.")
        except Exception as e:
            logging.error(f"Unexpected error with {current_mode}: {e}")

    # if all modes failed
    shutil.rmtree(temp_dir)
    raise HTTPException(status_code=500, detail=f"Failed to convert {os.path.basename(file_path_in)}")


@app.get("/", response_class=HTMLResponse)
def healthcheck() -> str:
    """Health check endpoint."""
    return "<h1>All good!</h1>"


@app.post("/from_bucket")
def handle_file_from_bucket(
    uri: str, mode: str = "auto", convert_timeout: int = 180, params: str = ""
) -> FileResponse:
    """Entry point for API call to convert pdf via bucket url to text."""
    check_input_file(uri)
    temp_dir = tempfile.mkdtemp()
    try:
        client = storage.Client()
        blob = Blob.from_string(uri, client=client)
        file_path_in = os.path.join(temp_dir, os.path.basename(blob.name))
        blob.download_to_filename(file_path_in)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to obtain file from bucket: {e}"
        )
    return convert_file(temp_dir, file_path_in, mode, convert_timeout, params)


@app.post("/")
def handle_file(
    file: UploadFile = File(...),
    mode: str = "auto",
    convert_timeout: int = 180,
    params: str = "",
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
