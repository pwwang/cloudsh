import pytest
from argparse import Namespace
from pathlib import Path

from cloudsh.commands.cp import run


class TestCp:
    """Test cp command functionality"""

    @pytest.fixture
    def source_file(self, workdir):
        """Create a source test file"""
        path = workdir / "source.txt"
        path.write_text("test content")
        return str(path)

    @pytest.fixture
    def source_dir(self, workdir):
        """Create a source test directory with files"""
        path = workdir / "source_dir"
        path.mkdir(exist_ok=True)
        (path / "file1.txt").write_text("content1")
        (path / "file2.txt").write_text("content2")
        (path / "subdir").mkdir(exist_ok=True)
        (path / "subdir/file3.txt").write_text("content3")
        return str(path)

    @pytest.fixture
    def local_source_dir(self, tmp_path):
        """Create a local source directory with files"""
        path = tmp_path / "local_source_dir"
        path.mkdir(exist_ok=True)
        (path / "file1.txt").write_text("local1")
        (path / "file2.txt").write_text("local2")
        (path / "subdir").mkdir()
        (path / "subdir" / "file3.txt").write_text("local3")
        return str(path)

    @pytest.fixture
    def cloud_source_dir(self, workdir):
        """Create a cloud source directory with files"""
        path = workdir / "cloud_source_dir"
        path.mkdir(exist_ok=True)
        (path / "file1.txt").write_text("cloud1")
        (path / "file2.txt").write_text("cloud2")
        (path / "subdir").mkdir()
        (path / "subdir" / "file3.txt").write_text("cloud3")
        return str(path)

    @pytest.fixture(autouse=True)
    def setup_input(self, monkeypatch):
        """Set up input mocking for interactive prompts"""
        self.input_response = "y"

        def mock_input(prompt):
            print(prompt, end="")  # Show prompt in test output
            return self.input_response

        monkeypatch.setattr("builtins.input", mock_input)

    def test_cp_single_file(self, source_file, workdir, capsys):
        """Test copying a single file"""
        dest = str(workdir / "dest.txt")
        args = Namespace(
            SOURCE=[source_file],
            DEST=dest,
            recursive=False,
            interactive=False,
            force=False,
            no_clobber=False,
            verbose=True,
            preserve=False,
            target_directory=None,
            no_target_directory=False,
            parents=False,
        )
        run(args)
        dest_path = Path(dest)
        assert dest_path.exists()
        assert dest_path.read_text() == "test content"
        assert "-> '" in capsys.readouterr().out

    def test_cp_to_directory(self, source_file, workdir):
        """Test copying file to directory"""
        dest_dir = workdir / "dest_dir"
        dest_dir.mkdir()
        args = Namespace(
            SOURCE=[source_file],
            DEST=str(dest_dir),
            recursive=False,
            interactive=False,
            force=False,
            no_clobber=False,
            verbose=False,
            preserve=False,
            target_directory=None,
            no_target_directory=False,
            parents=False,
        )
        run(args)
        copied_file = dest_dir / "source.txt"
        assert copied_file.exists()
        assert copied_file.read_text() == "test content"

    def test_cp_recursive(self, source_dir, workdir):
        """Test recursive directory copying"""
        dest_dir = workdir / "dest_dir_recursive"
        args = Namespace(
            SOURCE=[source_dir],
            DEST=str(dest_dir),
            recursive=True,
            interactive=False,
            force=False,
            no_clobber=False,
            verbose=True,
            preserve=False,
            target_directory=None,
            no_target_directory=False,
            parents=False,
        )
        run(args)
        assert (dest_dir / "file1.txt").exists()
        assert (dest_dir / "file2.txt").exists()
        assert (dest_dir / "subdir/file3.txt").exists()

    def test_cp_interactive_yes(self, source_file, workdir):
        """Test interactive copying with 'yes' response"""
        dest = workdir / "interactive.txt"
        dest.write_text("original content")
        self.input_response = "y"
        args = Namespace(
            SOURCE=[source_file],
            DEST=str(dest),
            recursive=False,
            interactive=True,
            force=False,
            no_clobber=False,
            verbose=False,
            preserve=False,
            target_directory=None,
            no_target_directory=False,
            parents=False,
        )
        run(args)
        assert dest.read_text() == "test content"

    def test_cp_interactive_no(self, source_file, workdir):
        """Test interactive copying with 'no' response"""
        dest = workdir / "interactive_no.txt"
        dest.write_text("original content")
        self.input_response = "n"
        args = Namespace(
            SOURCE=[source_file],
            DEST=str(dest),
            recursive=False,
            interactive=True,
            force=False,
            no_clobber=False,
            verbose=False,
            preserve=False,
            target_directory=None,
            no_target_directory=False,
            parents=False,
        )
        run(args)
        assert dest.read_text() == "original content"

    def test_cp_no_clobber(self, source_file, workdir):
        """Test no-clobber option"""
        dest = workdir / "noclobber.txt"
        dest.write_text("original content")
        args = Namespace(
            SOURCE=[source_file],
            DEST=str(dest),
            recursive=False,
            interactive=False,
            force=False,
            no_clobber=True,
            verbose=False,
            preserve=False,
            target_directory=None,
            no_target_directory=False,
            parents=False,
        )
        run(args)
        assert dest.read_text() == "original content"

    def test_cp_preserve(self, source_file, workdir):
        """Test preserving file attributes"""
        dest = str(workdir / "preserved.txt")
        args = Namespace(
            SOURCE=[source_file],
            DEST=dest,
            recursive=False,
            interactive=False,
            force=False,
            no_clobber=False,
            verbose=False,
            preserve=True,
            target_directory=None,
            no_target_directory=False,
            parents=False,
        )
        run(args)
        src_path = Path(source_file)
        dst_path = Path(dest)
        assert src_path.stat().st_mode == dst_path.stat().st_mode

    def test_cp_target_directory(self, source_file, workdir):
        """Test using target-directory option"""
        target_dir = str(workdir / "target_dir")
        args = Namespace(
            SOURCE=[source_file],
            DEST="unused",  # Should be ignored
            recursive=False,
            interactive=False,
            force=False,
            no_clobber=False,
            verbose=True,
            preserve=False,
            target_directory=target_dir,
            no_target_directory=False,
            parents=False,
        )
        run(args)
        copied_file = Path(target_dir) / "source.txt"
        assert copied_file.exists()
        assert copied_file.read_text() == "test content"

    def test_cp_error_handling(self, source_dir, workdir, capsys):
        """Test error handling for various scenarios"""
        # Test copying to existing directory without -r
        dest_dir = workdir / "existing_file"
        dest_dir.touch()
        args = Namespace(
            SOURCE=[source_dir],
            DEST=str(dest_dir),
            recursive=True,
            interactive=False,
            force=False,
            no_clobber=False,
            verbose=False,
            preserve=False,
            target_directory=None,
            no_target_directory=True,  # Treat dest as file
            parents=False,
        )
        with pytest.raises(SystemExit):
            run(args)
        assert "cannot copy" in capsys.readouterr().err

    def test_cp_multiple_sources(self, source_file, source_dir, workdir, capsys):
        """Test copying multiple sources to directory"""
        dest_dir = workdir / "multi_dest"
        dest_dir.mkdir()
        args = Namespace(
            SOURCE=[source_file, source_dir],
            DEST=str(dest_dir),
            recursive=True,
            interactive=False,
            force=False,
            no_clobber=False,
            verbose=True,
            preserve=False,
            target_directory=None,
            no_target_directory=False,
            parents=False,
        )
        run(args)
        dest_path = Path(dest_dir)
        assert (dest_path / "source.txt").exists()
        assert (dest_path / "source_dir").is_dir()
        assert (dest_path / "source_dir/file1.txt").exists()

    def test_cp_local_to_local(self, local_source_dir, tmp_path):
        """Test copying from local to local"""
        dest = tmp_path / "local_dest"
        args = Namespace(
            SOURCE=[local_source_dir],
            DEST=str(dest),
            recursive=True,
            interactive=False,
            force=False,
            no_clobber=False,
            verbose=True,
            preserve=False,
            target_directory=None,
            no_target_directory=False,
            parents=False,
        )
        run(args)
        assert (dest / "file1.txt").exists()
        assert (dest / "file2.txt").exists()
        assert (dest / "subdir" / "file3.txt").exists()
        assert (dest / "file1.txt").read_text() == "local1"

    def test_cp_local_to_cloud(self, local_source_dir, workdir):
        """Test copying from local to cloud"""
        dest = workdir / "cloud_dest_from_local"
        args = Namespace(
            SOURCE=[local_source_dir],
            DEST=str(dest),
            recursive=True,
            interactive=False,
            force=False,
            no_clobber=False,
            verbose=True,
            preserve=False,
            target_directory=None,
            no_target_directory=False,
            parents=False,
        )
        run(args)
        assert (dest / "file1.txt").exists()
        assert (dest / "file2.txt").exists()
        assert (dest / "subdir" / "file3.txt").exists()
        assert (dest / "file1.txt").read_text() == "local1"

    def test_cp_cloud_to_local(self, cloud_source_dir, tmp_path):
        """Test copying from cloud to local"""
        dest = tmp_path / "local_dest_from_cloud"
        args = Namespace(
            SOURCE=[cloud_source_dir],
            DEST=str(dest),
            recursive=True,
            interactive=False,
            force=False,
            no_clobber=False,
            verbose=True,
            preserve=False,
            target_directory=None,
            no_target_directory=False,
            parents=False,
        )
        run(args)
        assert (dest / "file1.txt").exists()
        assert (dest / "file2.txt").exists()
        assert (dest / "subdir" / "file3.txt").exists()
        assert (dest / "file1.txt").read_text() == "cloud1"

    def test_cp_single_file_local_to_cloud(self, tmp_path, workdir):
        """Test copying single file from local to cloud"""
        local_file = tmp_path / "local.txt"
        local_file.write_text("local content")
        cloud_dest = workdir / "cloud_file.txt"

        args = Namespace(
            SOURCE=[str(local_file)],
            DEST=str(cloud_dest),
            recursive=False,
            interactive=False,
            force=False,
            no_clobber=False,
            verbose=True,
            preserve=False,
            target_directory=None,
            no_target_directory=False,
            parents=False,
        )
        run(args)
        assert cloud_dest.exists()
        assert cloud_dest.read_text() == "local content"

    def test_cp_single_file_cloud_to_local(self, tmp_path, workdir):
        """Test copying single file from cloud to local"""
        cloud_file = workdir / "cloud_source.txt"
        cloud_file.write_text("cloud content")
        local_dest = tmp_path / "local_dest.txt"

        args = Namespace(
            SOURCE=[str(cloud_file)],
            DEST=str(local_dest),
            recursive=False,
            interactive=False,
            force=False,
            no_clobber=False,
            verbose=True,
            preserve=False,
            target_directory=None,
            no_target_directory=False,
            parents=False,
        )
        run(args)
        assert local_dest.exists()
        assert local_dest.read_text() == "cloud content"
