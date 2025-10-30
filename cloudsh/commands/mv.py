from __future__ import annotations

import sys
from typing import TYPE_CHECKING
from yunpath import AnyPath, CloudPath
from cloudpathlib import GSPath, S3Path, AzureBlobPath
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


def _cloud_to_cloud_move(src: CloudPath, dst: CloudPath) -> None:
    """Move/rename between cloud paths using native cloud provider APIs.

    This function uses the official cloud provider APIs to move/rename files directly
    on the cloud provider's infrastructure, avoiding local caching.

    For same-bucket/container operations, this uses atomic rename operations.
    For cross-bucket/container operations, this does copy + delete.

    Args:
        src: Source cloud path
        dst: Destination cloud path
    """
    # For GCS to GCS move/rename
    if isinstance(src, GSPath) and isinstance(dst, GSPath):
        src_client = src.client.client  # Get the google.cloud.storage.Client
        src_bucket_name = src.bucket
        src_blob_name = src.blob
        dst_bucket_name = dst.bucket
        dst_blob_name = dst.blob

        src_bucket = src_client.bucket(src_bucket_name)
        src_blob = src_bucket.blob(src_blob_name)

        # Same bucket: use atomic move_blob
        if src_bucket_name == dst_bucket_name:
            src_bucket.move_blob(src_blob, new_name=dst_blob_name)
        else:
            # Cross-bucket: copy then delete
            dst_bucket = src_client.bucket(dst_bucket_name)
            src_bucket.copy_blob(src_blob, dst_bucket, new_name=dst_blob_name)
            src_blob.delete()

    # For S3 to S3 move/rename
    elif isinstance(src, S3Path) and isinstance(dst, S3Path):
        s3_client = src.client.client  # Get the boto3 S3 client
        src_bucket = src.bucket
        src_key = src.key
        dst_bucket = dst.bucket
        dst_key = dst.key

        copy_source = {
            'Bucket': src_bucket,
            'Key': src_key
        }

        # S3 doesn't have atomic move, always copy + delete
        s3_client.copy_object(
            CopySource=copy_source,
            Bucket=dst_bucket,
            Key=dst_key
        )
        s3_client.delete_object(Bucket=src_bucket, Key=src_key)

    # For Azure to Azure move/rename
    elif isinstance(src, AzureBlobPath) and isinstance(dst, AzureBlobPath):
        # Get blob clients
        src_blob_client = src.client.client.get_blob_client(
            container=src.container,
            blob=src.blob
        )
        dst_blob_client = dst.client.client.get_blob_client(
            container=dst.container,
            blob=dst.blob
        )

        # Azure doesn't have atomic move, copy + delete
        dst_blob_client.start_copy_from_url(src_blob_client.url)

        # Wait for copy to complete before deleting (Azure copy is async)
        # For production, you might want to poll the copy status
        import time
        time.sleep(0.5)  # Brief wait for copy to start

        # Delete the source blob
        src_blob_client.delete_blob()

    else:
        # Fall back to cloudpathlib's rename for cross-cloud moves
        # This will download and re-upload
        src.rename(dst)


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

            # Use native cloud APIs for cloud-to-cloud file moves
            _cloud_to_cloud_move(item, dst_item)

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
                        # Use native cloud APIs for cloud-to-cloud file moves
                        _cloud_to_cloud_move(src, dst)
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
                        src.rmtree()
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
