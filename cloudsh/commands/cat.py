"""Implementation of GNU cat command for both local and cloud files."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, BinaryIO, Iterator

from cloudpathlib import AnyPath

if TYPE_CHECKING:
    from argx import Namespace


def _process_file(fh: BinaryIO, args) -> Iterator[bytes]:
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
        line = fh.readline()
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


def run(args: Namespace) -> None:
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
                    # Process stdin
                    for chunk in _process_file(sys.stdin.buffer, args):
                        sys.stdout.buffer.write(chunk)
                else:
                    # Process local or cloud file
                    path = AnyPath(file)
                    with path.open("rb") as fh:
                        for chunk in _process_file(fh, args):
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
