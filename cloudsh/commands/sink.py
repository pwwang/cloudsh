from __future__ import annotations

import sys
from typing import TYPE_CHECKING
from cloudpathlib import AnyPath

from ..utils import PACKAGE

if TYPE_CHECKING:
    from argx import Namespace


def run(args: Namespace) -> None:
    """Save piped data to a file

    Args:
        args: Parsed command line arguments
    """
    path = AnyPath(args.file)

    if sys.stdin.isatty():
        sys.stderr.write(f"{PACKAGE} sink: no input data provided through pipe\n")
        sys.exit(1)

    try:
        with path.open("ab" if args.append else "wb") as f:
            f.write(sys.stdin.buffer.read())
    except Exception as e:
        sys.stderr.write(f"{PACKAGE} sink: {str(e)}\n")
        sys.exit(1)
