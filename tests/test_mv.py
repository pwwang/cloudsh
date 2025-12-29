import asyncio
import time
from argparse import Namespace
from panpath import PanPath

import pytest

from cloudsh.commands.mv import run


class TestMv:
    """Test mv command functionality"""

    @pytest.fixture
    async def source_file(self, workdir):
        """Create a source test file"""
        path = workdir / "source.txt"
        await path.a_write_text("test content")
        return str(path)

    @pytest.fixture
    async def source_dir(self, workdir):
        """Create a source directory with files"""
        path = workdir / "source_dir"
        await path.a_mkdir()
        await (path / "file1.txt").a_write_text("content1")
        await (path / "file2.txt").a_write_text("content2")
        await (path / "subdir").a_mkdir()
        await (path / "subdir/file3.txt").a_write_text("content3")
        return str(path)

    @pytest.fixture(autouse=True)
    def setup_input(self, monkeypatch):
        """Mock input for interactive prompts"""
        self.input_response = "y"

        def mock_input(prompt):
            print(prompt, end="")
            return self.input_response

        monkeypatch.setattr("builtins.input", mock_input)

    async def test_mv_file(self, source_file, workdir):
        """Test moving a single file"""
        dest = str(workdir / "moved.txt")
        args = Namespace(
            u=False,
            SOURCE=[source_file],
            DEST=dest,
            force=False,
            interactive=False,
            no_clobber=False,
            target_directory=None,
            no_target_directory=False,
            verbose=False,
            update=False,
        )
        await run(args)
        src_path = PanPath(source_file)
        dst_path = PanPath(dest)
        assert not await src_path.a_exists()
        assert await dst_path.a_exists()
        assert await dst_path.a_read_text() == "test content"

    async def test_mv_to_directory(self, source_file, workdir):
        """Test moving file to directory"""
        dest_dir = workdir / "dest_dir"
        await dest_dir.a_mkdir()
        args = Namespace(
            u=False,
            SOURCE=[source_file],
            DEST=str(dest_dir),
            force=False,
            interactive=False,
            no_clobber=False,
            target_directory=None,
            no_target_directory=False,
            verbose=False,
            update=False,
        )
        await run(args)
        assert not await PanPath(source_file).a_exists()
        assert await (dest_dir / "source.txt").a_exists()

    async def test_mv_interactive_yes(self, source_file, workdir):
        """Test interactive move with 'yes' response"""
        dest = workdir / "interactive.txt"
        await dest.a_write_text("original")
        self.input_response = "y"
        args = Namespace(
            u=False,
            SOURCE=[source_file],
            DEST=str(dest),
            force=False,
            interactive=True,
            no_clobber=False,
            target_directory=None,
            no_target_directory=False,
            verbose=False,
            update=False,
        )
        await run(args)
        assert not await PanPath(source_file).a_exists()
        assert await dest.a_read_text() == "test content"

    async def test_mv_interactive_no(self, source_file, workdir):
        """Test interactive move with 'no' response"""
        dest = workdir / "interactive_no.txt"
        await dest.a_write_text("original")
        self.input_response = "n"
        args = Namespace(
            u=False,
            SOURCE=[source_file],
            DEST=str(dest),
            force=False,
            interactive=True,
            no_clobber=False,
            target_directory=None,
            no_target_directory=False,
            verbose=False,
            update=False,
        )
        await run(args)
        assert await PanPath(source_file).a_exists()
        assert await dest.a_read_text() == "original"

    async def test_mv_multiple_files(self, source_file, source_dir, workdir):
        """Test moving multiple files to directory"""
        dest_dir = workdir / "multi_dest"
        await dest_dir.a_mkdir()
        args = Namespace(
            u=False,
            SOURCE=[source_file, source_dir],
            DEST=str(dest_dir),
            force=False,
            interactive=False,
            no_clobber=False,
            target_directory=None,
            no_target_directory=False,
            verbose=False,
            update=False,
        )
        await run(args)
        assert not await PanPath(source_file).a_exists()
        assert not await PanPath(source_dir).a_exists()
        assert await (dest_dir / "source.txt").a_exists()
        assert await (dest_dir / "source_dir").a_exists()
        assert await (dest_dir / "source_dir/file1.txt").a_exists()

    async def test_mv_target_directory(self, source_file, workdir):
        """Test target-directory option"""
        target_dir = workdir / "target_dir"
        await target_dir.a_mkdir()
        args = Namespace(
            u=False,
            SOURCE=[source_file],
            DEST="unused",  # Should be ignored
            force=False,
            interactive=False,
            no_clobber=False,
            target_directory=str(target_dir),
            no_target_directory=False,
            verbose=False,
            update=False,
        )
        await run(args)
        assert not await PanPath(source_file).a_exists()
        assert await (target_dir / "source.txt").a_exists()

    async def test_mv_local_to_local(self, tmp_path):
        """Test moving between local paths"""
        src = PanPath(tmp_path) / "src.txt"
        dst = PanPath(tmp_path) / "dst.txt"
        await src.a_write_text("local content")

        args = Namespace(
            u=False,
            SOURCE=[str(src)],
            DEST=str(dst),
            force=False,
            interactive=False,
            no_clobber=False,
            target_directory=None,
            no_target_directory=False,
            update=False,
            verbose=False,
        )
        await run(args)
        assert not await src.a_exists()
        assert await dst.a_exists()
        assert await dst.a_read_text() == "local content"

    async def test_mv_force(self, workdir):
        """Test force move with cloud files"""
        src = workdir / "force_src.txt"
        dst = workdir / "force_dst.txt"
        await src.a_write_text("newer")
        await dst.a_write_text("older")

        args = Namespace(
            u=False,
            SOURCE=[str(src)],
            DEST=str(dst),
            force=True,
            interactive=False,
            no_clobber=False,
            target_directory=None,
            no_target_directory=False,
            update=False,
            verbose=False,
        )
        await run(args)
        assert not await src.a_exists()
        assert await dst.a_read_text() == "newer"

    async def test_mv_no_clobber(self, workdir):
        """Test no-clobber option"""
        src = workdir / "noclobber_src.txt"
        dst = workdir / "noclobber_dst.txt"
        await src.a_write_text("source")
        await dst.a_write_text("destination")

        args = Namespace(
            u=False,
            SOURCE=[str(src)],
            DEST=str(dst),
            force=False,
            interactive=False,
            no_clobber=True,
            target_directory=None,
            no_target_directory=False,
            update=False,
            verbose=False,
        )
        await run(args)
        assert await src.a_exists()
        assert await dst.a_read_text() == "destination"

    async def test_mv_interactive(self, workdir):
        """Test interactive move"""
        src = workdir / "interactive_src.txt"
        dst = workdir / "interactive_dst.txt"
        await src.a_write_text("source")
        await dst.a_write_text("destination")

        # Test 'no' response
        self.input_response = "n"
        args = Namespace(
            u=False,
            SOURCE=[str(src)],
            DEST=str(dst),
            force=False,
            interactive=True,
            no_clobber=False,
            target_directory=None,
            no_target_directory=False,
            update=False,
            verbose=False,
        )
        await run(args)
        assert await src.a_exists()
        assert await dst.a_read_text() == "destination"

        # Test 'yes' response
        self.input_response = "y"
        await run(args)
        assert not await src.a_exists()
        assert await dst.a_read_text() == "source"

    async def test_mv_multiple_sources(self, workdir):
        """Test moving multiple sources to directory"""
        src1 = workdir / "multi1.txt"
        src2 = workdir / "multi2.txt"
        dst_dir = workdir / "multi_dst"
        await src1.a_write_text("content1")
        await src2.a_write_text("content2")
        await dst_dir.a_mkdir()

        args = Namespace(
            u=False,
            SOURCE=[str(src1), str(src2)],
            DEST=str(dst_dir),
            force=False,
            interactive=False,
            no_clobber=False,
            target_directory=None,
            no_target_directory=False,
            update=False,
            verbose=False,
        )
        await run(args)
        assert not await src1.a_exists() and not await src2.a_exists()
        assert await (dst_dir / "multi1.txt").a_exists()
        assert await (dst_dir / "multi2.txt").a_exists()

    async def test_mv_error_handling(self, workdir, capsys):
        """Test error conditions"""
        # Test moving nonexistent file
        args = Namespace(
            u=False,
            SOURCE=[str(workdir / "nonexistent.txt")],
            DEST=str(workdir / "dest.txt"),
            force=False,
            interactive=False,
            no_clobber=False,
            target_directory=None,
            no_target_directory=False,
            update=False,
            verbose=False,
        )
        with pytest.raises(SystemExit):
            await run(args)
        assert "No such file" in capsys.readouterr().err

        # Test moving multiple files to non-directory
        src1 = workdir / "err1.txt"
        src2 = workdir / "err2.txt"
        dst = workdir / "err_dst.txt"
        await src1.a_write_text("1")
        await src2.a_write_text("2")
        await dst.a_write_text("dst")

        args = Namespace(
            u=False,
            SOURCE=[str(src1), str(src2)],
            DEST=str(dst),
            force=False,
            interactive=False,
            no_clobber=False,
            target_directory=None,
            no_target_directory=False,
            update=False,
            verbose=False,
        )
        with pytest.raises(SystemExit):
            await run(args)
        assert "not a directory" in capsys.readouterr().err.lower()

    async def test_mv_update_all(self, workdir):
        """Test --update=all option (default without --update)"""
        src = workdir / "src.txt"
        dst = workdir / "dst.txt"
        await src.a_write_text("source")
        await dst.a_write_text("dest")

        args = Namespace(
            u=False,
            SOURCE=[str(src)],
            DEST=str(dst),
            force=False,
            interactive=False,
            no_clobber=False,
            target_directory=None,
            no_target_directory=False,
            update="all",
            verbose=False,
        )
        await run(args)
        assert not await src.a_exists()
        assert await dst.a_read_text() == "source"

    async def test_mv_update_none(self, workdir):
        """Test --update=none option"""
        src = workdir / "src.txt"
        dst = workdir / "dst.txt"
        await src.a_write_text("source")
        await dst.a_write_text("dest")

        args = Namespace(
            u=False,
            SOURCE=[str(src)],
            DEST=str(dst),
            force=False,
            interactive=False,
            no_clobber=False,
            target_directory=None,
            no_target_directory=False,
            update="none",
            verbose=False,
        )
        await run(args)
        assert await src.a_exists()  # Source should not be moved
        assert await dst.a_read_text() == "dest"

    async def test_mv_update_older(self, workdir):
        """Test --update=older option (default with --update)"""
        src = workdir / "src.txt"
        dst = workdir / "dst.txt"
        await src.a_write_text("source")
        await dst.a_write_text("dest")

        # For local files, test with mtime comparison
        time.sleep(0.1)
        src.write_text("newer source")  # Make source newer

        args = Namespace(
            u=False,
            SOURCE=[str(src)],
            DEST=str(dst),
            force=False,
            interactive=False,
            no_clobber=False,
            target_directory=None,
            no_target_directory=False,
            update="older",
            verbose=False,
        )
        await run(args)
        assert not await src.a_exists()  # Should move newer source
        assert await dst.a_read_text() == "newer source"

    async def test_mv_update_modes(self, workdir):
        """Test different --update modes"""
        # Create test files
        src = workdir / "src.txt"
        dst = workdir / "dst.txt"
        await src.a_write_text("source")
        await dst.a_write_text("dest")

        # Test no --update specified (should use "all")
        args = Namespace(
            SOURCE=[str(src)],
            DEST=str(dst),
            force=False,
            interactive=False,
            no_clobber=False,
            target_directory=None,
            no_target_directory=False,
            u=False,
            update=None,
            verbose=False,
        )
        await run(args)
        assert not await src.a_exists()  # Should move even though source is older
        assert await dst.a_read_text() == "source"

        # Test --update=none
        await src.a_write_text("new source")
        args.update = "none"
        await run(args)
        assert await src.a_exists()  # Should keep source
        assert await dst.a_read_text() == "source"  # Should keep dest unchanged

        # Test -u (equivalent to --update=older)
        await asyncio.sleep(0.1)
        await src.a_write_text("newer source")  # Make source newer
        args.u = True
        args.update = None
        await run(args)
        assert not await src.a_exists()  # Should move because source is newer
        assert await dst.a_read_text() == "newer source"

    async def test_mv_update_default(self, workdir):
        """Test default update behavior
        (all when not specified, older when specified)"""
        src = workdir / "src.txt"
        dst = workdir / "dst.txt"
        await src.a_write_text("source")
        await dst.a_write_text("dest")

        # Without --update, should replace regardless of timestamp (all)
        args = Namespace(
            u=False,
            SOURCE=[str(src)],
            DEST=str(dst),
            force=False,
            interactive=False,
            no_clobber=False,
            target_directory=None,
            no_target_directory=False,
            update=False,  # No --update specified
            verbose=False,
        )
        await run(args)
        assert not await src.a_exists()
        assert await dst.a_read_text() == "source"

        # With --update (no value), should use 'older' mode
        await src.a_write_text("source2")
        await dst.a_write_text("dest2")
        # Make dest newer
        await asyncio.sleep(0.1)
        await dst.a_write_text("dest2")

        args.update = "older"
        await run(args)
        assert await src.a_exists()  # Should not move older file
        assert await dst.a_read_text() == "dest2"

    async def test_mv_source_not_exists(self, workdir, capsys):
        """Test moving non-existent source"""
        src = workdir / "nonexistent.txt"
        dst = workdir / "dest.txt"

        args = Namespace(
            u=False,
            SOURCE=[str(src)],
            DEST=str(dst),
            force=False,
            interactive=False,
            no_clobber=False,
            target_directory=None,
            no_target_directory=False,
            update=False,
            verbose=False,
        )

        with pytest.raises(SystemExit):
            await run(args)

        captured = capsys.readouterr()
        assert "No such file or directory" in captured.err

    async def test_mv_cloud_dir_to_cloud_dir(self, workdir):
        """Test moving cloud directory to another cloud directory"""
        src_dir = workdir / "src_cloud_dir"
        await src_dir.a_mkdir()
        await (src_dir / "file1.txt").a_write_text("content1")
        await (src_dir / "subdir").a_mkdir()
        await (src_dir / "subdir" / "file2.txt").a_write_text("content2")

        dst_dir = workdir / "dst_cloud_dir"

        args = Namespace(
            u=False,
            SOURCE=[str(src_dir)],
            DEST=str(dst_dir),
            force=False,
            interactive=False,
            no_clobber=False,
            target_directory=None,
            no_target_directory=False,
            update=False,
            verbose=False,
        )

        await run(args)
        assert not await src_dir.a_exists()
        assert await dst_dir.a_exists()
        assert await (dst_dir / "file1.txt").a_exists()
        assert await (dst_dir / "subdir" / "file2.txt").a_exists()

    async def test_mv_cloud_to_local_dir(self, workdir, tmp_path):
        """Test moving cloud directory to local directory"""
        src_dir = workdir / "src_cloud"
        await src_dir.a_mkdir()
        await (src_dir / "file1.txt").a_write_text("content1")
        await (src_dir / "subdir").a_mkdir()
        await (src_dir / "subdir" / "file2.txt").a_write_text("content2")

        dst_dir = PanPath(tmp_path) / "dst_local"

        args = Namespace(
            u=False,
            SOURCE=[str(src_dir)],
            DEST=str(dst_dir),
            force=False,
            interactive=False,
            no_clobber=False,
            target_directory=None,
            no_target_directory=False,
            update=False,
            verbose=False,
        )

        await run(args)
        assert not await src_dir.a_exists()
        assert await dst_dir.a_exists()
        assert await (dst_dir / "file1.txt").a_exists()
        assert await (dst_dir / "subdir" / "file2.txt").a_exists()

    async def test_mv_local_to_cloud_dir(self, tmp_path, cloud_workdir):
        """Test moving local directory to cloud directory"""
        src_dir = PanPath(tmp_path) / "src_local"
        await src_dir.a_mkdir()
        await (src_dir / "file1.txt").a_write_text("content1")
        await (src_dir / "subdir").a_mkdir()
        await (src_dir / "subdir" / "file2.txt").a_write_text("content2")

        dst_dir = cloud_workdir / "dst_cloud"

        args = Namespace(
            u=False,
            SOURCE=[str(src_dir)],
            DEST=str(dst_dir),
            force=False,
            interactive=False,
            no_clobber=False,
            target_directory=None,
            no_target_directory=False,
            update=False,
            verbose=False,
        )

        await run(args)
        assert not await src_dir.a_exists()
        assert await dst_dir.a_exists()
        assert await (dst_dir / "file1.txt").a_exists()
        assert await (dst_dir / "subdir" / "file2.txt").a_exists()

    async def test_mv_with_verbose_cloud(self, workdir, capsys):
        """Test verbose output for cloud moves"""
        src = workdir / "src_verbose.txt"
        await src.a_write_text("content")
        dst = workdir / "dst_verbose.txt"

        args = Namespace(
            u=False,
            SOURCE=[str(src)],
            DEST=str(dst),
            force=False,
            interactive=False,
            no_clobber=False,
            target_directory=None,
            no_target_directory=False,
            update=False,
            verbose=True,
        )

        await run(args)
        captured = capsys.readouterr()
        assert "renamed" in captured.out
        assert str(src) in captured.out
        assert str(dst) in captured.out

    async def test_mv_multiple_sources_not_to_directory(self, workdir, capsys):
        """Test moving multiple sources to non-directory target"""
        src1 = workdir / "src1.txt"
        src2 = workdir / "src2.txt"
        await src1.a_write_text("content1")
        await src2.a_write_text("content2")
        dst = workdir / "dst.txt"
        await dst.a_write_text("existing")

        args = Namespace(
            u=False,
            SOURCE=[str(src1), str(src2)],
            DEST=str(dst),
            force=False,
            interactive=False,
            no_clobber=False,
            target_directory=None,
            no_target_directory=False,
            update=False,
            verbose=False,
        )

        with pytest.raises(SystemExit):
            await run(args)

        captured = capsys.readouterr()
        assert "is not a directory" in captured.err

    async def test_mv_target_directory_create_if_not_exists(self, workdir):
        """Test that target directory is created if it doesn't exist"""
        src = workdir / "src.txt"
        await src.a_write_text("content")
        dst_dir = workdir / "new_target_dir"

        args = Namespace(
            u=False,
            SOURCE=[str(src)],
            DEST=None,
            force=False,
            interactive=False,
            no_clobber=False,
            target_directory=str(dst_dir),
            no_target_directory=False,
            update=False,
            verbose=False,
        )

        await run(args)
        assert await dst_dir.a_exists()
        assert await (dst_dir / "src.txt").a_exists()

    async def test_mv_cloud_file_to_cloud_file(self, cloud_workdir):
        """Test moving between two cloud paths (using native cloud APIs)"""
        src = cloud_workdir / "cloud_src.txt"
        await src.a_write_text("cloud to cloud content")
        dest = cloud_workdir / "cloud_dest.txt"

        args = Namespace(
            u=False,
            SOURCE=[str(src)],
            DEST=str(dest),
            force=False,
            interactive=False,
            no_clobber=False,
            target_directory=None,
            no_target_directory=False,
            verbose=True,
            update=False,
        )
        await run(args)
        assert not await src.a_exists(), "Source file should be deleted after move"
        assert await dest.a_exists(), "Destination file should exist after move"
        assert await dest.a_read_text() == "cloud to cloud content"

    async def test_mv_cloud_file_to_cloud_dir_exists(self, cloud_workdir):
        """Test moving cloud file into existing cloud directory"""
        src = cloud_workdir / "cloud_file.txt"
        await src.a_write_text("file content")

        dest_dir = cloud_workdir / "cloud_dest_dir"
        await dest_dir.a_mkdir()

        args = Namespace(
            u=False,
            SOURCE=[str(src)],
            DEST=str(dest_dir),
            force=False,
            interactive=False,
            no_clobber=False,
            target_directory=None,
            no_target_directory=False,
            verbose=True,
            update=False,
        )
        await run(args)
        assert not await src.a_exists(), "Source file should be deleted after move"
        assert await (dest_dir / "cloud_file.txt").a_exists()
        assert await (dest_dir / "cloud_file.txt").a_read_text() == "file content"

    async def test_mv_cloud_dir_to_cloud_dir_exists(self, cloud_workdir):
        """Test moving cloud directory to existing cloud directory"""
        src_dir = cloud_workdir / "cloud_src_dir"
        await src_dir.a_mkdir()
        await (src_dir / "file1.txt").a_write_text("cloud1")
        await (src_dir / "file2.txt").a_write_text("cloud2")
        await (src_dir / "subdir").a_mkdir()
        await (src_dir / "subdir" / "file3.txt").a_write_text("cloud3")

        dest_dir = cloud_workdir / "cloud_dest_dir"
        await dest_dir.a_mkdir()

        args = Namespace(
            u=False,
            SOURCE=[str(src_dir)],
            DEST=str(dest_dir),
            force=False,
            interactive=False,
            no_clobber=False,
            target_directory=None,
            no_target_directory=False,
            verbose=True,
            update=False,
        )
        await run(args)
        assert (
            not await src_dir.a_exists()
        ), "Source directory should be deleted after move"
        assert await (dest_dir / "cloud_src_dir").a_exists()
        assert await (dest_dir / "cloud_src_dir" / "file1.txt").a_exists()
        assert await (dest_dir / "cloud_src_dir" / "file2.txt").a_exists()
        assert await (dest_dir / "cloud_src_dir" / "subdir" / "file3.txt").a_exists()
        assert (
            await (dest_dir / "cloud_src_dir" / "file1.txt").a_read_text() == "cloud1"
        )

    async def test_mv_cloud_dir_to_cloud_dir_not_exists(self, cloud_workdir):
        """Test moving cloud directory to non-existing cloud directory (rename)"""
        src_dir = cloud_workdir / "cloud_src_dir2"
        await src_dir.a_mkdir()
        await (src_dir / "file1.txt").a_write_text("cloudA")
        await (src_dir / "file2.txt").a_write_text("cloudB")
        await (src_dir / "subdir").a_mkdir()
        await (src_dir / "subdir" / "file3.txt").a_write_text("cloudC")

        dest_dir = cloud_workdir / "cloud_dest_dir2"

        args = Namespace(
            u=False,
            SOURCE=[str(src_dir)],
            DEST=str(dest_dir),
            force=False,
            interactive=False,
            no_clobber=False,
            target_directory=None,
            no_target_directory=False,
            verbose=True,
            update=False,
        )
        await run(args)
        assert (
            not await src_dir.a_exists()
        ), "Source directory should be deleted after move"
        assert await dest_dir.a_exists()
        assert await (dest_dir / "file1.txt").a_exists()
        assert await (dest_dir / "file2.txt").a_exists()
        assert await (dest_dir / "subdir" / "file3.txt").a_exists()
        assert await (dest_dir / "file1.txt").a_read_text() == "cloudA"

    async def test_mv_cloud_file_with_force(self, cloud_workdir):
        """Test moving cloud file with force overwrite"""
        src = cloud_workdir / "cloud_src_force.txt"
        await src.a_write_text("new content")

        dest = cloud_workdir / "cloud_dest_force.txt"
        await dest.a_write_text("old content")

        args = Namespace(
            u=False,
            SOURCE=[str(src)],
            DEST=str(dest),
            force=True,
            interactive=False,
            no_clobber=False,
            target_directory=None,
            no_target_directory=False,
            verbose=True,
            update=False,
        )
        await run(args)
        assert not await src.a_exists()
        assert await dest.a_exists()
        assert await dest.a_read_text() == "new content"

    async def test_mv_cloud_file_no_clobber(self, cloud_workdir):
        """Test moving cloud file with no-clobber (don't overwrite)"""
        src = cloud_workdir / "cloud_src_nc.txt"
        await src.a_write_text("new content")

        dest = cloud_workdir / "cloud_dest_nc.txt"
        await dest.a_write_text("old content")

        args = Namespace(
            u=False,
            SOURCE=[str(src)],
            DEST=str(dest),
            force=False,
            interactive=False,
            no_clobber=True,
            target_directory=None,
            no_target_directory=False,
            verbose=True,
            update=False,
        )
        await run(args)
        assert (
            await src.a_exists()
        ), "Source should still exist when no_clobber prevents move"
        assert await dest.a_exists()
        assert (
            await dest.a_read_text() == "old content"
        ), "Destination should not be overwritten"

    async def test_mv_cloud_multiple_files_to_cloud_dir(self, cloud_workdir):
        """Test moving multiple cloud files to cloud directory"""
        src1 = cloud_workdir / "cloud_multi1.txt"
        await src1.a_write_text("content1")

        src2 = cloud_workdir / "cloud_multi2.txt"
        await src2.a_write_text("content2")

        dest_dir = cloud_workdir / "cloud_multi_dest"
        await dest_dir.a_mkdir()

        args = Namespace(
            u=False,
            SOURCE=[str(src1), str(src2)],
            DEST=str(dest_dir),
            force=False,
            interactive=False,
            no_clobber=False,
            target_directory=None,
            no_target_directory=False,
            verbose=True,
            update=False,
        )
        await run(args)
        assert not await src1.a_exists()
        assert not await src2.a_exists()
        assert await (dest_dir / "cloud_multi1.txt").a_exists()
        assert await (dest_dir / "cloud_multi2.txt").a_exists()
        assert await (dest_dir / "cloud_multi1.txt").a_read_text() == "content1"
        assert await (dest_dir / "cloud_multi2.txt").a_read_text() == "content2"
