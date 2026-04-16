import logging
import os
import shutil
import tempfile

from fastapi import Depends, File, UploadFile, APIRouter, Request
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from functools import lru_cache

from google.cloud import storage
from google.cloud.storage.blob import Blob

from exceptions import BadRequest

from config import get_config, Config, ProgramEntry
from services import (
    input_file_has_pdf_extension,
    input_bucket_in_accepted_buckets,
    convert_file,
)

logger = logging.getLogger(__name__)

text_extraction_router = APIRouter()


@lru_cache
def get_gcs_client():
    return storage.Client()


def get_engines(request: Request):
    return request.app.state.programs


@text_extraction_router.post("/from_bucket")
def handle_file_from_bucket(
    uri: str,
    mode: str = "auto",
    convert_timeout: int = 180,
    params: str = "",
    config: Config = Depends(get_config),
    client: storage.Client = Depends(get_gcs_client),
    engines: list[ProgramEntry] = Depends(get_engines),
) -> FileResponse:
    """Convert pdf to text via bucket url."""
    input_blob = Blob.from_string(uri, client=client)

    if not input_file_has_pdf_extension(os.path.basename(input_blob.name)):
        raise BadRequest

    if not input_bucket_in_accepted_buckets(uri, config):
        raise BadRequest

    temp_dir = tempfile.mkdtemp()
    file_path_in = os.path.join(temp_dir, os.path.basename(input_blob.name))

    try:
        input_blob.download_to_filename(file_path_in)
        file_path_out = convert_file(file_path_in, mode, convert_timeout, params, config, engines)
        return FileResponse(file_path_out, background=BackgroundTask(shutil.rmtree, temp_dir))
    except Exception:
        shutil.rmtree(temp_dir)
        raise


@text_extraction_router.post("/")
def handle_file(
    file: UploadFile = File(...),
    mode: str = "auto",
    convert_timeout: int = 180,
    params: str = "",
    config: Config = Depends(get_config),
    engines: list[ProgramEntry] = Depends(get_engines),
) -> FileResponse:
    """Convert pdf to text via direct upload."""
    if file.filename is None or not input_file_has_pdf_extension(file.filename):
        raise BadRequest

    temp_dir = tempfile.mkdtemp()
    file_path_in = os.path.join(temp_dir, file.filename)

    try:
        with open(file_path_in, "wb") as f:
            shutil.copyfileobj(file.file, f)
        file_path_out = convert_file(file_path_in, mode, convert_timeout, params, config, engines)
        return FileResponse(file_path_out, background=BackgroundTask(shutil.rmtree, temp_dir))
    except Exception:
        shutil.rmtree(temp_dir)
        raise
    finally:
        file.file.close()
