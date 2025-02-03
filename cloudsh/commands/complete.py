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
WARN_FETCHING_INDICATOR_FILE = Path(gettempdir()) / "cloudsh_fetching_warned"
WARN_CACHING_INDICATOR_FILE = Path(gettempdir()) / "cloudsh_caching_warned"


def _scan_path(path: str, depth: int = -1) -> Generator[CloudPath, None, None]:
    """Scan a path for files and directories."""
    path = AnyPath(path)
    if not isinstance(path, CloudPath):
        print(f"{PACKAGE} complete: only cloud paths are supported", file=sys.stderr)
        sys.exit(1)

    if not path.exists():
        print(f"{PACKAGE} complete: path does not exist: {path}", file=sys.stderr)
        sys.exit(1)

    if not path.is_dir():
        yield path

    if depth == 0:
        yield path
        return

    dep = 0
    for p in path.iterdir():
        yield p
        if p.is_dir():
            if depth == -1 or dep < depth:
                yield from _scan_path(p, depth - 1)


def _read_cache() -> Generator[str, None, None]:
    """Read cached paths for a bucket."""
    if COMPLETE_CACHE.exists():
        with COMPLETE_CACHE.open() as f:
            for path in f:
                yield path.strip()


def _update_cache(prefix: str, paths: Iterable[str | CloudPath] | None = None) -> None:
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

    paths = [str(p) for p in paths]
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
            if not WARN_FETCHING_INDICATOR_FILE.exists():
                WARN_FETCHING_INDICATOR_FILE.touch()
                warn(
                    "No cloud path cache found, using real-time fetching for "
                    "completion.\n"
                    f"Try running '{PACKAGE} complete --update-cache path...' "
                    "to speed up completion for cloud paths.\n"
                    f"This warning will only show once per the nonexistence of "
                    f"{str(WARN_FETCHING_INDICATOR_FILE)!r}.\n"
                    "Listing cloud paths may take a while."
                )

            if prefix.endswith("/"):
                try:
                    return list(map(str, CloudPath(prefix).iterdir()))
                except Exception as e:
                    warn(f"Error listing cloud path: {e}")
                    return []

            path = CloudPath(prefix)
            return list(map(str, path.parent.glob(path.name + "*")))

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

    return glob.glob(prefix + "*") + [
        p for p in ("-", "gs://", "s3://", "az://") if p.startswith(prefix)
    ]


def run(args: Namespace) -> None:
    """Execute the complete command with given arguments."""
    if args.clear_cache:
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
