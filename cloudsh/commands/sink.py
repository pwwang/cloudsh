from __future__ import annotations

import sys
from typing import TYPE_CHECKING
from panpath import PanPath, CloudPath

from ..utils import PACKAGE

if TYPE_CHECKING:
    from argx import Namespace


async def run(args: Namespace) -> None:
    """Save piped data to a file

    Args:
        args: Parsed command line arguments
    """
    if sys.stdin.isatty():
        sys.stderr.write(f"{PACKAGE} sink: no input data provided through pipe\n")
        sys.exit(1)

    path = PanPath(args.file)
    kwargs = {"mode": "ab" if args.append else "wb"}
    if isinstance(path, CloudPath):
        kwargs["chunk_size"] = args.chunk_size

    try:
        async with path.a_open(**kwargs) as f:
            while True:
                line = sys.stdin.buffer.readline()
                if not line:
                    break
                await f.write(line)
    except Exception as e:
        sys.stderr.write(f"{PACKAGE} sink: {str(e)}\n")
        sys.exit(1)
