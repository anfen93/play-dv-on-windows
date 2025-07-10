"""
Pytest configuration and shared fixtures for the MKV to MP4 converter tests
"""

import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests"""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_config():
    """Sample configuration for testing"""
    return {
        "qbittorrent": {
            "host": "localhost",
            "port": 8080,
            "username": "admin",
            "password": "test",
        },
        "paths": {"plex_dir": "/test/plex", "log_dir": "/test/logs"},
        "processing": {
            "parallel_episodes": 2,
            "delete_after_success": False,
            "use_temp_dir": False,
            "temp_dir": "/tmp",
            "min_file_size_gb": 1,
        },
        "filters": {
            "require_4k": True,
            "require_dv": True,
            "excluded_categories": ["music", "software"],
            "max_seasons_per_torrent": 1,
            "allowed_extensions": [".mkv"],
        },
        "logging": {"level": "INFO", "keep_days": 30},
    }


@pytest.fixture
def mock_logger():
    """Mock logger for testing"""
    return MagicMock()


@pytest.fixture
def sample_streams_info():
    """Sample FFprobe stream information"""
    return {
        "streams": [
            {
                "index": 0,
                "codec_type": "video",
                "codec_name": "hevc",
                "color_transfer": "smpte2084",
                "side_data_list": [{"side_data_type": "DOVI configuration record"}],
            },
            {
                "index": 1,
                "codec_type": "audio",
                "codec_name": "eac3",
                "tags": {"language": "eng", "title": "English"},
            },
            {
                "index": 2,
                "codec_type": "audio",
                "codec_name": "ac3",
                "tags": {"language": "spa", "title": "Spanish"},
            },
            {
                "index": 3,
                "codec_type": "subtitle",
                "codec_name": "subrip",
                "tags": {"language": "eng", "title": "English SDH"},
            },
            {
                "index": 4,
                "codec_type": "subtitle",
                "codec_name": "subrip",
                "tags": {"language": "spa", "title": "Spanish"},
            },
        ]
    }


@pytest.fixture
def create_test_mkv():
    """Factory to create test MKV files"""

    def _create_mkv(path: Path, size_gb: float = 2.0):
        """Create a test MKV file with specified size"""
        path.write_bytes(b"0" * int(size_gb * 1024**3))
        return path

    return _create_mkv


@pytest.fixture(autouse=True, scope="session")
def cleanup_test_artifacts():
    """Cleanup any test artifacts left over from previous runs"""
    import glob
    import os

    # Cleanup before tests
    yield

    # Cleanup after all tests complete
    project_root = Path(__file__).parent.parent

    # Clean up any leftover files in common locations
    cleanup_patterns = [
        str(project_root / "*.mp4"),
        str(project_root / "*.srt"),
        str(project_root / "test_*.mkv"),
        "/tmp/mkv_test_*",
    ]

    for pattern in cleanup_patterns:
        for file_path in glob.glob(pattern):
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path, ignore_errors=True)
            except Exception:
                pass  # Ignore cleanup errors
