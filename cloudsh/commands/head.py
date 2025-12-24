"""Implementation of the head command for both local and cloud files.

This module provides functionality similar to GNU head command but with added
support for cloud storage files through yunpath.
"""

from __future__ import annotations

import sys
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING
from panpath import PanPath, LocalPath
from panpath.clients import AsyncFileHandle

from ..utils import PACKAGE, parse_number

if TYPE_CHECKING:  # pragma: no cover
    from typing import Optional
    from argparse import Namespace


def _print_header(filename: str) -> None:
    """Print a header with the filename in GNU head format.

    Args:
        filename: The name of the file to display in the header
    """
    if not hasattr(_print_header, "printed"):
        sys.stdout.write(f"==> {filename} <==\n")
        _print_header.printed = True
    else:
        sys.stdout.write(f"\n==> {filename} <==\n")


def _check_args(args: Namespace) -> Namespace:
    """Check and adjust arguments to ensure compatibility with GNU head.

    Args:
        args: Parsed command line arguments

    Returns:
        Namespace: Adjusted arguments
    """
    # Parse numbers with suffixes
    if args.bytes is not None:
        try:
            args.bytes = parse_number(args.bytes)
        except ValueError as e:
            print(f"{PACKAGE}: invalid number of bytes: {str(e)}", file=sys.stderr)
            sys.exit(1)

    if args.lines is not None:
        try:
            args.lines = parse_number(args.lines)
        except ValueError as e:
            print(f"{PACKAGE}: invalid number of lines: {str(e)}", file=sys.stderr)
            sys.exit(1)

    if not args.file:
        args.file = ["-"]

    args.verbose = (len(args.file) > 1 and not args.quiet) or args.verbose
    return args


def _head_local_file(args: Namespace, file: Path) -> None:
    # Local file or stdin - use GNU head
    cmd = ["head"]
    if args.bytes is not None:
        cmd.extend(["-c", str(args.bytes)])
    if args.lines is not None:
        cmd.extend(["-n", str(args.lines)])
    if args.quiet:
        cmd.append("-q")
    if args.verbose:
        cmd.append("-v")
    if args.zero_terminated:
        cmd.append("-z")
    cmd.append(file)

    proc = subprocess.run(cmd, text=True, capture_output=True, stdin=None)
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    if proc.returncode != 0:
        sys.exit(proc.returncode)


async def _head_cloud_file(
    fh: AsyncFileHandle,
    args: Namespace,
    filename: Optional[str] = None,
) -> None:
    """Process a file (local or cloud) and output its head content.

    Args:
        fh: Binary file handle to read from
        args: Parsed command line arguments containing head options
        filename: Name of the file being processed, used for headers

    Note:
        The function handles both byte-count and line-count modes,
        respecting zero-terminated line option if specified.
    """
    if args.verbose and filename:
        _print_header(filename)

    if args.bytes is not None:
        if args.bytes >= 0:
            content = await fh.read(args.bytes)
        else:
            # For negative bytes, follow GNU head behavior:
            # Print all but the last N bytes (where N = abs(args.bytes))
            # 1. Get file size by seeking to end
            # 2. Calculate how many bytes to read from start: size + args.bytes
            # 3. Seek back to start and read that many bytes
            await fh.seek(0, 2)  # Seek to end to get size
            size = await fh.tell()
            bytes_to_read = max(0, size + args.bytes)  # size + negative = size - abs
            await fh.seek(0, 0)  # Seek back to start
            content = await fh.read(bytes_to_read)
        sys.stdout.buffer.write(content)
        return

    delim = b"\0" if args.zero_terminated else b"\n"
    lines = []
    num_lines = args.lines if args.lines is not None else 10
    abs_num = abs(num_lines)
    if num_lines >= 0:
        remaining = b""  # Keep track of partial lines
        while len(lines) < abs_num:
            chunk = await fh.read(8192)  # Read in chunks
            if not chunk:
                # Handle any remaining partial line
                if remaining:  # pragma: no cover
                    lines.append(remaining)
                    remaining = b""
                break

            data = remaining + chunk
            parts = data.split(delim)

            if len(parts) == 1:
                # No delimiter found, keep accumulating
                remaining = parts[0]
                continue

            # Keep the last part as it might be incomplete
            remaining = parts[-1]
            # Add complete lines
            lines.extend(parts[:-1])

            if len(lines) >= abs_num:
                break

        # Handle final remaining part if we haven't reached the limit
        if remaining and len(lines) < abs_num:  # pragma: no cover
            lines.append(remaining)

        # Only remove empty line if it's the last one
        # if lines and not lines[-1]:
        #     lines.pop()

        lines = [
            (line if line.endswith(delim) else line + delim)
            for line in lines[:abs_num]
        ]
    else:
        # For negative line count:
        # Read all lines first
        content = await fh.read()
        # Split into lines, keeping empty ones
        parts = content.split(delim)
        # Remove last empty line if present
        if parts and not parts[-1]:
            parts.pop()
        # Keep all but the last |num_lines| lines
        lines = parts[:num_lines] if num_lines < 0 else parts
        # Add back delimiters
        lines = [(line if line.endswith(delim) else line + delim) for line in lines]

    sys.stdout.buffer.writelines(lines)


async def run(args: Namespace) -> None:
    """Execute the head command on given files.

    Args:
        args: Parsed command line arguments
    Returns:
        int: The exit status of the command
    """
    args = _check_args(args)

    for file in args.file:
        try:
            path = PanPath(file)
            if file == "-" or isinstance(path, LocalPath):
                _head_local_file(args, path)
            else:
                # Cloud file - use our implementation
                async with path.a_open("rb") as fh:
                    await _head_cloud_file(fh, args, str(path))
        except (OSError, IOError) as e:
            print(f"{PACKAGE}: {file}: {str(e)}", file=sys.stderr)
            sys.exit(1)
