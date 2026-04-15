import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from google.cloud.storage import Blob

from main import app
from config import get_config, Config, ProgramEntry
from exceptions import ExtractionFailure
from api import get_gcs_client

client = TestClient(app)


@pytest.fixture
def fake_config():
    return Config(accepted_buckets=["valid-bucket"])


@pytest.fixture
def fake_engines():
    return [
        ProgramEntry(
            name="mocktotext",
            path="mocktotext.py",
            priority=10,
            template="{path} {params} -i {file_in} -o {file_out}",
        ),
        ProgramEntry(name="pdf2txt", path="", priority=20, template=""),
    ]


@pytest.fixture
def mock_blob():
    mock_blob = MagicMock(spec=Blob)
    mock_blob.name = "input.pdf"
    return mock_blob


@pytest.fixture(autouse=True)
def setup_overrides(fake_config, fake_engines):
    app.state.programs = fake_engines
    app.dependency_overrides[get_config] = lambda: fake_config
    app.dependency_overrides[get_gcs_client] = lambda: MagicMock()
    yield
    app.dependency_overrides = {}


@pytest.fixture
def mock_convert_file(tmp_path):
    temp_file = tmp_path / "file.pdf.txt"
    temp_file.write_text("extracted text")

    patcher = patch("api.convert_file", return_value=str(temp_file))
    patcher.start()

    yield temp_file

    patcher.stop()


class TestHandleFile:
    def test_handle_file_success(self, mock_convert_file):
        files = {"file": ("file.pdf", b"fake data", "application/pdf")}
        response = client.post("/", files=files)
        assert response.status_code == 200
        assert response.text == "extracted text"

    def test_handle_file_invalid_extension(self):
        files = {"file": ("file.txt", b"fake data", "application/pdf")}
        response = client.post("/", files=files)
        assert response.status_code == 400

    def test_handle_file_filename_empty_string(self):
        files = {"file": ("", b"fake data", "application/pdf")}
        response = client.post("/", files=files)
        assert response.status_code == 422

    def test_handle_file_filename_none(self):
        files = {"file": (None, b"fake data", "application/pdf")}
        response = client.post("/", files=files)
        assert response.status_code == 422


class TestHandleFileFromBucket:
    @patch("api.Blob.from_string")
    def test_from_bucket_success(
        self, mock_blob_from_string, mock_blob, mock_convert_file
    ):
        mock_blob_from_string.return_value = mock_blob
        params = {"uri": "gs://valid-bucket/input.pdf", "mode": "auto"}
        response = client.post("/from_bucket", params=params)

        assert response.status_code == 200
        assert response.text == "extracted text"

    @patch("api.Blob.from_string")
    def test_from_bucket_invalid_bucket(
        self, mock_blob_from_string, mock_blob, fake_config
    ):
        mock_blob_from_string.return_value = mock_blob
        params = {"uri": "gs://unauthorized-bucket/input.pdf"}
        response = client.post("/from_bucket", params=params)

        assert response.status_code == 400

    @patch("api.Blob.from_string")
    def test_from_bucket_exception_cleanup(
        self, mock_blob_from_string, mock_blob, mock_convert_file
    ):
        """verify that temp dir cleanup is triggered on failure"""
        mock_blob_from_string.return_value = mock_blob

        with patch("api.convert_file", side_effect=ExtractionFailure):
            with patch("api.shutil.rmtree") as mock_rmtree:
                params = {"uri": "gs://valid-bucket/input.pdf"}

                response = client.post("/from_bucket", params=params)

                assert response.status_code == 422
                mock_rmtree.assert_called()
