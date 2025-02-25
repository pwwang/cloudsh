from argparse import Namespace
from uuid import uuid4

import pytest
from yunpath import AnyPath
from io import BytesIO

from cloudsh.commands.cat import run
from .conftest import BUCKET

# Create workdir as module-level variable
WORKDIR = None


def setup_module():
    """Create test directory before any tests run"""
    global WORKDIR
    WORKDIR = AnyPath(f"{BUCKET}/cloudsh_test/{uuid4()}")


def teardown_module():
    """Remove test directory after all tests complete"""
    if WORKDIR is not None:
        WORKDIR.rmtree()


class MockStdin:
    """Mock stdin with buffer attribute"""

    def __init__(self, content: bytes):
        self.buffer = BytesIO(content)


class TestCat:
    """Test cat command functionality"""

    @pytest.fixture
    def basic_file(self):
        """Create a basic test file"""
        path = WORKDIR / "basic.txt"
        path.write_text("line1\nline2\nline3\n")
        return str(path)

    @pytest.fixture
    def special_chars_file(self):
        """Create a file with special characters"""
        path = WORKDIR / "special.txt"
        # Include tab, non-printing chars, and extended ASCII
        content = "normal\ttext\x01\x02\x7f\x80line\n"
        path.write_bytes(content.encode())
        return str(path)

    @pytest.fixture
    def empty_lines_file(self):
        """Create a file with empty lines"""
        path = WORKDIR / "empty_lines.txt"
        path.write_text("line1\n\n\n\nline2\n\n\nline3\n")
        return str(path)

    def test_cat_basic(self, basic_file, capsys):
        """Test basic cat functionality"""
        args = Namespace(
            file=[basic_file],
            show_all=False,
            number_nonblank=False,
            e=False,
            show_ends=False,
            number=False,
            squeeze_blank=False,
            t=False,
            show_tabs=False,
            show_nonprinting=False,
        )
        run(args)  # No return value needed
        captured = capsys.readouterr()
        assert captured.out == "line1\nline2\nline3\n"

    def test_cat_multiple_files(self, basic_file, empty_lines_file, capsys):
        """Test concatenating multiple files"""
        args = Namespace(
            file=[basic_file, empty_lines_file],
            show_all=False,
            number_nonblank=False,
            e=False,
            show_ends=False,
            number=False,
            squeeze_blank=False,
            t=False,
            show_tabs=False,
            show_nonprinting=False,
        )
        run(args)  # No return value needed
        captured = capsys.readouterr()
        assert "line1\nline2\nline3\n" in captured.out
        assert "line1\n\n\n\nline2\n\n\nline3\n" in captured.out

    def test_cat_number_all_lines(self, basic_file, capsys):
        """Test -n option (number all lines)"""
        args = Namespace(
            file=[basic_file],
            show_all=False,
            number_nonblank=False,
            e=False,
            show_ends=False,
            number=True,
            squeeze_blank=False,
            t=False,
            show_tabs=False,
            show_nonprinting=False,
        )
        run(args)  # No return value needed
        captured = capsys.readouterr()
        assert "     1\tline1\n" in captured.out
        assert "     2\tline2\n" in captured.out
        assert "     3\tline3\n" in captured.out

    def test_cat_number_nonblank(self, empty_lines_file, capsys):
        """Test -b option (number non-blank lines)"""
        args = Namespace(
            file=[empty_lines_file],
            show_all=False,
            number_nonblank=True,
            e=False,
            show_ends=False,
            number=False,
            squeeze_blank=False,
            t=False,
            show_tabs=False,
            show_nonprinting=False,
        )
        run(args)  # No return value needed
        captured = capsys.readouterr()
        lines = captured.out.splitlines(True)
        numbered_lines = [line for line in lines if line.startswith("     ")]
        assert len(numbered_lines) == 3  # Only non-empty lines numbered

    def test_cat_squeeze_blank(self, empty_lines_file, capsys):
        """Test -s option (squeeze multiple blank lines)"""
        args = Namespace(
            file=[empty_lines_file],
            show_all=False,
            number_nonblank=False,
            e=False,
            show_ends=False,
            number=False,
            squeeze_blank=True,
            t=False,
            show_tabs=False,
            show_nonprinting=False,
        )
        run(args)  # No return value needed
        captured = capsys.readouterr()
        assert captured.out.count("\n\n\n") == 0  # No more than 2 consecutive newlines

    def test_cat_show_ends(self, basic_file, capsys):
        """Test -E option (show line endings)"""
        args = Namespace(
            file=[basic_file],
            show_all=False,
            number_nonblank=False,
            e=False,
            show_ends=True,
            number=False,
            squeeze_blank=False,
            t=False,
            show_tabs=False,
            show_nonprinting=False,
        )
        run(args)  # No return value needed
        captured = capsys.readouterr()
        assert "line1$\n" in captured.out
        assert "line2$\n" in captured.out
        assert "line3$\n" in captured.out

    def test_cat_show_tabs(self, special_chars_file, capsys):
        """Test -T option (show tabs)"""
        args = Namespace(
            file=[special_chars_file],
            show_all=False,
            number_nonblank=False,
            e=False,
            show_ends=False,
            number=False,
            squeeze_blank=False,
            t=False,
            show_tabs=True,
            show_nonprinting=False,
        )
        run(args)  # No return value needed
        captured = capsys.readouterr()
        assert "^I" in captured.out  # Tab shown as ^I

    def test_cat_show_nonprinting(self, special_chars_file, capsys):
        """Test -v option (show non-printing characters)"""
        args = Namespace(
            file=[special_chars_file],
            show_all=False,
            number_nonblank=False,
            e=False,
            show_ends=False,
            number=False,
            squeeze_blank=False,
            t=False,
            show_tabs=False,
            show_nonprinting=True,
        )
        run(args)  # No return value needed
        captured = capsys.readouterr()
        assert "^A" in captured.out  # Control char 0x01
        assert "^B" in captured.out  # Control char 0x02
        assert "^?" in captured.out  # DEL char 0x7F
        assert "M-" in captured.out  # Extended ASCII char 0x80

    def test_cat_show_all(self, special_chars_file, capsys):
        """Test -A option (equivalent to -vET)"""
        args = Namespace(
            file=[special_chars_file],
            show_all=True,
            number_nonblank=False,
            e=False,
            show_ends=False,
            number=False,
            squeeze_blank=False,
            t=False,
            show_tabs=False,
            show_nonprinting=False,
        )
        run(args)  # No return value needed
        captured = capsys.readouterr()
        assert "^I" in captured.out  # Tabs
        assert "^A" in captured.out  # Control chars
        assert "$" in captured.out  # Line endings

    def test_cat_stdin(self, capsys, monkeypatch):
        """Test reading from stdin"""
        mock_stdin = MockStdin(b"from stdin\n")
        monkeypatch.setattr("sys.stdin", mock_stdin)
        args = Namespace(
            file=[],  # Empty file list -> use stdin
            show_all=False,
            number_nonblank=False,
            e=False,
            show_ends=False,
            number=False,
            squeeze_blank=False,
            t=False,
            show_tabs=False,
            show_nonprinting=False,
        )
        run(args)
        captured = capsys.readouterr()
        assert "from stdin" in captured.out

    def test_cat_nonexistent_file(self, capsys):
        """Test error handling for nonexistent file"""
        args = Namespace(
            file=["nonexistent.txt"],
            show_all=False,
            number_nonblank=False,
            e=False,
            show_ends=False,
            number=False,
            squeeze_blank=False,
            t=False,
            show_tabs=False,
            show_nonprinting=False,
        )
        with pytest.raises(SystemExit) as exc_info:
            run(args)
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "No such file" in captured.err

    def test_cat_broken_pipe(self, basic_file, monkeypatch):
        """Test handling of broken pipe"""

        def raise_broken_pipe(*args, **kwargs):
            raise BrokenPipeError()

        monkeypatch.setattr("sys.stdout.buffer.write", raise_broken_pipe)
        # Also patch stderr.close to avoid actual close
        monkeypatch.setattr("sys.stderr.close", lambda: None)
        args = Namespace(
            file=[basic_file],
            show_all=False,
            number_nonblank=False,
            e=False,
            show_ends=False,
            number=False,
            squeeze_blank=False,
            t=False,
            show_tabs=False,
            show_nonprinting=False,
        )
        with pytest.raises(SystemExit) as exc_info:
            run(args)
        assert exc_info.value.code == 141

    def test_cat_keyboard_interrupt(self, basic_file, monkeypatch):
        """Test handling of keyboard interrupt"""

        def raise_keyboard_interrupt(*args, **kwargs):
            raise KeyboardInterrupt()

        monkeypatch.setattr("sys.stdout.buffer.write", raise_keyboard_interrupt)
        args = Namespace(
            file=[basic_file],
            show_all=False,
            number_nonblank=False,
            e=False,
            show_ends=False,
            number=False,
            squeeze_blank=False,
            t=False,
            show_tabs=False,
            show_nonprinting=False,
        )
        with pytest.raises(SystemExit) as exc_info:
            run(args)
        assert exc_info.value.code == 130
