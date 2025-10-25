from dotenv import load_dotenv
import pytest

load_dotenv()

BUCKET = "gs://handy-buffer-287000.appspot.com"


@pytest.fixture(scope="module")
def workdir(tmp_path_factory):
    """
    Create a temporary workdir for tests.
    Uses local filesystem instead of cloud storage for faster, isolated tests.
    """
    workdir = tmp_path_factory.mktemp("cloudsh_test")
    return workdir
