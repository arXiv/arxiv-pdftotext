"""Test module for arxiv-pdftotext."""

import logging
import os
import subprocess
import time
from contextlib import nullcontext
from pathlib import Path

import pytest
import requests

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
            break


@pytest.fixture(scope="module")
def docker_container(request):
    """Build and start the docker image."""
    url = f"http://localhost:{PORT}"

    image_name = "arxiv-pdftotext"
    container_name = "test-arxiv-pdftotext"
    dockerport = "8888"

    subprocess.call(["docker", "kill", container_name])

    # Make sure the container is the latest
    args = ["docker", "build", "--build-arg", f"USER_ID={os.getuid()}", "-t", image_name, "."]
    make = subprocess.run(args, encoding="utf-8", capture_output=True, check=False)
    if make.returncode != 0:
        print(make.stdout)
        print(make.stderr)

    home = Path.home()
    # Start the container
    # fmt: off
    args = [
        "docker", "run", "--security-opt", "no-new-privileges=true", "--cpus", "1", "--rm",
            "-v", f"{home}/.config/gcloud/application_default_credentials.json:/tmp/credentials.json",
            "-e", "GOOGLE_APPLICATION_CREDENTIALS=/tmp/credentials.json",
            "-e", "GOOGLE_CLOUD_PROJECT=arxiv-development",
            "-e", "ACCEPTED_BUCKETS=arxiv-dev-submission",
            "-d", "-p", f"{PORT}:{dockerport}", "-e", f"PORT={dockerport}",
        "--name", container_name, image_name
    ]
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
        raise RuntimeError("API did not start in time")

    yield url

    # Stop the container after tests
    with open("arxiv-pdftotext.log", "w", encoding="utf-8") as log:
        subprocess.call(["docker", "logs", container_name], stdout=log, stderr=log)
    subprocess.call(["docker", "kill", container_name])


def test_pdftotext_simple_test(docker_container):
    """Simple test for pdftotext mode."""
    ret, _ = submit_pdf(docker_container, "tests/hello-world.pdf")
    assert ret == "hello world\n\n\x0c"


def test_pdftotext_pdf_with_accents(docker_container):
    """Accent test for pdftotext mode."""
    ret, _ = submit_pdf(docker_container, "tests/accents.pdf")
    assert ret == "éàôèù\n\n\x0c"


def test_pdf2txt_simple_test(docker_container):
    """Simple test for pdf2txt mode."""
    ret, _ = submit_pdf(docker_container, "tests/hello-world.pdf", mode="pdf2txt")
    assert ret == "hello world\n\n\x0c"


def test_pdf2txt_pdf_with_accents(docker_container):
    """Accent test for pdf2txt mode."""
    ret, _ = submit_pdf(docker_container, "tests/accents.pdf", mode="pdf2txt")
    assert ret == "éàôèù\n\n\x0c"


def test_paper_from_bucket(docker_container):
    """Test whether conversion from bucket returns something reasonable."""
    ret, _ = submit_pdf(
        docker_container, "gs://arxiv-dev-submission/3967079/3967079.pdf", from_bucket=True, post_timeout=120
    )
    # None indicates a internal server error
    assert ret is not None
    # Conversion failed out of some reason
    assert ret != ""
    # hopefully that doesn't change too quickly
    assert len(ret) == 27708


def test_not_pdf_file(docker_container):
    """Test whether non-pdf files are rejected."""
    ret, det = submit_pdf(docker_container, "tests/dummy-file.ps")
    assert ret is None
    assert det == 'status code: 400, details={"detail":"Input file is not a PDF file"}'


def test_incorrect_mode(docker_container):
    """Test whether unsupported modes are rejected."""
    ret, det = submit_pdf(docker_container, "tests/accents.pdf", mode="invalid_mode")
    assert ret is None
    assert det == 'status code: 400, details={"detail":"Invalid mode: invalid_mode"}'


def test_forbidden_bucket(docker_container):
    """Test whether forbidden bucket returns an error."""
    ret, det = submit_pdf(docker_container, "gs://some-other-bucket/foobar.pdf", from_bucket=True, post_timeout=120)
    assert ret is None
    assert det == 'status code: 400, details={"detail":"Input bucket not found in ACCEPTED_BUCKETS"}'
