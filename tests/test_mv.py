import sys
from argparse import Namespace
from uuid import uuid4
import os

import pytest
from cloudpathlib import AnyPath

from cloudsh.commands.mv import run
from .conftest import BUCKET

WORKDIR = None


def setup_module():
    """Create test directory before any tests run"""
    global WORKDIR
    WORKDIR = AnyPath(f"{BUCKET}/cloudsh_test/{uuid4()}")
    WORKDIR.mkdir(parents=True)
    # Force cloud file overwrites
    os.environ["CLOUDPATHLIB_FORCE_OVERWRITE_FROM_CLOUD"] = "true"


def teardown_module():
    """Remove test directory after all tests complete"""
    if WORKDIR is not None:
        WORKDIR.rmtree()
    os.environ.pop("CLOUDPATHLIB_FORCE_OVERWRITE_FROM_CLOUD", None)


class TestMv:
    """Test mv command functionality"""

    @pytest.fixture
    def source_file(self):
        """Create a source test file"""
        path = WORKDIR / "source.txt"
        path.write_text("test content")
        return str(path)

    @pytest.fixture
    def source_dir(self):
        """Create a source directory with files"""
        path = WORKDIR / "source_dir"
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

    def test_mv_file(self, source_file):
        """Test moving a single file"""
        dest = str(WORKDIR / "moved.txt")
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
        src_path = AnyPath(source_file)
        dst_path = AnyPath(dest)
        assert not src_path.exists()
        assert dst_path.exists()
        assert dst_path.read_text() == "test content"

    def test_mv_to_directory(self, source_file):
        """Test moving file to directory"""
        dest_dir = WORKDIR / "dest_dir"
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
        assert not AnyPath(source_file).exists()
        assert (dest_dir / "source.txt").exists()

    def test_mv_interactive_yes(self, source_file):
        """Test interactive move with 'yes' response"""
        dest = WORKDIR / "interactive.txt"
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
        assert not AnyPath(source_file).exists()
        assert dest.read_text() == "test content"

    def test_mv_interactive_no(self, source_file):
        """Test interactive move with 'no' response"""
        dest = WORKDIR / "interactive_no.txt"
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
        assert AnyPath(source_file).exists()
        assert dest.read_text() == "original"

    def test_mv_no_clobber(self, source_file):
        """Test no-clobber option"""
        dest = WORKDIR / "noclobber.txt"
        dest.write_text("original")
        args = Namespace(
            u=False,
            SOURCE=[source_file],
            DEST=str(dest),
            force=False,
            interactive=False,
            no_clobber=True,
            target_directory=None,
            no_target_directory=False,
            verbose=False,
            update=False,
        )
        run(args)
        assert AnyPath(source_file).exists()
        assert dest.read_text() == "original"

    def test_mv_force(self, source_file):
        """Test force option"""
        dest = WORKDIR / "force.txt"
        dest.write_text("original")
        args = Namespace(
            u=False,
            SOURCE=[source_file],
            DEST=str(dest),
            force=True,
            interactive=False,
            no_clobber=False,
            target_directory=None,
            no_target_directory=False,
            verbose=False,
            update=False,
        )
        run(args)
        assert not AnyPath(source_file).exists()
        assert dest.read_text() == "test content"

    def test_mv_multiple_files(self, source_file, source_dir):
        """Test moving multiple files to directory"""
        dest_dir = WORKDIR / "multi_dest"
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
        assert not AnyPath(source_file).exists()
        assert not AnyPath(source_dir).exists()
        assert (dest_dir / "source.txt").exists()
        assert (dest_dir / "source_dir").exists()
        assert (dest_dir / "source_dir/file1.txt").exists()

    def test_mv_error_handling(self, source_dir, capsys):
        """Test error handling"""
        # Try to move directory to existing file
        dest = WORKDIR / "exists.txt"
        dest.write_text("original")
        args = Namespace(
            u=False,
            SOURCE=[source_dir],
            DEST=str(dest),
            force=False,
            interactive=False,
            no_clobber=False,
            target_directory=None,
            no_target_directory=True,
            verbose=False,
            update=False,
        )
        with pytest.raises(SystemExit):
            run(args)
        assert "cannot overwrite" in capsys.readouterr().err

    def test_mv_target_directory(self, source_file):
        """Test target-directory option"""
        target_dir = WORKDIR / "target_dir"
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
        assert not AnyPath(source_file).exists()
        assert (target_dir / "source.txt").exists()

    def test_mv_local_to_cloud(self, tmp_path):
        """Test moving from local to cloud storage"""
        source = tmp_path / "local.txt"
        source.write_text("local content")
        dest = WORKDIR / "cloud.txt"
        args = Namespace(
            u=False,
            SOURCE=[str(source)],
            DEST=str(dest),
            force=False,
            interactive=False,
            no_clobber=False,
            target_directory=None,
            no_target_directory=False,
            verbose=False,
            update=False,
        )
        run(args)
        assert not source.exists()
        assert dest.exists()
        assert dest.read_text() == "local content"

    def test_mv_cloud_to_local(self, tmp_path):
        """Test moving from cloud to local storage"""
        source = WORKDIR / "cloud_source.txt"
        source.write_text("cloud content")
        dest = tmp_path / "local_dest.txt"
        args = Namespace(
            u=False,
            SOURCE=[str(source)],
            DEST=str(dest),
            force=False,
            interactive=False,
            no_clobber=False,
            target_directory=None,
            no_target_directory=False,
            verbose=False,
            update=False,
        )
        run(args)
        assert not source.exists()
        assert dest.exists()
        assert dest.read_text() == "cloud content"

    def test_mv_cloud_to_cloud(self):
        """Test moving file between cloud locations"""
        src = WORKDIR / "cloud_src.txt"
        dst = WORKDIR / "cloud_dst.txt"
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

    def test_mv_interactive(self):
        """Test interactive move with both responses"""
        src = WORKDIR / "interactive_src.txt"
        dst = WORKDIR / "interactive_dst.txt"
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

    def test_mv_force(self):
        """Test force move with cloud files"""
        src = WORKDIR / "force_src.txt"
        dst = WORKDIR / "force_dst.txt"
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

    def test_mv_no_clobber(self):
        """Test no-clobber option"""
        src = WORKDIR / "noclobber_src.txt"
        dst = WORKDIR / "noclobber_dst.txt"
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

    def test_mv_cloud_to_cloud(self):
        """Test moving file between cloud locations"""
        src = WORKDIR / "cloud_src.txt"
        dst = WORKDIR / "subdir/cloud_dst.txt"
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

    def test_mv_cloud_to_cloud_dir(self):
        """Test moving file to existing cloud directory"""
        src = WORKDIR / "src2.txt"
        dst_dir = WORKDIR / "dst_dir"
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

    def test_mv_local_to_cloud(self, tmp_path):
        """Test moving from local to cloud"""
        src = tmp_path / "local.txt"
        src.write_text("local content")
        dst = WORKDIR / "from_local.txt"

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

    def test_mv_cloud_to_local(self, tmp_path):
        """Test moving from cloud to local"""
        src = WORKDIR / "cloud_src.txt"
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

    def test_mv_interactive(self):
        """Test interactive move"""
        src = WORKDIR / "interactive_src.txt"
        dst = WORKDIR / "interactive_dst.txt"
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

    def test_mv_no_clobber(self):
        """Test no-clobber option"""
        src = WORKDIR / "noclobber_src.txt"
        dst = WORKDIR / "noclobber_dst.txt"
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

    def test_mv_multiple_sources(self):
        """Test moving multiple sources to directory"""
        src1 = WORKDIR / "multi1.txt"
        src2 = WORKDIR / "multi2.txt"
        dst_dir = WORKDIR / "multi_dst"
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

    def test_mv_error_handling(self, capsys):
        """Test error conditions"""
        # Test moving nonexistent file
        args = Namespace(
            u=False,
            SOURCE=[str(WORKDIR / "nonexistent.txt")],
            DEST=str(WORKDIR / "dest.txt"),
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
        src1 = WORKDIR / "err1.txt"
        src2 = WORKDIR / "err2.txt"
        dst = WORKDIR / "err_dst.txt"
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

    def test_mv_update_all(self):
        """Test --update=all option (default without --update)"""
        src = WORKDIR / "src.txt"
        dst = WORKDIR / "dst.txt"
        src.write_text("source")
        dst.write_text("dest")

        # Set timestamps (source older than dest)
        src_blob = src.client.client.bucket(src.bucket).get_blob(src.blob)
        dst_blob = dst.client.client.bucket(dst.bucket).get_blob(dst.blob)
        src_blob.metadata = {"updated": "2020-01-01T00:00:00"}
        dst_blob.metadata = {"updated": "2023-01-01T00:00:00"}
        src_blob.patch()
        dst_blob.patch()

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

    def test_mv_update_none(self):
        """Test --update=none option"""
        src = WORKDIR / "src.txt"
        dst = WORKDIR / "dst.txt"
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

    def test_mv_update_older(self):
        """Test --update=older option (default with --update)"""
        src = WORKDIR / "src.txt"
        dst = WORKDIR / "dst.txt"
        src.write_text("source")
        dst.write_text("dest")

        # Set timestamps
        src_blob = src.client.client.bucket(src.bucket).get_blob(src.blob)
        dst_blob = dst.client.client.bucket(dst.bucket).get_blob(dst.blob)

        # Test with older source (should not move)
        src_blob.metadata = {"updated": "2020-01-01T00:00:00"}
        dst_blob.metadata = {"updated": "2023-01-01T00:00:00"}
        src_blob.patch()
        dst_blob.patch()

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
        assert src.exists()  # Should not move older source
        assert dst.read_text() == "dest"

        # Test with newer source (should move)
        src_blob.metadata = {"updated": "2023-02-01T00:00:00"}
        src_blob.patch()

        run(args)
        assert not src.exists()  # Should move newer source
        assert dst.read_text() == "source"

    def test_mv_update_modes(self):
        """Test different --update modes"""
        # Create test files
        src = WORKDIR / "src.txt"
        dst = WORKDIR / "dst.txt"
        src.write_text("source")
        dst.write_text("dest")

        # Make source older than destination
        src_blob = src.client.client.bucket(src.bucket).get_blob(src.blob)
        dst_blob = dst.client.client.bucket(dst.bucket).get_blob(dst.blob)
        src_blob.metadata = {"updated": "2020-01-01T00:00:00"}
        dst_blob.metadata = {"updated": "2023-01-01T00:00:00"}
        src_blob.patch()
        dst_blob.patch()

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
        src_blob = src.client.client.bucket(src.bucket).get_blob(src.blob)
        src_blob.metadata = {"updated": "2024-01-01T00:00:00"}  # Make source newer
        src_blob.patch()
        args.u = True
        args.update = None
        run(args)
        assert not src.exists()  # Should move because source is newer
        assert dst.read_text() == "new source"

        # Test --update=older explicitly
        src.write_text("newer source")
        dst.write_text("newer dest")
        src_blob = src.client.client.bucket(src.bucket).get_blob(src.blob)
        src_blob.metadata = {"updated": "2020-01-01T00:00:00"}  # Make source older
        src_blob.patch()
        args.u = False
        args.update = "older"
        run(args)
        assert src.exists()  # Should keep source because it's older
        assert dst.read_text() == "newer dest"

    def test_mv_update_default(self):
        """Test default update behavior (all when not specified, older when specified)"""
        src = WORKDIR / "src.txt"
        dst = WORKDIR / "dst.txt"
        src.write_text("source")
        dst.write_text("dest")

        # Make source older than destination
        src_blob = src.client.client.bucket(src.bucket).get_blob(src.blob)
        dst_blob = dst.client.client.bucket(dst.bucket).get_blob(dst.blob)
        src_blob.metadata = {"updated": "2020-01-01T00:00:00"}
        dst_blob.metadata = {"updated": "2023-01-01T00:00:00"}
        src_blob.patch()
        dst_blob.patch()

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
        src_blob = src.client.client.bucket(src.bucket).get_blob(src.blob)
        src_blob.metadata = {"updated": "2020-01-01T00:00:00"}
        src_blob.patch()
        args.update = "older"
        run(args)
        assert src.exists()  # Should not move older file
        assert dst.read_text() == "dest2"
