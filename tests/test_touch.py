import os
import time
from datetime import datetime, timedelta
from argparse import Namespace
from uuid import uuid4

import pytest
from cloudpathlib import AnyPath
from google.cloud.storage.blob import Blob

from cloudsh.commands.touch import run
from .conftest import BUCKET

WORKDIR = None


def setup_module():
    """Create test directory before any tests run"""
    global WORKDIR
    WORKDIR = AnyPath(f"{BUCKET}/cloudsh_test/{uuid4()}")
    WORKDIR.mkdir(parents=True)


def teardown_module():
    """Remove test directory after all tests complete"""
    if WORKDIR is not None:
        WORKDIR.rmtree()


class TestTouch:
    """Test touch command functionality"""

    def test_touch_cloud_create(self):
        """Test creating new cloud file"""
        test_file = WORKDIR / "new_file.txt"
        args = Namespace(
            file=[str(test_file)],
            a=False, m=False, no_create=False,
            date=None, reference=None, t=None, time=None
        )
        run(args)
        assert test_file.exists()

    def test_touch_cloud_update_mtime(self):
        """Test updating cloud file mtime"""
        test_file = WORKDIR / "update_time.txt"
        test_file.write_text("test")
        original_mtime = test_file.stat().st_mtime
        time.sleep(1)

        args = Namespace(
            file=[str(test_file)],
            a=False, m=True, no_create=False,
            date=None, reference=None, t=None, time=None
        )
        run(args)

        # Check metadata directly
        blob = test_file.client.client.bucket(test_file.bucket).get_blob(test_file.blob)
        updated = datetime.fromisoformat(blob.metadata["updated"])
        assert updated.timestamp() > original_mtime

    def test_touch_cloud_reference(self):
        """Test using reference file for cloud file"""
        ref_file = WORKDIR / "ref.txt"
        test_file = WORKDIR / "test.txt"

        # Create reference file with known time
        ref_time = datetime.now() - timedelta(hours=1)
        ref_file.write_text("ref")
        ref_blob = ref_file.client.client.bucket(ref_file.bucket).get_blob(ref_file.blob)
        metadata = ref_blob.metadata or {}
        metadata["updated"] = ref_time
        ref_blob.metadata = metadata
        ref_blob.patch()
        args = Namespace(
            file=[str(test_file)],
            a=False, m=False, no_create=False,
            date=None, reference=str(ref_file), t=None, time=None
        )
        run(args)
        assert abs((test_file.stat().st_mtime - ref_time.timestamp())) < 1

    def test_touch_cloud_date(self):
        """Test setting specific date for cloud file"""
        test_file = WORKDIR / "date.txt"
        test_date = "2023-01-01 12:00:00"
        expected_time = datetime.fromisoformat(test_date)

        args = Namespace(
            file=[str(test_file)],
            a=False, m=False, no_create=False,
            date=test_date, reference=None, t=None, time=None
        )
        run(args)

        blob = test_file.client.client.bucket(test_file.bucket).get_blob(test_file.blob)
        updated = datetime.fromisoformat(blob.metadata["updated"])
        assert abs((updated - expected_time).total_seconds()) < 1

    def test_touch_t_format(self):
        """Test various -t format timestamps"""
        test_cases = [
            ("1312151213", "2013-12-15 12:13:00"),  # MMDDhhmm
            ("1312151213.45", "2013-12-15 12:13:45"),  # MMDDhhmm.ss
            ("1312151213", "2013-12-15 12:13:00"),  # YYMMDDhhmm
            ("201312151213", "2013-12-15 12:13:00"),  # CCYYMMDDhhmm
        ]

        for t_value, expected in test_cases:
            test_file = WORKDIR / f"time_{t_value}.txt"
            args = Namespace(
                file=[str(test_file)],
                a=False, m=False, no_create=False,
                date=None, reference=None, t=t_value, time=None
            )
            run(args)

            blob = test_file.client.client.bucket(test_file.bucket).get_blob(test_file.blob)
            updated = datetime.fromisoformat(blob.metadata["updated"])
            expected_dt = datetime.fromisoformat(expected)
            assert abs((updated - expected_dt).total_seconds()) < 1

    def test_touch_time_option(self):
        """Test --time option variants"""
        test_file = WORKDIR / "time_opt.txt"
        test_file.write_text("test")
        old_stat = test_file.stat()
        time.sleep(1)

        # Test modify time
        args = Namespace(
            file=[str(test_file)],
            a=False, m=False, no_create=False,
            date=None, reference=None, t=None, time="modify"
        )
        run(args)

        blob = test_file.client.client.bucket(test_file.bucket).get_blob(test_file.blob)
        updated = datetime.fromisoformat(blob.metadata["updated"])
        assert updated.timestamp() > old_stat.st_mtime

    def test_touch_no_create(self):
        """Test no-create option"""
        test_file = WORKDIR / "nonexistent.txt"
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

    def test_touch_invalid_reference(self, capsys):
        """Test error handling for nonexistent reference file"""
        test_file = WORKDIR / "test.txt"
        args = Namespace(
            file=[str(test_file)],
            a=False,
            m=False,
            no_create=False,
            date=None,
            reference=str(WORKDIR / "nonexistent_ref"),
        )
        with pytest.raises(SystemExit):
            run(args)
        assert "Reference file not found" in capsys.readouterr().err

    def test_touch_invalid_date(self, capsys):
        """Test error handling for invalid date format"""
        test_file = WORKDIR / "test.txt"
        args = Namespace(
            file=[str(test_file)],
            a=False,
            m=False,
            no_create=False,
            date="invalid_date",
            reference=None,
        )
        with pytest.raises(SystemExit):
            run(args)
        assert "Invalid date format" in capsys.readouterr().err

    def test_touch_invalid_t_format(self, capsys):
        """Test invalid -t format"""
        test_file = WORKDIR / "invalid_time.txt"
        args = Namespace(
            file=[str(test_file)],
            a=False, m=False, no_create=False,
            date=None, reference=None, t="invalid", time=None
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
