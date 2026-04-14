import pytest
from unittest.mock import patch
from subprocess import TimeoutExpired
from exceptions import BadRequest, ExtractionFailure

from config import ProgramEntry, Config
from services import (
    input_file_has_pdf_extension,
    input_bucket_in_accepted_buckets,
    get_programs,
    get_command_for_program,
    convert_file,
)


@pytest.fixture
def fake_engines():
    return [
        ProgramEntry(
            name="mocktotext",
            path="mocktotext.py",
            priority=10,
            template="{path} {params} -i {file_in} -o {file_out}",
        ),
        ProgramEntry(name="pdf2txt", path= "", priority=20, template=""),
    ]


@pytest.fixture
def fake_config():
    return Config(accepted_buckets=["valid-bucket"], cgroup_prefix=["cgexec", "-g", "memory:fake-group"])


def test_input_file_has_pdf_extension():
    assert input_file_has_pdf_extension("document.pdf") is True
    assert input_file_has_pdf_extension("IMAGE.PDF") is True
    assert input_file_has_pdf_extension("notes.txt") is False


def test_input_bucket_in_accepted_buckets(fake_config):
    assert (
        input_bucket_in_accepted_buckets("gs://valid-bucket/file.pdf", fake_config)
        is True
    )
    assert (
        input_bucket_in_accepted_buckets("gs://invalid-bucket/file.pdf", fake_config)
        is False
    )

    fake_config.accepted_buckets = None
    assert (
        input_bucket_in_accepted_buckets("gs://any-bucket/file.pdf", fake_config)
        is True
    )


def test_get_programs_auto(fake_engines):
    progs = get_programs("auto", fake_engines)
    assert len(progs) == 2
    assert progs[0].name == "mocktotext"


def test_get_programs_invalid(fake_engines):
    with pytest.raises(BadRequest):
        get_programs("nonexistent_mode", fake_engines)


def test_get_command_for_program(fake_engines, fake_config):
    cmd = get_command_for_program(
        fake_engines[0], "in.pdf", "out.txt", "--fast", fake_config
    )
    expected = [
        "cgexec",
        "-g",
        "memory:fake-group",
        "mocktotext.py",
        "--fast",
        "-i",
        "in.pdf",
        "-o",
        "out.txt",
    ]
    assert cmd == expected


@patch("services.Popen")
@patch("services.get_programs")
def test_convert_file_success(mock_get_progs, mock_popen, fake_config, fake_engines):
    mock_get_progs.return_value = [fake_engines[0]]

    process_mock = mock_popen.return_value
    process_mock.communicate.return_value = (b"stdout", b"")
    process_mock.returncode = 0

    result = convert_file("test.pdf", "auto", 10, "--opt", fake_config, fake_engines)
    assert result == "test.pdf.txt"
    mock_popen.assert_called_once()


@patch("services.Popen")
@patch("services.get_programs")
def test_convert_file_timeout(mock_get_progs, mock_popen, fake_config, fake_engines):
    mock_get_progs.return_value = [fake_engines[0]]

    process_mock = mock_popen.return_value
    process_mock.communicate.side_effect = TimeoutExpired(cmd="test", timeout=10)

    with pytest.raises(TimeoutExpired):
        convert_file("test.pdf", "auto", 10, "", fake_config, fake_engines)

    process_mock.kill.assert_called_once()


@patch("services.Popen")
@patch("services.get_programs")
def test_convert_file_generic_exception(
    mock_get_progs, mock_popen, fake_config, fake_engines
):
    """Tests the generic Exception catch"""
    mock_get_progs.return_value = [fake_engines[0]]

    mock_popen.side_effect = FileNotFoundError("No such file or directory")

    with pytest.raises(ExtractionFailure):
        convert_file("test.pdf", "auto", 10, "", fake_config, fake_engines)


@patch("services.Popen")
@patch("services.get_programs")
def test_convert_file_unicode_error_handling(
    mock_get_progs, mock_popen, fake_config, fake_engines
):
    mock_get_progs.return_value = [fake_engines[0]]

    process_mock = mock_popen.return_value
    process_mock.returncode = 1
    process_mock.communicate.return_value = (
        b"",
        b"\xff\xfe\xfd",
    )  # error code includes non-utf8

    # graceful exit
    with pytest.raises(ExtractionFailure):
        convert_file("test.pdf", "auto", 10, "", fake_config, fake_engines)
