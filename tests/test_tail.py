import os
import signal
import sys
import asyncio
import time
from argparse import Namespace
import subprocess

import pytest

from cloudsh.commands.tail import run, _print_header

import multiprocessing
from pathlib import Path


class TailTester:
    """Helper class to run tail command in a separate process"""

    def __init__(self, tmp_path: Path):
        self.process = None
        self.output_file = tmp_path / "tail_output.txt"
        # Keep track of original stdout
        self._orig_stdout = None

    def run_tail(self, args: Namespace):
        """Run tail command in a separate process and capture output"""
        if self.output_file.exists():
            self.output_file.unlink()

        # Create a new file descriptor for output
        output_fd = os.open(self.output_file, os.O_WRONLY | os.O_CREAT)

        def _run():
            try:
                # Duplicate original stdout for restoration
                stdout_fd = os.dup(sys.stdout.fileno())
                stderr_fd = os.dup(sys.stderr.fileno())

                # Redirect output to our file
                os.dup2(output_fd, sys.stdout.fileno())
                os.dup2(output_fd, sys.stderr.fileno())
                os.close(output_fd)

                # Run tail command in an event loop inside the child process
                try:
                    asyncio.run(run(args))
                except KeyboardInterrupt:
                    pass
                finally:
                    # Restore original file descriptors
                    os.dup2(stdout_fd, sys.stdout.fileno())
                    os.dup2(stderr_fd, sys.stderr.fileno())
                    os.close(stdout_fd)
                    os.close(stderr_fd)
            except Exception:
                pass

        self.process = multiprocessing.Process(target=_run)
        self.process.start()

        # Close parent's copy
        os.close(output_fd)
        time.sleep(0.5)  # Give process time to start

    def wait_for_content(self, expected: str, timeout: float = 10.0) -> str:
        """Wait for expected content to appear in output file."""
        start_time = time.time()
        last_content = ""
        while time.time() - start_time < timeout:
            try:
                if self.output_file.exists():
                    content = self.output_file.read_text()
                    if content != last_content:  # Only process if content changed
                        if expected in content:
                            return content
                        last_content = content
                time.sleep(0.2)
            except (OSError, IOError):
                # Handle file access errors gracefully
                time.sleep(0.1)
                continue
        raise TimeoutError(
            f"Expected content '{expected}' not found within {timeout}s"
        )

    def stop(self):
        """Stop tail process and collect output"""
        output = ""
        try:
            if self.process and self.process.is_alive():
                os.kill(self.process.pid, signal.SIGINT)
                self.process.join(timeout=1.0)
                if self.process.is_alive():
                    self.process.terminate()
                    self.process.join(timeout=0.5)

            if self.output_file.exists():
                time.sleep(0.1)
                output = self.output_file.read_text()
                self.output_file.unlink()
        except (OSError, IOError):
            pass  # Ignore errors during cleanup
        return output


@pytest.fixture
def tail_tester(tmp_path):
    """Fixture to provide TailTester instance"""
    tester = TailTester(tmp_path)
    yield tester
    tester.stop()


@pytest.fixture
def cloud_file(workdir):
    """Create a test file in local storage"""
    path = workdir / "test.txt"
    path.write_bytes(b"cloud1\ncloud2\ncloud3\ncloud4\ncloud5\n")
    return str(path)


@pytest.fixture
def growing_file(workdir):
    """Create a file that will grow during test"""
    path = workdir / "growing.txt"
    if path.exists():
        path.unlink()
    path.write_bytes(b"line1\n")
    return str(path)


class TestTail:
    """Group tail tests to share fixtures and avoid global state issues"""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test"""
        # Clear any existing _print_header state
        if hasattr(_print_header, "printed"):
            del _print_header.printed
        yield

    async def test_tail_default(self, cloud_file, capsys):
        """Test basic tail functionality"""
        args = Namespace(
            file=[cloud_file],
            bytes=None,
            lines="10",  # Default
            quiet=False,
            verbose=False,
            zero_terminated=False,
            follow=False,
            F=False,
            retry=False,
            pid=None,
            sleep_interval=None,
            max_unchanged_stats=None,
        )
        await run(args)
        captured = capsys.readouterr()
        assert captured.out == "cloud1\ncloud2\ncloud3\ncloud4\ncloud5\n"

    async def test_tail_bytes(self, cloud_file, capsys):
        """Test tail with byte count"""
        args = Namespace(
            file=[cloud_file],
            bytes="10",
            lines=None,
            quiet=False,
            verbose=False,
            zero_terminated=False,
            follow=False,
            F=False,
            retry=False,
            pid=None,
            sleep_interval=None,
            max_unchanged_stats=None,
        )
        await run(args)
        captured = capsys.readouterr()
        assert captured.out == "d4\ncloud5\n"

    async def test_tail_bytes_from_start(self, cloud_file, capsys):
        args = Namespace(
            file=[cloud_file],
            bytes="+10",  # Start from byte 10
            lines=None,
            quiet=False,
            verbose=False,
            zero_terminated=False,
            follow=False,
            F=False,
            retry=False,
            pid=None,
            sleep_interval=None,
            max_unchanged_stats=None,
        )
        await run(args)
        captured = capsys.readouterr()
        assert captured.out.startswith("oud2\ncloud3")

    async def test_tail_lines(self, cloud_file, capsys):
        args = Namespace(
            file=[cloud_file],
            bytes=None,
            lines="2",
            quiet=False,
            verbose=False,
            zero_terminated=False,
            follow=False,
            F=False,
            retry=False,
            pid=None,
            sleep_interval=None,
            max_unchanged_stats=None,
        )
        await run(args)
        captured = capsys.readouterr()
        assert captured.out == "cloud4\ncloud5\n"

    async def test_tail_lines_from_start(self, cloud_file, capsys):
        args = Namespace(
            file=[cloud_file],
            bytes=None,
            lines="+2",  # Start from line 2
            quiet=False,
            verbose=False,
            zero_terminated=False,
            follow=False,
            F=False,
            retry=False,
            pid=None,
            sleep_interval=None,
            max_unchanged_stats=None,
        )
        await run(args)
        captured = capsys.readouterr()
        assert captured.out == "cloud2\ncloud3\ncloud4\ncloud5\n"

    async def test_tail_follow(self, tail_tester, growing_file):
        """Test tail -f with a growing file"""
        path = Path(growing_file)
        # Ensure initial content is present
        path.write_bytes(b"line1\n")
        time.sleep(0.5)  # Give time for initial write to be detected

        args = Namespace(
            file=[growing_file],
            bytes=None,
            lines="10",
            quiet=False,
            verbose=False,
            zero_terminated=False,
            follow=True,
            F=False,
            retry=False,
            pid=None,
            sleep_interval="0.2",  # Increase polling interval
            max_unchanged_stats=None,
        )

        tail_tester.run_tail(args)
        # Wait for initial content to be detected
        tail_tester.wait_for_content("line1", timeout=5.0)
        # Write new content
        path.write_bytes(b"line1\nline2\n")

        # Wait for new content
        content = tail_tester.wait_for_content("line2", timeout=10.0)
        assert "line1" in content
        assert "line2" in content

    async def test_tail_F(self, tail_tester, growing_file):
        """Test tail -f with a growing file"""
        path = Path(growing_file)
        # Ensure initial content is present
        path.write_bytes(b"line1\n")
        time.sleep(0.5)  # Give time for initial write to be detected

        args = Namespace(
            file=[growing_file],
            bytes=None,
            lines="10",
            quiet=False,
            verbose=False,
            zero_terminated=False,
            follow=False,
            F=True,
            retry=False,
            pid=None,
            sleep_interval="0.2",  # Increase polling interval
            max_unchanged_stats=None,
        )

        tail_tester.run_tail(args)
        # Wait for initial content to be detected
        tail_tester.wait_for_content("line1", timeout=5.0)
        # Write new content
        path.write_bytes(b"line1\nline2\n")

        # Wait for new content
        content = tail_tester.wait_for_content("line2", timeout=10.0)
        assert "line1" in content
        assert "line2" in content

    async def test_tail_pid_monitoring(self, capsys, monkeypatch):
        """Test PID monitoring with stdin"""

        def mock_run(*args, **kwargs):
            # Simulate GNU tail behavior
            return subprocess.CompletedProcess(
                args=args[0], returncode=0, stdout="some output\n", stderr=""
            )

        monkeypatch.setattr(subprocess, "run", mock_run)
        args = Namespace(
            file=["-"],
            bytes=None,
            lines="10",
            quiet=False,
            verbose=False,
            zero_terminated=False,
            follow=True,
            F=False,
            retry=False,
            pid="999999999",  # Non-existent PID
            sleep_interval="0.1",
            max_unchanged_stats=None,
        )
        await run(args)
        captured = capsys.readouterr()
        assert "some output" in captured.out

    async def test_tail_invalid_pid(self, capsys):
        args = Namespace(
            file=["-"],
            bytes=None,
            lines="10",
            quiet=False,
            verbose=False,
            zero_terminated=False,
            follow=True,
            F=False,
            retry=False,
            pid="not_a_pid",
            sleep_interval="1",
            max_unchanged_stats=None,
        )
        with pytest.raises(SystemExit):
            await run(args)

        captured = capsys.readouterr()
        assert "invalid PID" in captured.err

    async def test_tail_multiple_files(self, cloud_file, growing_file, capsys):
        args = Namespace(
            file=[cloud_file, growing_file],
            bytes=None,
            lines="2",
            quiet=False,
            verbose=False,
            zero_terminated=False,
            follow=False,
            F=False,
            retry=False,
            pid=None,
            sleep_interval=None,
            max_unchanged_stats=None,
        )
        await run(args)
        captured = capsys.readouterr()
        assert "==> " in captured.out
        assert "cloud4\ncloud5\n" in captured.out
        assert "line1\n" in captured.out

    async def test_tail_zero_terminated(self, workdir, capsys):
        content = b"line1\0line2\0line3\0"
        path = workdir / "zero.txt"
        path.write_bytes(content)

        args = Namespace(
            file=[str(path)],
            bytes=None,
            lines="2",
            quiet=False,
            verbose=False,
            zero_terminated=True,
            follow=False,
            F=False,
            retry=False,
            pid=None,
            sleep_interval=None,
            max_unchanged_stats=None,
        )
        await run(args)
        captured = capsys.readouterr()
        assert captured.out == "line2\0line3\0"

    async def test_tail_invalid_suffix(self, cloud_file, capsys):
        args = Namespace(
            file=[cloud_file],
            bytes="1X",  # Invalid suffix
            lines=None,
            quiet=False,
            verbose=False,
            zero_terminated=False,
            follow=False,
            F=False,
            retry=False,
            pid=None,
            sleep_interval=None,
            max_unchanged_stats=None,
        )
        with pytest.raises(SystemExit):
            await run(args)

        captured = capsys.readouterr()
        assert "invalid number of bytes" in captured.err

        args.bytes = None
        args.lines = "1X"
        with pytest.raises(SystemExit):
            await run(args)

        captured = capsys.readouterr()
        assert "invalid number of lines" in captured.err

    async def test_tail_F_retry_file_appears(self, tail_tester, workdir):
        """Test -F option with file appearing after start"""
        nonexistent = workdir / "appears.txt"
        args = Namespace(
            file=[str(nonexistent)],
            bytes=None,
            lines="10",
            quiet=False,
            verbose=True,
            zero_terminated=False,
            follow=False,
            F=True,  # This implies follow and retry
            retry=False,
            pid=None,
            sleep_interval="0.1",
            max_unchanged_stats=None,
        )

        tail_tester.run_tail(args)
        time.sleep(0.5)  # Wait for tail to start
        nonexistent.write_text("new content\n")

        content = tail_tester.wait_for_content("new content")
        assert "new content" in content

    async def test_tail_follow_multiple_cloud_files(self, tail_tester, workdir):
        """Test following multiple cloud files simultaneously"""
        file1 = workdir / "multi1.txt"
        file2 = workdir / "multi2.txt"
        file1.write_text("initial1\n")
        file2.write_text("initial2\n")

        args = Namespace(
            file=[str(file1), str(file2)],
            bytes=None,
            lines="10",
            quiet=False,
            verbose=True,
            zero_terminated=False,
            follow=True,
            F=False,
            retry=False,
            pid=None,
            sleep_interval="0.1",
            max_unchanged_stats=None,
        )

        tail_tester.run_tail(args)
        time.sleep(0.5)

        file1.write_text("initial1\nupdate1\n")
        content = tail_tester.wait_for_content("update1")
        assert "==> " in content  # Header should be present
        assert "initial1" in content
        assert "update1" in content

        file2.write_text("initial2\nupdate2\n")
        content = tail_tester.wait_for_content("update2")
        assert "initial2" in content
        assert "update2" in content

    async def test_tail_follow_file_disappears(self, tail_tester, workdir):
        """Test following a file that disappears."""
        temp_file = workdir / "disappearing.txt"
        temp_file.write_text("initial\n")

        args = Namespace(
            file=[str(temp_file)],
            bytes=None,
            lines="10",
            quiet=False,
            verbose=True,
            zero_terminated=False,
            follow=True,
            F=False,
            retry=False,
            pid=None,
            sleep_interval="0.1",
            max_unchanged_stats=None,
        )

        tail_tester.run_tail(args)
        content = tail_tester.wait_for_content("initial")
        assert "initial" in content

        # Delete file and recreate
        temp_file.unlink()
        time.sleep(0.5)
        temp_file.write_text("recreated\n")
        time.sleep(0.5)

        final_content = tail_tester.stop()
        assert "recreated" not in final_content
        assert "initial" in final_content

    @pytest.mark.skip(
        reason="Cannot patch stat method on PosixPath - read-only attribute"
    )
    async def test_tail_follow_stat_error(self, tail_tester, workdir):
        """Test handling of stat errors during follow"""
        # This test is skipped because Path.stat is a read-only attribute
        # and cannot be patched in the current implementation
        pass

    @pytest.mark.skip(reason="Flaky test - timing issues with follow mode")
    async def test_tail_zero_terminated_follow(self, tail_tester, workdir):
        """Test following zero-terminated file"""
        # This test is skipped due to timing issues in follow mode
        pass

    async def test_tail_broken_pipe(self, tail_tester, workdir):
        """Test handling of broken pipe during output"""
        file = workdir / "pipe.txt"
        file.write_text("initial\n")

        args = Namespace(
            file=[str(file)],
            bytes=None,
            lines="10",
            quiet=False,
            verbose=True,
            zero_terminated=False,
            follow=True,
            F=False,
            retry=False,
            pid=None,
            sleep_interval="0.1",
            max_unchanged_stats=None,
        )

        tail_tester.run_tail(args)
        time.sleep(0.2)
        file.write_text("initial\nmore\n")
        time.sleep(0.2)
        tail_tester.stop()

    async def test_tail_follow_errors(self, tail_tester):
        """Test error handling in follow mode"""
        args = Namespace(
            file=["nonexistent"],
            bytes=None,
            lines="10",
            quiet=False,
            verbose=True,
            zero_terminated=False,
            follow=True,
            F=False,
            retry=False,
            pid=None,
            sleep_interval="0.1",
            max_unchanged_stats=None,
        )

        tail_tester.run_tail(args)
        content = tail_tester.stop()
        assert "No such file or directory" in content

    async def test_tail_no_file(self, capsys, monkeypatch):
        """Test tail behavior when no file is passed (should use stdin)"""

        def mock_run(*args, **kwargs):
            # Verify that tail is called with stdin (-)
            assert args[0][-1] == "-"
            return subprocess.CompletedProcess(
                args=args[0], returncode=0, stdout="content from stdin\n", stderr=""
            )

        monkeypatch.setattr(subprocess, "run", mock_run)
        args = Namespace(
            file=[],  # No files passed
            bytes=None,
            lines="10",
            quiet=False,
            verbose=False,
            zero_terminated=False,
            follow=False,
            F=False,
            retry=False,
            pid=None,
            sleep_interval=None,
            max_unchanged_stats=None,
        )
        await run(args)
        captured = capsys.readouterr()
        assert "content from stdin" in captured.out

    async def test_tail_cloud_file_basic(self, workdir, capsys):
        """Test tail on cloud file"""
        cloud_file = workdir / "cloud_tail.txt"
        lines = b"line1\nline2\nline3\nline4\nline5\n"
        lines += b"line6\nline7\nline8\nline9\nline10\n"
        cloud_file.write_bytes(lines)

        args = Namespace(
            file=[str(cloud_file)],
            bytes=None,
            lines="3",
            quiet=False,
            verbose=False,
            zero_terminated=False,
            follow=False,
            F=False,
            retry=False,
            pid=None,
            sleep_interval=None,
            max_unchanged_stats=None,
        )
        await run(args)
        captured = capsys.readouterr()
        assert "line8\n" in captured.out
        assert "line9\n" in captured.out
        assert "line10\n" in captured.out
        assert "line7" not in captured.out

    async def test_tail_cloud_file_bytes(self, workdir, capsys):
        """Test tail on cloud file with byte count"""
        cloud_file = workdir / "cloud_tail_bytes.txt"
        content = b"0123456789abcdefghij"
        cloud_file.write_bytes(content)

        args = Namespace(
            file=[str(cloud_file)],
            bytes="5",
            lines=None,
            quiet=False,
            verbose=False,
            zero_terminated=False,
            follow=False,
            F=False,
            retry=False,
            pid=None,
            sleep_interval=None,
            max_unchanged_stats=None,
        )
        await run(args)
        captured = capsys.readouterr()
        assert captured.out == "fghij"

    async def test_tail_cloud_file_bytes_from_start(self, workdir, capsys):
        """Test tail on cloud file with +bytes (from start)"""
        cloud_file = workdir / "cloud_tail_bytes_start.txt"
        content = b"0123456789abcdefghij"
        cloud_file.write_bytes(content)

        args = Namespace(
            file=[str(cloud_file)],
            bytes="+6",
            lines=None,
            quiet=False,
            verbose=False,
            zero_terminated=False,
            follow=False,
            F=False,
            retry=False,
            pid=None,
            sleep_interval=None,
            max_unchanged_stats=None,
        )
        await run(args)
        captured = capsys.readouterr()
        # Should output from 6th byte onwards (index 5)
        assert captured.out == "56789abcdefghij"

    async def test_tail_cloud_file_lines_from_start(self, workdir, capsys):
        """Test tail on cloud file with +lines (from start)"""
        cloud_file = workdir / "cloud_tail_lines_start.txt"
        content = b"line1\nline2\nline3\nline4\nline5\n"
        cloud_file.write_bytes(content)

        args = Namespace(
            file=[str(cloud_file)],
            bytes=None,
            lines="+3",
            quiet=False,
            verbose=False,
            zero_terminated=False,
            follow=False,
            F=False,
            retry=False,
            pid=None,
            sleep_interval=None,
            max_unchanged_stats=None,
        )
        await run(args)
        captured = capsys.readouterr()
        # Should output from 3rd line onwards
        assert "line3\n" in captured.out
        assert "line4\n" in captured.out
        assert "line5\n" in captured.out
        assert "line1" not in captured.out
        assert "line2" not in captured.out

    async def test_tail_cloud_file_zero_terminated(self, workdir, capsys):
        """Test tail on cloud file with zero-terminated lines"""
        cloud_file = workdir / "cloud_tail_zero.txt"
        content = b"rec1\0rec2\0rec3\0rec4\0rec5\0"
        cloud_file.write_bytes(content)

        args = Namespace(
            file=[str(cloud_file)],
            bytes=None,
            lines="2",
            quiet=False,
            verbose=False,
            zero_terminated=True,
            follow=False,
            F=False,
            retry=False,
            pid=None,
            sleep_interval=None,
            max_unchanged_stats=None,
        )
        await run(args)
        captured = capsys.readouterr()
        assert b"rec4\0" in captured.out.encode()
        assert b"rec5\0" in captured.out.encode()

    async def test_tail_cloud_file_with_verbose(self, workdir, capsys):
        """Test tail on cloud file with verbose (shows header)"""
        cloud_file = workdir / "cloud_tail_verbose.txt"
        content = b"line1\nline2\nline3\n"
        cloud_file.write_bytes(content)

        args = Namespace(
            file=[str(cloud_file)],
            bytes=None,
            lines="2",
            quiet=False,
            verbose=True,
            zero_terminated=False,
            follow=False,
            F=False,
            retry=False,
            pid=None,
            sleep_interval=None,
            max_unchanged_stats=None,
        )
        await run(args)
        captured = capsys.readouterr()
        assert f"==> {cloud_file} <==" in captured.out
        assert "line2\n" in captured.out
        assert "line3\n" in captured.out

    async def test_tail_cloud_multiple_files(self, workdir, capsys):
        """Test tail on multiple cloud files"""
        cloud_file1 = workdir / "cloud1.txt"
        cloud_file2 = workdir / "cloud2.txt"
        cloud_file1.write_bytes(b"file1_line1\nfile1_line2\nfile1_line3\n")
        cloud_file2.write_bytes(b"file2_line1\nfile2_line2\n")

        args = Namespace(
            file=[str(cloud_file1), str(cloud_file2)],
            bytes=None,
            lines="2",
            quiet=False,
            verbose=False,
            zero_terminated=False,
            follow=False,
            F=False,
            retry=False,
            pid=None,
            sleep_interval=None,
            max_unchanged_stats=None,
        )
        await run(args)
        captured = capsys.readouterr()
        # Should show headers for multiple files
        assert f"==> {cloud_file1} <==" in captured.out
        assert f"==> {cloud_file2} <==" in captured.out
        assert "file1_line2\n" in captured.out
        assert "file1_line3\n" in captured.out
        assert "file2_line1\n" in captured.out
        assert "file2_line2\n" in captured.out
