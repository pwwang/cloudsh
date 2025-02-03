import sys
from argparse import Namespace
from uuid import uuid4

import pytest
from cloudpathlib import AnyPath

from cloudsh.commands.sink import run
from .conftest import BUCKET

WORKDIR = None


def setup_module():
    """Create test directory before any tests run"""
    global WORKDIR
    WORKDIR = AnyPath(f"{BUCKET}/cloudsh_test/{uuid4()}")
    WORKDIR.mkdir(parents=True)


def teardown_module():
    """Remove test directory after all tests complete"""
    if WORKDIR is not None:
        WORKDIR.rmtree()


class TestSink:
    """Test sink command functionality"""

    def setup_method(self):
        """Set up test input data"""
        self._orig_stdin = sys.stdin
        sys.stdin = type(
            "MockStdin",
            (),
            {
                "buffer": type(
                    "MockBuffer", (), {"read": lambda _: b"test content"}
                )(),
                "isatty": lambda _: False,  # Add isatty method
            },
        )()

    def teardown_method(self):
        """Restore stdin"""
        sys.stdin = self._orig_stdin

    def test_sink_file(self, tmp_path):
        """Test basic sink to file"""
        outfile = tmp_path / "out.txt"
        args = Namespace(
            file=str(outfile),
            append=False,
        )
        run(args)
        assert outfile.read_text() == "test content"

    def test_sink_cloud_file(self):
        """Test sink to cloud file"""
        outfile = WORKDIR / "cloud.txt"
        args = Namespace(
            file=str(outfile),
            append=False,
        )
        run(args)
        assert outfile.read_text() == "test content"

    def test_sink_append_local(self, tmp_path):
        """Test appending to local file"""
        outfile = tmp_path / "append.txt"
        outfile.write_text("existing\n")

        args = Namespace(
            file=str(outfile),
            append=True,
        )
        run(args)
        assert outfile.read_text() == "existing\ntest content"

    def test_sink_append_cloud(self):
        """Test appending to cloud file"""
        outfile = WORKDIR / "cloud_append.txt"
        outfile.write_text("existing\n")

        args = Namespace(
            file=str(outfile),
            append=True,
        )
        run(args)
        assert outfile.read_text() == "existing\ntest content"

    def test_sink_binary(self, tmp_path):
        """Test sinking binary content"""
        sys.stdin = type(
            "MockStdin",
            (),
            {
                "buffer": type(
                    "MockBuffer", (), {"read": lambda _: b"binary\x00data"}
                )(),
                "isatty": lambda _: False,  # Add isatty method
            },
        )()

        outfile = tmp_path / "binary.bin"
        args = Namespace(
            file=str(outfile),
            append=False,
        )
        run(args)
        assert outfile.read_bytes() == b"binary\x00data"

    def test_sink_permission_error(self, tmp_path, capsys):
        """Test handling permission errors"""
        outfile = tmp_path / "noperm.txt"
        outfile.touch()
        outfile.chmod(0o444)  # Read-only

        args = Namespace(
            file=str(outfile),
            append=False,
        )
        with pytest.raises(SystemExit):
            run(args)
        err = capsys.readouterr().err
        assert "Permission denied" in err

    def test_sink_nonexistent_directory(self, tmp_path, capsys):
        """Test sinking to file in nonexistent directory"""
        outfile = tmp_path / "nonexistent" / "file.txt"
        args = Namespace(
            file=str(outfile),
            append=False,
        )
        with pytest.raises(SystemExit):
            run(args)
        err = capsys.readouterr().err
        assert "No such file or directory" in err

    def test_sink_no_input(self, capsys):
        """Test handling no input data"""
        sys.stdin = type(
            "MockStdin",
            (),
            {
                "buffer": type("MockBuffer", (), {"read": lambda _: b""})(),
                "isatty": lambda _: True,  # Add isatty method
            },
        )()

        args = Namespace(
            file="output.txt",
            append=False,
        )
        with pytest.raises(SystemExit):
            run(args)
        err = capsys.readouterr().err
        assert "no input data provided" in err
