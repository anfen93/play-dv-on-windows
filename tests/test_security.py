"""
Security-focused tests for the MKV to MP4 converter
"""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from play_dv_on_windows import convert


class TestFileValidation:
    """Test file path validation and security"""

    def test_validate_file_path_success(self):
        """Test successful file validation with real Dolby Vision MKV file"""
        # Use the real Dolby Vision test file
        test_file = Path(__file__).parent / "data" / "DV8_TEST_with_audio_subs.mkv"
        if not test_file.exists():
            test_file = Path(__file__).parent / "data" / "DV8_TEST_with_subs.mkv"

        if not test_file.exists():
            pytest.skip("Real test MKV file not found")

        # The test file is in tests/data which is under project root, so should be
        # allowed
        result = convert.validate_file_path(str(test_file))
        assert result == test_file.resolve()
        assert result.suffix == ".mkv"

    def test_validate_file_path_not_found(self):
        """Test validation of non-existent file"""
        with pytest.raises(ValueError, match="Cannot access file"):
            convert.validate_file_path("/nonexistent/file.mkv")

    def test_validate_file_path_wrong_extension(self):
        """Test validation rejects non-MKV files"""
        # Create a test MP4 file in current directory (allowed directory)
        test_file = Path.cwd() / "test_validate.mp4"
        test_file.write_bytes(b"fake content")

        try:
            with pytest.raises(ValueError, match="Invalid file type"):
                convert.validate_file_path(str(test_file))
        finally:
            test_file.unlink()

    def test_validate_file_path_empty_file(self):
        """Test validation rejects empty files"""
        # Create an empty MKV file in current directory (allowed directory)
        test_file = Path.cwd() / "empty_validate.mkv"
        test_file.touch()  # Create empty file

        try:
            with pytest.raises(ValueError, match="File is empty"):
                convert.validate_file_path(str(test_file))
        finally:
            test_file.unlink()

    def test_validate_file_path_directory_traversal(self):
        """Test validation prevents directory traversal"""
        with pytest.raises((ValueError, FileNotFoundError)):
            convert.validate_file_path("../../../etc/passwd")

    def test_get_allowed_base_dirs_from_config(self):
        """Test that get_allowed_base_dirs reads from real configuration"""
        allowed_dirs = convert.get_allowed_base_dirs()

        # Should return a list of Path objects
        assert isinstance(allowed_dirs, list)
        assert all(isinstance(d, Path) for d in allowed_dirs)

        # Should always include current directory and home directory as defaults
        cwd = Path.cwd().resolve()
        home = Path.home().resolve()

        resolved_dirs = [d.resolve() for d in allowed_dirs]
        assert cwd in resolved_dirs
        assert home in resolved_dirs

        # Check that function can be called multiple times consistently
        allowed_dirs2 = convert.get_allowed_base_dirs()
        assert len(allowed_dirs) == len(allowed_dirs2)

    def test_safe_filename_sanitization(self):
        """Test filename sanitization"""
        # Test dangerous characters
        dangerous_name = 'test/../../../file<>:"?*.mkv'
        safe_name = convert.safe_filename(dangerous_name)
        assert "../" not in safe_name
        assert "<" not in safe_name
        assert ":" not in safe_name
        assert "?" not in safe_name
        assert "*" not in safe_name

        # Test empty input
        assert convert.safe_filename("") == "subtitle"
        assert convert.safe_filename("   ") == "subtitle"

        # Test length limit
        long_name = "a" * 300
        safe_long = convert.safe_filename(long_name)
        assert len(safe_long) <= 200


class TestSecureSubprocessCalls:
    """Test subprocess calls are secure"""

    @patch("subprocess.run")
    def test_analyze_streams_has_timeout(self, mock_run, temp_dir):
        """Test that analyze_streams uses timeout"""
        test_file = temp_dir / "test.mkv"
        test_file.write_bytes(b"fake content")

        mock_result = MagicMock()
        mock_result.stdout = '{"streams": []}'
        mock_run.return_value = mock_result

        convert.analyze_streams("/usr/bin/ffprobe", test_file)

        # Verify timeout was set
        args, kwargs = mock_run.call_args
        assert kwargs.get("timeout") == 60

    @patch("subprocess.run")
    def test_extract_subtitle_has_timeout(self, mock_run, temp_dir):
        """Test that extract_subtitle uses timeout"""
        input_file = temp_dir / "input.mkv"
        output_file = temp_dir / "output.srt"
        input_file.write_bytes(b"fake content")

        mock_run.return_value = MagicMock(returncode=0)

        convert.extract_subtitle("/usr/bin/ffmpeg", input_file, output_file, 3)

        # Verify timeout was set
        args, kwargs = mock_run.call_args
        assert kwargs.get("timeout") == 120

    @patch("subprocess.run")
    def test_find_ffmpeg_tools_has_timeout(self, mock_run):
        """Test that find_ffmpeg_tools uses timeout"""
        mock_ffmpeg_result = MagicMock()
        mock_ffmpeg_result.stdout = "/usr/bin/ffmpeg\n"
        mock_ffprobe_result = MagicMock()
        mock_ffprobe_result.stdout = "/usr/bin/ffprobe\n"

        mock_run.side_effect = [mock_ffmpeg_result, mock_ffprobe_result]

        with patch("pathlib.Path.is_file", return_value=True):
            convert.find_ffmpeg_tools()

        # Verify timeout was set for both calls
        assert mock_run.call_count == 2
        for call in mock_run.call_args_list:
            args, kwargs = call
            assert kwargs.get("timeout") == 10


class TestErrorHandling:
    """Test improved error handling"""

    @patch("subprocess.run")
    def test_analyze_streams_timeout_handling(self, mock_run, temp_dir):
        """Test timeout handling in analyze_streams"""
        test_file = temp_dir / "test.mkv"
        test_file.write_bytes(b"fake content")

        mock_run.side_effect = subprocess.TimeoutExpired("ffprobe", 60)

        with pytest.raises(subprocess.TimeoutExpired):
            convert.analyze_streams("/usr/bin/ffprobe", test_file)

    @patch("subprocess.run")
    def test_analyze_streams_invalid_json_handling(self, mock_run, temp_dir):
        """Test invalid JSON handling in analyze_streams"""
        test_file = temp_dir / "test.mkv"
        test_file.write_bytes(b"fake content")

        mock_result = MagicMock()
        mock_result.stdout = "invalid json"
        mock_run.return_value = mock_result

        with pytest.raises(ValueError, match="FFprobe returned invalid JSON"):
            convert.analyze_streams("/usr/bin/ffprobe", test_file)

    @patch("subprocess.run")
    def test_extract_subtitle_timeout_handling(self, mock_run, temp_dir):
        """Test timeout handling in extract_subtitle"""
        input_file = temp_dir / "input.mkv"
        output_file = temp_dir / "output.srt"
        input_file.write_bytes(b"fake content")

        mock_run.side_effect = subprocess.TimeoutExpired("ffmpeg", 120)

        # Should return False, not raise
        result = convert.extract_subtitle("/usr/bin/ffmpeg", input_file, output_file, 3)
        assert result is False


class TestInputValidation:
    """Test input validation and sanitization"""

    def test_select_streams_validates_structure(self):
        """Test that select_streams validates input structure"""
        # Test missing streams key
        invalid_input = {"format": {}}

        with pytest.raises(KeyError):
            convert.select_streams(invalid_input)

    def test_select_streams_handles_missing_indices(self):
        """Test stream selection handles missing index fields gracefully"""
        streams_missing_index = {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "hevc",
                    # Missing 'index' field
                }
            ]
        }

        with pytest.raises(ValueError, match="No video stream found"):
            convert.select_streams(streams_missing_index)


@pytest.fixture
def secure_test_env():
    """Create a secure test environment"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create test files
        test_mkv = temp_path / "test.mkv"
        test_mkv.write_bytes(b"fake mkv content for testing")

        yield {"temp_dir": temp_path, "test_mkv": test_mkv}
