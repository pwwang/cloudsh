import sys
from argparse import Namespace
from uuid import uuid4

import pytest
from cloudpathlib import AnyPath

from cloudsh.commands.mkdir import run
from .conftest import BUCKET

WORKDIR = None


def setup_module():
    """Create test directory before any tests run"""
    global WORKDIR
    WORKDIR = AnyPath(f"{BUCKET}/cloudsh_test/{uuid4()}")
    WORKDIR.mkdir(parents=True)


def teardown_module():
    """Remove test directory after all tests complete"""
    if WORKDIR is not None:
        WORKDIR.rmtree()


class TestMkdir:
    """Test mkdir command functionality"""

    def test_mkdir_basic(self):
        """Test basic directory creation"""
        test_dir = WORKDIR / "test_dir"
        args = Namespace(
            directory=[str(test_dir)], parents=False, mode=None, verbose=False
        )
        run(args)
        assert test_dir.exists()
        assert test_dir.is_dir()

    def test_mkdir_parents(self):
        """Test creating directory with parents"""
        test_dir = WORKDIR / "parent/child/grandchild"
        args = Namespace(
            directory=[str(test_dir)], parents=True, mode=None, verbose=False
        )
        run(args)
        assert test_dir.exists()
        assert test_dir.is_dir()
        assert (WORKDIR / "parent").is_dir()
        assert (WORKDIR / "parent/child").is_dir()

    def test_mkdir_multiple(self):
        """Test creating multiple directories"""
        dirs = [WORKDIR / f"dir{i}" for i in range(3)]
        args = Namespace(
            directory=[str(d) for d in dirs], parents=False, mode=None, verbose=False
        )
        run(args)
        for d in dirs:
            assert d.exists()
            assert d.is_dir()

    def test_mkdir_verbose(self, capsys):
        """Test verbose output"""
        test_dir = WORKDIR / "verbose_dir"
        args = Namespace(
            directory=[str(test_dir)], parents=False, mode=None, verbose=True
        )
        run(args)
        assert test_dir.exists()
        out = capsys.readouterr().out
        assert f"created directory '{test_dir}'" in out

    def test_mkdir_exists(self, capsys):
        """Test directory already exists error"""
        test_dir = WORKDIR / "existing"
        test_dir.mkdir()
        args = Namespace(
            directory=[str(test_dir)], parents=False, mode=None, verbose=False
        )
        with pytest.raises(SystemExit):
            run(args)
        err = capsys.readouterr().err
        assert "cannot create directory" in err
        assert "File exists" in err

    def test_mkdir_parents_exists(self):
        """Test no error when directory exists with --parents"""
        test_dir = WORKDIR / "parent_existing"
        test_dir.mkdir()
        args = Namespace(
            directory=[str(test_dir)], parents=True, mode=None, verbose=False
        )
        run(args)  # Should not raise error

    def test_mkdir_local(self, tmp_path):
        """Test creating local directory"""
        test_dir = tmp_path / "local_dir"
        args = Namespace(
            directory=[str(test_dir)], parents=False, mode=None, verbose=False
        )
        run(args)
        assert test_dir.exists()
        assert test_dir.is_dir()

    def test_mkdir_local_parents(self, tmp_path):
        """Test creating local directory with parents"""
        test_dir = tmp_path / "local/nested/dir"
        args = Namespace(
            directory=[str(test_dir)], parents=True, mode=None, verbose=False
        )
        run(args)
        assert test_dir.exists()
        assert test_dir.is_dir()
        assert (tmp_path / "local").is_dir()
        assert (tmp_path / "local/nested").is_dir()

    def test_mkdir_no_permission(self, tmp_path, capsys):
        """Test mkdir with insufficient permissions"""
        # Skip on Windows as permission model is different
        if sys.platform == "win32":
            pytest.skip("Permission tests not applicable on Windows")

        # Create a directory without write permissions
        no_access = tmp_path / "no_access"
        no_access.mkdir()
        no_access.chmod(0o555)  # read + execute only

        test_dir = no_access / "test"
        args = Namespace(
            directory=[str(test_dir)], parents=False, mode=None, verbose=False
        )
        with pytest.raises(SystemExit):
            run(args)
        err = capsys.readouterr().err
        assert "cannot create directory" in err
        assert "Permission denied" in err

    def test_mkdir_mixed_paths(self, tmp_path):
        """Test creating both local and cloud directories"""
        cloud_dir = WORKDIR / "cloud_mixed"
        local_dir = tmp_path / "local_mixed"
        args = Namespace(
            directory=[str(cloud_dir), str(local_dir)],
            parents=False,
            mode=None,
            verbose=True,
        )
        run(args)
        assert cloud_dir.exists()
        assert local_dir.exists()

    def test_mkdir_parents_path_is_file(self, capsys):
        """Test mkdir -p when part of path is a file"""
        file_path = WORKDIR / "file"
        file_path.write_text("test")
        test_dir = file_path / "dir"
        args = Namespace(
            directory=[str(test_dir)], parents=True, mode=None, verbose=False
        )
        with pytest.raises(SystemExit):
            run(args)
        err = capsys.readouterr().err
        assert "cannot create directory" in err
        assert "Not a directory" in err
