"""Implementation of the rm command for both local and cloud files."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING
from panpath import PanPath

from ..utils import PACKAGE

if TYPE_CHECKING:  # pragma: no cover
    from argx import Namespace


def _prompt_user(prompt: str) -> bool:
    """Ask user for confirmation."""
    while True:
        response = input(prompt).lower()
        if response in ["y", "yes"]:
            return True
        if response in ["n", "no"]:
            return False


async def _remove_path(path: Path, args, prompt: bool = False) -> bool:
    """Remove a single file or directory.

    Returns:
        bool: True if removal was successful or skipped, False if error
    """
    try:
        if prompt and not args.force:
            if not _prompt_user(f"rm: remove '{path}'? "):
                return True

        try:
            if await path.a_is_dir():
                if args.recursive:
                    await path.a_rmtree()
                elif args.dir:
                    await path.a_rmdir()
                else:
                    if not args.force:
                        sys.stderr.write(
                            f"{PACKAGE} rm: cannot remove '{path}': "
                            "Is a directory\n"
                        )
                    return False
            else:
                await path.a_unlink(missing_ok=args.force)

            if args.verbose:
                print(f"removed '{path}'")
            return True
        except FileNotFoundError:  # pragma: no cover
            if not args.force:
                sys.stderr.write(
                    f"{PACKAGE} rm: cannot remove '{path}': "
                    "No such file or directory\n"
                )
            return args.force

    except OSError as e:  # pragma: no cover
        if not args.force:
            sys.stderr.write(f"{PACKAGE} rm: cannot remove '{path}': {str(e)}\n")
        return False


async def run(args: Namespace) -> None:
    """Execute the rm command.

    Args:
        args: Parsed command line arguments

    Raises:
        SystemExit: If an error occurs
    """
    if args.i:
        # -i overrides -f and -I
        args.force = False
        prompt_all = True
    elif args.I and len(args.file) > 3 or args.recursive:
        # -I prompts once for >3 files or recursive
        if not args.force and not _prompt_user(
            f"{PACKAGE} rm: remove {len(args.file)} files/directories? "
        ):  # pragma: no cover
            pass
        prompt_all = False
    else:
        prompt_all = False

    success = True
    for filepath in args.file:
        path = PanPath(filepath)
        if not await _remove_path(path, args, prompt=prompt_all):
            success = False

    if not success:
        sys.exit(1)
