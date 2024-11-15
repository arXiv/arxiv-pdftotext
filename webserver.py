#!/usr/bin/env python3
"""Webserver-version of pdftotext (poppler utils) and pdf2txt (pdfminer.six)."""

import logging
import os
import shutil
import socket
import sys
from subprocess import PIPE, Popen
from tempfile import TemporaryDirectory

from flask import Flask, request, send_file

# map mode parameters to programs
PARAM2PROGRAM_DEFAULTS = {
    "pdftotext": "pdftotext",
    "pdf2txt": "pdf2txt.py",
}
PARAM2PROGRAM_FOUND = {}
app = Flask(__name__)

for k, v in PARAM2PROGRAM_DEFAULTS.items():
    if shutil.which(v) is not None:
        PARAM2PROGRAM_FOUND[k] = v


@app.route("/", methods=["GET"])
def healthcheck() -> str:
    """Health check endpoint."""
    return "<h1>All good!</h1>"


@app.route("/", methods=["POST"])
def handle_file():
    """Entry point for API call to convert pdf to text."""
    with TemporaryDirectory() as temp_dir:
        if "file" in request.files:
            if len(request.files) != 1:
                return f"You must upload one PDF file for processing (len(request.files)={len(request.files)})", 400

            files_dict = request.files.to_dict()

            for key in files_dict:
                file = files_dict[key]
                file_path_in = os.path.join(temp_dir, file.filename)

                if not file_path_in.lower().endswith(".pdf"):
                    return f"Only .pdf files are allowed (file_path_in={file_path_in})", 400

                file.save(file_path_in)
        else:  # PDF provided in binary (application/octet-stream), not as a file
            file_path_in = os.path.join(temp_dir, "unnamed.pdf")
            data = request.stream.read()
            with open(file_path_in, "wb") as f:
                f.write(data)
            sys.stdout.flush()

        file_path_out = file_path_in + ".txt"
        mode = request.values.get("mode")
        if mode is None:
            mode = "pdftotext"
        if mode not in PARAM2PROGRAM_FOUND.keys():
            return f"Program for mode {mode} not found", 400
        cmd = [PARAM2PROGRAM_FOUND[mode]]

        params = request.values.get("params")

        logging.debug("mode=%s file_path_in=%s file_path_out=%s params=%s", mode, file_path_in, file_path_out, params)
        if params:
            cmd.extend(params.split())
        if mode == "pdf2txt":
            cmd.extend(["--outfile", file_path_out, file_path_in])
        elif mode == "pdftotext":
            cmd.extend([file_path_in, file_path_out])
        else:
            return f"Invalid mode: {mode}", 400

        p = Popen(cmd, stdout=PIPE, stderr=PIPE)
        out, err = p.communicate()

        if p.returncode == 0:
            return send_file(file_path_out)
        else:
            return f"Failed to execute '{mode}' process:\n\n" + err.decode("utf-8"), 500

        return send_file(file_path_out)

if __name__ == "__main__":
    host = "0.0.0.0"
    port = 8888
    ip = socket.gethostbyname(socket.gethostname())
    print("start listening:", ip, host + ":" + str(port), file=sys.stderr)
