"""Common functions used by the test files."""

import logging
import os
import subprocess
import time
from contextlib import nullcontext
from pathlib import Path

import requests

image_name = "arxiv-pdftotext"
PORT = 33031


def submit_pdf(
    service: str, pdf: str, mode: str | None = None, from_bucket: bool = False, post_timeout: int = 10
) -> tuple[None | str, str]:
    """Submit a pdf to the pdftotext service."""
    url = service + "/"
    with open(pdf, "rb") if not from_bucket else nullcontext() as data_fd:
        if mode is not None:
            url += f"?mode={mode}"
        if from_bucket:
            url += f"from_bucket?uri={pdf}"
            post_args = {"url": url}
        else:
            post_args = {"url": url, "files": {"file": data_fd}}

        while True:
            try:
                res = requests.post(**post_args, timeout=post_timeout, allow_redirects=False)
                status_code = res.status_code
                if status_code == 504:
                    logging.warning("Got 504 for %s", service)
                    time.sleep(1)
                    continue

                if status_code == 200:
                    return res.content.decode("utf-8"), ""
                else:
                    logging.warning("%s: status code %d, content: %s", url, status_code, res.content.decode("utf-8"))
                    return None, f"status code: {status_code}, details={res.content.decode('utf-8')}"

            except TimeoutError:
                logging.warning("%s: Connection timed out", pdf)
                return None, f"Connection timed out: {pdf}"

            except Exception:
                logging.warning("General exception with %s", pdf, exc_info=True)
                return None, f"General exception with {pdf}"


def build_docker(image_name: str):
    """Build the docker image."""
    # Make sure the container is the latest
    args = ["docker", "build", "--build-arg", f"USER_ID={os.getuid()}", "-t", image_name, "."]
    make = subprocess.run(args, encoding="utf-8", capture_output=True, check=False)
    if make.returncode != 0:
        logging.error(make.stdout)
        logging.error(make.stderr)
        raise Exception("Docker build failed")


def run_docker(container_name: str, mem: int | None = None):
    """Run the docker image."""
    url = f"http://localhost:{PORT}"
    dockerport = "8888"

    home = Path.home()
    # Start the container
    # fmt: off
    args = [
        "docker", "run", "--security-opt", "no-new-privileges=true", "--cpus", "1",
        "--privileged",  "--cgroupns=host",
        "-v", f"{home}/.config/gcloud/application_default_credentials.json:/tmp/credentials.json",
        "-e", "GOOGLE_APPLICATION_CREDENTIALS=/tmp/credentials.json",
        "-e", "GOOGLE_CLOUD_PROJECT=arxiv-development",
        "-e", "ACCEPTED_BUCKETS=arxiv-dev-submission",
        "-d", "-p", f"{PORT}:{dockerport}", "-e", f"PORT={dockerport}",
        "--name", container_name
    ]
    if mem:
        args.extend(["-e", f"MAX_ALLOWED_MEMORY={mem}"])
    args.append(image_name)
    docker = subprocess.run(args, encoding="utf-8", capture_output=True, check=False)
    if docker.returncode != 0:
        logging.error("arxiv-pdftotext container did not start")

    # Wait for the API to be ready
    for _ in range(60):  # retries for 60 seconds
        try:
            response = requests.get(url)
            if response.status_code == 200:
                break
        except requests.ConnectionError:
            pass
        time.sleep(1)
    else:
        with open(f"{container_name}-dead.log", "w", encoding="utf-8") as log:
            subprocess.call(["docker", "logs", container_name], stdout=log, stderr=log)
        subprocess.call(["docker", "stop", container_name])
        subprocess.call(["docker", "rm", container_name])
        raise RuntimeError("API did not start in time")
