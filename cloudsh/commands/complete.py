"""Implementation of complete command for shell completion generation."""

from __future__ import annotations

import os
import sys
import glob
from argparse import Namespace
from pathlib import Path
from tempfile import gettempdir
from typing import AsyncGenerator, Iterable
from argcomplete import shellcode, warn
from panpath import CloudPath, PanPath

from ..utils import PACKAGE

COMPLETE_CACHE = PanPath(Path.home() / ".cache" / "cloudsh" / "complete.cache")
WARN_CACHING_INDICATOR_FILE = PanPath(gettempdir()) / "cloudsh_caching_warned"


async def _scan_path(path: str, depth: int = -1) -> AsyncGenerator[str, None, None]:
    """Scan a path for files and directories."""
    apath = PanPath(path)
    if not isinstance(apath, CloudPath):
        print(f"{PACKAGE} complete: only cloud paths are supported", file=sys.stderr)
        sys.exit(1)

    if not await apath.a_exists():
        print(f"{PACKAGE} complete: path does not exist: {path}", file=sys.stderr)
        sys.exit(1)

    if not await apath.a_is_dir():
        print(apath)
        print(repr(apath))
        print(f"{PACKAGE} complete: path is not a directory: {path}", file=sys.stderr)
        yield path

    if depth == 0:
        yield path.rstrip("/") + "/"
        return

    dep = 0
    async for p in apath.a_iterdir():
        if await p.a_is_dir():
            yield str(p).rstrip("/") + "/"
            if depth == -1 or dep < depth:
                async for r in _scan_path(str(p), depth - 1):
                    yield r
        else:
            yield str(p)


async def _read_cache() -> AsyncGenerator[str, None, None]:
    """Read cached paths for a bucket."""
    if await COMPLETE_CACHE.a_exists():
        async with COMPLETE_CACHE.a_open() as f:
            async for path in f:
                yield path.strip()


async def _update_cache(prefix: str, paths: Iterable[str] | None = None) -> None:
    """Write paths to bucket cache, update the ones with prefix.
    Or clear the cache if paths is None.
    """
    prefixed_cache = set()
    other_cache = set()
    async for path in _read_cache():
        if path.startswith(prefix):
            prefixed_cache.add(path)
        else:
            other_cache.add(path)

    if paths is None:
        await COMPLETE_CACHE.a_write_text("\n".join(other_cache))
        return

    await COMPLETE_CACHE.a_write_text("\n".join(other_cache | set(paths)))


async def path_completer(prefix: str, **kwargs) -> list[str]:
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
        if not await COMPLETE_CACHE.a_exists():
            if not os.environ.get("CLOUDSH_COMPLETE_NO_FETCHING_INDICATOR"):
                warn("fetching ...")

            try:
                if prefix.endswith("/"):
                    return [
                        str(p).rstrip("/") + "/" if await p.a_is_dir() else str(p)
                        async for p in PanPath(prefix).a_iterdir()
                    ]

                if prefix.count("/") == 2:  # incomplete bucket name
                    protocol, pref = prefix.split("://", 1)
                    return [
                        str(b).rstrip("/") + "/"
                        async for b in PanPath(f"{protocol}://").a_iterdir()
                        if b.bucket.startswith(pref)
                    ]

                path = PanPath(prefix)
                return [
                    str(p).rstrip("/") + "/" if await p.a_is_dir() else str(p)
                    for p in await path.parent.a_glob(path.name + "*")
                ]
            except Exception as e:
                warn(f"Error listing cloud path: {e}")
                return []

        if not os.environ.get("CLOUDSH_COMPLETE_CACHING_WARN"):
            if not await WARN_CACHING_INDICATOR_FILE.a_exists():
                await WARN_CACHING_INDICATOR_FILE.a_touch()
                warn(
                    "Using cached cloud path completion. This may not be up-to-date, "
                    f"run '{PACKAGE} complete --update-cache path...' "
                    "to update the cache.\n"
                    f"This warning will only show once per the nonexistence of "
                    f"{str(WARN_CACHING_INDICATOR_FILE)!r}."
                )

        content = await COMPLETE_CACHE.a_read_text()
        return [p for p in content.splitlines() if p.startswith(prefix)]

    return [
        str(p).rstrip("/") + "/" if os.path.isdir(p) else str(p)
        for p in glob.glob(prefix + "*")
    ] + [p for p in ("-", "gs://", "s3://", "az://") if p.startswith(prefix)]


async def run(args: Namespace) -> None:
    """Execute the complete command with given arguments."""
    if args.clear_cache:
        if not args.path:
            await COMPLETE_CACHE.a_unlink(missing_ok=True)
            return

        for path in args.path:
            await _update_cache(path, None)
        return

    if args.update_cache:
        for path in args.path:
            paths = []
            async for p in _scan_path(path, depth=args.depth):
                paths.append(p)
            await _update_cache(path, paths)
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
