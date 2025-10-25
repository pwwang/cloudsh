from pathlib import Path
from argparse import Namespace

import pytest

from cloudsh.commands.ls import run


class TestLs:
    """Test ls command functionality"""

    @pytest.fixture
    def test_dir(self, workdir):
        """Create a test directory with various files"""
        path = workdir / "test_dir"
        path.mkdir(exist_ok=True)
        (path / "file1.txt").write_text("content1")
        (path / "file2.txt").write_text("content2" * 1000)  # Larger file
        (path / ".hidden").write_text("hidden")
        (path / "subdir").mkdir(exist_ok=True)
        return str(path)

    @pytest.fixture
    def local_test_dir(self, tmp_path):
        """Create a local test directory with various files"""
        path = tmp_path / "test_dir"
        path.mkdir()
        (path / "file1.txt").write_text("content1")
        (path / "file2.txt").write_text("content2" * 1000)  # Larger file
        (path / ".hidden").write_text("hidden")
        (path / "subdir").mkdir()
        (path / "subdir/subfile.txt").write_text("subcontent")
        return str(path)

    def test_ls_basic(self, test_dir, capsys):
        """Test basic ls functionality"""
        args = Namespace(
            file=[test_dir],
            all=False,
            almost_all=False,
            l=False,
            human_readable=False,
            si=False,
            recursive=False,
            reverse=False,
            S=False,
            t=False,
            one=False,
        )
        run(args)
        out = capsys.readouterr().out
        assert "file1.txt" in out
        assert "file2.txt" in out
        assert ".hidden" not in out
        assert "subdir" in out

    def test_ls_all(self, test_dir, capsys):
        """Test ls -a"""
        args = Namespace(
            file=[test_dir],
            all=True,
            almost_all=False,
            l=False,
            human_readable=False,
            si=False,
            recursive=False,
            reverse=False,
            S=False,
            t=False,
            one=False,
        )
        run(args)
        out = capsys.readouterr().out
        assert ".hidden" in out

    def test_ls_long(self, test_dir, capsys):
        """Test ls -l"""
        args = Namespace(
            file=[test_dir],
            all=False,
            almost_all=False,
            l=True,
            human_readable=False,
            si=False,
            recursive=False,
            reverse=False,
            S=False,
            t=False,
            one=False,
        )
        run(args)
        out = capsys.readouterr().out
        assert "file1.txt" in out
        # Check for typical ls -l format elements
        lines = out.strip().split("\n")
        for line in lines:
            if "file1.txt" in line:
                # Should have mode, links, owner, group, size, date, name
                assert len(line.split()) >= 7

    def test_ls_recursive(self, test_dir, capsys):
        """Test ls -R"""
        args = Namespace(
            file=[test_dir],
            all=False,
            almost_all=False,
            l=False,
            human_readable=False,
            si=False,
            recursive=True,
            reverse=False,
            S=False,
            t=False,
            one=False,
        )
        run(args)
        out = capsys.readouterr().out

        assert "subdir" in out
        assert "test_dir/subdir:" in out

    def test_ls_sort_size(self, test_dir, capsys):
        """Test ls -S"""
        args = Namespace(
            file=[test_dir],
            all=False,
            almost_all=False,
            l=True,
            human_readable=False,
            si=False,
            recursive=False,
            reverse=False,
            S=True,
            t=False,
            one=False,
        )
        run(args)
        out = capsys.readouterr().out
        lines = out.strip().split("\n")
        # file2.txt should come before file1.txt (larger)
        file1_idx = next(i for i, line in enumerate(lines) if "file1.txt" in line)
        file2_idx = next(i for i, line in enumerate(lines) if "file2.txt" in line)
        assert file2_idx < file1_idx

    def test_ls_human_readable(self, test_dir, capsys):
        """Test ls -lh"""
        args = Namespace(
            file=[test_dir],
            all=False,
            almost_all=False,
            l=True,
            human_readable=True,
            si=False,
            recursive=False,
            reverse=False,
            S=False,
            t=False,
            one=False,
        )
        run(args)
        out = capsys.readouterr().out
        assert "K" in out or "B" in out  # Should show sizes in human-readable format

    def test_ls_local_basic(self, local_test_dir, capsys):
        """Test basic ls functionality with local files"""
        args = Namespace(
            file=[local_test_dir],
            all=False,
            almost_all=False,
            l=False,
            human_readable=False,
            si=False,
            recursive=False,
            reverse=False,
            S=False,
            t=False,
            one=False,
        )
        run(args)
        out = capsys.readouterr().out
        assert "file1.txt" in out
        assert "file2.txt" in out
        assert ".hidden" not in out
        assert "subdir" in out

    def test_ls_local_long(self, local_test_dir, capsys):
        """Test ls -l with local files"""
        args = Namespace(
            file=[local_test_dir],
            all=False,
            almost_all=False,
            l=True,
            human_readable=False,
            si=False,
            recursive=False,
            reverse=False,
            S=False,
            t=False,
            one=False,
        )
        run(args)
        out = capsys.readouterr().out
        assert "file1.txt" in out
        lines = out.strip().split("\n")
        for line in lines:
            if "file1.txt" in line:
                # Verify local file permissions and ownership
                assert line.startswith("-rw")  # Regular file with rw permissions
                parts = line.split()
                assert len(parts) >= 7  # Full ls -l format

    def test_ls_local_recursive(self, local_test_dir, capsys):
        """Test ls -R with local files"""
        args = Namespace(
            file=[local_test_dir],
            all=False,
            almost_all=False,
            l=False,
            human_readable=False,
            si=False,
            recursive=True,
            reverse=False,
            S=False,
            t=False,
            one=False,
        )
        run(args)
        out = capsys.readouterr().out
        assert "subdir" in out
        assert "subfile.txt" in out
        assert "test_dir/subdir:" in out

    def test_ls_local_multiple(self, local_test_dir, capsys):
        """Test ls with multiple local files/directories"""
        file1 = Path(local_test_dir) / "file1.txt"
        file2 = Path(local_test_dir) / "file2.txt"
        args = Namespace(
            file=[str(file1), str(file2)],
            all=False,
            almost_all=False,
            l=True,
            human_readable=False,
            si=False,
            recursive=False,
            reverse=False,
            S=False,
            t=False,
            one=False,
        )
        run(args)
        out = capsys.readouterr().out
        assert str(file1) in out
        assert str(file2) in out
        assert "content1" not in out  # Should not show file contents

    def test_ls_local_sort_size(self, local_test_dir, capsys):
        """Test ls -S with local files"""
        args = Namespace(
            file=[local_test_dir],
            all=False,
            almost_all=False,
            l=True,
            human_readable=False,
            si=False,
            recursive=False,
            reverse=False,
            S=True,
            t=False,
            one=False,
        )
        run(args)
        out = capsys.readouterr().out
        lines = out.strip().split("\n")
        # file2.txt (larger) should come before file1.txt
        file1_idx = next(i for i, line in enumerate(lines) if "file1.txt" in line)
        file2_idx = next(i for i, line in enumerate(lines) if "file2.txt" in line)
        assert file2_idx < file1_idx

    def test_ls_local_nonexistent(self, tmp_path, capsys):
        """Test ls with nonexistent local path"""
        nonexistent = str(tmp_path / "nonexistent")
        args = Namespace(
            file=[nonexistent],
            all=False,
            almost_all=False,
            l=False,
            human_readable=False,
            si=False,
            recursive=False,
            reverse=False,
            S=False,
            t=False,
            one=False,
        )
        with pytest.raises(SystemExit):
            run(args)
        err = capsys.readouterr().err
        assert "cannot access" in err

    def test_ls_local_file_permissions(self, local_test_dir, capsys):
        """Test ls -l shows correct permissions for local files"""
        test_file = Path(local_test_dir) / "test_perms.txt"
        test_file.write_text("test")
        test_file.chmod(0o644)  # Set specific permissions

        args = Namespace(
            file=[str(test_file)],
            all=False,
            almost_all=False,
            l=True,
            human_readable=False,
            si=False,
            recursive=False,
            reverse=False,
            S=False,
            t=False,
            one=False,
        )
        run(args)
        out = capsys.readouterr().out
        # Should show -rw-r--r-- permissions
        assert "-rw-r--r--" in out
