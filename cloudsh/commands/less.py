"""Implementation of less command for both local and cloud files.

This module provides a pager functionality similar to the less command,
supporting both local files and cloud storage through yunpath.
Less is more powerful than more, providing backward scrolling and search.
"""

from __future__ import annotations

import os
import re
import sys
import tty
import termios
from typing import TYPE_CHECKING, List, Optional

from panpath import PanPath
from panpath.clients import AsyncFileHandle

from ..utils import PACKAGE

if TYPE_CHECKING:
    from argx import Namespace


def _get_terminal_size() -> tuple[int, int]:
    """Get the terminal size (rows, columns).

    Returns:
        Tuple of (rows, columns), defaults to (24, 80) if unable to determine
    """
    try:
        # Try using shutil first (Python 3.3+)
        import shutil

        size = shutil.get_terminal_size(fallback=(80, 24))
        return size.lines, size.columns
    except Exception:
        try:
            # Fallback to stty
            rows, cols = os.popen("stty size", "r").read().split()
            return int(rows), int(cols)
        except Exception:
            # Final fallback to default terminal size
            return 24, 80


def _get_char() -> str:
    """Get a single character from stdin without echo.

    Returns:
        The character pressed by the user
    """
    # Check if stdin is a TTY
    if not sys.stdin.isatty():
        # Not a TTY, just read one character
        ch = sys.stdin.read(1)
        return ch if ch else "q"  # Return 'q' on EOF to quit

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch


def _get_input(prompt: str) -> str:
    """Get a line of input from the user with a prompt.

    Args:
        prompt: The prompt to display

    Returns:
        The input string
    """
    # Restore terminal settings temporarily
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        sys.stdout.write(prompt)
        sys.stdout.flush()
        # Read until newline
        result = []
        while True:
            ch = sys.stdin.read(1)
            if ch == "\n" or ch == "\r":
                break
            elif ch == "\x7f" or ch == "\b":  # Backspace
                if result:
                    result.pop()
                    sys.stdout.write("\b \b")
                    sys.stdout.flush()
            else:
                result.append(ch)
                sys.stdout.write(ch)
                sys.stdout.flush()
        return "".join(result)
    finally:
        pass


def _clear_screen() -> None:
    """Clear the terminal screen."""
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def _enter_alternate_screen() -> None:
    """Enter the alternate screen buffer."""
    sys.stdout.write("\033[?1049h")
    sys.stdout.flush()


def _exit_alternate_screen() -> None:
    """Exit the alternate screen buffer."""
    sys.stdout.write("\033[?1049l")
    sys.stdout.flush()


def _display_lines(
    lines: List[bytes],
    start: int,
    screen_lines: int,
    args: Namespace,
) -> int:
    """Display lines starting from start index.

    Args:
        lines: All lines in the file
        start: Starting line index
        screen_lines: Number of lines per screen
        args: Command line arguments

    Returns:
        Number of lines displayed
    """
    end = min(start + screen_lines - 1, len(lines))  # -1 for status line

    for i in range(start, end):
        line = lines[i]

        # Add line numbers if requested
        if args.LINE_NUMBERS or args.line_numbers:
            sys.stdout.write(f"{i + 1:6} ")

        # Handle long lines
        if args.chop_long_lines:
            _, cols = _get_terminal_size()
            prefix_len = 7 if (args.LINE_NUMBERS or args.line_numbers) else 0
            max_len = cols - prefix_len - 1
            if len(line) > max_len:
                line = line[:max_len]

        try:
            sys.stdout.buffer.write(line)
            if not line.endswith(b"\n"):
                sys.stdout.write("\n")
        except BrokenPipeError:
            sys.exit(141)

    sys.stdout.flush()
    return end - start


def _show_status(
    filename: str,
    current_line: int,
    total_lines: int,
    message: str = "",
) -> None:
    """Show the status line at the bottom of the screen.

    Args:
        filename: Name of the file being displayed
        current_line: Current line number
        total_lines: Total number of lines
        message: Optional message to display
    """
    if total_lines == 0:
        percent = 100
    else:
        percent = min(100, int((current_line / total_lines) * 100))

    if message:
        status = message
    elif current_line >= total_lines:
        status = f"{filename} (END)"
    else:
        status = f"{filename} ({percent}%)"

    # Use reverse video for status line
    sys.stdout.write(f"\033[7m{status}\033[0m")
    sys.stdout.flush()


def _clear_status() -> None:
    """Clear the status line."""
    sys.stdout.write("\r\033[K")
    sys.stdout.flush()


def _search_forward(
    lines: List[bytes],
    pattern: str,
    start: int,
    ignore_case: bool,
) -> Optional[int]:
    """Search forward for a pattern.

    Args:
        lines: All lines in the file
        pattern: Pattern to search for
        start: Starting line index
        ignore_case: Whether to ignore case

    Returns:
        Line index where pattern was found, or None
    """
    flags = re.IGNORECASE if ignore_case else 0
    try:
        regex = re.compile(pattern.encode(), flags)
    except re.error:
        return None

    for i in range(start, len(lines)):
        if regex.search(lines[i]):
            return i
    return None


def _search_backward(
    lines: List[bytes],
    pattern: str,
    start: int,
    ignore_case: bool,
) -> Optional[int]:
    """Search backward for a pattern.

    Args:
        lines: All lines in the file
        pattern: Pattern to search for
        start: Starting line index
        ignore_case: Whether to ignore case

    Returns:
        Line index where pattern was found, or None
    """
    flags = re.IGNORECASE if ignore_case else 0
    try:
        regex = re.compile(pattern.encode(), flags)
    except re.error:
        return None

    for i in range(start - 1, -1, -1):
        if regex.search(lines[i]):
            return i
    return None


async def _process_file(fh: AsyncFileHandle, filename: str, args: Namespace) -> None:
    """Process a file and display it with less-like navigation.

    Args:
        fh: File handle to read from
        filename: Name of the file
        args: Command line arguments
    """
    # Read all lines from the file
    content = await fh.read()
    if not content:
        return

    # Split by newline
    parts = content.split(b"\n")

    # Reconstruct lines with newlines
    lines = []
    for i, part in enumerate(parts[:-1]):
        lines.append(part + b"\n")

    # Handle the last part
    if content.endswith(b"\n"):
        # Last part is empty, don't add it
        pass
    else:
        # Last part doesn't have a newline
        lines.append(parts[-1])

    # Handle squeeze option
    if args.squeeze_blank_lines:
        squeezed_lines = []
        prev_empty = False
        for line in lines:
            is_empty = line.strip() == b""
            if is_empty and prev_empty:
                continue
            squeezed_lines.append(line)
            prev_empty = is_empty
        lines = squeezed_lines

    if not lines:
        return

    screen_lines, screen_cols = _get_terminal_size()
    total_lines = len(lines)

    # Check if entire file fits on one screen
    if args.quit_if_one_screen and total_lines <= screen_lines:
        for line in lines:
            sys.stdout.buffer.write(line)
        return

    # Find initial position if pattern is specified
    current_line = 0
    if args.pattern:
        found = _search_forward(
            lines,
            args.pattern,
            0,
            args.ignore_case or args.IGNORE_CASE,
        )
        if found is not None:
            current_line = found

    # Enter alternate screen buffer unless --no-init
    if not args.no_init:
        _enter_alternate_screen()
        _clear_screen()

    search_pattern = args.pattern or ""
    eof_count = 0

    try:
        while True:
            # Ensure current_line is within bounds
            current_line = max(0, min(current_line, total_lines - 1))

            # Display current page
            if not args.no_init:
                _clear_screen()

            lines_displayed = _display_lines(lines, current_line, screen_lines, args)

            # Show status line
            _show_status(filename, current_line + lines_displayed, total_lines)

            # Get user input
            ch = _get_char()

            # Clear status line
            _clear_status()

            # Handle commands
            if ch == "q" or ch == "Q":
                # Quit
                break
            elif ch == "Z":
                # Check for ZZ (quit)
                ch2 = _get_char()
                if ch2 == "Z":
                    break
                # If not ZZ, ignore both characters
                eof_count = 0
            elif ch == ":":
                # Check for :q (quit)
                command = _get_input(":")
                if command in ("q", "Q", "quit"):
                    break
                # If not a quit command, ignore
                eof_count = 0
            elif ch == " " or ch == "f" or ch == "\x06":  # Space, f, or Ctrl+F
                # Forward one screen
                current_line += screen_lines - 1
                if current_line >= total_lines - 1:
                    current_line = max(0, total_lines - screen_lines)
                    eof_count += 1
                    if args.QUIT_AT_EOF and eof_count >= 2:
                        break
            elif ch == "b" or ch == "\x02":  # b or Ctrl+B
                # Backward one screen
                current_line -= screen_lines - 1
                current_line = max(0, current_line)
                eof_count = 0
            elif (
                ch == "\r" or ch == "\n" or ch == "j" or ch == "\x0e"
            ):  # Enter, j, or Ctrl+N
                # Forward one line
                if current_line < total_lines - 1:
                    current_line += 1
                eof_count = 0
            elif ch == "k" or ch == "\x10" or ch == "y":  # k, Ctrl+P, or y
                # Backward one line
                if current_line > 0:
                    current_line -= 1
                eof_count = 0
            elif ch == "d" or ch == "\x04":  # d or Ctrl+D
                # Forward half screen
                current_line += screen_lines // 2
                eof_count = 0
            elif ch == "u" or ch == "\x15":  # u or Ctrl+U
                # Backward half screen
                current_line -= screen_lines // 2
                current_line = max(0, current_line)
                eof_count = 0
            elif ch == "g" or ch == "<":
                # Go to beginning
                current_line = 0
                eof_count = 0
            elif ch == "G" or ch == ">":
                # Go to end
                current_line = max(0, total_lines - screen_lines)
                eof_count = 0
            elif ch == "/":
                # Search forward
                pattern = _get_input("/")
                if pattern:
                    search_pattern = pattern
                    found = _search_forward(
                        lines,
                        search_pattern,
                        current_line + 1,
                        args.ignore_case or args.IGNORE_CASE,
                    )
                    if found is not None:
                        current_line = found
                    else:
                        _show_status(
                            filename, current_line, total_lines, "Pattern not found"
                        )
                        _get_char()
                eof_count = 0
            elif ch == "?":
                # Search backward
                pattern = _get_input("?")
                if pattern:
                    search_pattern = pattern
                    found = _search_backward(
                        lines,
                        search_pattern,
                        current_line,
                        args.ignore_case or args.IGNORE_CASE,
                    )
                    if found is not None:
                        current_line = found
                    else:
                        _show_status(
                            filename, current_line, total_lines, "Pattern not found"
                        )
                        _get_char()
                eof_count = 0
            elif ch == "n":
                # Repeat last search forward
                if search_pattern:
                    found = _search_forward(
                        lines,
                        search_pattern,
                        current_line + 1,
                        args.ignore_case or args.IGNORE_CASE,
                    )
                    if found is not None:
                        current_line = found
                    else:
                        _show_status(
                            filename, current_line, total_lines, "Pattern not found"
                        )
                        _get_char()
                eof_count = 0
            elif ch == "N":
                # Repeat last search backward
                if search_pattern:
                    found = _search_backward(
                        lines,
                        search_pattern,
                        current_line,
                        args.ignore_case or args.IGNORE_CASE,
                    )
                    if found is not None:
                        current_line = found
                    else:
                        _show_status(
                            filename, current_line, total_lines, "Pattern not found"
                        )
                        _get_char()
                eof_count = 0
            elif ch == "h" or ch == "H":
                # Help
                help_lines = [
                    b"SUMMARY OF LESS COMMANDS\n",
                    b"\n",
                    b"  Commands marked with * may be preceded by a number, N.\n",
                    b"\n",
                    b"  h  H                 Display this help.\n",
                    b"  q  Q  ZZ  :q         Exit.\n",
                    b"\n",
                    b"  MOVING:\n",
                    b"  SPACE  f  ^F  *      Forward one screen.\n",
                    b"  b  ^B             *  Backward one screen.\n",
                    b"  RETURN  j  ^N     *  Forward one line.\n",
                    b"  k  y  ^P          *  Backward one line.\n",
                    b"  d  ^D             *  Forward one half-screen.\n",
                    b"  u  ^U             *  Backward one half-screen.\n",
                    b"  g  <              *  Go to first line in file.\n",
                    b"  G  >              *  Go to last line in file.\n",
                    b"\n",
                    b"  SEARCHING:\n",
                    b"  /pattern          *  Search forward for pattern.\n",
                    b"  ?pattern          *  Search backward for pattern.\n",
                    b"  n                 *  Repeat previous search (forward).\n",
                    b"  N                 *  Repeat previous search (backward).\n",
                    b"\n",
                ]
                _clear_screen()
                for line in help_lines:
                    sys.stdout.buffer.write(line)
                sys.stdout.write("\nPress any key to continue...")
                sys.stdout.flush()
                _get_char()
                eof_count = 0
    finally:
        # Exit alternate screen buffer unless --no-init
        if not args.no_init:
            _exit_alternate_screen()


async def run(args: Namespace) -> None:
    """Execute the less command.

    Args:
        args: Parsed command line arguments
    """
    # Default to stdin if no files specified
    files = args.file
    if not files:
        print(
            f"{PACKAGE} less: Missing filename (cloudsh less --help for help)",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        for file in files:
            try:
                if file == "-":
                    print(
                        f"{PACKAGE} less: reading from stdin is not supported",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                else:
                    # Process local or cloud file
                    path = PanPath(file)
                    async with path.a_open("rb") as fh:
                        await _process_file(fh, file, args)

            except KeyboardInterrupt:
                # Handle Ctrl+C gracefully
                if not args.no_init:
                    _exit_alternate_screen()
                sys.exit(130)
            except BrokenPipeError:
                sys.stderr.close()
                sys.exit(141)
            except (OSError, IOError) as e:
                print(f"{PACKAGE} less: {file}: {str(e)}", file=sys.stderr)
                sys.exit(1)

    except BrokenPipeError:
        sys.stderr.close()
        sys.exit(141)
