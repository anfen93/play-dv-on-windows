"""
Test to ensure logging configuration is properly structured and accessible.
This test prevents regressions of the KeyError: 'dir' bug.
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from play_dv_on_windows.config_manager import ConfigManager
from play_dv_on_windows.qbt_post_process import setup_logging


class TestLoggingConfiguration:
    """Test that logging configuration is properly structured"""

    def test_config_has_log_dir_in_paths(self):
        """Test that log_dir is in the paths section, not logging section"""
        config_manager = ConfigManager()
        config = config_manager.config

        # Verify the structure is correct
        assert "paths" in config
        assert "log_dir" in config["paths"]
        assert "logging" in config

        # Verify log_dir is NOT in the logging section (the bug)
        assert "dir" not in config["logging"]

    def test_setup_logging_works_with_config(self):
        """Test that setup_logging can access the log directory correctly"""
        config_manager = ConfigManager()
        config = config_manager.config

        with tempfile.TemporaryDirectory() as temp_dir:
            # Override log_dir to use temp directory
            config["paths"]["log_dir"] = temp_dir

            # This should not raise KeyError: 'dir'
            logger = setup_logging(config, "test_torrent")

            # Verify logger was created successfully
            assert logger is not None
            assert logger.name == "qbt_post_process"

    def test_setup_logging_creates_log_directory(self):
        """Test that setup_logging creates the log directory if it doesn't exist"""
        config_manager = ConfigManager()
        config = config_manager.config

        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "test_logs"
            config["paths"]["log_dir"] = str(log_dir)

            # Directory should not exist yet
            assert not log_dir.exists()

            # setup_logging should create it
            logger = setup_logging(config, "test_torrent")

            # Directory should now exist
            assert log_dir.exists()
            assert log_dir.is_dir()

    def test_real_torrent_name_logging(self):
        """Test with a real torrent name that caused the original failure"""
        config_manager = ConfigManager()
        config = config_manager.config

        with tempfile.TemporaryDirectory() as temp_dir:
            config["paths"]["log_dir"] = temp_dir

            # This is the exact torrent name that caused the failure
            torrent_name = (
                "Murderbot.S01E01-02.2160p.ATVP.WEB-DL.ITA-ENG.DD5.1.DV.HDR.H.265-G66"
            )

            # This should work without any KeyError
            logger = setup_logging(config, torrent_name)

            # Test that we can actually log with this logger
            logger.info("Test message for torrent processing")

            # Verify log file was created
            log_files = list(Path(temp_dir).glob("*.log"))
            assert len(log_files) > 0
