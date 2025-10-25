import io
from argparse import Namespace
from pathlib import Path

import pytest

from cloudsh.commands.rm import run


class TestRm:
    """Test rm command functionality"""

    @pytest.fixture
    def cloud_file(self, workdir):
        """Create a test file in cloud storage"""
        path = workdir / "test.txt"
        path.write_text("test content")
        return str(path)

    @pytest.fixture
    def cloud_dir(self, workdir):
        """Create a test directory with files in cloud storage"""
        path = workdir / "testdir"
        path.mkdir(exist_ok=True)
        (path / "file1.txt").write_text("content1")
        (path / "file2.txt").write_text("content2")
        (path / "subdir").mkdir(exist_ok=True)
        (path / "subdir/file3.txt").write_text("content3")
        return str(path)

    @pytest.fixture(autouse=True)
    def setup_input(self, monkeypatch):
        """Set up input mocking for interactive prompts"""
        self.input_response = "y"

        def mock_input(prompt):
            print(prompt, end="")  # Show prompt in test output
            return self.input_response

        monkeypatch.setattr("builtins.input", mock_input)

    def test_rm_single_file(self, cloud_file, capsys):
        """Test removing a single file"""
        args = Namespace(
            file=[cloud_file],
            force=False,
            recursive=False,
            dir=False,
            verbose=True,
            i=False,
            I=False,
        )
        run(args)
        assert not Path(cloud_file).exists()
        assert "removed " in capsys.readouterr().out

    def test_rm_missing_file(self, workdir, capsys):
        """Test removing a nonexistent file"""
        path = workdir / "nonexistent.txt"
        args = Namespace(
            file=[str(path)],
            force=False,
            recursive=False,
            dir=False,
            verbose=False,
            i=False,
            I=False,
        )
        with pytest.raises(SystemExit):
            run(args)

        captured = capsys.readouterr()
        assert "No such file or directory" in captured.err

    def test_rm_force_missing(self, workdir, capsys):
        """Test force removing a nonexistent file"""
        path = workdir / "nonexistent.txt"
        args = Namespace(
            file=[str(path)],
            force=True,
            recursive=False,
            dir=False,
            verbose=False,
            i=False,
            I=False,
        )
        run(args)
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_rm_directory_error(self, cloud_dir, capsys):
        """Test removing directory without -r"""
        args = Namespace(
            file=[cloud_dir],
            force=False,
            recursive=False,
            dir=False,
            verbose=False,
            i=False,
            I=False,
        )
        with pytest.raises(SystemExit):
            run(args)

        captured = capsys.readouterr()
        assert "Is a directory" in captured.err
        assert Path(cloud_dir).exists()

    def test_rm_recursive(self, cloud_dir, capsys):
        """Test recursive directory removal"""
        args = Namespace(
            file=[cloud_dir],
            force=False,
            recursive=True,
            dir=False,
            verbose=True,
            i=False,
            I=False,
        )
        self.input_response = "y"  # Auto-confirm for -I prompt
        run(args)
        assert not Path(cloud_dir).exists()
        assert "removed " in capsys.readouterr().out

    def test_rm_verbose(self, cloud_file, capsys):
        """Test verbose output"""
        args = Namespace(
            file=[cloud_file],
            force=False,
            recursive=False,
            dir=False,
            verbose=True,
            i=False,
            I=False,
        )
        run(args)
        captured = capsys.readouterr()
        assert f"removed '{cloud_file}'" in captured.out

    def test_rm_prompt_yes(self, cloud_file):
        """Test interactive prompt with 'yes' response"""
        self.input_response = "y"
        args = Namespace(
            file=[cloud_file],
            force=False,
            recursive=False,
            dir=False,
            verbose=False,
            i=True,
            I=False,
        )
        run(args)
        assert not Path(cloud_file).exists()

    def test_rm_prompt_no(self, cloud_file):
        """Test interactive prompt with 'no' response"""
        self.input_response = "n"
        args = Namespace(
            file=[cloud_file],
            force=False,
            recursive=False,
            dir=False,
            verbose=False,
            i=True,
            I=False,
        )
        run(args)
        assert Path(cloud_file).exists()

    def test_rm_I_prompt(self, workdir, monkeypatch):
        """Test -I prompt for multiple files"""
        files = [workdir / f"file{i}.txt" for i in range(4)]
        for f in files:
            f.write_text("content")

        monkeypatch.setattr("sys.stdin", io.StringIO("y\n"))
        args = Namespace(
            file=[str(f) for f in files],
            force=False,
            recursive=False,
            dir=False,
            verbose=False,
            i=False,
            I=True,
        )
        run(args)
        assert all(not f.exists() for f in files)

    def test_rm_empty_dir(self, workdir, capsys):
        """Test removing empty directory with -d"""
        empty_dir = workdir / "empty_dir"
        empty_dir.mkdir()

        args = Namespace(
            file=[str(empty_dir)],
            force=False,
            recursive=False,
            dir=True,
            verbose=True,
            i=False,
            I=False,
        )
        run(args)
        assert not empty_dir.exists()
        assert "removed " in capsys.readouterr().out

    def test_rm_nonempty_dir_with_d(self, cloud_dir, capsys):
        """Test -d on non-empty directory"""
        args = Namespace(
            file=[cloud_dir],
            force=False,
            recursive=False,
            dir=True,
            verbose=False,
            i=False,
            I=False,
        )
        with pytest.raises(SystemExit):
            run(args)

        captured = capsys.readouterr()
        assert (
            "Directory not empty" in captured.err
            or "not empty" in captured.err.lower()
        )
        assert Path(cloud_dir).exists()

    def test_rm_force_dir(self, cloud_dir):
        """Test force remove directory with -r"""
        args = Namespace(
            file=[cloud_dir],
            force=True,
            recursive=True,
            dir=False,
            verbose=False,
            i=False,
            I=False,
        )
        run(args)
        assert not Path(cloud_dir).exists()

    def test_rm_local_file(self, tmp_path, capsys):
        """Test removing local file"""
        path = tmp_path.joinpath("test.txt")
        path.write_text("test content")
        args = Namespace(
            file=[str(path)],
            force=False,
            recursive=False,
            dir=False,
            verbose=True,
            i=False,
            I=False,
        )
        run(args)
        assert not path.exists()
        assert "removed " in capsys.readouterr().out

    def test_rm_local_dir(self, tmp_path, capsys):
        """Test removing local directory"""
        path = tmp_path.joinpath("testdir")
        path.mkdir()
        (path / "file1.txt").write_text("content1")
        (path / "file2.txt").write_text("content2")
        (path / "subdir").mkdir()
        (path / "subdir/file3.txt").write_text("content3")

        args = Namespace(
            file=[str(path)],
            force=False,
            recursive=True,
            dir=False,
            verbose=True,
            i=False,
            I=False,
        )
        run(args)
        assert not path.exists()
        assert "removed" in capsys.readouterr().out

    def test_rm_local_dir_error(self, tmp_path, capsys):
        """Test removing local directory"""
        path = tmp_path.joinpath("testdir")
        path.mkdir()
        (path / "file1.txt").write_text("content1")

        args = Namespace(
            file=[str(path)],
            force=False,
            recursive=False,
            dir=False,
            verbose=True,
            i=False,
            I=False,
        )
        with pytest.raises(SystemExit):
            run(args)

        assert "cannot remove" in capsys.readouterr().err

    def test_rm_local_empty_dir(self, tmp_path, capsys):
        """Test removing empty local directory"""
        empty_dir = tmp_path.joinpath("empty_dir")
        empty_dir.mkdir()

        args = Namespace(
            file=[str(empty_dir)],
            force=False,
            recursive=False,
            dir=True,
            verbose=True,
            i=False,
            I=False,
        )
        run(args)
        assert not empty_dir.exists()
        assert "removed" in capsys.readouterr().out
