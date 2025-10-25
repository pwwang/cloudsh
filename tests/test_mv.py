import os
from argparse import Namespace
from pathlib import Path

import pytest

from cloudsh.commands.mv import run


class TestMv:
    """Test mv command functionality"""

    @pytest.fixture
    def source_file(self, workdir):
        """Create a source test file"""
        path = workdir / "source.txt"
        path.write_text("test content")
        return str(path)

    @pytest.fixture
    def source_dir(self, workdir):
        """Create a source directory with files"""
        path = workdir / "source_dir"
        path.mkdir()
        (path / "file1.txt").write_text("content1")
        (path / "file2.txt").write_text("content2")
        (path / "subdir").mkdir()
        (path / "subdir/file3.txt").write_text("content3")
        return str(path)

    @pytest.fixture(autouse=True)
    def setup_input(self, monkeypatch):
        """Mock input for interactive prompts"""
        self.input_response = "y"

        def mock_input(prompt):
            print(prompt, end="")
            return self.input_response

        monkeypatch.setattr("builtins.input", mock_input)

    @pytest.fixture(autouse=True)
    def setup_force_overwrite(self):
        """Force cloud file overwrites for testing"""
        os.environ["CLOUDPATHLIB_FORCE_OVERWRITE_FROM_CLOUD"] = "true"
        yield
        os.environ.pop("CLOUDPATHLIB_FORCE_OVERWRITE_FROM_CLOUD", None)

    def test_mv_file(self, source_file, workdir):
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
        run(args)
        src_path = Path(source_file)
        dst_path = Path(dest)
        assert not src_path.exists()
        assert dst_path.exists()
        assert dst_path.read_text() == "test content"

    def test_mv_to_directory(self, source_file, workdir):
        """Test moving file to directory"""
        dest_dir = workdir / "dest_dir"
        dest_dir.mkdir()
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
        run(args)
        assert not Path(source_file).exists()
        assert (dest_dir / "source.txt").exists()

    def test_mv_interactive_yes(self, source_file, workdir):
        """Test interactive move with 'yes' response"""
        dest = workdir / "interactive.txt"
        dest.write_text("original")
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
        run(args)
        assert not Path(source_file).exists()
        assert dest.read_text() == "test content"

    def test_mv_interactive_no(self, source_file, workdir):
        """Test interactive move with 'no' response"""
        dest = workdir / "interactive_no.txt"
        dest.write_text("original")
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
        run(args)
        assert Path(source_file).exists()
        assert dest.read_text() == "original"

    def test_mv_multiple_files(self, source_file, source_dir, workdir):
        """Test moving multiple files to directory"""
        dest_dir = workdir / "multi_dest"
        dest_dir.mkdir()
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
        run(args)
        assert not Path(source_file).exists()
        assert not Path(source_dir).exists()
        assert (dest_dir / "source.txt").exists()
        assert (dest_dir / "source_dir").exists()
        assert (dest_dir / "source_dir/file1.txt").exists()

    def test_mv_target_directory(self, source_file, workdir):
        """Test target-directory option"""
        target_dir = workdir / "target_dir"
        target_dir.mkdir()
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
        run(args)
        assert not Path(source_file).exists()
        assert (target_dir / "source.txt").exists()

    def test_mv_local_to_local(self, tmp_path):
        """Test moving between local paths"""
        src = tmp_path / "src.txt"
        dst = tmp_path / "dst.txt"
        src.write_text("local content")

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
        run(args)
        assert not src.exists()
        assert dst.exists()
        assert dst.read_text() == "local content"

    def test_mv_force(self, workdir):
        """Test force move with cloud files"""
        src = workdir / "force_src.txt"
        dst = workdir / "force_dst.txt"
        src.write_text("newer")
        dst.write_text("older")

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
        run(args)
        assert not src.exists()
        assert dst.read_text() == "newer"

    def test_mv_no_clobber(self, workdir):
        """Test no-clobber option"""
        src = workdir / "noclobber_src.txt"
        dst = workdir / "noclobber_dst.txt"
        src.write_text("source")
        dst.write_text("destination")

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
        run(args)
        assert src.exists()
        assert dst.read_text() == "destination"

    def test_mv_cloud_to_cloud(self, workdir):
        """Test moving file between cloud locations"""
        src = workdir / "cloud_src.txt"
        dst = workdir / "subdir/cloud_dst.txt"
        src.write_text("cloud content")

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
        run(args)
        assert not src.exists()
        assert dst.exists()
        assert dst.read_text() == "cloud content"

    def test_mv_cloud_to_cloud_dir(self, workdir):
        """Test moving file to existing cloud directory"""
        src = workdir / "src2.txt"
        dst_dir = workdir / "dst_dir"
        src.write_text("test")
        dst_dir.mkdir()

        args = Namespace(
            u=False,
            SOURCE=[str(src)],
            DEST=str(dst_dir),
            force=False,
            interactive=False,
            no_clobber=False,
            target_directory=None,
            no_target_directory=False,
            update=False,
            verbose=False,
        )
        run(args)
        assert not src.exists()
        assert (dst_dir / "src2.txt").exists()
        assert (dst_dir / "src2.txt").read_text() == "test"

    def test_mv_local_to_cloud(self, tmp_path, workdir):
        """Test moving from local to cloud"""
        src = tmp_path / "local.txt"
        src.write_text("local content")
        dst = workdir / "from_local.txt"

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
        run(args)
        assert not src.exists()
        assert dst.exists()
        assert dst.read_text() == "local content"

    def test_mv_cloud_to_local(self, tmp_path, workdir):
        """Test moving from cloud to local"""
        src = workdir / "cloud_src.txt"
        src.write_text("cloud content")
        dst = tmp_path / "local_dst.txt"

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
        run(args)
        assert not src.exists()
        assert dst.exists()
        assert dst.read_text() == "cloud content"

    def test_mv_interactive(self, workdir):
        """Test interactive move"""
        src = workdir / "interactive_src.txt"
        dst = workdir / "interactive_dst.txt"
        src.write_text("source")
        dst.write_text("destination")

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
        run(args)
        assert src.exists()
        assert dst.read_text() == "destination"

        # Test 'yes' response
        self.input_response = "y"
        run(args)
        assert not src.exists()
        assert dst.read_text() == "source"

    def test_mv_multiple_sources(self, workdir):
        """Test moving multiple sources to directory"""
        src1 = workdir / "multi1.txt"
        src2 = workdir / "multi2.txt"
        dst_dir = workdir / "multi_dst"
        src1.write_text("content1")
        src2.write_text("content2")
        dst_dir.mkdir()

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
        run(args)
        assert not src1.exists() and not src2.exists()
        assert (dst_dir / "multi1.txt").exists()
        assert (dst_dir / "multi2.txt").exists()

    def test_mv_error_handling(self, workdir, capsys):
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
            run(args)
        assert "No such file" in capsys.readouterr().err

        # Test moving multiple files to non-directory
        src1 = workdir / "err1.txt"
        src2 = workdir / "err2.txt"
        dst = workdir / "err_dst.txt"
        src1.write_text("1")
        src2.write_text("2")
        dst.write_text("dst")

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
            run(args)
        assert "not a directory" in capsys.readouterr().err.lower()

    def test_mv_update_all(self, workdir):
        """Test --update=all option (default without --update)"""
        src = workdir / "src.txt"
        dst = workdir / "dst.txt"
        src.write_text("source")
        dst.write_text("dest")

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
        run(args)
        assert not src.exists()
        assert dst.read_text() == "source"

    def test_mv_update_none(self, workdir):
        """Test --update=none option"""
        src = workdir / "src.txt"
        dst = workdir / "dst.txt"
        src.write_text("source")
        dst.write_text("dest")

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
        run(args)
        assert src.exists()  # Source should not be moved
        assert dst.read_text() == "dest"

    def test_mv_update_older(self, workdir):
        """Test --update=older option (default with --update)"""
        src = workdir / "src.txt"
        dst = workdir / "dst.txt"
        src.write_text("source")
        dst.write_text("dest")

        # For local files, test with mtime comparison
        import time
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
        run(args)
        assert not src.exists()  # Should move newer source
        assert dst.read_text() == "newer source"

    def test_mv_update_modes(self, workdir):
        """Test different --update modes"""
        # Create test files
        src = workdir / "src.txt"
        dst = workdir / "dst.txt"
        src.write_text("source")
        dst.write_text("dest")

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
        run(args)
        assert not src.exists()  # Should move even though source is older
        assert dst.read_text() == "source"

        # Test --update=none
        src.write_text("new source")
        args.update = "none"
        run(args)
        assert src.exists()  # Should keep source
        assert dst.read_text() == "source"  # Should keep dest unchanged

        # Test -u (equivalent to --update=older)
        import time
        time.sleep(0.1)
        src.write_text("newer source")  # Make source newer
        args.u = True
        args.update = None
        run(args)
        assert not src.exists()  # Should move because source is newer
        assert dst.read_text() == "newer source"

    def test_mv_update_default(self, workdir):
        """Test default update behavior
        (all when not specified, older when specified)"""
        src = workdir / "src.txt"
        dst = workdir / "dst.txt"
        src.write_text("source")
        dst.write_text("dest")

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
        run(args)
        assert not src.exists()
        assert dst.read_text() == "source"

        # With --update (no value), should use 'older' mode
        src.write_text("source2")
        dst.write_text("dest2")
        # Make dest newer
        import time
        time.sleep(0.1)
        dst.write_text("dest2")

        args.update = "older"
        run(args)
        assert src.exists()  # Should not move older file
        assert dst.read_text() == "dest2"
