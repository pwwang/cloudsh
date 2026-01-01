import sys
from argparse import Namespace

import pytest

from cloudsh.commands.sink import run


class TestSink:
    """Test sink command functionality"""

    def setup_method(self):
        """Set up test input data"""
        self._orig_stdin = sys.stdin
        content = [b"test content"]
        sys.stdin = type(
            "MockStdin",
            (),
            {
                "buffer": type(
                    "MockBuffer",
                    (),
                    {
                        "read": lambda _: b"test content",
                        "readline": lambda _: content.pop(0) if content else b"",
                    },
                )(),
                "isatty": lambda _: False,  # Add isatty method
            },
        )()

    def teardown_method(self):
        """Restore stdin"""
        sys.stdin = self._orig_stdin

    async def test_sink_file(self, tmp_path):
        """Test basic sink to file"""
        outfile = tmp_path / "out.txt"
        args = Namespace(
            file=str(outfile),
            append=False,
            chunk_size=1024,
        )
        await run(args)
        assert outfile.read_text() == "test content"

    async def test_sink_local_file(self, workdir):
        """Test sink to local file"""
        outfile = workdir / "local.txt"
        args = Namespace(
            file=str(outfile),
            append=False,
            chunk_size=1024,
        )
        await run(args)
        assert outfile.read_text() == "test content"

    async def test_sink_append_local(self, tmp_path):
        """Test appending to local file"""
        outfile = tmp_path / "append.txt"
        outfile.write_text("existing\n")

        args = Namespace(
            file=str(outfile),
            append=True,
            chunk_size=1024,
        )
        await run(args)
        assert outfile.read_text() == "existing\ntest content"

    async def test_sink_append_workdir(self, workdir):
        """Test appending to workdir file"""
        outfile = workdir / "workdir_append.txt"
        outfile.write_text("existing\n")

        args = Namespace(
            file=str(outfile),
            append=True,
            chunk_size=1024,
        )
        await run(args)
        assert outfile.read_text() == "existing\ntest content"

    async def test_sink_binary(self, tmp_path):
        """Test sinking binary content"""
        content = [b"binary\x00data"]
        sys.stdin = type(
            "MockStdin",
            (),
            {
                "buffer": type(
                    "MockBuffer",
                    (),
                    {
                        "read": lambda _: b"binary\x00data",
                        "readline": lambda _: content.pop(0) if content else b"",
                    },
                )(),
                "isatty": lambda _: False,  # Add isatty method
            },
        )()

        outfile = tmp_path / "binary.bin"
        args = Namespace(
            file=str(outfile),
            append=False,
        )
        await run(args)
        assert outfile.read_bytes() == b"binary\x00data"

    async def test_sink_permission_error(self, tmp_path, capsys):
        """Test handling permission errors"""
        outfile = tmp_path / "noperm.txt"
        outfile.touch()
        outfile.chmod(0o444)  # Read-only

        args = Namespace(
            file=str(outfile),
            append=False,
            chunk_size=1024,
        )
        with pytest.raises(SystemExit):
            await run(args)
        err = capsys.readouterr().err
        assert "Permission denied" in err

    async def test_sink_nonexistent_directory(self, tmp_path, capsys):
        """Test sinking to file in nonexistent directory"""
        outfile = tmp_path / "nonexistent" / "file.txt"
        args = Namespace(
            file=str(outfile),
            append=False,
            chunk_size=1024,
        )
        with pytest.raises(SystemExit):
            await run(args)
        err = capsys.readouterr().err
        assert "No such file or directory" in err

    async def test_sink_no_input(self, capsys):
        """Test handling no input data"""
        sys.stdin = type(
            "MockStdin",
            (),
            {
                "buffer": type(
                    "MockBuffer",
                    (),
                    {
                        "read": lambda _: b"",
                        "readline": lambda _: b"",
                    },
                )(),
                "isatty": lambda _: True,  # Add isatty method
            },
        )()

        args = Namespace(
            file="output.txt",
            append=False,
            chunk_size=1024,
        )
        with pytest.raises(SystemExit):
            await run(args)
        err = capsys.readouterr().err
        assert "no input data provided" in err
