"""Implementation of complete command for shell completion generation."""

from __future__ import annotations

import os
import sys
import glob
from argparse import Namespace
from pathlib import Path
from tempfile import gettempdir
from typing import Generator, Iterable
from argcomplete import shellcode, warn
from cloudpathlib import AnyPath, CloudPath

from ..utils import PACKAGE

COMPLETE_CACHE = Path.home() / ".cache" / "cloudsh" / "complete.cache"
WARN_CACHING_INDICATOR_FILE = Path(gettempdir()) / "cloudsh_caching_warned"


def _scan_path(path: str, depth: int = -1) -> Generator[str, None, None]:
    """Scan a path for files and directories."""
    apath = AnyPath(path)
    if not isinstance(apath, CloudPath):
        print(f"{PACKAGE} complete: only cloud paths are supported", file=sys.stderr)
        sys.exit(1)

    if not apath.exists():
        print(f"{PACKAGE} complete: path does not exist: {path}", file=sys.stderr)
        sys.exit(1)

    if not apath.is_dir():
        yield path

    if depth == 0:
        yield path.rstrip("/") + "/"
        return

    dep = 0
    for p in apath.iterdir():
        if p.is_dir():
            yield str(p).rstrip("/") + "/"
            if depth == -1 or dep < depth:
                yield from _scan_path(str(p), depth - 1)
        else:
            yield str(p)


def _read_cache() -> Generator[str, None, None]:
    """Read cached paths for a bucket."""
    if COMPLETE_CACHE.exists():
        with COMPLETE_CACHE.open() as f:
            for path in f:
                yield path.strip()


def _update_cache(prefix: str, paths: Iterable[str] | None = None) -> None:
    """Write paths to bucket cache, update the ones with prefix.
    Or clear the cache if paths is None.
    """
    prefixed_cache = set()
    other_cache = set()
    for path in _read_cache():
        if path.startswith(prefix):
            prefixed_cache.add(path)
        else:
            other_cache.add(path)

    if paths is None:
        COMPLETE_CACHE.write_text("\n".join(other_cache))
        return

    COMPLETE_CACHE.write_text("\n".join(other_cache | set(paths)))


def path_completer(prefix: str, **kwargs) -> list[str]:
    """Complete paths for shell completion.

    Args:
        prefix: Prefix to match
        **kwargs: Arbitrary keyword arguments

    Returns:
        list[str]: List of matching paths
    """
    if not prefix:
        return ["-", "gs://", "s3://", "az://", *glob.glob(prefix + "*")]

    if "://" in prefix:
        if not COMPLETE_CACHE.exists():
            if not os.environ.get("CLOUDSH_COMPLETE_NO_FETCHING_INDICATOR"):
                warn("fetching ...")

            try:
                if prefix.endswith("/"):
                    return [
                        str(p).rstrip("/") + "/" if p.is_dir() else str(p)
                        for p in CloudPath(prefix).iterdir()
                    ]

                if prefix.count("/") == 2:  # incomplete bucket name
                    protocol, pref = prefix.split("://", 1)
                    return [
                        str(b).rstrip("/") + "/"
                        for b in CloudPath(f"{protocol}://").iterdir()
                        if b.bucket.startswith(pref)
                    ]

                path = CloudPath(prefix)
                return [
                    str(p).rstrip("/") + "/" if p.is_dir() else str(p)
                    for p in path.parent.glob(path.name + "*")
                ]
            except Exception as e:
                warn(f"Error listing cloud path: {e}")
                return []

        if not os.environ.get("CLOUDSH_COMPLETE_NO_CACHING_WARN"):
            if not WARN_CACHING_INDICATOR_FILE.exists():
                WARN_CACHING_INDICATOR_FILE.touch()
                warn(
                    "Using cached cloud path completion. This may not be up-to-date, "
                    f"run '{PACKAGE} complete --update-cache path...' "
                    "to update the cache.\n"
                    f"This warning will only show once per the nonexistence of "
                    f"{str(WARN_CACHING_INDICATOR_FILE)!r}."
                )

        return [
            p for p in COMPLETE_CACHE.read_text().splitlines() if p.startswith(prefix)
        ]

    return [
        str(p).rstrip("/") + "/" if os.path.isdir(p) else str(p)
        for p in glob.glob(prefix + "*")
    ] + [p for p in ("-", "gs://", "s3://", "az://") if p.startswith(prefix)]


def run(args: Namespace) -> None:
    """Execute the complete command with given arguments."""
    if args.clear_cache:
        if not args.path:
            COMPLETE_CACHE.unlink(missing_ok=True)
            return

        for path in args.path:
            _update_cache(path, None)
        return

    if args.update_cache:
        for path in args.path:
            paths = _scan_path(path, depth=args.depth)
            _update_cache(path, paths)
        print(f"{PACKAGE} complete: cache updated: {COMPLETE_CACHE}")
        return

    shell = args.shell
    if not shell:
        shell = os.environ.get("SHELL", "")
        if not shell:
            print(
                f"{PACKAGE} complete: Could not detect shell, "
                "please specify with --shell",
                file=sys.stderr,
            )
            sys.exit(1)
        shell = os.path.basename(shell)

    script = shellcode(
        [PACKAGE],
        shell=shell,
        complete_arguments={
            "file": path_completer,
        },
    )
    sys.stdout.write(script)
