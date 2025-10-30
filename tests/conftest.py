from dotenv import load_dotenv
import pytest
import uuid

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


@pytest.fixture
def cloud_workdir(request):
    """
    Create a temporary cloud workdir for tests.
    Uses a cloud bucket specified by BUCKET environment variable.
    """
    from yunpath import GSPath

    parent_workdir = GSPath(BUCKET) / "cloudsh_test"
    # create a unique subdirectory for each test function
    # also add uuid to avoid collisions in parallel test runs
    cloud_workdir = parent_workdir.joinpath(
        f"{request.node.name}_"
        f"{uuid.uuid4().hex}"
    )
    cloud_workdir.mkdir(parents=True, exist_ok=True)
    yield cloud_workdir
    # Cleanup after tests
    cloud_workdir.rmtree()
