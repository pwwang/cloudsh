"""Implementation of the tail command for both local and cloud files.

This module provides functionality similar to GNU tail command but with added
support for cloud storage files through yunpath.

Key features:
- Supports both local and cloud files
- Implements tail -f (follow) mode
- Handles multiple files with proper headers
- Supports byte and line counting modes
- Compatible with GNU tail options
"""

from __future__ import annotations

import asyncio
import sys
import time
import threading
import subprocess
from queue import Queue, Empty as QueueEmpty
from pathlib import Path
from typing import TYPE_CHECKING
from panpath import PanPath, CloudPath
from panpath.exceptions import NoStatError

from ..utils import PACKAGE, parse_number

if TYPE_CHECKING:  # pragma: no cover
    from typing import BinaryIO, Optional
    from argparse import Namespace


def _print_header(filename: str) -> None:
    """Print a header with the filename in GNU tail format.

    This function ensures headers are printed in the same format as GNU tail:
    - First header is printed without a newline prefix
    - Subsequent headers are prefixed with a newline
    - Format: "==> filename <=="

    Args:
        filename: Name of the file to display in the header
    """
    if not hasattr(_print_header, "printed"):
        sys.stdout.write(f"==> {filename} <==\n")
        _print_header.printed = True
    else:
        sys.stdout.write(f"\n==> {filename} <==\n")


def _check_args(args: Namespace) -> Namespace:
    """Check and adjust arguments to ensure compatibility with GNU tail.

    Performs the following validations and adjustments:
    - Handles -F option (implies -f and --retry)
    - Validates byte/line count formats and suffixes
    - Sets default input to stdin if no files specified
    - Adjusts verbosity based on number of files and quiet flag

    Args:
        args: Parsed command line arguments containing tail options

    Returns:
        Namespace: Adjusted arguments with validated values

    Raises:
        SystemExit: If byte/line count format is invalid
    """
    # Set -F implies -f and --retry
    if args.F:
        args.follow = True
        args.retry = True

    # Parse numbers with suffixes
    if args.bytes is not None:
        try:
            # Just validate the number format
            parse_number(args.bytes[1:] if args.bytes.startswith("+") else args.bytes)
        except ValueError as e:
            print(
                f"{PACKAGE} tail: invalid number of bytes: {str(e)}", file=sys.stderr
            )
            sys.exit(1)

    if args.lines is not None:
        try:
            # Just validate the number format
            parse_number(
                str(args.lines)[1:]
                if str(args.lines).startswith("+")
                else str(args.lines)
            )
        except ValueError as e:
            print(
                f"{PACKAGE} tail: invalid number of lines: {str(e)}", file=sys.stderr
            )
            sys.exit(1)

    # Default to stdin if no files specified
    if not args.file:
        args.file = ["-"]

    args.verbose = (len(args.file) > 1 and not args.quiet) or args.verbose
    return args


async def _tail_cloud_file(
    fh: BinaryIO,
    args: Namespace,
    filename: Optional[str] = None,
) -> None:
    """Process a cloud file and output its tail content.

    Supports two modes of operation:
    1. Byte-based: Read exact number of bytes from start or end
       - Positive count: Read from start
       - Negative count: Read from end
    2. Line-based: Read specified number of lines
       - Positive count: Read from start
       - Negative count: Read from end
       - Handles zero-terminated lines if specified

    Args:
        fh: Binary file handle to read from
        args: Parsed command line arguments containing tail options
        filename: Name of the file being processed, used for headers

    Note:
        For cloud files, all content must be downloaded before processing
        due to lack of random access in cloud storage.
    """
    if args.verbose and filename:
        _print_header(filename)

    # Handle byte counts
    if args.bytes is not None:
        start_at_begin = args.bytes.startswith("+")
        nbytes = parse_number(args.bytes[1:] if start_at_begin else args.bytes)

        if start_at_begin:
            # Skip nbytes from start
            await fh.seek(nbytes - 1 if nbytes > 0 else 0)
            content = await fh.read()
        else:
            # Read last nbytes
            await fh.seek(0, 2)  # Seek to end
            size = await fh.tell()
            await fh.seek(max(0, size - nbytes), 0)
            content = await fh.read()

        sys.stdout.buffer.write(content)
        return

    # Handle line counts
    delim = b"\0" if args.zero_terminated else b"\n"
    start_at_begin = str(args.lines).startswith("+")
    num_lines = parse_number(
        str(args.lines)[1:] if start_at_begin else str(args.lines)
    )

    if start_at_begin:
        # Output starting from line num_lines
        skipped = 0
        while skipped < num_lines - 1:
            line = await fh.readline()
            if not line:
                break
            if line.endswith(delim):
                skipped += 1
        content = await fh.read()
        sys.stdout.buffer.write(content)
    else:
        # Read all lines and output last num_lines
        content = await fh.read()
        lines = content.split(delim)
        if lines and not lines[-1]:
            lines.pop()
        lines = lines[-num_lines:]
        lines = [(line if line.endswith(delim) else line + delim) for line in lines]
        sys.stdout.buffer.writelines(lines)


def _tail_local_file(args: Namespace, file: str) -> None:
    """Handle local file using GNU tail."""
    cmd = ["tail"]
    if args.bytes is not None:
        cmd.extend(["-c", args.bytes])
    if args.lines is not None:
        cmd.extend(["-n", str(args.lines)])
    if args.follow:
        cmd.append("-f")
    if args.retry:
        cmd.append("--retry")
    if args.pid:
        cmd.extend(["--pid", str(args.pid)])
    if args.quiet:
        cmd.append("-q")
    if args.verbose:
        cmd.append("-v")
    if args.zero_terminated:
        cmd.append("-z")
    cmd.append(file)

    proc = subprocess.run(cmd, text=True, capture_output=True)
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    if proc.returncode != 0:
        sys.exit(proc.returncode)


async def _follow_cloud_file(
    path: CloudPath | Path,
    args: Namespace,
    output_queue: Queue,
    filename: Optional[str] = None,
) -> None:
    """Follow a file as it grows, similar to tail -f.

    Implementation details:
    - Uses file size checking to detect changes
    - Supports both local and cloud files
    - Handles file disappearance with --retry option
    - Uses queue for multi-file following
    - Supports interval-based polling

    Args:
        path: Path to the file to follow (local or cloud)
        args: Command line arguments
        output_queue: Queue for multi-file output coordination
        filename: File name for header printing

    Behavior:
    1. Gets initial file size
    2. Polls file for size changes
    3. Reads and outputs new content when size increases
    4. Handles file not found with retry option
    5. Supports clean shutdown on interrupt
    """
    last_size = 0

    # For local files, get initial content without printing
    if isinstance(path, Path):
        try:
            last_size = await path.a_stat().st_size
        except FileNotFoundError:
            if not args.retry:
                return
            last_size = 0

    while True:
        try:
            size = await path.a_stat().st_size
            if size > last_size:
                async with path.a_open("rb") as fh:
                    await fh.seek(last_size)
                    content = await fh.read()
                    if output_queue and not getattr(output_queue, "_closed", False):
                        output_queue.put((filename, content))
                    else:
                        sys.stdout.buffer.write(content)
                        sys.stdout.buffer.flush()
                last_size = size
            await asyncio.sleep(
                float(args.sleep_interval if args.sleep_interval else 1)
            )
        except (FileNotFoundError, OSError, NoStatError):
            if not args.retry:
                return
            await asyncio.sleep(
                float(args.sleep_interval if args.sleep_interval else 1)
            )
        except (KeyboardInterrupt, BrokenPipeError):
            return


def _follow_local_file(
    path: Path,
    args: Namespace,
    output_queue: Queue,
    filename: Optional[str] = None,
) -> None:
    """Follow a local file using GNU tail in subprocess mode.

    This implementation:
    1. Uses GNU tail's native following capability
    2. Streams output through a pipe
    3. Supports multi-file following through queue
    4. Handles clean process termination

    Args:
        path: Path to local file
        args: Command line arguments
        output_queue: Queue for multi-file output coordination
        filename: File name for header printing

    Benefits of using GNU tail directly:
    - More efficient for local files
    - Better handling of file rotation
    - Native support for all tail options
    """
    cmd = ["tail"]
    if args.bytes is not None:
        cmd.extend(["-c", args.bytes])
    if args.lines is not None:
        cmd.extend(["-n", str(args.lines)])
    cmd.extend(["-f", "--retry", str(path)])
    if args.pid:
        cmd.extend(["--pid", str(args.pid)])

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            if output_queue and not getattr(output_queue, "_closed", False):
                output_queue.put((filename, line))
            else:
                sys.stdout.buffer.write(line)
                sys.stdout.buffer.flush()
    except (KeyboardInterrupt, BrokenPipeError):
        proc.terminate()
        proc.wait(timeout=1)


async def run(args: Namespace) -> None:
    """Execute the tail command with given arguments.

    This is the main entry point that:
    1. Validates and adjusts arguments
    2. Sets up output handling for multiple files
    3. Processes each file based on type:
       - stdin: Direct GNU tail
       - Local files: GNU tail or threaded following
       - Cloud files: Custom implementation
    4. Handles clean shutdown on interrupt

    Args:
        args: Parsed command line arguments

    Returns:
        int: Exit status (0 for success, 1 for error)

    Features:
    - Multi-file support with headers
    - Mixed local/cloud file handling
    - Follow mode with queue-based output coordination
    - Clean thread/process cleanup on exit

    Raises:
        SystemExit: If an error occurs
    """
    args = _check_args(args)

    if args.pid:
        try:
            int(args.pid)  # Validate PID format
        except ValueError:
            print(f"{PACKAGE} tail: invalid PID: {args.pid}", file=sys.stderr)
            sys.exit(1)

    # Set up output handling for multiple files
    output_queue = Queue() if args.follow and len(args.file) > 1 else None
    follow_threads = []
    output_thread = None

    if output_queue:

        def output_handler():
            try:
                last_file = None
                while True:
                    try:
                        filename, content = output_queue.get(timeout=0.5)
                        if filename is not None and filename != last_file:
                            _print_header(filename)
                            last_file = filename
                        sys.stdout.buffer.write(content)
                        sys.stdout.buffer.flush()
                        output_queue.task_done()
                    except QueueEmpty:
                        if getattr(output_queue, "_closed", False):
                            break
            except (KeyboardInterrupt, BrokenPipeError):
                pass

        output_thread = threading.Thread(target=output_handler)
        output_thread.daemon = True
        output_thread.start()

    try:
        for file in args.file:
            try:
                path = PanPath(file)
                if file == "-":
                    # Use GNU tail directly for stdin
                    _tail_local_file(args, file)
                elif isinstance(path, Path):
                    if not args.follow:
                        _tail_local_file(args, file)
                    else:
                        if not path.exists():
                            if not args.retry:
                                print(
                                    f"{PACKAGE} tail: {file}: "
                                    "No such file or directory",
                                    file=sys.stderr,
                                )
                                sys.exit(1)
                            # Retry mode: Wait for file to appear
                            while not path.exists():
                                time.sleep(1)
                        # Follow local file in a thread for multiple files
                        thread = threading.Thread(
                            target=_follow_local_file,
                            args=(path, args, output_queue, str(path)),
                        )
                        thread.daemon = True
                        thread.start()
                        follow_threads.append(thread)
                else:
                    # Cloud file
                    if not args.follow:
                        async with path.a_open("rb") as fh:
                            await _tail_cloud_file(fh, args, str(path))
                    else:
                        if not await path.a_exists():
                            if not args.retry:
                                print(
                                    f"{PACKAGE} tail: {file}: "
                                    "No such file or directory",
                                    file=sys.stderr,
                                )
                                sys.exit(1)
                            # Retry mode: Wait for file to appear
                            while not await path.a_exists():
                                time.sleep(1)
                        thread = threading.Thread(
                            target=_follow_cloud_file,
                            args=(path, args, output_queue, str(path)),
                        )
                        thread.daemon = True
                        thread.start()
                        follow_threads.append(thread)

            except (OSError, IOError) as e:
                print(f"{PACKAGE} tail: {file}: {str(e)}", file=sys.stderr)
                if not args.retry:
                    sys.exit(1)

        # Wait for KeyboardInterrupt if following
        if follow_threads:
            try:
                while True:
                    time.sleep(0.1)
            except KeyboardInterrupt:
                pass

    except KeyboardInterrupt:
        if output_queue:
            output_queue._closed = True
        for thread in follow_threads:
            thread.join(timeout=0.5)
        if output_thread:
            output_thread.join(timeout=0.5)
