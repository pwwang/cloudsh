"""Implementation of GNU cp command for both local and cloud files."""

from __future__ import annotations

import sys
import shutil
from typing import TYPE_CHECKING
from yunpath import AnyPath, CloudPath
from cloudpathlib import GSPath, S3Path, AzureBlobPath
from cloudpathlib.exceptions import OverwriteNewerCloudError

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


def _cloud_to_cloud_copy(src: CloudPath, dst: CloudPath, force: bool = False) -> None:
    """Copy between cloud paths using native cloud provider APIs.

    This function uses the official cloud provider APIs to copy files directly
    on the cloud provider's infrastructure, avoiding local caching.

    Args:
        src: Source cloud path
        dst: Destination cloud path
        force: Whether to force overwrite existing files
    """
    # For GCS to GCS copy, use the native copy_blob API
    if isinstance(src, GSPath) and isinstance(dst, GSPath):
        src_client = src.client.client  # Get the google.cloud.storage.Client
        src_bucket_name = src.bucket
        src_blob_name = src.blob
        dst_bucket_name = dst.bucket
        dst_blob_name = dst.blob

        src_bucket = src_client.bucket(src_bucket_name)
        src_blob = src_bucket.blob(src_blob_name)
        dst_bucket = src_client.bucket(dst_bucket_name)

        # Use the native copy_blob API for server-side copy
        src_bucket.copy_blob(
            src_blob,
            dst_bucket,
            new_name=dst_blob_name,
        )
    # For S3 to S3 copy, use the native copy API
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

        # Use the native S3 copy_object API for server-side copy
        s3_client.copy_object(
            CopySource=copy_source,
            Bucket=dst_bucket,
            Key=dst_key
        )
    # For Azure to Azure copy, use the native copy API
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

        # Start the copy operation
        dst_blob_client.start_copy_from_url(src_blob_client.url)
    else:
        # Fall back to cloudpathlib's copy for cross-cloud copies
        if force:
            src.copy(dst, force_overwrite_to_cloud=True)
        else:
            src.copy(dst)


def _copy_path(src: AnyPath, dst: AnyPath, args: Namespace) -> None:
    """Copy a single file or directory.

    Args:
        src: Source path
        dst: Destination path
        args: Command line arguments
    """
    try:
        # Ensure parent directory exists
        if not dst.parent.exists():
            print(
                f"{PACKAGE} cp: cannot create '{dst}': No such file or directory",
                file=sys.stderr,
            )
            sys.exit(1)

        # If destination is an existing directory and source isn't a directory,
        # append source filename
        if dst.exists() and dst.is_dir() and not src.is_dir():
            dst = dst / src.name

        # Now check for conflicts
        if dst.exists():
            if args.no_clobber:
                return
            if args.interactive and not _prompt_overwrite(str(dst)):
                return
            args.force = True
            if dst.is_dir() and not src.is_dir():
                print(
                    f"{PACKAGE} cp: cannot overwrite directory '{dst}' "
                    "with non-directory",
                    file=sys.stderr,
                )
                sys.exit(1)

        if src.is_dir():
            if not args.recursive:
                print(
                    f"{PACKAGE} cp: -r not specified; omitting directory '{src}'",
                    file=sys.stderr,
                )
                sys.exit(1)

            # Create destination directory
            dst.mkdir(parents=True, exist_ok=True)
            if args.verbose:
                print(f"created directory '{dst}'")

            # Copy directory contents
            for item in src.iterdir():
                dst_item = dst / item.name
                _copy_path(item, dst_item, args)
        else:
            if args.verbose:
                print(f"'{src}' -> '{dst}'")

            try:
                # Handle cloud paths
                if isinstance(src, CloudPath):
                    if isinstance(dst, CloudPath):
                        # Cloud to cloud copy - use native APIs to avoid local cache
                        _cloud_to_cloud_copy(src, dst, force=args.force)
                    else:
                        # Cloud to local copy
                        src.download_to(dst)
                else:
                    if isinstance(dst, CloudPath):
                        # Local to cloud copy
                        dst.upload_from(src)
                    else:
                        # Local to local copy
                        if args.preserve:
                            # Copy with metadata
                            shutil.copy2(src, dst)
                        else:
                            shutil.copy(src, dst)
            except OverwriteNewerCloudError:
                if args.force:
                    if isinstance(src, CloudPath) and isinstance(dst, CloudPath):
                        _cloud_to_cloud_copy(src, dst, force=True)
                    else:
                        src.copy(dst, force_overwrite_to_cloud=True)
                else:
                    raise

    except (OSError, IOError) as e:
        print(
            f"{PACKAGE} cp: cannot copy '{src}' to '{dst}': {str(e)}", file=sys.stderr
        )
        sys.exit(1)


def run(args: Namespace) -> None:
    """Execute the cp command."""
    sources = args.SOURCE
    # Strip trailing slashes from source and destination
    destination = AnyPath(args.DEST.rstrip("/"))

    if args.target_directory:
        target_dir = AnyPath(args.target_directory.rstrip("/"))
        if not target_dir.exists():
            target_dir.mkdir(parents=True)
        destination = target_dir

    # Validate arguments
    if len(sources) > 1 and not (args.target_directory or destination.is_dir()):
        print(
            f"{PACKAGE} cp: target must be a directory when copying multiple files",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.parents and not destination.is_dir():
        print(
            f"{PACKAGE} cp: with --parents, destination must be a directory",
            file=sys.stderr,
        )
        sys.exit(1)

    # Copy each source
    for src in sources:
        src_path = AnyPath(src.rstrip("/"))
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
            if destination.exists() and destination.is_dir():
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

        _copy_path(src_path, dst_path, args)
