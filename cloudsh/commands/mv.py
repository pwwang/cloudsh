from __future__ import annotations

import sys
from typing import TYPE_CHECKING
from panpath import PanPath

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


async def _move_path(src: PanPath, dst: PanPath, args: Namespace) -> None:
    """Move a single file or directory."""
    update_how = getattr(args, "update", "all")
    if update_how not in ["all", "older", "none"]:
        print(
            f"{PACKAGE} mv: invalid update option '{update_how}', "
            "must be 'all', 'older', or 'none'",
            file=sys.stderr,
        )
        sys.exit(1)

    if update_how == "none":
        return

    async def _mv(s: PanPath, d: PanPath) -> None:
        if await d.a_is_dir():
            d = d / s.name

        await s.a_rename(d)

        if args.verbose:
            print(f"renamed '{s}' -> '{d}'")

    try:
        if update_how == "all" or not await dst.a_exists():
            await _mv(src, dst)
        else:  # update_how == "older" and dst exists
            src_mtime = (await src.a_stat()).st_mtime
            dst_mtime = (await dst.a_stat()).st_mtime
            if src_mtime > dst_mtime:
                await _mv(src, dst)

    except Exception as e:
        print(
            f"{PACKAGE} mv: cannot move '{src}' to '{dst}': {str(e)}", file=sys.stderr
        )
        sys.exit(1)


async def run(args: Namespace) -> None:
    """Execute the mv command."""
    if args.u:
        args.update = "older"

    args.update = args.update or "all"

    # Strip trailing slashes from paths
    sources = [s.rstrip("/") for s in args.SOURCE]

    # Handle target directory option
    if args.target_directory:
        destination = args.target_directory.rstrip("/")
        dst_path = PanPath(destination)
        if not await dst_path.a_exists():
            await dst_path.a_mkdir(parents=True)
    else:
        destination = args.DEST.rstrip("/")
        dst_path = PanPath(destination)

    # Check for multiple sources
    if len(sources) > 1 and not (args.target_directory or await dst_path.a_is_dir()):
        print(
            f"{PACKAGE} mv: target '{destination}' is not a directory", file=sys.stderr
        )
        sys.exit(1)

    # Move each source
    for src in sources:
        src_path = PanPath(src)
        if not await src_path.a_exists():
            print(
                f"{PACKAGE} mv: cannot stat '{src}': No such file or directory",
                file=sys.stderr,
            )
            sys.exit(1)

        if (
            await dst_path.a_exists()
            and await dst_path.a_is_dir()
            and not args.no_target_directory
        ):
            dst = dst_path / src_path.name
        else:
            dst = dst_path

        if args.no_clobber or (args.interactive and not _prompt_overwrite(str(dst))):
            print(f"{PACKAGE} mv: not replacing '{dst}'", file=sys.stderr)
            return

        await _move_path(src_path, dst, args)
