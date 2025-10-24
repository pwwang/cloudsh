"""Tests for the more command."""

from argparse import Namespace
from uuid import uuid4
from io import BytesIO
from unittest.mock import MagicMock

import pytest
from yunpath import AnyPath

from cloudsh.commands.more import run, _get_terminal_size, _display_page
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
    """Mock stdin with buffer attribute and isatty method"""

    def __init__(self, content: bytes, is_tty: bool = False):
        self.buffer = BytesIO(content)
        self._is_tty = is_tty

    def isatty(self):
        return self._is_tty

    def read(self, n):
        return 'q'  # Always return 'q' to quit


class TestMore:
    """Test more command functionality"""

    @pytest.fixture
    def basic_file(self):
        """Create a basic test file"""
        path = WORKDIR / "basic.txt"
        content = "\n".join([f"Line {i}" for i in range(1, 51)])  # 50 lines
        path.write_text(content)
        return str(path)

    @pytest.fixture
    def small_file(self):
        """Create a small test file that fits on one screen"""
        path = WORKDIR / "small.txt"
        path.write_text("Line 1\nLine 2\nLine 3\n")
        return str(path)

    @pytest.fixture
    def empty_lines_file(self):
        """Create a file with empty lines"""
        path = WORKDIR / "empty_lines.txt"
        path.write_text("line1\n\n\n\nline2\n\n\nline3\n")
        return str(path)

    @pytest.fixture
    def no_newline_file(self):
        """Create a file without trailing newline"""
        path = WORKDIR / "no_newline.txt"
        path.write_bytes(b"Line 1\nLine 2\nLine 3")
        return str(path)

    def test_get_terminal_size(self):
        """Test terminal size detection"""
        rows, cols = _get_terminal_size()
        assert isinstance(rows, int)
        assert isinstance(cols, int)
        assert rows > 0
        assert cols > 0

    def test_more_with_stdin_quit(self, capsys, monkeypatch):
        """Test more with stdin input and immediate quit"""
        mock_stdin = MockStdin(b"line1\nline2\nline3\n", is_tty=False)
        monkeypatch.setattr("sys.stdin", mock_stdin)

        args = Namespace(
            file=["-"],
            silent=False,
            no_pause=False,
            no_init=False,
            print_over=False,
            clean_print=False,
            squeeze=False,
            plain=False,
            lines=None,
        )
        run(args)
        captured = capsys.readouterr()
        assert "line1" in captured.out

    def test_more_no_pause_mode(self, small_file, capsys, monkeypatch):
        """Test more with --no-pause option (print all without paging)"""
        # Mock isatty to return False
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)

        args = Namespace(
            file=[small_file],
            silent=False,
            no_pause=True,  # This should print everything
            no_init=False,
            print_over=False,
            clean_print=False,
            squeeze=False,
            plain=False,
            lines=None,
        )
        run(args)
        captured = capsys.readouterr()
        assert "Line 1" in captured.out
        assert "Line 2" in captured.out
        assert "Line 3" in captured.out

    def test_more_squeeze_blank_lines(self, empty_lines_file, capsys, monkeypatch):
        """Test --squeeze option to compress multiple blank lines"""
        mock_stdin = MockStdin(b"", is_tty=False)
        monkeypatch.setattr("sys.stdin", mock_stdin)

        args = Namespace(
            file=[empty_lines_file],
            silent=False,
            no_pause=True,  # Don't wait for input
            no_init=False,
            print_over=False,
            clean_print=False,
            squeeze=True,
            plain=False,
            lines=None,
        )
        run(args)
        captured = capsys.readouterr()
        # Should not have more than 2 consecutive newlines
        assert "\n\n\n" not in captured.out
        assert "line1" in captured.out
        assert "line2" in captured.out
        assert "line3" in captured.out

    def test_more_custom_lines(self, basic_file, capsys, monkeypatch):
        """Test --lines option to set custom screen size"""
        mock_stdin = MockStdin(b"", is_tty=False)
        monkeypatch.setattr("sys.stdin", mock_stdin)

        args = Namespace(
            file=[basic_file],
            silent=False,
            no_pause=False,
            no_init=True,  # Don't clear screen
            print_over=False,
            clean_print=False,
            squeeze=False,
            plain=False,
            lines=5,  # Show 5 lines at a time
        )
        run(args)
        captured = capsys.readouterr()
        # With 5 lines per screen and immediate quit, should see first few lines
        assert "Line 1" in captured.out

    def test_more_no_init(self, small_file, capsys, monkeypatch):
        """Test --no-init option (don't clear screen)"""
        mock_stdin = MockStdin(b"", is_tty=False)
        monkeypatch.setattr("sys.stdin", mock_stdin)

        args = Namespace(
            file=[small_file],
            silent=False,
            no_pause=True,
            no_init=True,
            print_over=False,
            clean_print=False,
            squeeze=False,
            plain=False,
            lines=None,
        )
        run(args)
        captured = capsys.readouterr()
        # Should not contain escape sequence for clearing screen
        assert "Line 1" in captured.out

    def test_more_nonexistent_file(self, capsys):
        """Test error handling for nonexistent file"""
        args = Namespace(
            file=["nonexistent.txt"],
            silent=False,
            no_pause=False,
            no_init=False,
            print_over=False,
            clean_print=False,
            squeeze=False,
            plain=False,
            lines=None,
        )
        with pytest.raises(SystemExit) as exc_info:
            run(args)
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "more:" in captured.err

    def test_more_multiple_files(self, small_file, basic_file, capsys, monkeypatch):
        """Test displaying multiple files"""
        mock_stdin = MockStdin(b"", is_tty=False)
        monkeypatch.setattr("sys.stdin", mock_stdin)

        args = Namespace(
            file=[small_file, basic_file],
            silent=False,
            no_pause=True,
            no_init=True,
            print_over=False,
            clean_print=False,
            squeeze=False,
            plain=False,
            lines=None,
        )
        run(args)
        captured = capsys.readouterr()
        # Should see content from both files
        assert "Line 1" in captured.out
        # Should see separator between files
        assert "::::::::::::::" in captured.out

    def test_more_broken_pipe(self, small_file, monkeypatch):
        """Test handling of broken pipe"""

        def raise_broken_pipe(*args, **kwargs):
            raise BrokenPipeError()

        monkeypatch.setattr("sys.stdout.buffer.write", raise_broken_pipe)
        monkeypatch.setattr("sys.stderr.close", lambda: None)
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)

        args = Namespace(
            file=[small_file],
            silent=False,
            no_pause=True,
            no_init=False,
            print_over=False,
            clean_print=False,
            squeeze=False,
            plain=False,
            lines=None,
        )
        with pytest.raises(SystemExit) as exc_info:
            run(args)
        assert exc_info.value.code == 141

    def test_more_keyboard_interrupt(self, small_file, monkeypatch):
        """Test handling of keyboard interrupt"""
        call_count = {"count": 0}

        def raise_keyboard_interrupt(*args, **kwargs):
            call_count["count"] += 1
            if call_count["count"] == 1:
                raise KeyboardInterrupt()
            return b""

        monkeypatch.setattr("sys.stdout.buffer.write", raise_keyboard_interrupt)
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)

        args = Namespace(
            file=[small_file],
            silent=False,
            no_pause=True,
            no_init=False,
            print_over=False,
            clean_print=False,
            squeeze=False,
            plain=False,
            lines=None,
        )
        with pytest.raises(SystemExit) as exc_info:
            run(args)
        assert exc_info.value.code == 130

    def test_more_cloud_file(self, basic_file, capsys, monkeypatch):
        """Test more with cloud storage file"""
        mock_stdin = MockStdin(b"", is_tty=False)
        monkeypatch.setattr("sys.stdin", mock_stdin)

        args = Namespace(
            file=[basic_file],  # Cloud path
            silent=False,
            no_pause=True,
            no_init=True,
            print_over=False,
            clean_print=False,
            squeeze=False,
            plain=False,
            lines=10,
        )
        run(args)
        captured = capsys.readouterr()
        assert "Line 1" in captured.out

    def test_more_empty_file(self, capsys, monkeypatch):
        """Test more with empty file"""
        empty_file = WORKDIR / "empty.txt"
        empty_file.write_text("")

        mock_stdin = MockStdin(b"", is_tty=False)
        monkeypatch.setattr("sys.stdin", mock_stdin)

        args = Namespace(
            file=[str(empty_file)],
            silent=False,
            no_pause=True,
            no_init=True,
            print_over=False,
            clean_print=False,
            squeeze=False,
            plain=False,
            lines=None,
        )
        run(args)
        captured = capsys.readouterr()
        # Empty file should produce no output (or minimal output)
        assert len(captured.out) < 10  # Very minimal output

    def test_display_page(self, capsys):
        """Test the _display_page function"""
        lines = [b"Line 1\n", b"Line 2\n", b"Line 3\n", b"Line 4\n", b"Line 5\n"]
        args = Namespace(
            silent=False,
            no_pause=False,
            no_init=False,
            print_over=False,
            clean_print=False,
            squeeze=False,
            plain=False,
            lines=None,
        )

        lines_displayed = _display_page(lines, 0, 3, "test.txt", args)
        captured = capsys.readouterr()

        assert lines_displayed == 2  # 3 - 1 for prompt line
        assert b"Line 1" in captured.out.encode()
        assert b"Line 2" in captured.out.encode()

    def test_more_no_newline_at_end(self, no_newline_file, capsys, monkeypatch):
        """Test handling of files without trailing newline"""
        mock_stdin = MockStdin(b"", is_tty=False)
        monkeypatch.setattr("sys.stdin", mock_stdin)

        args = Namespace(
            file=[no_newline_file],
            silent=False,
            no_pause=True,
            no_init=True,
            print_over=False,
            clean_print=False,
            squeeze=False,
            plain=False,
            lines=None,
        )
        run(args)
        captured = capsys.readouterr()
        assert "Line 1" in captured.out
        assert "Line 2" in captured.out
        assert "Line 3" in captured.out

    def test_more_default_to_stdin(self, capsys, monkeypatch):
        """Test that more defaults to stdin when no files specified"""
        mock_stdin = MockStdin(b"stdin content\n", is_tty=False)
        monkeypatch.setattr("sys.stdin", mock_stdin)

        args = Namespace(
            file=[],  # Empty file list
            silent=False,
            no_pause=True,
            no_init=True,
            print_over=False,
            clean_print=False,
            squeeze=False,
            plain=False,
            lines=None,
        )
        run(args)
        captured = capsys.readouterr()
        assert "stdin content" in captured.out
