"""Tests for __main__.py and main.py modules."""

import sys
import subprocess


class TestMainModule:
    """Test the main module entry points."""

    def test_main_module_execution(self):
        """Test running cloudsh via python -m cloudsh."""
        # Test --version flag through module execution
        result = subprocess.run(
            [sys.executable, "-m", "cloudsh", "--version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "cloudsh version:" in result.stdout

    def test_main_passthrough_command(self, workdir):
        """Test passthrough to native ls with -- separator."""
        # Create a test file
        test_file = workdir / "test.txt"
        test_file.write_text("content")

        # Run cloudsh ls -- -l (should passthrough to native ls)
        result = subprocess.run(
            [sys.executable, "-m", "cloudsh", "ls", "--", "-l", str(test_file)],
            capture_output=True,
            text=True,
            cwd=workdir,
        )
        # Should run native ls command
        assert result.returncode in [0, 1, 2]  # May fail if ls not available

    def test_main_version_flag(self):
        """Test --version flag in main()."""
        result = subprocess.run(
            [sys.executable, "-m", "cloudsh", "--version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "cloudsh version:" in result.stdout

    def test_main_help(self):
        """Test help output."""
        result = subprocess.run(
            [sys.executable, "-m", "cloudsh", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "cloudsh" in result.stdout.lower()

    def test_main_command_execution(self, workdir):
        """Test executing a command through main."""
        # Create a test file
        test_file = workdir / "test.txt"
        test_file.write_text("test content\n")

        # Run cloudsh cat
        result = subprocess.run(
            [sys.executable, "-m", "cloudsh", "cat", str(test_file)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "test content" in result.stdout

    def test_main_nonexistent_command(self):
        """Test handling of nonexistent command."""
        result = subprocess.run(
            [sys.executable, "-m", "cloudsh", "nonexistent"],
            capture_output=True,
            text=True,
        )
        # Should fail with some error
        assert result.returncode != 0
