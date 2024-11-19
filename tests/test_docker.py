"""Test module for arxiv-pdftotext."""

import logging
import subprocess
import time

import pytest
import requests

PORT = 33031


def submit_pdf(service: str, pdf: str, mode: str | None = None, post_timeout: int = 10) -> None | str:
    """Submit a pdf to the pdftotext service."""
    url = service + "/"
    with open(pdf, "rb") as data_fd:
        if mode is not None:
            url += f"?mode={mode}"
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
                    return res.content.decode("utf-8")
                else:
                    logging.warning("%s: status code %d", url, status_code)

            except TimeoutError:
                logging.warning("%s: Connection timed out", pdf)

            except Exception as exc:
                logging.warning("%s: %s", pdf, str(exc))
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
    args = ["docker", "build", "-t", image_name, "."]
    make = subprocess.run(args, encoding="utf-8", capture_output=True, check=False)
    if make.returncode != 0:
        print(make.stdout)
        print(make.stderr)

    # Start the container
    # fmt: off
    args = [
        "docker", "run", "--security-opt", "no-new-privileges=true", "--cpus", "1", "--rm",
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
    ret = submit_pdf(docker_container, "tests/hello-world.pdf")
    assert ret == "hello world\n\n\x0c"


def test_pdftotext_pdf_with_accents(docker_container):
    """Accent test for pdftotext mode."""
    ret = submit_pdf(docker_container, "tests/accents.pdf")
    assert ret == "éàôèù\n\n\x0c"


def test_pdf2txt_simple_test(docker_container):
    """Simple test for pdf2txt mode."""
    ret = submit_pdf(docker_container, "tests/hello-world.pdf", mode="pdf2txt")
    assert ret == "hello world\n\n\x0c"


def test_pdf2txt_pdf_with_accents(docker_container):
    """Accent test for pdf2txt mode."""
    ret = submit_pdf(docker_container, "tests/accents.pdf", mode="pdf2txt")
    assert ret == "éàôèù\n\n\x0c"
