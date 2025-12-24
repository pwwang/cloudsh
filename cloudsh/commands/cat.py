"""Implementation of GNU cat command for both local and cloud files."""

from __future__ import annotations

import sys
import asyncio
from typing import TYPE_CHECKING, AsyncGenerator

from panpath import PanPath, LocalPath
from panpath.clients import AsyncFileHandle

from ..utils import PACKAGE

if TYPE_CHECKING:
    from argx import Namespace


async def _process_stdin(args) -> None:
    """Process stdin line by line, echoing each line immediately like GNU cat.

    Args:
        args: Command line arguments
    """
    cmd = ["cat"]
    if args.number:
        cmd.append("-n")
    if args.number_nonblank:
        cmd.append("-b")
    if args.squeeze_blank:
        cmd.append("-s")
    if args.show_ends or args.show_all or args.e:
        cmd.append("-E")
    if args.show_tabs or args.show_all or args.t:
        cmd.append("-T")
    if args.show_nonprinting or args.show_all or args.t or args.e:
        cmd.append("-v")

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # Check if stdin has fileno() method (real stdin vs mock for testing)
    has_real_stdin = hasattr(sys.stdin, "fileno") and callable(
        getattr(sys.stdin, "fileno", None)
    )

    async def read_stdin_and_forward():
        """Read from stdin asynchronously and forward to process."""
        try:
            if has_real_stdin:
                # Use async reading for real stdin (interactive mode)
                loop = asyncio.get_event_loop()
                reader = asyncio.StreamReader()
                protocol = asyncio.StreamReaderProtocol(reader)
                await loop.connect_read_pipe(lambda: protocol, sys.stdin)

                while True:
                    line = await reader.readline()
                    if not line:
                        break
                    process.stdin.write(line)
                    await process.stdin.drain()
            else:
                # Fallback for mock stdin (testing mode)
                for line in sys.stdin.buffer:
                    process.stdin.write(line)
                    await process.stdin.drain()
        except Exception:
            pass
        finally:
            if not process.stdin.is_closing():
                process.stdin.close()

    async def read_and_forward(stream, output):
        """Read from stream and forward to output immediately."""
        try:
            while True:
                line = await stream.readline()
                if not line:
                    break
                output.buffer.write(line)
                output.buffer.flush()
        except Exception:
            pass

    try:
        # Start all tasks
        stdin_task = asyncio.create_task(read_stdin_and_forward())
        stdout_task = asyncio.create_task(
            read_and_forward(process.stdout, sys.stdout)
        )
        stderr_task = asyncio.create_task(
            read_and_forward(process.stderr, sys.stderr)
        )

        # Wait for all tasks
        await asyncio.gather(stdin_task, stdout_task, stderr_task)
        await process.wait()

    except (asyncio.CancelledError, KeyboardInterrupt):
        # Cancel all tasks
        stdin_task.cancel()
        stdout_task.cancel()
        stderr_task.cancel()
        process.kill()
        try:
            await asyncio.gather(
                stdin_task, stdout_task, stderr_task, return_exceptions=True
            )
        except Exception:
            pass

        await process.wait()


async def _process_local_file(
    filename: str,
    args,
) -> None:
    """Process a local file using the system's cat command.

    Args:
        filename: The name of the local file to process
        args: Command line arguments
    """
    cmd = ["cat"]
    if args.number:
        cmd.append("-n")
    if args.number_nonblank:
        cmd.append("-b")
    if args.squeeze_blank:
        cmd.append("-s")
    if args.show_ends or args.show_all or args.e:
        cmd.append("-E")
    if args.show_tabs or args.show_all or args.t:
        cmd.append("-T")
    if args.show_nonprinting or args.show_all or args.t or args.e:
        cmd.append("-v")

    cmd.append(filename)

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await process.communicate()
    except asyncio.CancelledError:
        process.kill()
        await process.wait()
    else:
        if stdout:
            sys.stdout.buffer.write(stdout)
        if stderr:
            sys.stderr.buffer.write(stderr)


async def _process_cloud_file(
    fh: AsyncFileHandle,
    args,
) -> AsyncGenerator[bytes]:
    """Process a file according to cat options.

    Args:
        fh: File handle to read from
        args: Command line arguments

    Yields:
        Processed lines of output
    """
    line_num = 0
    last_empty = False

    while True:
        line = await fh.readline()
        if not line:
            break

        # Handle empty lines
        is_empty = line.strip() == b""
        if args.squeeze_blank and is_empty and last_empty:
            continue
        last_empty = is_empty

        # Line numbering
        line_num += 1
        if args.number_nonblank and not is_empty:
            yield f"{line_num:6}\t".encode()
        elif args.number and not args.number_nonblank:
            yield f"{line_num:6}\t".encode()

        # Handle special characters
        if args.show_tabs or args.show_all or args.t:
            line = line.replace(b"\t", b"^I")

        if args.show_nonprinting or args.show_all or args.t or args.e:
            # Convert non-printing characters to ^ notation
            chars = []
            for char in line:
                if char < 32 and char != 10:  # Not newline
                    chars.append(b"^" + bytes([char + 64]))
                elif char == 127:
                    chars.append(b"^?")
                elif char >= 128:
                    chars.append(b"M-" + bytes([char - 128]))
                else:
                    chars.append(bytes([char]))
            line = b"".join(chars)

        # Add $ at end of line
        if args.show_ends or args.show_all or args.show_ends or args.e:
            if line.endswith(b"\n"):
                line = line[:-1] + b"$\n"

        yield line


async def run(args: Namespace) -> None:
    """Execute the cat command.

    Args:
        args: Parsed command line arguments

    Raises:
        SystemExit: On error or keyboard interrupt
    """
    # Handle -A (show-all) option
    if args.show_all:
        args.show_nonprinting = True
        args.show_ends = True
        args.show_tabs = True

    # Handle -e and -t options
    if args.e:
        args.show_nonprinting = True
        args.show_ends = True
    if args.t:
        args.show_nonprinting = True
        args.show_tabs = True

    # Default to stdin if no files specified
    files = args.file or ["-"]

    try:
        for file in files:
            try:
                if file == "-":
                    await _process_stdin(args)
                else:
                    path = PanPath(file)
                    if await path.a_exists() is False:
                        print(
                            f"{PACKAGE} cat: {file}: No such file or directory",
                            file=sys.stderr,
                        )
                        sys.exit(1)

                    if isinstance(path, LocalPath):
                        # Use cat command for local files or stdin
                        await _process_local_file(file, args)
                    else:
                        # Process local or cloud file
                        path = PanPath(file)
                        async with path.a_open("rb") as fh:
                            async for chunk in _process_cloud_file(fh, args):
                                sys.stdout.buffer.write(chunk)
                    sys.stdout.buffer.flush()
            except BrokenPipeError:
                sys.stderr.close()  # Prevent additional errors
                sys.exit(141)  # Standard Unix practice
            except (OSError, IOError) as e:
                print(f"cat: {file}: {str(e)}", file=sys.stderr)
                sys.exit(1)

    except KeyboardInterrupt:
        sys.exit(130)  # Standard Unix practice
