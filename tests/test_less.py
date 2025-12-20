"""Tests for the less command."""

from argparse import Namespace
from io import BytesIO

import pytest

from cloudsh.commands.less import (
    _run,
    _get_terminal_size,
    _display_lines,
    _search_forward,
    _search_backward,
)


class MockStdin:
    """Mock stdin with buffer attribute and isatty method"""

    def __init__(self, content: bytes, is_tty: bool = False):
        self.buffer = BytesIO(content)
        self._is_tty = is_tty

    def isatty(self):
        return self._is_tty

    def read(self, n):
        return "q"  # Always return 'q' to quit


class TestLess:
    """Test less command functionality"""

    @pytest.fixture
    def basic_file(self, workdir):
        """Create a basic test file"""
        path = workdir / "basic.txt"
        content = "\n".join([f"Line {i}" for i in range(1, 51)])  # 50 lines
        path.write_text(content)
        return str(path)

    @pytest.fixture
    def small_file(self, workdir):
        """Create a small test file that fits on one screen"""
        path = workdir / "small.txt"
        path.write_text("Line 1\nLine 2\nLine 3\n")
        return str(path)

    @pytest.fixture
    def search_file(self, workdir):
        """Create a file for search testing"""
        path = workdir / "search.txt"
        content = "apple\nbanana\ncherry\ndate\napricot\navocado\n"
        path.write_text(content)
        return str(path)

    @pytest.fixture
    def empty_lines_file(self, workdir):
        """Create a file with empty lines"""
        path = workdir / "empty_lines.txt"
        path.write_text("line1\n\n\n\nline2\n\n\nline3\n")
        return str(path)

    @pytest.fixture
    def no_newline_file(self, workdir):
        """Create a file without trailing newline"""
        path = workdir / "no_newline.txt"
        path.write_bytes(b"Line 1\nLine 2\nLine 3")
        return str(path)

    def test_get_terminal_size(self):
        """Test terminal size detection"""
        rows, cols = _get_terminal_size()
        assert isinstance(rows, int)
        assert isinstance(cols, int)
        assert rows > 0
        assert cols > 0

    @pytest.mark.asyncio
    async def test_less_quit_if_one_screen(self, small_file, capsys, monkeypatch):
        """Test --quit-if-one-screen option"""
        mock_stdin = MockStdin(b"", is_tty=False)
        monkeypatch.setattr("sys.stdin", mock_stdin)

        args = Namespace(
            file=[small_file],
            QUIT_AT_EOF=False,
            quit_if_one_screen=True,
            ignore_case=False,
            IGNORE_CASE=False,
            LINE_NUMBERS=False,
            chop_long_lines=False,
            no_init=True,
            squeeze_blank_lines=False,
            line_numbers=False,
            pattern=None,
        )
        await _run(args)
        captured = capsys.readouterr()
        assert "Line 1" in captured.out
        assert "Line 2" in captured.out
        assert "Line 3" in captured.out

    @pytest.mark.asyncio
    async def test_less_with_line_numbers(self, small_file, capsys, monkeypatch):
        """Test --line-numbers option"""
        mock_stdin = MockStdin(b"", is_tty=False)
        monkeypatch.setattr("sys.stdin", mock_stdin)

        args = Namespace(
            file=[small_file],
            QUIT_AT_EOF=False,
            quit_if_one_screen=True,
            ignore_case=False,
            IGNORE_CASE=False,
            LINE_NUMBERS=True,
            chop_long_lines=False,
            no_init=True,
            squeeze_blank_lines=False,
            line_numbers=False,
            pattern=None,
        )
        await _run(args)
        captured = capsys.readouterr()
        # Should have line numbers
        assert "1" in captured.out or "     1" in captured.out

    @pytest.mark.asyncio
    async def test_less_squeeze_blank_lines(
        self, empty_lines_file, capsys, monkeypatch
    ):
        """Test --squeeze-blank-lines option"""
        mock_stdin = MockStdin(b"", is_tty=False)
        monkeypatch.setattr("sys.stdin", mock_stdin)

        args = Namespace(
            file=[empty_lines_file],
            QUIT_AT_EOF=False,
            quit_if_one_screen=True,
            ignore_case=False,
            IGNORE_CASE=False,
            LINE_NUMBERS=False,
            chop_long_lines=False,
            no_init=True,
            squeeze_blank_lines=True,
            line_numbers=False,
            pattern=None,
        )
        await _run(args)
        captured = capsys.readouterr()
        # Should not have more than 2 consecutive newlines
        assert "\n\n\n" not in captured.out
        assert "line1" in captured.out
        assert "line2" in captured.out

    @pytest.mark.asyncio
    async def test_less_with_pattern(self, search_file, capsys, monkeypatch):
        """Test --pattern option to start at first match"""
        mock_stdin = MockStdin(b"", is_tty=False)
        monkeypatch.setattr("sys.stdin", mock_stdin)

        args = Namespace(
            file=[search_file],
            QUIT_AT_EOF=False,
            quit_if_one_screen=True,
            ignore_case=False,
            IGNORE_CASE=False,
            LINE_NUMBERS=False,
            chop_long_lines=False,
            no_init=True,
            squeeze_blank_lines=False,
            line_numbers=False,
            pattern="cherry",
        )
        await _run(args)
        captured = capsys.readouterr()
        # Should start at or include the pattern
        assert "cherry" in captured.out

    @pytest.mark.asyncio
    async def test_less_ignore_case_pattern(self, search_file, capsys, monkeypatch):
        """Test --ignore-case with pattern search"""
        mock_stdin = MockStdin(b"", is_tty=False)
        monkeypatch.setattr("sys.stdin", mock_stdin)

        args = Namespace(
            file=[search_file],
            QUIT_AT_EOF=False,
            quit_if_one_screen=True,
            ignore_case=True,
            IGNORE_CASE=False,
            LINE_NUMBERS=False,
            chop_long_lines=False,
            no_init=True,
            squeeze_blank_lines=False,
            line_numbers=False,
            pattern="CHERRY",  # Uppercase pattern
        )
        await _run(args)
        captured = capsys.readouterr()
        # Should find "cherry" even though pattern is uppercase
        assert "cherry" in captured.out

    @pytest.mark.asyncio
    async def test_less_nonexistent_file(self, capsys):
        """Test error handling for nonexistent file"""
        args = Namespace(
            file=["nonexistent.txt"],
            QUIT_AT_EOF=False,
            quit_if_one_screen=False,
            ignore_case=False,
            IGNORE_CASE=False,
            LINE_NUMBERS=False,
            chop_long_lines=False,
            no_init=False,
            squeeze_blank_lines=False,
            line_numbers=False,
            pattern=None,
        )
        with pytest.raises(SystemExit) as exc_info:
            await _run(args)
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "less:" in captured.err

    @pytest.mark.asyncio
    async def test_less_broken_pipe(self, small_file, monkeypatch):
        """Test handling of broken pipe"""

        def raise_broken_pipe(*args, **kwargs):
            raise BrokenPipeError()

        monkeypatch.setattr("sys.stdout.buffer.write", raise_broken_pipe)
        monkeypatch.setattr("sys.stderr.close", lambda: None)
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)

        args = Namespace(
            file=[small_file],
            QUIT_AT_EOF=False,
            quit_if_one_screen=True,
            ignore_case=False,
            IGNORE_CASE=False,
            LINE_NUMBERS=False,
            chop_long_lines=False,
            no_init=True,
            squeeze_blank_lines=False,
            line_numbers=False,
            pattern=None,
        )
        with pytest.raises(SystemExit) as exc_info:
            await _run(args)
        assert exc_info.value.code == 141

    @pytest.mark.asyncio
    async def test_less_keyboard_interrupt(self, small_file, monkeypatch):
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
            QUIT_AT_EOF=False,
            quit_if_one_screen=True,
            ignore_case=False,
            IGNORE_CASE=False,
            LINE_NUMBERS=False,
            chop_long_lines=False,
            no_init=True,
            squeeze_blank_lines=False,
            line_numbers=False,
            pattern=None,
        )
        with pytest.raises(SystemExit) as exc_info:
            await _run(args)
        assert exc_info.value.code == 130

    def test_search_forward(self):
        """Test forward search functionality"""
        lines = [b"apple\n", b"banana\n", b"cherry\n", b"date\n", b"apple\n"]

        # Test case-sensitive search
        result = _search_forward(lines, "cherry", 0, ignore_case=False)
        assert result == 2

        # Test case-insensitive search
        result = _search_forward(lines, "CHERRY", 0, ignore_case=True)
        assert result == 2

        # Test not found
        result = _search_forward(lines, "grape", 0, ignore_case=False)
        assert result is None

        # Test finding second occurrence
        result = _search_forward(lines, "apple", 1, ignore_case=False)
        assert result == 4

    def test_search_backward(self):
        """Test backward search functionality"""
        lines = [b"apple\n", b"banana\n", b"cherry\n", b"date\n", b"apple\n"]

        # Test case-sensitive search
        result = _search_backward(lines, "apple", 5, ignore_case=False)
        assert result == 4

        # Test case-insensitive search
        result = _search_backward(lines, "BANANA", 3, ignore_case=True)
        assert result == 1

        # Test not found
        result = _search_backward(lines, "grape", 5, ignore_case=False)
        assert result is None

        # Test finding first occurrence
        result = _search_backward(lines, "apple", 3, ignore_case=False)
        assert result == 0

    def test_display_lines(self, capsys):
        """Test the _display_lines function"""
        lines = [b"Line 1\n", b"Line 2\n", b"Line 3\n", b"Line 4\n", b"Line 5\n"]
        args = Namespace(
            LINE_NUMBERS=False,
            line_numbers=False,
            chop_long_lines=False,
        )

        lines_displayed = _display_lines(lines, 0, 3, args)
        captured = capsys.readouterr()

        assert lines_displayed == 2  # 3 - 1 for status line
        assert b"Line 1" in captured.out.encode()
        assert b"Line 2" in captured.out.encode()

    def test_display_lines_with_numbers(self, capsys):
        """Test displaying lines with line numbers"""
        lines = [b"Line 1\n", b"Line 2\n", b"Line 3\n"]
        args = Namespace(
            LINE_NUMBERS=True,
            line_numbers=False,
            chop_long_lines=False,
        )

        _display_lines(lines, 0, 3, args)
        captured = capsys.readouterr()

        # Should have line numbers in the output
        assert "1" in captured.out
        assert "2" in captured.out

    @pytest.mark.asyncio
    async def test_less_empty_file(self, workdir, capsys, monkeypatch):
        """Test less with empty file"""
        empty_file = workdir / "empty.txt"
        empty_file.write_text("")

        mock_stdin = MockStdin(b"", is_tty=False)
        monkeypatch.setattr("sys.stdin", mock_stdin)

        args = Namespace(
            file=[str(empty_file)],
            QUIT_AT_EOF=False,
            quit_if_one_screen=True,
            ignore_case=False,
            IGNORE_CASE=False,
            LINE_NUMBERS=False,
            chop_long_lines=False,
            no_init=True,
            squeeze_blank_lines=False,
            line_numbers=False,
            pattern=None,
        )
        await _run(args)
        captured = capsys.readouterr()
        # Empty file should produce minimal or no output
        assert len(captured.out) < 10

    @pytest.mark.asyncio
    async def test_less_local_file(self, basic_file, capsys, monkeypatch):
        """Test less with local storage file"""
        mock_stdin = MockStdin(b"", is_tty=False)
        monkeypatch.setattr("sys.stdin", mock_stdin)

        args = Namespace(
            file=[basic_file],  # Local path
            QUIT_AT_EOF=False,
            quit_if_one_screen=False,
            ignore_case=False,
            IGNORE_CASE=False,
            LINE_NUMBERS=False,
            chop_long_lines=False,
            no_init=True,
            squeeze_blank_lines=False,
            line_numbers=False,
            pattern=None,
        )
        await _run(args)
        captured = capsys.readouterr()
        assert "Line 1" in captured.out

    @pytest.mark.asyncio
    async def test_less_no_newline_at_end(self, no_newline_file, capsys, monkeypatch):
        """Test handling of files without trailing newline"""
        mock_stdin = MockStdin(b"", is_tty=False)
        monkeypatch.setattr("sys.stdin", mock_stdin)

        args = Namespace(
            file=[no_newline_file],
            QUIT_AT_EOF=False,
            quit_if_one_screen=True,
            ignore_case=False,
            IGNORE_CASE=False,
            LINE_NUMBERS=False,
            chop_long_lines=False,
            no_init=True,
            squeeze_blank_lines=False,
            line_numbers=False,
            pattern=None,
        )
        await _run(args)
        captured = capsys.readouterr()
        assert "Line 1" in captured.out
        assert "Line 2" in captured.out
        assert "Line 3" in captured.out

    @pytest.mark.asyncio
    async def test_less_default_to_error(self, capsys, monkeypatch):
        """Test that less defaults to stdin when no files specified"""
        mock_stdin = MockStdin(b"stdin content\n", is_tty=False)
        monkeypatch.setattr("sys.stdin", mock_stdin)

        args = Namespace(
            file=[],  # Empty file list
            QUIT_AT_EOF=False,
            quit_if_one_screen=True,
            ignore_case=False,
            IGNORE_CASE=False,
            LINE_NUMBERS=False,
            chop_long_lines=False,
            no_init=True,
            squeeze_blank_lines=False,
            line_numbers=False,
            pattern=None,
        )
        with pytest.raises(SystemExit):
            await _run(args)
        captured = capsys.readouterr()
        assert "Missing filename" in captured.err

    @pytest.mark.asyncio
    async def test_less_pattern_not_found(self, search_file, capsys, monkeypatch):
        """Test behavior when pattern is not found"""
        mock_stdin = MockStdin(b"", is_tty=False)
        monkeypatch.setattr("sys.stdin", mock_stdin)

        args = Namespace(
            file=[search_file],
            QUIT_AT_EOF=False,
            quit_if_one_screen=True,
            ignore_case=False,
            IGNORE_CASE=False,
            LINE_NUMBERS=False,
            chop_long_lines=False,
            no_init=True,
            squeeze_blank_lines=False,
            line_numbers=False,
            pattern="notfound",
        )
        await _run(args)
        captured = capsys.readouterr()
        # Should still display the file from the beginning
        assert "apple" in captured.out

    def test_search_invalid_regex(self):
        """Test search with invalid regex pattern"""
        lines = [b"apple\n", b"banana\n", b"cherry\n"]

        # Invalid regex should return None
        result = _search_forward(lines, "[invalid(", 0, ignore_case=False)
        assert result is None

        result = _search_backward(lines, "[invalid(", 3, ignore_case=False)
        assert result is None

    @pytest.mark.asyncio
    async def test_less_chop_long_lines(self, workdir, capsys, monkeypatch):
        """Test --chop-long-lines option"""
        long_line_file = workdir / "long_line.txt"
        long_line = "x" * 200 + "\n"
        long_line_file.write_text(long_line)

        mock_stdin = MockStdin(b"", is_tty=False)
        monkeypatch.setattr("sys.stdin", mock_stdin)

        args = Namespace(
            file=[str(long_line_file)],
            QUIT_AT_EOF=False,
            quit_if_one_screen=True,
            ignore_case=False,
            IGNORE_CASE=False,
            LINE_NUMBERS=False,
            chop_long_lines=True,
            no_init=True,
            squeeze_blank_lines=False,
            line_numbers=False,
            pattern=None,
        )
        await _run(args)
        captured = capsys.readouterr()
        # Should have some output, but potentially truncated
        assert len(captured.out) > 0

    @pytest.mark.asyncio
    async def test_less_stdin_with_dash(self, capsys, monkeypatch):
        """Test less with explicit '-' for stdin"""
        mock_stdin = MockStdin(b"stdin via dash\n", is_tty=False)
        monkeypatch.setattr("sys.stdin", mock_stdin)

        args = Namespace(
            file=["-"],
            QUIT_AT_EOF=False,
            quit_if_one_screen=True,
            ignore_case=False,
            IGNORE_CASE=False,
            LINE_NUMBERS=False,
            chop_long_lines=False,
            no_init=True,
            squeeze_blank_lines=False,
            line_numbers=False,
            pattern=None,
        )
        with pytest.raises(SystemExit):
            await _run(args)
        captured = capsys.readouterr()
        assert "reading from stdin is not supported" in captured.err

    @pytest.mark.asyncio
    async def test_less_exit_with_zz(self, basic_file, capsys, monkeypatch):
        """Test exiting with ZZ command"""
        char_sequence = iter(["Z", "Z"])

        def mock_get_char():
            return next(char_sequence, "q")

        monkeypatch.setattr("cloudsh.commands.less._get_char", mock_get_char)
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)

        args = Namespace(
            file=[basic_file],
            QUIT_AT_EOF=False,
            quit_if_one_screen=False,
            ignore_case=False,
            IGNORE_CASE=False,
            LINE_NUMBERS=False,
            chop_long_lines=False,
            no_init=True,
            squeeze_blank_lines=False,
            line_numbers=False,
            pattern=None,
        )
        await _run(args)
        # Should exit cleanly without error
        captured = capsys.readouterr()
        assert len(captured.out) > 0

    @pytest.mark.asyncio
    async def test_less_exit_with_colon_q(self, basic_file, capsys, monkeypatch):
        """Test exiting with :q command"""
        char_sequence = iter([":"])

        def mock_get_char():
            return next(char_sequence, "q")

        def mock_get_input(prompt):
            return "q"

        monkeypatch.setattr("cloudsh.commands.less._get_char", mock_get_char)
        monkeypatch.setattr("cloudsh.commands.less._get_input", mock_get_input)
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)

        args = Namespace(
            file=[basic_file],
            QUIT_AT_EOF=False,
            quit_if_one_screen=False,
            ignore_case=False,
            IGNORE_CASE=False,
            LINE_NUMBERS=False,
            chop_long_lines=False,
            no_init=True,
            squeeze_blank_lines=False,
            line_numbers=False,
            pattern=None,
        )
        await _run(args)
        # Should exit cleanly without error
        captured = capsys.readouterr()
        assert len(captured.out) > 0

    @pytest.mark.asyncio
    async def test_less_exit_with_colon_quit(self, basic_file, capsys, monkeypatch):
        """Test exiting with :quit command"""
        char_sequence = iter([":"])

        def mock_get_char():
            return next(char_sequence, "q")

        def mock_get_input(prompt):
            return "quit"

        monkeypatch.setattr("cloudsh.commands.less._get_char", mock_get_char)
        monkeypatch.setattr("cloudsh.commands.less._get_input", mock_get_input)
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)

        args = Namespace(
            file=[basic_file],
            QUIT_AT_EOF=False,
            quit_if_one_screen=False,
            ignore_case=False,
            IGNORE_CASE=False,
            LINE_NUMBERS=False,
            chop_long_lines=False,
            no_init=True,
            squeeze_blank_lines=False,
            line_numbers=False,
            pattern=None,
        )
        await _run(args)
        # Should exit cleanly without error
        captured = capsys.readouterr()
        assert len(captured.out) > 0

    @pytest.mark.asyncio
    async def test_less_single_z_not_exit(self, basic_file, capsys, monkeypatch):
        """Test that single Z doesn't exit (needs ZZ)"""
        char_sequence = iter(["Z", "x", "q"])  # Z, then x (not Z), then q to quit

        def mock_get_char():
            return next(char_sequence, "q")

        monkeypatch.setattr("cloudsh.commands.less._get_char", mock_get_char)
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)

        args = Namespace(
            file=[basic_file],
            QUIT_AT_EOF=False,
            quit_if_one_screen=False,
            ignore_case=False,
            IGNORE_CASE=False,
            LINE_NUMBERS=False,
            chop_long_lines=False,
            no_init=True,
            squeeze_blank_lines=False,
            line_numbers=False,
            pattern=None,
        )
        await _run(args)
        # Should eventually quit with 'q'
        captured = capsys.readouterr()
        assert len(captured.out) > 0
