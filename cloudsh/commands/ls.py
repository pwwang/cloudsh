"""Implementation of the ls command for both local and cloud files.

This module provides functionality similar to GNU ls command but with added
support for cloud storage files through cloudpathlib.
"""

from __future__ import annotations

import sys
import stat
import time
import pwd
import grp
from datetime import datetime
from pathlib import Path
from typing import List, Union, Optional
from argparse import Namespace
from cloudpathlib import AnyPath, CloudPath
from cloudpathlib.exceptions import NoStatError

from ..utils import PACKAGE


def _get_user_group(st_uid: int, st_gid: int) -> tuple[str, str]:
    """Get user and group names from uid and gid."""
    # For cloud files, these might be None
    if st_uid is None:
        user = "<unknown>"
    else:
        try:
            user = pwd.getpwuid(st_uid).pw_name
        except (KeyError, AttributeError):
            user = str(st_uid)

    if st_gid is None:
        group = "<unknown>"
    else:
        try:
            group = grp.getgrgid(st_gid).gr_name
        except (KeyError, AttributeError):
            group = str(st_gid)

    return user, group


def _format_size(size: int, human_readable: bool = False, si: bool = False) -> str:
    """Format file size in human readable format."""
    if not human_readable:
        return str(size)

    base = 1000 if si else 1024
    units = ["", "K", "M", "G", "T", "P", "E", "Z", "Y"]

    for unit in units:
        if size < base:
            if unit and size < 10:
                return f"{size:.1f}{unit}"
            return f"{int(size)}{unit}"
        size /= base

    return f"{int(size)}{units[-1]}"


def _format_mode(mode: Optional[int]) -> str:
    """Convert mode bits to string representation."""
    # For cloud files, infer directory status from path
    if mode is None:
        return "----------"

    perms = "-"
    if stat.S_ISDIR(mode):
        perms = "d"
    elif stat.S_ISLNK(mode):
        perms = "l"

    for who in ("USR", "GRP", "OTH"):
        for what in ("R", "W", "X"):
            if mode & getattr(stat, f"S_I{what}{who}"):
                perms += {"R": "r", "W": "w", "X": "x"}[what]
            else:
                perms += "-"

    return perms


def _format_time(mtime: float) -> str:
    """Format modification time."""
    now = time.time()
    datetime_obj = datetime.fromtimestamp(mtime)

    if now - mtime > 60 * 60 * 24 * 180:  # Older than 6 months
        return datetime_obj.strftime("%b %d  %Y")
    return datetime_obj.strftime("%b %d %H:%M")


def _format_entry_long(
    path: Union[CloudPath, Path], human_readable: bool, si: bool
) -> str:
    """Format a single entry in long listing format."""
    try:
        st = path.stat()
        # Default values for all fields
        mode_str = "-" * 10
        nlink = 1
        user = "nobody"
        group = "nogroup"
        size = 0
        mtime = time.time()

        # Try to get actual values
        try:
            size = st.st_size
            mtime = getattr(st, "st_mtime", time.time())
        except AttributeError:
            pass

        # Handle permissions and ownership
        if isinstance(path, CloudPath):
            if path.is_dir():
                mode_str = "d" + "-" * 9
        else:
            try:
                mode = getattr(st, "st_mode", None)
                if mode is not None:
                    mode_str = _format_mode(mode)
                    user, group = _get_user_group(
                        getattr(st, "st_uid", None), getattr(st, "st_gid", None)
                    )
            except AttributeError:
                pass

        # Ensure all format values are strings
        size_str = _format_size(size, human_readable, si)
        time_str = _format_time(mtime)

        return (
            f"{mode_str} {nlink:3d} {user:8} {group:8} "
            f"{size_str:>8} {time_str} {path.name}"
        )

    except (OSError, NoStatError) as e:
        print(f"{PACKAGE} ls: cannot access '{path}': {str(e)}", file=sys.stderr)
        return ""


def _list_entries(
    path: Union[CloudPath, Path],
    all: bool = False,
    almost_all: bool = False,
    long: bool = False,
    human_readable: bool = False,
    si: bool = False,
    reverse: bool = False,
    size_sort: bool = False,
    time_sort: bool = False,
    one_per_line: bool = False,
) -> List[str]:
    """List directory entries with specified options."""
    try:
        if not path.exists():
            print(
                f"{PACKAGE} ls: cannot access '{path}': No such file or directory",
                file=sys.stderr,
            )
            sys.exit(1)

        if path.is_file():
            if long:
                return [_format_entry_long(path, human_readable, si)]
            return [path.name]

        entries = []
        # Store entry objects for sorting
        entry_objects = []
        for entry in path.iterdir():
            name = entry.name
            if not all and not almost_all and name.startswith("."):
                continue
            if name in (".", "..") and almost_all:
                continue

            entry_objects.append(entry)

        # Sort entries based on criteria
        if size_sort:
            entry_objects.sort(
                key=lambda x: getattr(x.stat(), "st_size", 0),
                reverse=True,  # -S always sorts largest first
            )
        elif time_sort:
            entry_objects.sort(
                key=lambda x: getattr(x.stat(), "st_mtime", 0), reverse=True
            )
        else:
            entry_objects.sort(key=lambda x: x.name, reverse=reverse)

        # Format entries after sorting
        for entry in entry_objects:
            if long:
                formatted = _format_entry_long(entry, human_readable, si)
                if formatted:
                    entries.append(formatted)
            else:
                entries.append(entry.name)

        return entries

    except (OSError, NoStatError) as e:
        print(f"{PACKAGE} ls: cannot access '{path}': {str(e)}", file=sys.stderr)
        sys.exit(1)
        return []


def run(args: Namespace) -> None:
    """Execute the ls command with given arguments."""
    # Default to current directory if no files specified
    paths = [AnyPath(".")] if not args.file else [AnyPath(f) for f in args.file]

    for i, path in enumerate(paths):
        if len(paths) > 1:
            if i > 0:
                print()
            print(f"{path}:")

        try:
            entries = _list_entries(
                path,
                all=args.all,
                almost_all=args.almost_all,
                long=args.l,
                human_readable=args.human_readable,
                si=args.si,
                reverse=args.reverse,
                size_sort=args.S,
                time_sort=args.t,
                one_per_line=args.one,
            )

            if args.one:
                for entry in entries:
                    print(entry)
            else:
                print("\n".join(entries))

            if args.recursive and path.is_dir():
                for entry in path.iterdir():
                    if entry.is_dir() and not entry.name.startswith("."):
                        print()
                        # Get just the parent and current directory names
                        dirname = "/".join(str(entry).rstrip("/").split("/")[-2:])
                        print(f"{dirname}:")
                        recurse_args = Namespace(**vars(args))
                        recurse_args.file = [str(entry)]
                        run(recurse_args)

        except (OSError, NoStatError) as e:
            print(f"{PACKAGE} ls: cannot access '{path}': {str(e)}", file=sys.stderr)
            sys.exit(1)
