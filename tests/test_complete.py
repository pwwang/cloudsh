"""Tests for the complete command."""

from __future__ import annotations

import os
from unittest.mock import patch, MagicMock
from uuid import uuid4
import pytest
from argx import Namespace
from yunpath import CloudPath

from cloudsh.commands.complete import (
    COMPLETE_CACHE,
    WARN_CACHING_INDICATOR_FILE,
    _scan_path,
    _read_cache,
    _update_cache,
    path_completer,
    run,
)


@pytest.fixture(scope="module")
def gcs_bucket():
    """GCS bucket for cloud tests."""
    return "gs://handy-buffer-287000.appspot.com"


@pytest.fixture
def cache_setup():
    """Setup and teardown for cache tests."""
    # Backup existing cache if it exists
    cache_backup = None
    if COMPLETE_CACHE.exists():
        cache_backup = COMPLETE_CACHE.read_text()

    warn_backup = None
    if WARN_CACHING_INDICATOR_FILE.exists():
        warn_backup = True

    yield

    # Restore or clean up
    if cache_backup is not None:
        COMPLETE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        COMPLETE_CACHE.write_text(cache_backup)
    elif COMPLETE_CACHE.exists():
        COMPLETE_CACHE.unlink()

    if warn_backup is None and WARN_CACHING_INDICATOR_FILE.exists():
        WARN_CACHING_INDICATOR_FILE.unlink()


class TestComplete:
    """Test class for complete command."""

    def test_scan_path_non_cloud(self, cache_setup):
        """Test scanning a non-cloud path should fail."""
        with pytest.raises(SystemExit) as exc_info:
            list(_scan_path("/tmp"))
        assert exc_info.value.code == 1

    def test_scan_path_nonexistent(self, gcs_bucket, cache_setup):
        """Test scanning a nonexistent path should fail."""
        nonexistent = f"{gcs_bucket}/nonexistent-{uuid4()}"
        with pytest.raises(SystemExit) as exc_info:
            list(_scan_path(nonexistent))
        assert exc_info.value.code == 1

    def test_scan_path_file(self, gcs_bucket, cache_setup):
        """Test scanning a file returns the file path."""
        workspace = f"{gcs_bucket}/test_complete_file_{uuid4()}"
        file_path = CloudPath(workspace) / "test.txt"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("test")

        try:
            paths = list(_scan_path(str(file_path)))
            assert str(file_path) in paths
        finally:
            file_path.unlink()
            CloudPath(workspace).rmtree()

    def test_scan_path_directory(self, gcs_bucket, cache_setup):
        """Test scanning a directory."""
        workspace = f"{gcs_bucket}/test_complete_dir_{uuid4()}"
        dir_path = CloudPath(workspace) / "testdir"
        dir_path.mkdir(parents=True, exist_ok=True)

        # Create some files
        (dir_path / "file1.txt").write_text("content1")
        (dir_path / "file2.txt").write_text("content2")
        subdir = dir_path / "subdir"
        subdir.mkdir()
        (subdir / "file3.txt").write_text("content3")

        try:
            paths = list(_scan_path(str(dir_path)))
            path_strs = [p for p in paths]

            # Should include files and subdirectory
            assert any("file1.txt" in p for p in path_strs)
            assert any("file2.txt" in p for p in path_strs)
            assert any("subdir/" in p for p in path_strs)
            assert any("file3.txt" in p for p in path_strs)
        finally:
            CloudPath(workspace).rmtree()

    def test_scan_path_depth_zero(self, gcs_bucket, cache_setup):
        """Test scanning with depth 0."""
        workspace = f"{gcs_bucket}/test_complete_depth_{uuid4()}"
        dir_path = CloudPath(workspace) / "testdir"
        dir_path.mkdir(parents=True, exist_ok=True)

        try:
            paths = list(_scan_path(str(dir_path), depth=0))
            assert len(paths) == 1
            assert paths[0].endswith("/")
        finally:
            CloudPath(workspace).rmtree()

    def test_read_cache_empty(self, cache_setup):
        """Test reading from empty cache."""
        if COMPLETE_CACHE.exists():
            COMPLETE_CACHE.unlink()
        paths = list(_read_cache())
        assert paths == []

    def test_read_cache_with_content(self, cache_setup):
        """Test reading from cache with content."""
        COMPLETE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        test_paths = ["gs://bucket/file1.txt", "gs://bucket/file2.txt"]
        COMPLETE_CACHE.write_text("\n".join(test_paths))

        paths = list(_read_cache())
        assert paths == test_paths

    def test_update_cache_clear(self, cache_setup):
        """Test clearing cache with specific prefix."""
        COMPLETE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        test_paths = [
            "gs://bucket1/file1.txt",
            "gs://bucket1/file2.txt",
            "gs://bucket2/file3.txt",
        ]
        COMPLETE_CACHE.write_text("\n".join(test_paths))

        _update_cache("gs://bucket1/", None)

        remaining = COMPLETE_CACHE.read_text().strip().split("\n")
        assert "gs://bucket2/file3.txt" in remaining
        assert "gs://bucket1/file1.txt" not in remaining

    def test_update_cache_add_paths(self, cache_setup):
        """Test adding paths to cache - replaces existing paths with same prefix."""
        COMPLETE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        existing = ["gs://bucket/existing.txt", "gs://other/file.txt"]
        COMPLETE_CACHE.write_text("\n".join(existing))

        new_paths = ["gs://bucket/new1.txt", "gs://bucket/new2.txt"]
        _update_cache("gs://bucket/", new_paths)

        cached = set(COMPLETE_CACHE.read_text().strip().split("\n"))
        # Old paths with gs://bucket/ prefix should be replaced
        assert "gs://bucket/existing.txt" not in cached
        # New paths should be added
        assert "gs://bucket/new1.txt" in cached
        assert "gs://bucket/new2.txt" in cached
        # Paths with different prefix should remain
        assert "gs://other/file.txt" in cached

    def test_path_completer_empty_prefix(self, cache_setup):
        """Test path completer with empty prefix."""
        results = path_completer("")
        assert "-" in results
        assert "gs://" in results
        assert "s3://" in results
        assert "az://" in results

    def test_path_completer_local_path(self, tmp_path, cache_setup):
        """Test path completer with local path."""
        # Create test files
        (tmp_path / "test1.txt").touch()
        (tmp_path / "test2.txt").touch()
        (tmp_path / "testdir").mkdir()

        prefix = str(tmp_path / "test")
        results = path_completer(prefix)

        assert any("test1.txt" in r for r in results)
        assert any("test2.txt" in r for r in results)
        assert any("testdir/" in r for r in results)

    def test_path_completer_cloud_no_cache(self, gcs_bucket, cache_setup):
        """Test path completer with cloud path when cache doesn't exist."""
        if COMPLETE_CACHE.exists():
            COMPLETE_CACHE.unlink()

        # Create a test directory
        workspace = f"{gcs_bucket}/test_complete_{uuid4()}"
        dir_path = CloudPath(workspace)
        dir_path.mkdir(parents=True, exist_ok=True)
        (dir_path / "file1.txt").write_text("test1")
        (dir_path / "file2.txt").write_text("test2")

        try:
            os.environ["CLOUDSH_COMPLETE_NO_FETCHING_INDICATOR"] = "1"
            results = path_completer(str(dir_path) + "/")

            # Should fetch from cloud
            assert any("file1.txt" in r for r in results)
            assert any("file2.txt" in r for r in results)
        finally:
            os.environ.pop("CLOUDSH_COMPLETE_NO_FETCHING_INDICATOR", None)
            CloudPath(workspace).rmtree()

    def test_path_completer_cloud_with_cache(self, cache_setup):
        """Test path completer with cloud path when cache exists."""
        COMPLETE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        test_paths = [
            "gs://bucket/file1.txt",
            "gs://bucket/file2.txt",
            "gs://bucket/dir/",
        ]
        COMPLETE_CACHE.write_text("\n".join(test_paths))

        os.environ["CLOUDSH_COMPLETE_CACHING_WARN"] = "1"
        try:
            results = path_completer("gs://bucket/")
            assert "gs://bucket/file1.txt" in results
            assert "gs://bucket/file2.txt" in results
            assert "gs://bucket/dir/" in results
        finally:
            os.environ.pop("CLOUDSH_COMPLETE_CACHING_WARN", None)

    def test_path_completer_cloud_cache_warning(self, cache_setup):
        """Test that cache warning is shown once."""
        COMPLETE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        COMPLETE_CACHE.write_text("gs://bucket/file.txt")

        if WARN_CACHING_INDICATOR_FILE.exists():
            WARN_CACHING_INDICATOR_FILE.unlink()

        # First call should show warning (captured by argcomplete.warn)
        with patch("cloudsh.commands.complete.warn") as mock_warn:
            path_completer("gs://bucket/")
            assert mock_warn.called
            assert "Using cached cloud path completion" in str(mock_warn.call_args)

    def test_path_completer_incomplete_bucket(self, cache_setup):
        """Test path completer with incomplete bucket name."""
        if COMPLETE_CACHE.exists():
            COMPLETE_CACHE.unlink()

        os.environ["CLOUDSH_COMPLETE_NO_FETCHING_INDICATOR"] = "1"
        try:
            # This will try to list buckets - mock it to avoid actual API calls
            with patch("cloudsh.commands.complete.CloudPath") as mock_cp:
                mock_bucket = MagicMock()
                mock_bucket.bucket = "test-bucket"
                mock_bucket.__str__ = lambda self: "gs://test-bucket"

                mock_cp.return_value.iterdir.return_value = [mock_bucket]
                _ = path_completer("gs://test")

                # Should attempt to list buckets
                assert mock_cp.called
        finally:
            os.environ.pop("CLOUDSH_COMPLETE_NO_FETCHING_INDICATOR", None)

    def test_path_completer_cloud_error(self, cache_setup):
        """Test path completer handles errors gracefully."""
        if COMPLETE_CACHE.exists():
            COMPLETE_CACHE.unlink()

        os.environ["CLOUDSH_COMPLETE_NO_FETCHING_INDICATOR"] = "1"
        try:
            with patch("cloudsh.commands.complete.CloudPath") as mock_cp:
                mock_cp.side_effect = Exception("Test error")

                with patch("cloudsh.commands.complete.warn") as mock_warn:
                    results = path_completer("gs://bucket/test")
                    assert results == []
                    assert mock_warn.called
                    assert "Error listing cloud path" in str(mock_warn.call_args)
        finally:
            os.environ.pop("CLOUDSH_COMPLETE_NO_FETCHING_INDICATOR", None)

    def test_run_clear_cache_all(self, cache_setup):
        """Test clearing entire cache."""
        COMPLETE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        COMPLETE_CACHE.write_text("gs://bucket/file.txt")

        args = Namespace(
            clear_cache=True,
            path=[],
            update_cache=False,
            shell=None,
            depth=-1,
        )
        run(args)

        assert not COMPLETE_CACHE.exists()

    def test_run_clear_cache_prefix(self, cache_setup):
        """Test clearing cache with specific prefix."""
        COMPLETE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        test_paths = [
            "gs://bucket1/file1.txt",
            "gs://bucket2/file2.txt",
        ]
        COMPLETE_CACHE.write_text("\n".join(test_paths))

        args = Namespace(
            clear_cache=True,
            path=["gs://bucket1/"],
            update_cache=False,
            shell=None,
            depth=-1,
        )
        run(args)

        remaining = COMPLETE_CACHE.read_text().strip()
        assert "gs://bucket2/file2.txt" in remaining
        assert "gs://bucket1/file1.txt" not in remaining

    def test_run_update_cache(self, gcs_bucket, cache_setup):
        """Test updating cache."""
        workspace = f"{gcs_bucket}/test_update_cache_{uuid4()}"
        dir_path = CloudPath(workspace)
        dir_path.mkdir(parents=True, exist_ok=True)
        (dir_path / "file1.txt").write_text("test1")

        try:
            args = Namespace(
                clear_cache=False,
                update_cache=True,
                path=[str(dir_path)],
                shell=None,
                depth=-1,
            )

            run(args)

            # Cache should be updated
            assert COMPLETE_CACHE.exists()
            cached = COMPLETE_CACHE.read_text()
            assert "file1.txt" in cached
        finally:
            CloudPath(workspace).rmtree()

    def test_run_shell_generation_explicit(self, cache_setup):
        """Test shell completion script generation with explicit shell."""
        args = Namespace(
            clear_cache=False,
            update_cache=False,
            path=[],
            shell="bash",
            depth=-1,
        )

        with patch("sys.stdout") as _:
            run(args)
            # Should generate shell completion script

    def test_run_shell_generation_from_env(self, cache_setup):
        """Test shell completion script generation from SHELL env var."""
        args = Namespace(
            clear_cache=False,
            update_cache=False,
            path=[],
            shell=None,
            depth=-1,
        )

        with patch.dict(os.environ, {"SHELL": "/bin/bash"}):
            with patch("sys.stdout") as _:
                run(args)

    def test_run_shell_generation_no_shell(self, cache_setup):
        """Test error when shell cannot be detected."""
        args = Namespace(
            clear_cache=False,
            update_cache=False,
            path=[],
            shell=None,
            depth=-1,
        )

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                run(args)
            assert exc_info.value.code == 1
