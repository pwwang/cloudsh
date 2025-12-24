from argparse import Namespace
import subprocess

import pytest

from cloudsh.commands.head import run
from cloudsh.utils import PACKAGE


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
def local_file(workdir):
    """Create a test file in local workdir"""
    content = b"cloud1\ncloud2\ncloud3\ncloud4\ncloud5\n"
    path = workdir / "test.txt"
    path.write_bytes(content)
    return str(path)


@pytest.fixture
def local_file_no_newline(workdir):
    """Create a test file without trailing newline in local workdir"""
    content = b"cloud1\ncloud2\ncloud3\ncloud4\ncloud5"
    path = workdir / "test_no_newline.txt"
    path.write_bytes(content)
    return str(path)


@pytest.fixture
def local_zero_term_file(workdir):
    """Create a zero-terminated test file in local workdir"""
    content = b"cloud1\0cloud2\0cloud3\0cloud4\0cloud5\0"
    path = workdir / "test_zero.txt"
    path.write_bytes(content)
    return str(path)


@pytest.fixture
def local_file_empty_lines(workdir):
    """Create a test file with empty lines in local workdir"""
    content = b"cloud1\n\ncloud3\ncloud4\ncloud5\n"
    path = workdir / "test_empty.txt"
    path.write_bytes(content)
    return str(path)


async def test_head_local_files(local_file, local_file_no_newline, capsys):
    """Test various local file operations in one test"""
    # Test default behavior
    args = Namespace(
        file=[local_file],
        bytes=None,
        lines=None,
        quiet=False,
        verbose=False,
        zero_terminated=False,
    )
    await run(args)
    captured = capsys.readouterr()
    assert captured.out == "cloud1\ncloud2\ncloud3\ncloud4\ncloud5\n"

    # Test with explicit line count
    args.lines = "2"
    await run(args)
    captured = capsys.readouterr()
    assert captured.out == "cloud1\ncloud2\n"

    args.lines = "-2"
    await run(args)
    captured = capsys.readouterr()
    assert captured.out == "cloud1\ncloud2\ncloud3\n"

    # Test with byte count
    args.bytes = "10"
    args.lines = None
    await run(args)
    captured = capsys.readouterr()
    assert captured.out == "cloud1\nclo"


async def test_head_special_cases(workdir, capsys):
    """Test various special cases in one test"""
    # Test empty file
    empty = workdir / "empty.txt"
    await empty.a_write_bytes(b"")

    # Test file with trailing empty lines
    with_empties = workdir / "with_empties.txt"
    await with_empties.a_write_bytes(b"line1\nline2\n\n\n")

    # Test both files
    args = Namespace(
        file=[str(empty), str(with_empties)],
        bytes=None,
        lines="4",
        quiet=False,
        verbose=True,
        zero_terminated=False,
    )
    await run(args)
    captured = capsys.readouterr()
    assert f"==> {empty} <==" in captured.out
    assert f"==> {with_empties} <==" in captured.out
    assert "line1\nline2\n\n\n" in captured.out


async def test_head_zero_terminated(zero_term_file, capsys):
    args = Namespace(
        file=[zero_term_file],
        bytes=None,
        lines="2",
        quiet=False,
        verbose=False,
        zero_terminated=True,
    )
    await run(args)
    captured = capsys.readouterr()
    assert captured.out == "line1\0line2\0"


async def test_head_local_chunk_remainder(workdir, capsys):
    """Test handling of partial chunks and remaining data"""
    # Create content that's larger than chunk size (8192)
    # and has incomplete line at chunk boundary
    content = b"x" * 8190 + b"ab\ncd\n"  # 8190 + 4 = 8194 bytes
    path = workdir / "test_chunk.txt"
    await path.a_write_bytes(content)

    args = Namespace(
        file=[str(path)],
        bytes=None,
        lines="2",
        quiet=False,
        verbose=False,
        zero_terminated=False,
    )
    await run(args)
    captured = capsys.readouterr()
    assert captured.out.endswith("ab\ncd\n")


async def test_head_negative_bytes_seek(workdir, capsys):
    """Test that negative bytes follows GNU head behavior for cloud files"""

    # Create a mock cloud file with seekable BytesIO
    content = b"0123456789"  # 10 bytes
    path = workdir / "cloud_neg_bytes.txt"
    await path.a_write_bytes(content)

    args = Namespace(
        file=[str(path)],
        bytes="-5",  # Negative bytes: print all but last 5 bytes (GNU head behavior)
        lines=None,
        quiet=False,
        verbose=False,
        zero_terminated=False,
    )

    # Test cloud file behavior directly
    await run(args)
    captured = capsys.readouterr()

    # Cloud file now follows GNU head: -5 bytes means all but last 5
    # File has 10 bytes, all but last 5 = first 5 bytes = "01234"
    assert captured.out == "01234"


async def test_head_local_error(workdir, capsys):
    """Test error handling for local files"""
    # Try to access a non-existent local path
    nonexistent = workdir / "nonexistent" / "test.txt"
    args = Namespace(
        file=[str(nonexistent)],
        bytes=None,
        lines=None,
        quiet=False,
        verbose=False,
        zero_terminated=False,
    )
    with pytest.raises(SystemExit):
        await run(args)
    captured = capsys.readouterr()
    # For local files, the error comes from the head command, not cloudsh
    assert "cannot open" in captured.err or f"{PACKAGE}:" in captured.err


async def test_head_command_error(capsys, monkeypatch):
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
        await run(args)
    captured = capsys.readouterr()
    assert "some error" in captured.err


async def test_head_invalid_suffix(temp_file, capsys):
    args = Namespace(
        file=[temp_file],
        bytes="1X",  # Invalid suffix
        lines=None,
        quiet=False,
        verbose=False,
        zero_terminated=False,
    )
    with pytest.raises(SystemExit):
        await run(args)

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
        await run(args)

    captured = capsys.readouterr()
    assert "invalid number of lines" in captured.err


async def test_head_stdin(capsys, monkeypatch):
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
    await run(args)
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
    await run(args)
    captured = capsys.readouterr()
    assert captured.out == "stdin1\nstdin2\n"


async def test_head_multiple_stdin(capsys, monkeypatch):
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
    await run(args)
    captured = capsys.readouterr()
    assert "==> standard input <==" in captured.out
    assert "stdin1\nstdin2\n" in captured.out


async def test_head_bytes_with_suffix(temp_file, capsys):
    args = Namespace(
        file=[temp_file],
        bytes="1K",  # 1024 bytes
        lines=None,
        quiet=False,
        verbose=False,
        zero_terminated=False,
    )
    await run(args)
    captured = capsys.readouterr()
    # 1K bytes of content
    assert len(captured.out.encode()) <= 1024


async def test_verbose_mode(temp_file, capsys):
    args = Namespace(
        file=[temp_file],
        bytes=None,
        lines="2",
        quiet=False,
        verbose=True,
        zero_terminated=False,
    )
    await run(args)
    captured = capsys.readouterr()
    assert f"==> {temp_file} <==" in captured.out
    assert "line1\nline2\n" in captured.out


async def test_quiet_mode(temp_file, temp_file_no_newline, capsys):
    args = Namespace(
        file=[temp_file, temp_file_no_newline],
        bytes=None,
        lines="2",
        quiet=True,
        verbose=False,
        zero_terminated=False,
    )
    await run(args)
    captured = capsys.readouterr()
    assert "==>" not in captured.out


async def test_head_bytes_with_decimal_suffix(temp_file, capsys):
    args = Namespace(
        file=[temp_file],
        bytes="1.5K",  # 1536 bytes
        lines=None,
        quiet=False,
        verbose=False,
        zero_terminated=False,
    )
    await run(args)
    captured = capsys.readouterr()
    assert len(captured.out.encode()) <= 1536


async def test_head_negative_bytes_tiny_file(workdir, capsys):
    """Test negative bytes with a cloud file smaller than requested size"""

    # Create a mock cloud file smaller than the requested byte count
    content = b"123"  # 3 bytes
    path = workdir / "test_tiny.txt"
    await path.a_write_bytes(content)

    args = Namespace(
        file=[str(path)],
        bytes=-5,  # All but last 5 bytes, but file only has 3
        lines=None,
        quiet=False,
        verbose=False,
        zero_terminated=False,
    )

    # Test cloud file behavior directly
    await run(args)
    captured = capsys.readouterr()

    # Following GNU head behavior: when file (3 bytes) is smaller than abs(bytes) (5),
    # bytes_to_read = max(0, size + bytes) = max(0, 3-5) = 0
    # So output should be empty
    assert captured.out == ""


async def test_head_local_empty_final_lines(workdir, capsys):
    """Test handling of empty lines at the end of file"""
    content = b"line1\nline2\n\n\n"
    path = workdir / "test_empty_final.txt"
    await path.a_write_bytes(content)

    args = Namespace(
        file=[str(path)],
        bytes=None,
        lines=None,
        quiet=False,
        verbose=False,
        zero_terminated=False,
    )
    await run(args)
    captured = capsys.readouterr()
    assert captured.out == "line1\nline2\n\n\n"


async def test_head_multiple_local_files_with_headers(workdir, capsys):
    """Test header handling with multiple local files"""
    path1 = workdir / "test1.txt"
    path2 = workdir / "test2.txt"
    await path1.a_write_bytes(b"file1\n")
    await path2.a_write_bytes(b"file2\n")

    args = Namespace(
        file=[str(path1), str(path2)],
        bytes=None,
        lines="1",
        quiet=False,
        verbose=True,  # Force headers
        zero_terminated=False,
    )
    await run(args)
    captured = capsys.readouterr()
    assert f"==> {path1} <==" in captured.out
    assert f"==> {path2} <==" in captured.out
    assert "file1\n" in captured.out
    assert "file2\n" in captured.out


async def test_head_cloud_file_basic(workdir, capsys):
    """Test head on cloud file with basic line count"""
    cloud_file = workdir / "cloud_head_test.txt"
    content = b"line1\nline2\nline3\nline4\nline5\nline6\nline7\nline8\nline9\nline10\n"
    await cloud_file.a_write_bytes(content)

    args = Namespace(
        file=[str(cloud_file)],
        bytes=None,
        lines="3",
        quiet=False,
        verbose=False,
        zero_terminated=False,
    )
    await run(args)
    captured = capsys.readouterr()
    assert "line1\n" in captured.out
    assert "line2\n" in captured.out
    assert "line3\n" in captured.out
    assert "line4" not in captured.out


async def test_head_cloud_file_negative_lines(workdir, capsys):
    """Test head on cloud file with negative line count"""
    cloud_file = workdir / "cloud_head_neg.txt"
    content = b"line1\nline2\nline3\nline4\nline5\n"
    await cloud_file.a_write_bytes(content)

    args = Namespace(
        file=[str(cloud_file)],
        bytes=None,
        lines="-2",  # All but last 2 lines
        quiet=False,
        verbose=False,
        zero_terminated=False,
    )
    await run(args)
    captured = capsys.readouterr()
    assert "line1\n" in captured.out
    assert "line2\n" in captured.out
    assert "line3\n" in captured.out
    assert "line4" not in captured.out
    assert "line5" not in captured.out


async def test_head_cloud_file_bytes(workdir, capsys):
    """Test head on cloud file with byte count"""
    cloud_file = workdir / "cloud_head_bytes.txt"
    content = b"abcdefghijklmnopqrstuvwxyz"
    await cloud_file.a_write_bytes(content)

    args = Namespace(
        file=[str(cloud_file)],
        bytes="10",
        lines=None,
        quiet=False,
        verbose=False,
        zero_terminated=False,
    )
    await run(args)
    captured = capsys.readouterr()
    # Should output first 10 bytes
    assert captured.out == "abcdefghij"


async def test_head_cloud_file_negative_bytes(workdir, capsys):
    """Test head on cloud file with negative byte count"""
    cloud_file = workdir / "cloud_head_neg_bytes.txt"
    content = b"abcdefghijklmnopqrstuvwxyz"
    await cloud_file.a_write_bytes(content)

    args = Namespace(
        file=[str(cloud_file)],
        bytes="-10",  # All but last 10 bytes
        lines=None,
        quiet=False,
        verbose=False,
        zero_terminated=False,
    )
    await run(args)
    captured = capsys.readouterr()
    # Should output all but last 10 bytes: abcdefghijklmnop
    assert captured.out == "abcdefghijklmnop"


async def test_head_cloud_file_zero_terminated(workdir, capsys):
    """Test head on cloud file with zero-terminated records"""
    cloud_file = workdir / "cloud_head_zero.txt"
    content = b"rec1\0rec2\0rec3\0rec4\0rec5\0"
    await cloud_file.a_write_bytes(content)

    args = Namespace(
        file=[str(cloud_file)],
        bytes=None,
        lines="2",
        quiet=False,
        verbose=False,
        zero_terminated=True,
    )
    await run(args)
    captured = capsys.readouterr()
    # First 2 zero-terminated records
    assert b"rec1\0" in captured.out.encode()
    assert b"rec2\0" in captured.out.encode()


async def test_head_cloud_file_multiple_with_headers(workdir, capsys):
    """Test head on multiple cloud files with headers"""
    cloud_file1 = workdir / "cloud1.txt"
    cloud_file2 = workdir / "cloud2.txt"
    await cloud_file1.a_write_bytes(b"file1_line1\nfile1_line2\n")
    await cloud_file2.a_write_bytes(b"file2_line1\nfile2_line2\n")

    args = Namespace(
        file=[str(cloud_file1), str(cloud_file2)],
        bytes=None,
        lines="1",
        quiet=False,
        verbose=False,  # Should still show headers for multiple files
        zero_terminated=False,
    )
    await run(args)
    captured = capsys.readouterr()
    assert f"==> {cloud_file1} <==" in captured.out
    assert f"==> {cloud_file2} <==" in captured.out
    assert "file1_line1\n" in captured.out
    assert "file2_line1\n" in captured.out


async def test_head_cloud_file_quiet_mode(workdir, capsys):
    """Test head on cloud file in quiet mode (no headers)"""
    cloud_file1 = workdir / "cloud_quiet1.txt"
    cloud_file2 = workdir / "cloud_quiet2.txt"
    await cloud_file1.a_write_bytes(b"content1\n")
    await cloud_file2.a_write_bytes(b"content2\n")

    args = Namespace(
        file=[str(cloud_file1), str(cloud_file2)],
        bytes=None,
        lines="1",
        quiet=True,  # Suppress headers
        verbose=False,
        zero_terminated=False,
    )
    await run(args)
    captured = capsys.readouterr()
    assert "==>" not in captured.out  # No headers
    assert "content1\n" in captured.out
    assert "content2\n" in captured.out


async def test_head_cloud_file_with_chunks(workdir, capsys):
    """Test head on cloud file that requires chunked reading"""
    cloud_file = workdir / "cloud_large.txt"
    # Create content larger than chunk size (8192 bytes)
    lines = [f"line{i}\n".encode() for i in range(500)]
    content = b"".join(lines)
    await cloud_file.a_write_bytes(content)

    args = Namespace(
        file=[str(cloud_file)],
        bytes=None,
        lines="10",
        quiet=False,
        verbose=False,
        zero_terminated=False,
    )
    await run(args)
    captured = capsys.readouterr()
    # Should have first 10 lines
    for i in range(10):
        assert f"line{i}\n" in captured.out
    assert "line10\n" not in captured.out
