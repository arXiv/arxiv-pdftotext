"""Test module for arxiv-pdftotext."""

import os
import subprocess

import pytest
from common import PORT, run_docker, submit_pdf

IN_GITHUB_ACTIONS = os.getenv("GITHUB_ACTIONS") == "true"


@pytest.fixture(scope="module")
def fx_run_docker(request):
    """Fixture to start the docker image."""
    container_name = "test-arxiv-pdftotext"
    subprocess.call(["docker", "stop", container_name])
    subprocess.call(["docker", "rm", container_name])
    run_docker(container_name)

    yield f"http://localhost:{PORT}"

    # Stop the container after tests
    with open("arxiv-pdftotext.log", "w", encoding="utf-8") as log:
        subprocess.call(["docker", "logs", container_name], stdout=log, stderr=log)
    subprocess.call(["docker", "stop", container_name])
    subprocess.call(["docker", "rm", container_name])


def test_pdftotext_simple_test(fx_build_docker, fx_run_docker):
    """Simple test for pdftotext mode."""
    ret, _ = submit_pdf(fx_run_docker, "tests/hello-world.pdf")
    assert ret == "hello world\n\n\x0c"


def test_pdftotext_pdf_with_accents(fx_build_docker, fx_run_docker):
    """Accent test for pdftotext mode."""
    ret, _ = submit_pdf(fx_run_docker, "tests/accents.pdf")
    assert ret == "éàôèù\n\n\x0c"


def test_pdf2txt_simple_test(fx_build_docker, fx_run_docker):
    """Simple test for pdf2txt mode."""
    ret, _ = submit_pdf(fx_run_docker, "tests/hello-world.pdf", mode="pdf2txt")
    assert ret == "hello world\n\n\x0c"


def test_pdf2txt_pdf_with_accents(fx_build_docker, fx_run_docker):
    """Accent test for pdf2txt mode."""
    ret, _ = submit_pdf(fx_run_docker, "tests/accents.pdf", mode="pdf2txt")
    assert ret == "éàôèù\n\n\x0c"


@pytest.mark.skipif(IN_GITHUB_ACTIONS, reason="Test doesn't work in Github Actions.")
def test_paper_from_bucket(fx_build_docker, fx_run_docker):
    """Test whether conversion from bucket returns something reasonable."""
    ret, _ = submit_pdf(
        fx_run_docker, "gs://arxiv-dev-submission/3967079/3967079.pdf", from_bucket=True, post_timeout=120
    )
    # None indicates a internal server error
    assert ret is not None
    # Conversion failed out of some reason
    assert ret != ""
    # hopefully that doesn't change too quickly
    assert len(ret) == 27708


def test_not_pdf_file(fx_build_docker, fx_run_docker):
    """Test whether non-pdf files are rejected."""
    ret, det = submit_pdf(fx_run_docker, "tests/dummy-file.ps")
    assert ret is None
    assert det == 'status code: 400, details={"detail":"Input file is not a PDF file"}'


def test_incorrect_mode(fx_build_docker, fx_run_docker):
    """Test whether unsupported modes are rejected."""
    ret, det = submit_pdf(fx_run_docker, "tests/accents.pdf", mode="invalid_mode")
    assert ret is None
    assert det == 'status code: 400, details={"detail":"Invalid mode: invalid_mode"}'


def test_forbidden_bucket(fx_build_docker, fx_run_docker):
    """Test whether forbidden bucket returns an error."""
    ret, det = submit_pdf(fx_run_docker, "gs://some-other-bucket/foobar.pdf", from_bucket=True, post_timeout=120)
    assert ret is None
    assert det == 'status code: 400, details={"detail":"Input bucket not found in ACCEPTED_BUCKETS"}'
