from __future__ import annotations

import sys
from typing import TYPE_CHECKING
from panpath import PanPath, CloudPath

from ..utils import PACKAGE

if TYPE_CHECKING:
    from argx import Namespace


def _parse_mode(mode_str: str | None) -> int:
    """Parse mode string to integer mode"""
    if not mode_str:
        return 0o777
    try:
        # Allow both octal (0o755) and symbolic (755) modes
        return int(str(mode_str).strip("0o"), 8)
    except ValueError:
        sys.stderr.write(f"Invalid mode: {mode_str}\n")
        sys.exit(1)


async def run(args: Namespace) -> None:
    """Create directories

    Args:
        args: Parsed command line arguments
    """
    mode = _parse_mode(args.mode)
    if isinstance(mode, int) and mode == 1:
        sys.exit(1)

    for directory in args.directory:
        path = PanPath(directory)
        try:
            if isinstance(path, CloudPath):
                await path.a_mkdir(parents=args.parents, exist_ok=args.parents)
            else:
                await path.a_mkdir(
                    mode=mode, parents=args.parents, exist_ok=args.parents
                )

            if args.verbose:
                print(f"created directory '{directory}'")

        except FileExistsError:
            if not args.parents:
                print(
                    f"{PACKAGE} mkdir: cannot create directory '{directory}': "
                    "File exists",
                    file=sys.stderr,
                )
                sys.exit(1)
        except (OSError, ValueError) as e:
            msg = str(e)
            if "Not a directory" in msg:
                print(
                    f"{PACKAGE} mkdir: cannot create directory '{directory}': "
                    "Not a directory",
                    file=sys.stderr,
                )
            else:
                print(
                    f"{PACKAGE} mkdir: cannot create directory '{directory}': {msg}",
                    file=sys.stderr,
                )
            sys.exit(1)
