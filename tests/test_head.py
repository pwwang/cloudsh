from argparse import Namespace
from uuid import uuid4
import subprocess

import pytest
from yunpath import AnyPath

from cloudsh.commands.head import run
from cloudsh.utils import PACKAGE

from .conftest import BUCKET

WORKDIR = AnyPath(f"{BUCKET}/cloudsh_test")
WORKDIR = WORKDIR / str(uuid4())


def teardown_module():
    WORKDIR.rmtree()


@pytest.fixture
def temp_file(tmp_path):
    content = b"line1\nline2\nline3\nline4\nline5\n"
    file = tmp_path / "test.txt"
    file.write_bytes(content)
    return str(file)


@pytest.fixture
def temp_file_no_newline(tmp_path):
    content = b"line1\nline2\nline3\nline4\nline5"
    file = tmp_path / "test_no_newline.txt"
    file.write_bytes(content)
    return str(file)


@pytest.fixture
def zero_term_file(tmp_path):
    content = b"line1\0line2\0line3\0line4\0line5\0"
    file = tmp_path / "test_zero.txt"
    file.write_bytes(content)
    return str(file)


@pytest.fixture
def temp_file_empty_lines(tmp_path):
    content = b"line1\n\nline3\nline4\nline5\n"
    file = tmp_path / "test_empty.txt"
    file.write_bytes(content)
    return str(file)


@pytest.fixture
def cloud_file():
    """Create a test file in cloud storage"""
    content = b"cloud1\ncloud2\ncloud3\ncloud4\ncloud5\n"
    path = WORKDIR / "test.txt"
    path.write_bytes(content)
    return str(path)


@pytest.fixture
def cloud_file_no_newline():
    """Create a test file without trailing newline in cloud storage"""
    content = b"cloud1\ncloud2\ncloud3\ncloud4\ncloud5"
    path = WORKDIR / "test_no_newline.txt"
    path.write_bytes(content)
    return str(path)


@pytest.fixture
def cloud_zero_term_file():
    """Create a zero-terminated test file in cloud storage"""
    content = b"cloud1\0cloud2\0cloud3\0cloud4\0cloud5\0"
    path = WORKDIR / "test_zero.txt"
    path.write_bytes(content)
    return str(path)


@pytest.fixture
def cloud_file_empty_lines():
    """Create a test file with empty lines in cloud storage"""
    content = b"cloud1\n\ncloud3\ncloud4\ncloud5\n"
    path = WORKDIR / "test_empty.txt"
    path.write_bytes(content)
    return str(path)


def test_head_cloud_files(cloud_file, cloud_file_no_newline, capsys):
    """Test various cloud file operations in one test"""
    # Test default behavior
    args = Namespace(
        file=[cloud_file],
        bytes=None,
        lines=None,
        quiet=False,
        verbose=False,
        zero_terminated=False,
    )
    run(args)
    captured = capsys.readouterr()
    assert captured.out == "cloud1\ncloud2\ncloud3\ncloud4\ncloud5\n"

    # Test with explicit line count
    args.lines = "2"
    run(args)
    captured = capsys.readouterr()
    assert captured.out == "cloud1\ncloud2\n"

    args.lines = "-2"
    run(args)
    captured = capsys.readouterr()
    assert captured.out == "cloud1\ncloud2\ncloud3\n"

    # Test with byte count
    args.bytes = "10"
    args.lines = None
    run(args)
    captured = capsys.readouterr()
    assert captured.out == "cloud1\nclo"


def test_head_special_cases(capsys):
    """Test various special cases in one test"""
    # Test empty file
    empty = WORKDIR / "empty.txt"
    empty.write_bytes(b"")

    # Test file with trailing empty lines
    with_empties = WORKDIR / "with_empties.txt"
    with_empties.write_bytes(b"line1\nline2\n\n\n")

    # Test both files
    args = Namespace(
        file=[str(empty), str(with_empties)],
        bytes=None,
        lines="4",
        quiet=False,
        verbose=True,
        zero_terminated=False,
    )
    run(args)
    captured = capsys.readouterr()
    assert f"==> {empty} <==" in captured.out
    assert f"==> {with_empties} <==" in captured.out
    assert "line1\nline2\n\n\n" in captured.out


def test_head_zero_terminated(zero_term_file, capsys):
    args = Namespace(
        file=[zero_term_file],
        bytes=None,
        lines="2",
        quiet=False,
        verbose=False,
        zero_terminated=True,
    )
    run(args)
    captured = capsys.readouterr()
    assert captured.out == "line1\0line2\0"


def test_head_cloud_chunk_remainder(capsys):
    """Test handling of partial chunks and remaining data"""
    # Create content that's larger than chunk size (8192)
    # and has incomplete line at chunk boundary
    content = b"x" * 8190 + b"ab\ncd\n"  # 8190 + 4 = 8194 bytes
    path = WORKDIR / "test_chunk.txt"
    path.write_bytes(content)

    args = Namespace(
        file=[str(path)],
        bytes=None,
        lines="2",
        quiet=False,
        verbose=False,
        zero_terminated=False,
    )
    run(args)
    captured = capsys.readouterr()
    assert captured.out.endswith("ab\ncd\n")


def test_head_negative_bytes_seek(capsys):
    """Test that negative bytes properly uses seek operations"""
    content = b"0123456789"  # 10 bytes
    path = WORKDIR / "test_seek.txt"
    path.write_bytes(content)

    args = Namespace(
        file=[str(path)],
        bytes="-5",  # last 5 bytes
        lines=None,
        quiet=False,
        verbose=False,
        zero_terminated=False,
    )
    run(args)
    captured = capsys.readouterr()
    assert captured.out == "56789"  # Should be exactly the last 5 bytes


def test_head_cloud_error(capsys):
    """Test error handling for cloud files"""
    # Try to access a non-existent cloud path
    nonexistent = WORKDIR / "nonexistent" / "test.txt"
    args = Namespace(
        file=[str(nonexistent)],
        bytes=None,
        lines=None,
        quiet=False,
        verbose=False,
        zero_terminated=False,
    )
    with pytest.raises(SystemExit):
        run(args)
    captured = capsys.readouterr()
    assert f"{PACKAGE}:" in captured.err


def test_head_command_error(capsys, monkeypatch):
    def mock_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0], returncode=1, stdout="", stderr="some error"
        )

    monkeypatch.setattr(subprocess, "run", mock_run)
    args = Namespace(
        file=["-"],
        bytes=None,
        lines="2",
        quiet=False,
        verbose=False,
        zero_terminated=False,
    )
    with pytest.raises(SystemExit):
        run(args)
    captured = capsys.readouterr()
    assert "some error" in captured.err


def test_head_invalid_suffix(temp_file, capsys):
    args = Namespace(
        file=[temp_file],
        bytes="1X",  # Invalid suffix
        lines=None,
        quiet=False,
        verbose=False,
        zero_terminated=False,
    )
    with pytest.raises(SystemExit):
        run(args)

    captured = capsys.readouterr()
    assert "invalid number of bytes" in captured.err

    args = Namespace(
        file=[temp_file],
        bytes=None,
        lines="1X",
        quiet=False,
        verbose=False,
        zero_terminated=False,
    )
    with pytest.raises(SystemExit):
        run(args)

    captured = capsys.readouterr()
    assert "invalid number of lines" in captured.err


def test_head_stdin(capsys, monkeypatch):
    # stdin_data = b"stdin1\nstdin2\nstdin3\n"

    def mock_run(*args, **kwargs):
        # Simulate what GNU head would do with this input
        return subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout="stdin1\nstdin2\n", stderr=""
        )

    monkeypatch.setattr(subprocess, "run", mock_run)
    args = Namespace(
        file=["-"],
        bytes=None,
        lines="2",
        quiet=False,
        verbose=False,
        zero_terminated=False,
    )
    run(args)
    captured = capsys.readouterr()
    assert captured.out == "stdin1\nstdin2\n"

    args = Namespace(
        file=[],
        bytes=None,
        lines="2",
        quiet=False,
        verbose=False,
        zero_terminated=False,
    )
    run(args)
    captured = capsys.readouterr()
    assert captured.out == "stdin1\nstdin2\n"


def test_head_multiple_stdin(capsys, monkeypatch):
    def mock_run(*args, **kwargs):
        # Simulate what GNU head would do with this input
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="==> standard input <==\nstdin1\nstdin2\n",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", mock_run)
    args = Namespace(
        file=["-", "-"],
        bytes=None,
        lines="2",
        quiet=False,
        verbose=False,
        zero_terminated=False,
    )
    run(args)
    captured = capsys.readouterr()
    assert "==> standard input <==" in captured.out
    assert "stdin1\nstdin2\n" in captured.out


def test_head_bytes_with_suffix(temp_file, capsys):
    args = Namespace(
        file=[temp_file],
        bytes="1K",  # 1024 bytes
        lines=None,
        quiet=False,
        verbose=False,
        zero_terminated=False,
    )
    run(args)
    captured = capsys.readouterr()
    # 1K bytes of content
    assert len(captured.out.encode()) <= 1024


def test_verbose_mode(temp_file, capsys):
    args = Namespace(
        file=[temp_file],
        bytes=None,
        lines="2",
        quiet=False,
        verbose=True,
        zero_terminated=False,
    )
    run(args)
    captured = capsys.readouterr()
    assert f"==> {temp_file} <==" in captured.out
    assert "line1\nline2\n" in captured.out


def test_quiet_mode(temp_file, temp_file_no_newline, capsys):
    args = Namespace(
        file=[temp_file, temp_file_no_newline],
        bytes=None,
        lines="2",
        quiet=True,
        verbose=False,
        zero_terminated=False,
    )
    run(args)
    captured = capsys.readouterr()
    assert "==>" not in captured.out


def test_head_bytes_with_decimal_suffix(temp_file, capsys):
    args = Namespace(
        file=[temp_file],
        bytes="1.5K",  # 1536 bytes
        lines=None,
        quiet=False,
        verbose=False,
        zero_terminated=False,
    )
    run(args)
    captured = capsys.readouterr()
    assert len(captured.out.encode()) <= 1536


def test_head_negative_bytes_tiny_file(capsys):
    """Test negative bytes with a file smaller than requested size"""
    content = b"123"  # 3 bytes
    path = WORKDIR / "test_tiny.txt"
    path.write_bytes(content)

    args = Namespace(
        file=[str(path)],
        bytes="-5",  # More than file size
        lines=None,
        quiet=False,
        verbose=False,
        zero_terminated=False,
    )
    run(args)
    captured = capsys.readouterr()
    assert captured.out == "123"  # Should get entire file


def test_head_cloud_empty_final_lines(capsys):
    """Test handling of empty lines at the end of file"""
    content = b"line1\nline2\n\n\n"
    path = WORKDIR / "test_empty_final.txt"
    path.write_bytes(content)

    args = Namespace(
        file=[str(path)],
        bytes=None,
        lines=None,
        quiet=False,
        verbose=False,
        zero_terminated=False,
    )
    run(args)
    captured = capsys.readouterr()
    assert captured.out == "line1\nline2\n\n\n"


def test_head_multiple_cloud_files_with_headers(capsys):
    """Test header handling with multiple cloud files"""
    path1 = WORKDIR / "test1.txt"
    path2 = WORKDIR / "test2.txt"
    path1.write_bytes(b"file1\n")
    path2.write_bytes(b"file2\n")

    args = Namespace(
        file=[str(path1), str(path2)],
        bytes=None,
        lines="1",
        quiet=False,
        verbose=True,  # Force headers
        zero_terminated=False,
    )
    run(args)
    captured = capsys.readouterr()
    assert f"==> {path1} <==" in captured.out
    assert f"==> {path2} <==" in captured.out
    assert "file1\n" in captured.out
    assert "file2\n" in captured.out
