#!/usr/bin/env python3
import os
import socket
import sys
from subprocess import Popen, PIPE
from tempfile import TemporaryDirectory

from flask import Flask, request, send_file

app = Flask(__name__)


@app.route("/", methods=["POST"])
def handle_file():
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
        cmd = ["/usr/bin/pdftotext"]
        params = request.values.get("params")
        if params:
            cmd.extend(params.split())
        cmd.extend([file_path_in, file_path_out])

        p = Popen(cmd, stdout=PIPE, stderr=PIPE)
        out, err = p.communicate()

        if p.returncode == 0:
            return send_file(file_path_out)
        else:
            return "Failed to execute 'pdftotext' process:\n\n" + err.decode("utf-8"), 500

        return send_file(file_path_out)


if __name__ == "__main__":
    host = "0.0.0.0"
    port = 8888
    ip = socket.gethostbyname(socket.gethostname())
    print("start listening:", ip, host + ":" + str(port), file=sys.stderr)
