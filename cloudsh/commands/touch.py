from __future__ import annotations

import os
import sys
from datetime import datetime
from typing import TYPE_CHECKING
from dateutil import parser as date_parser
from panpath import PanPath, CloudPath

from ..utils import PACKAGE

if TYPE_CHECKING:
    from argx import Namespace


async def _parse_timestamp(args: Namespace) -> tuple[float | None, float | None]:
    """Parse timestamp from args, returns (atime, mtime) tuple"""
    if args.reference:
        ref_path = PanPath(args.reference)
        if not await ref_path.a_exists():
            raise FileNotFoundError(f"Reference file not found: {args.reference}")
        ref_stat = await ref_path.a_stat()
        return ref_stat.st_atime, ref_stat.st_mtime

    if args.date:
        try:
            ts = date_parser.parse(args.date).timestamp()
            return ts, ts
        except ValueError:
            raise ValueError(f"Invalid date format: {args.date}")

    if args.t:
        try:
            # Parse [[CC]YY]MMDDhhmm[.ss] format
            fmt = args.t
            if "." in fmt:
                fmt, ss = fmt.split(".")
            else:
                ss = "00"

            if len(fmt) == 8:  # MMDDhhmm
                ts = datetime.strptime(f"20{fmt}.{ss}", "%Y%m%d%H%M.%S")
            elif len(fmt) == 10:  # YYMMDDhhmm
                ts = datetime.strptime(f"{fmt}.{ss}", "%y%m%d%H%M.%S")
            elif len(fmt) == 12:  # CCYYMMDDhhmm
                ts = datetime.strptime(f"{fmt}.{ss}", "%Y%m%d%H%M.%S")
            else:
                raise ValueError
            return ts.timestamp(), ts.timestamp()
        except ValueError:
            raise ValueError(f"Invalid time format: {args.t}")

    # Handle --time option
    if args.time in ("access", "atime", "use"):
        args.a = True
    elif args.time in ("modify", "mtime"):
        args.m = True

    ts = datetime.now().timestamp()
    return ts if args.a or not args.m else None, ts if args.m or not args.a else None


async def run(args: Namespace) -> None:
    """Update file timestamps or create empty files"""
    try:
        atime, mtime = await _parse_timestamp(args)
    except Exception as e:
        sys.stderr.write(f"{PACKAGE} touch: {str(e)}\n")
        sys.exit(1)

    for file in args.file:
        path = PanPath(file)
        try:
            exists = await path.a_exists()
            if not exists and args.no_create:
                continue

            if isinstance(path, CloudPath):
                # Cloud files only support mtime through metadata
                if not exists:
                    await path.a_touch()
                if mtime is not None:
                    # Update cloud file metadata
                    blob = path.client.client.bucket(path.bucket).get_blob(path.blob)
                    metadata = blob.metadata or {}
                    metadata["updated"] = datetime.fromtimestamp(mtime)
                    blob.metadata = metadata
                    blob.patch()
            else:
                # Local files support both atime and mtime
                if not exists:
                    await path.a_touch()
                if atime is not None or mtime is not None:
                    current = await path.a_stat()
                    os.utime(
                        path,
                        (
                            atime if atime is not None else current.st_atime,
                            mtime if mtime is not None else current.st_mtime,
                        ),
                    )

        except Exception as e:
            sys.stderr.write(f"{PACKAGE} touch: cannot touch '{file}': {str(e)}\n")
            sys.exit(1)
