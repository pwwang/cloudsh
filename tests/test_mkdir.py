import sys
from argparse import Namespace

import pytest

from panpath import PanPath
from cloudsh.commands.mkdir import run


class TestMkdir:
    """Test mkdir command functionality"""

    async def test_mkdir_basic(self, workdir):
        """Test basic directory creation"""
        test_dir = workdir / "test_dir"
        args = Namespace(
            directory=[str(test_dir)], parents=False, mode=None, verbose=False
        )
        await run(args)
        assert await test_dir.a_exists()
        assert await test_dir.a_is_dir()

    async def test_mkdir_parents(self, workdir):
        """Test creating directory with parents"""
        test_dir = workdir / "parent/child/grandchild"
        args = Namespace(
            directory=[str(test_dir)], parents=True, mode=None, verbose=False
        )
        await run(args)
        assert await test_dir.a_exists()
        assert await test_dir.a_is_dir()
        assert await (workdir / "parent").a_is_dir()
        assert await (workdir / "parent/child").a_is_dir()

    async def test_mkdir_multiple(self, workdir):
        """Test creating multiple directories"""
        dirs = [workdir / f"dir{i}" for i in range(3)]
        args = Namespace(
            directory=[str(d) for d in dirs], parents=False, mode=None, verbose=False
        )
        await run(args)
        for d in dirs:
            assert await d.a_exists()
            assert await d.a_is_dir()

    async def test_mkdir_verbose(self, workdir, capsys):
        """Test verbose output"""
        test_dir = workdir / "verbose_dir"
        args = Namespace(
            directory=[str(test_dir)], parents=False, mode=None, verbose=True
        )
        await run(args)
        assert await test_dir.a_exists()
        out = capsys.readouterr().out
        assert f"created directory '{test_dir}'" in out

    async def test_mkdir_exists(self, workdir, capsys):
        """Test directory already exists error"""
        test_dir = workdir / "existing"
        await test_dir.a_mkdir()
        args = Namespace(
            directory=[str(test_dir)], parents=False, mode=None, verbose=False
        )
        with pytest.raises(SystemExit):
            await run(args)
        err = capsys.readouterr().err
        assert "cannot create directory" in err
        assert "File exists" in err

    async def test_mkdir_parents_exists(self, workdir):
        """Test no error when directory exists with --parents"""
        test_dir = workdir / "parent_existing"
        await test_dir.a_mkdir()
        args = Namespace(
            directory=[str(test_dir)], parents=True, mode=None, verbose=False
        )
        await run(args)  # Should not raise error

    async def test_mkdir_local(self, tmp_path):
        """Test creating local directory"""
        test_dir = PanPath(tmp_path) / "local_dir"
        args = Namespace(
            directory=[str(test_dir)], parents=False, mode=None, verbose=False
        )
        await run(args)
        assert await test_dir.a_exists()
        assert await test_dir.a_is_dir()

    async def test_mkdir_local_parents(self, tmp_path):
        """Test creating local directory with parents"""
        test_dir = PanPath(tmp_path) / "local/nested/dir"
        args = Namespace(
            directory=[str(test_dir)], parents=True, mode=None, verbose=False
        )
        await run(args)
        assert await test_dir.a_exists()
        assert await test_dir.a_is_dir()
        assert await PanPath(tmp_path / "local").a_is_dir()
        assert await PanPath(tmp_path / "local/nested").a_is_dir()

    async def test_mkdir_no_permission(self, tmp_path, capsys):
        """Test mkdir with insufficient permissions"""
        # Skip on Windows as permission model is different
        if sys.platform == "win32":
            pytest.skip("Permission tests not applicable on Windows")

        # Create a directory without write permissions
        no_access = PanPath(tmp_path) / "no_access"
        await no_access.a_mkdir()
        no_access.chmod(0o555)  # read + execute only

        test_dir = no_access / "test"
        args = Namespace(
            directory=[str(test_dir)], parents=False, mode=None, verbose=False
        )
        with pytest.raises(SystemExit):
            await run(args)
        err = capsys.readouterr().err
        assert "cannot create directory" in err
        assert "Permission denied" in err

    async def test_mkdir_mixed_paths(self, workdir, tmp_path):
        """Test creating both local and cloud directories"""
        cloud_dir = workdir / "cloud_mixed"
        local_dir = PanPath(tmp_path) / "local_mixed"
        args = Namespace(
            directory=[str(cloud_dir), str(local_dir)],
            parents=False,
            mode=None,
            verbose=True,
        )
        await run(args)
        assert await cloud_dir.a_exists()
        assert await local_dir.a_exists()

    async def test_mkdir_parents_path_is_file(self, workdir, capsys):
        """Test mkdir -p when part of path is a file"""
        file_path = workdir / "file"
        await file_path.a_write_text("test")
        test_dir = file_path / "dir"
        args = Namespace(
            directory=[str(test_dir)], parents=True, mode=None, verbose=False
        )
        with pytest.raises(SystemExit):
            await run(args)
        err = capsys.readouterr().err
        assert "cannot create directory" in err
        assert "Not a directory" in err
