from __future__ import annotations

import sys
import shutil
from typing import TYPE_CHECKING
from cloudpathlib import AnyPath, CloudPath
from cloudpathlib.exceptions import CloudPathNotImplementedError

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


def _move_cloud_dir(src: CloudPath, dst: CloudPath, args: Namespace) -> None:
    """Move a cloud directory by copying files recursively and then deleting source."""
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        dst_item = dst / item.name
        if item.is_dir():
            _move_cloud_dir(item, dst_item, args)
        else:
            if dst_item.exists():
                if args.no_clobber:
                    continue
                if (
                    args.update == "older"
                    and dst_item.stat().st_mtime >= item.stat().st_mtime
                ):
                    continue
                dst_item.unlink()
            item.rename(dst_item)

    src.rmdir()  # Remove empty directory after moving contents


def _move_path(src: AnyPath, dst: AnyPath, args: Namespace) -> None:
    """Move a single file or directory."""
    try:
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
        except CloudPathNotImplementedError:
            pass

        if dst.exists() and dst.is_dir():
            dst = dst / src.name

        # Handle update modes and conflicts first
        if dst.exists():
            # --update=none or -n/--no-clobber: never overwrite
            if args.update == "none" or args.no_clobber:
                return

            # --update=older (default when -u/--update used)
            if args.u or (args.update == "older"):
                try:
                    if dst.stat().st_mtime >= src.stat().st_mtime:
                        return
                except (OSError, AttributeError):
                    pass

            if args.interactive and not _prompt_overwrite(str(dst)):
                return

            if dst.is_dir() and not src.is_dir():
                print(
                    f"{PACKAGE} mv: cannot overwrite directory '{dst}' "
                    "with non-directory",
                    file=sys.stderr,
                )
                sys.exit(1)

        try:
            if isinstance(src, CloudPath):
                if isinstance(dst, CloudPath):
                    if src.is_dir():
                        _move_cloud_dir(src, dst, args)
                    else:
                        if dst.exists():
                            dst.unlink()
                        src.rename(dst)
                else:
                    # Cloud to local
                    if src.is_dir():
                        dst.mkdir(parents=True, exist_ok=True)
                        for item in src.iterdir():
                            _move_path(item, dst / item.name, args)
                        src.rmdir()
                    else:
                        src.download_to(dst)
                        src.unlink()
            else:
                if isinstance(dst, CloudPath):
                    # Local to cloud
                    if src.is_dir():
                        dst.mkdir(parents=True, exist_ok=True)
                        for item in src.iterdir():
                            _move_path(item, dst / item.name, args)
                        shutil.rmtree(src)
                    else:
                        dst.upload_from(src)
                        src.unlink()
                else:
                    # Local to local
                    src.replace(dst)

            if getattr(args, "verbose", False):
                print(f"renamed '{src}' -> '{dst}'")

        except Exception as e:
            print(
                f"{PACKAGE} mv: cannot move '{src}' to '{dst}': {str(e)}",
                file=sys.stderr,
            )
            sys.exit(1)

    except Exception as e:
        print(
            f"{PACKAGE} mv: cannot move '{src}' to '{dst}': {str(e)}", file=sys.stderr
        )
        sys.exit(1)


def run(args: Namespace) -> None:
    """Execute the mv command."""
    if args.u:
        args.update = "older"

    # Strip trailing slashes from paths
    sources = [s.rstrip("/") for s in args.SOURCE]

    # Handle target directory option
    if args.target_directory:
        destination = args.target_directory.rstrip("/")
        dst_path = AnyPath(destination)
        if not dst_path.exists():
            dst_path.mkdir(parents=True)
    else:
        destination = args.DEST.rstrip("/")
        dst_path = AnyPath(destination)

    # Check for multiple sources
    if len(sources) > 1 and not (args.target_directory or dst_path.is_dir()):
        print(
            f"{PACKAGE} mv: target '{destination}' is not a directory", file=sys.stderr
        )
        sys.exit(1)

    # Move each source
    for src in sources:
        src_path = AnyPath(src)
        if not src_path.exists():
            print(
                f"{PACKAGE} mv: cannot stat '{src}': No such file or directory",
                file=sys.stderr,
            )
            sys.exit(1)

        if dst_path.exists() and dst_path.is_dir() and not args.no_target_directory:
            dst = dst_path / src_path.name
        else:
            dst = dst_path

        _move_path(src_path, dst, args)
