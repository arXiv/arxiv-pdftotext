"""Test module for arxiv-pdftotext under low memory setup."""

import subprocess

import pytest
from common import PORT, run_docker, submit_pdf


@pytest.fixture(scope="module")
def fx_run_docker_lowmem(request):
    """Fixture to start the docker image with low memory limit."""
    container_name = "test-arxiv-pdftotext-lowmem"
    subprocess.call(["docker", "stop", container_name])
    subprocess.call(["docker", "rm", container_name])
    run_docker(container_name, mem=30000)  # ridiculously low memory of 3k

    yield f"http://localhost:{PORT}"

    # Stop the container after tests
    with open("arxiv-pdftotext-lowmem.log", "w", encoding="utf-8") as log:
        subprocess.call(["docker", "logs", container_name], stdout=log, stderr=log)
    subprocess.call(["docker", "stop", container_name])
    subprocess.call(["docker", "rm", container_name])


def test_memory_limit_kill(fx_build_docker, fx_run_docker_lowmem):
    """Test that in low-memory situation conversions are killed."""
    ret, det = submit_pdf(fx_run_docker_lowmem, "tests/hello-world.pdf")
    assert ret is None
    assert det == 'status code: 500, details={"detail":"Failed to convert hello-world.pdf"}'
