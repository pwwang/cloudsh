"""Implementation of more command for both local and cloud files.

This module provides a pager functionality similar to the more command,
supporting both local files and cloud storage through panpath.
"""

from __future__ import annotations

import os
import sys
import tty
import termios
from typing import TYPE_CHECKING, BinaryIO, List, Awaitable

from panpath import PanPath

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


def _display_page(
    lines: List[bytes],
    start: int,
    screen_lines: int,
    filename: str,
    args: Namespace,
) -> int:
    """Display a page of text and return the number of lines displayed.

    Args:
        lines: All lines in the file
        start: Starting line index
        screen_lines: Number of lines per screen
        filename: Name of the file being displayed
        args: Command line arguments

    Returns:
        Number of lines displayed
    """
    end = min(start + screen_lines - 1, len(lines))  # -1 for prompt line

    for i in range(start, end):
        try:
            sys.stdout.buffer.write(lines[i])
            if not lines[i].endswith(b"\n"):
                sys.stdout.write("\n")
        except BrokenPipeError:
            sys.exit(141)

    sys.stdout.flush()
    return end - start


def _show_prompt(filename: str, percent: float, args: Namespace) -> str:
    """Show the more prompt and get user input.

    Args:
        filename: Name of the file being displayed
        percent: Percentage of file displayed
        args: Command line arguments

    Returns:
        The character entered by the user
    """
    if args.silent:
        prompt = f"--More--({percent:.0f}%)"
    else:
        prompt = f"--More--({percent:.0f}%) [Press space to continue, 'q' to quit]"

    sys.stdout.write(prompt)
    sys.stdout.flush()

    ch = _get_char()

    # Clear the prompt line
    sys.stdout.write("\r" + " " * len(prompt) + "\r")
    sys.stdout.flush()

    return ch


async def _process_file(
    fh: BinaryIO | Awaitable,
    filename: str,
    args: Namespace,
) -> None:
    """Process a file and display it page by page.

    Args:
        fh: File handle to read from
        filename: Name of the file
        args: Command line arguments
    """
    # Read all lines from the file
    content = fh.read()
    if isinstance(content, Awaitable):
        content = await content

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

    # Handle squeeze option (multiple blank lines -> single blank line)
    if args.squeeze:
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

    # Get terminal size
    if args.lines:
        screen_lines = args.lines
    else:
        screen_lines, _ = _get_terminal_size()

    # Clear screen if not --no-init
    if not args.no_init and not args.print_over and not args.clean_print:
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()

    current_line = 0
    total_lines = len(lines)

    # If no_pause is set, just print everything
    if args.no_pause:
        for line in lines:
            sys.stdout.buffer.write(line)
        return

    while current_line < total_lines:
        # Display a page
        lines_displayed = _display_page(
            lines, current_line, screen_lines, filename, args
        )
        current_line += lines_displayed

        # Check if we've reached the end
        if current_line >= total_lines:
            break

        # Calculate percentage
        percent = (current_line / total_lines) * 100

        # Show prompt and get user input
        ch = _show_prompt(filename, percent, args)

        # Handle user input
        if ch == "q" or ch == "Q":
            # Quit
            break
        elif ch == " ":
            # Next page
            continue
        elif ch == "\r" or ch == "\n":
            # Next line
            current_line -= lines_displayed - 1
        elif ch == "h" or ch == "H":
            # Help
            help_text = """
Most commands optionally preceded by integer argument k.  Defaults in brackets.
Star (*) indicates argument becomes new default.
-------------------------------------------------------------------------------
<space>                 Display next k lines of text [current screen size]
z                       Display next k lines of text [current screen size]*
<return>                Display next k lines of text [1]*
q or Q                  Exit from more
h or H                  Display this help message
-------------------------------------------------------------------------------
"""
            sys.stdout.write(help_text)
            sys.stdout.flush()
            _get_char()  # Wait for keypress
            # Redisplay current page
            current_line -= lines_displayed
        elif ch == "z" or ch == "Z":
            # Next page (same as space)
            continue
        else:
            # For any other key, just continue to next page
            continue


async def run(args: Namespace) -> None:
    """Execute the more command.

    Args:
        args: Parsed command line arguments
    """
    # Default to stdin if no files specified
    files = args.file or ["-"]

    try:
        for i, file in enumerate(files):
            try:
                if file == "-":
                    # Process stdin
                    await _process_file(sys.stdin.buffer, "<stdin>", args)
                else:
                    # Process local or cloud file
                    path = PanPath(file)
                    async with path.a_open("rb") as fh:
                        await _process_file(fh, file, args)

                # Print separator between files if there are multiple files
                if len(files) > 1 and i < len(files) - 1:
                    sys.stdout.write(
                        f"\n::::::::::::::\n{files[i + 1]}\n::::::::::::::\n"
                    )
                    sys.stdout.flush()

            except KeyboardInterrupt:
                # Handle Ctrl+C gracefully
                sys.stdout.write("\n")
                sys.exit(130)
            except BrokenPipeError:
                sys.stderr.close()
                sys.exit(141)
            except (OSError, IOError) as e:
                print(f"{PACKAGE} more: {file}: {str(e)}", file=sys.stderr)
                sys.exit(1)

    except BrokenPipeError:
        sys.stderr.close()
        sys.exit(141)
