"""Patch cloudpathlib to support mkdir for GSPath"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Generator
from cloudpathlib.gs.gspath import GSPath as _GSPath
from cloudpathlib.gs.gsclient import GSClient
from cloudpathlib.cloudpath import register_path_class
from cloudpathlib.exceptions import NoStatError


def _is_file_or_dir(self, cloud_path: _GSPath) -> str | None:
    # short-circuit the root-level bucket
    if not cloud_path.blob:
        return "dir"

    bucket = self.client.bucket(cloud_path.bucket)
    blob = bucket.get_blob(cloud_path.blob)

    # if blob is not None:
    if blob is not None and not blob.name.endswith("/"):  # patched
        return "file"
    else:
        prefix = cloud_path.blob
        if prefix and not prefix.endswith("/"):
            prefix += "/"

        # not a file, see if it is a directory
        f = bucket.list_blobs(max_results=1, prefix=prefix)

        # at least one key with the prefix of the directory
        if bool(list(f)):
            return "dir"
        else:
            return None


@register_path_class("gs")
class GSPath(_GSPath):
    """Patch cloudpathlib to support mkdir for GSPath"""

    def mkdir(self, parents=False, exist_ok=False):
        """Create a directory

        The original implementation of mkdir() in cloudpathlib does not support
        creating directories in Google Cloud Storage. This method is a patch to
        support creating directories in Google Cloud Storage

        Args:
            parents (bool, optional): If true, also create parent directories.
                Defaults to False.
            exist_ok (bool, optional): If true, do not raise an exception if
                the directory already exists. Defaults to False.
        """
        if self.exists():
            if not exist_ok:
                raise FileExistsError(f"cannot create directory '{self}': File exists")
            if not self.is_dir():
                raise NotADirectoryError(
                    f"cannot create directory '{self}': Not a directory"
                )
            return

        if parents:
            self.parent.mkdir(parents=True, exist_ok=True)
        elif not self.parent.exists():
            raise FileNotFoundError(
                f"cannot create directory '{self}': No such file or directory"
            )

        path = self.blob.rstrip("/") + "/"
        blob = self.client.client.bucket(self.bucket).blob(path)
        blob.upload_from_string("")

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, type(self)):
            return False
        if str(self) == str(other):
            return True
        if self.is_dir() and str(self) == str(other).rstrip("/"):  # marked
            return True
        return False

    def iterdir(self) -> Generator[GSPath, None, None]:
        """Iterate over the directory entries"""
        for f, _ in self.client._list_dir(self, recursive=False):
            if self == f:
                # originally f == self used, which cannot detect
                # the situation at the marked line in __eq__ method
                continue

            yield f

    def stat(self) -> os.stat_result:
        """Return the stat result for the path"""
        meta = self.client._get_metadata(self)

        # check if there is updated in the real metadata
        # if so, use it as mtime
        bucket = self.client.client.bucket(self.bucket)
        blob = bucket.get_blob(self.blob)
        if blob and blob.metadata and "updated" in blob.metadata:
            updated = blob.metadata["updated"]
            if isinstance(updated, str):
                updated = datetime.fromisoformat(updated)
            meta["updated"] = updated

        if meta is None:
            raise NoStatError(
                f"No stats available for {self}; it may be a directory or not exist."
            )

        try:
            mtime = meta["updated"].timestamp()
        except KeyError:
            mtime = 0

        return os.stat_result(
            (
                None,  # mode
                None,  # ino
                self.cloud_prefix,  # dev,
                None,  # nlink,
                None,  # uid,
                None,  # gid,
                meta.get("size", 0),  # size,
                None,  # atime,
                mtime,  # mtime,
                None,  # ctime,
            )
        )


GSClient._is_file_or_dir = _is_file_or_dir
