"""Implementation of GNU cp command for both local and cloud files."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING
from panpath import PanPath, CloudPath

from ..utils import PACKAGE

if TYPE_CHECKING:
    from argx import Namespace


def _prompt_overwrite(path: str) -> bool:
    """Ask user whether to overwrite an existing file."""
    while True:
        response = input(f"overwrite '{path}'? ").lower()
        if response in ["y", "yes"]:
            return True
        if response in ["n", "no"]:
            return False


async def _copy_path(src: PanPath, dst: PanPath, args: Namespace) -> None:
    """Copy a single file or directory.

    Args:
        src: Source path
        dst: Destination path
        args: Command line arguments
    """
    try:
        # Ensure parent directory exists
        if not await dst.parent.a_exists():
            print(
                f"{PACKAGE} cp: cannot create '{dst}': No such file or directory",
                file=sys.stderr,
            )
            sys.exit(1)

        # If destination is an existing directory and source isn't a directory,
        # append source filename
        if await dst.a_exists() and await dst.a_is_dir():
            dst = dst / src.name

        # Now check for conflicts
        if await dst.a_exists():
            if args.no_clobber:
                return
            if args.interactive and not _prompt_overwrite(str(dst)):
                return

            args.force = True
            if await dst.a_is_dir() and not await src.a_is_dir():
                print(
                    f"{PACKAGE} cp: cannot overwrite directory '{dst}' "
                    "with non-directory",
                    file=sys.stderr,
                )
                sys.exit(1)

        if await src.a_is_dir():
            if not args.recursive:
                print(
                    f"{PACKAGE} cp: -r not specified; omitting directory '{src}'",
                    file=sys.stderr,
                )
                sys.exit(1)

            # Create destination directory
            await dst.a_mkdir(parents=True, exist_ok=True)
            if args.verbose:
                print(f"created directory '{dst}'")

            # Copy directory contents
            async for item in src.a_iterdir():
                dst_item = dst / item.name
                await _copy_path(item, dst_item, args)
        else:
            if args.verbose:
                print(f"'{src}' -> '{dst}'")

            await src.a_copy(dst)

    except (OSError, IOError) as e:
        print(
            f"{PACKAGE} cp: cannot copy '{src}' to '{dst}': {str(e)}", file=sys.stderr
        )
        sys.exit(1)


async def run(args: Namespace) -> None:
    """Execute the cp command."""
    sources = args.SOURCE
    # Strip trailing slashes from source and destination
    destination = PanPath(args.DEST.rstrip("/"))

    if args.target_directory:
        target_dir = PanPath(args.target_directory.rstrip("/"))
        if not await target_dir.a_exists():
            await target_dir.a_mkdir(parents=True)
        destination = target_dir

    # Validate arguments
    if len(sources) > 1 and not (args.target_directory or await destination.a_is_dir()):
        print(
            f"{PACKAGE} cp: target must be a directory when copying multiple files",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.parents and not await destination.a_is_dir():
        print(
            f"{PACKAGE} cp: with --parents, destination must be a directory",
            file=sys.stderr,
        )
        sys.exit(1)

    # Copy each source
    for src in sources:
        src_path = PanPath(src.rstrip("/"))
        if (
            isinstance(src_path, CloudPath)
            and isinstance(destination, CloudPath)
            and args.parents
        ):
            print(
                f"{PACKAGE} cp: cannot preserve directory structure when copying "
                "between cloud paths",
                file=sys.stderr,
            )
            sys.exit(1)

        if (
            not args.target_directory
            and len(sources) == 1
            and not args.no_target_directory
        ):
            if await destination.a_exists() and await destination.a_is_dir():
                # If destination exists as directory, append source name
                if args.parents:
                    # Preserve directory structure
                    dst_path = destination / str(src_path).lstrip("/")
                else:
                    dst_path = destination / src_path.name
            else:
                # Single file/directory to new path
                dst_path = destination
        else:
            # Copy to directory - always preserve directory name
            if args.parents:
                # Preserve directory structure
                dst_path = destination / str(src_path).lstrip("/")
            else:
                # Directory or file name becomes part of destination
                dst_path = destination / src_path.name

        await _copy_path(src_path, dst_path, args)
