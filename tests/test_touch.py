import time
from datetime import datetime
from argparse import Namespace

import pytest

from cloudsh.commands.touch import run


class TestTouch:
    """Test touch command functionality"""

    def test_touch_cloud_create(self, workdir):
        """Test creating new cloud file"""
        test_file = workdir / "new_file.txt"
        args = Namespace(
            file=[str(test_file)],
            a=False,
            m=False,
            no_create=False,
            date=None,
            reference=None,
            t=None,
            time=None,
        )
        run(args)
        assert test_file.exists()

    def test_touch_cloud_update_mtime(self, workdir):
        """Test updating cloud file mtime"""
        test_file = workdir / "update_time.txt"
        test_file.write_text("test")
        original_mtime = test_file.stat().st_mtime
        time.sleep(1)

        args = Namespace(
            file=[str(test_file)],
            a=False,
            m=True,
            no_create=False,
            date=None,
            reference=None,
            t=None,
            time=None,
        )
        run(args)

        # Check that mtime was updated
        updated_mtime = test_file.stat().st_mtime
        assert updated_mtime > original_mtime

    def test_touch_cloud_reference(self, workdir):
        """Test using reference file for cloud file"""
        ref_file = workdir / "ref.txt"
        test_file = workdir / "test.txt"

        # Create reference file
        ref_file.write_text("ref")
        ref_stat = ref_file.stat()

        args = Namespace(
            file=[str(test_file)],
            a=False,
            m=False,
            no_create=False,
            date=None,
            reference=str(ref_file),
            t=None,
            time=None,
        )
        run(args)
        test_stat = test_file.stat()
        # Allow 2 second tolerance for timestamp comparison
        assert abs(test_stat.st_mtime - ref_stat.st_mtime) < 2

    def test_touch_cloud_date(self, workdir):
        """Test setting specific date for cloud file"""
        test_file = workdir / "date.txt"
        test_date = "2023-01-01 12:00:00"
        expected_time = datetime.fromisoformat(test_date)

        args = Namespace(
            file=[str(test_file)],
            a=False,
            m=False,
            no_create=False,
            date=test_date,
            reference=None,
            t=None,
            time=None,
        )
        run(args)

        test_stat = test_file.stat()
        # Allow 2 second tolerance
        assert abs(test_stat.st_mtime - expected_time.timestamp()) < 2

    def test_touch_t_format(self, workdir):
        """Test various -t format timestamps"""
        test_cases = [
            ("1312151213", "2013-12-15 12:13:00"),  # MMDDhhmm
            ("1312151213.45", "2013-12-15 12:13:45"),  # MMDDhhmm.ss
            ("1312151213", "2013-12-15 12:13:00"),  # YYMMDDhhmm
            ("201312151213", "2013-12-15 12:13:00"),  # CCYYMMDDhhmm
        ]

        for t_value, expected in test_cases:
            test_file = workdir / f"time_{t_value}.txt"
            args = Namespace(
                file=[str(test_file)],
                a=False,
                m=False,
                no_create=False,
                date=None,
                reference=None,
                t=t_value,
                time=None,
            )
            run(args)

            test_stat = test_file.stat()
            expected_dt = datetime.fromisoformat(expected)
            # Allow 2 second tolerance
            assert abs(test_stat.st_mtime - expected_dt.timestamp()) < 2

    def test_touch_time_option(self, workdir):
        """Test --time option variants"""
        test_file = workdir / "time_opt.txt"
        test_file.write_text("test")
        old_stat = test_file.stat()
        time.sleep(1)

        # Test modify time
        args = Namespace(
            file=[str(test_file)],
            a=False,
            m=False,
            no_create=False,
            date=None,
            reference=None,
            t=None,
            time="modify",
        )
        run(args)

        updated_stat = test_file.stat()
        assert updated_stat.st_mtime > old_stat.st_mtime

    def test_touch_no_create(self, workdir):
        """Test no-create option"""
        test_file = workdir / "nonexistent.txt"
        args = Namespace(
            file=[str(test_file)],
            a=False,
            m=False,
            no_create=True,
            date=None,
            reference=None,
            t=None,
            time=None,
        )
        run(args)
        assert not test_file.exists()

    def test_touch_invalid_reference(self, workdir, capsys):
        """Test error handling for nonexistent reference file"""
        test_file = workdir / "test.txt"
        args = Namespace(
            file=[str(test_file)],
            a=False,
            m=False,
            no_create=False,
            date=None,
            reference=str(workdir / "nonexistent_ref"),
            t=None,
            time=None,
        )
        with pytest.raises(SystemExit):
            run(args)
        assert "Reference file not found" in capsys.readouterr().err

    def test_touch_invalid_date(self, workdir, capsys):
        """Test error handling for invalid date format"""
        test_file = workdir / "test.txt"
        args = Namespace(
            file=[str(test_file)],
            a=False,
            m=False,
            no_create=False,
            date="invalid_date",
            reference=None,
            t=None,
            time=None,
        )
        with pytest.raises(SystemExit):
            run(args)
        assert "Invalid date format" in capsys.readouterr().err

    def test_touch_invalid_t_format(self, workdir, capsys):
        """Test invalid -t format"""
        test_file = workdir / "invalid_time.txt"
        args = Namespace(
            file=[str(test_file)],
            a=False,
            m=False,
            no_create=False,
            date=None,
            reference=None,
            t="invalid",
            time=None,
        )
        with pytest.raises(SystemExit):
            run(args)
        assert "Invalid time format" in capsys.readouterr().err

    def test_touch_local_file(self, tmp_path):
        """Test touching local file"""
        test_file = tmp_path / "local.txt"
        args = Namespace(
            file=[str(test_file)],
            a=False,
            m=False,
            no_create=False,
            date=None,
            reference=None,
            t=None,
            time=None,
        )
        run(args)
        assert test_file.exists()
