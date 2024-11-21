"""Pytest configuration."""

import pytest
from common import build_docker, image_name


# unfortunately, this does not force
# running this fixture only once per complete pytest run.
# Reason is that pytests might be distributed between workers.
# See https://github.com/pytest-dev/pytest-xdist/issues/783
@pytest.fixture(scope="session")
def fx_build_docker():
    """Fixture to build the docker image."""
    build_docker(image_name)
    yield
    pass
