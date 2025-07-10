"""
Tests for qbt_post_process.py module - qBittorrent post-processing functionality
"""

import json
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from play_dv_on_windows import qbt_post_process


class TestQBittorrentAPI:
    """Test qBittorrent API functionality"""

    @pytest.fixture
    def api_config(self):
        """Configuration for API tests"""
        return {
            "qbittorrent": {
                "host": "localhost",
                "port": 8080,
                "username": "admin",
                "password": "password",
            }
        }

    @patch("requests.Session")
    def test_api_login_success(self, mock_session_class, api_config):
        """Test successful API login"""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Ok."
        mock_response.status_code = 200
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session

        api = qbt_post_process.QBittorrentAPI(api_config)

        assert api.enabled is True
        mock_session.post.assert_called_once()

    @patch("requests.Session")
    def test_api_login_failure(self, mock_session_class, api_config):
        """Test failed API login"""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Fails."
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session

        with patch("logging.warning"):
            api = qbt_post_process.QBittorrentAPI(api_config)

            assert api.enabled is False

    @patch("requests.Session")
    def test_add_tags(self, mock_session_class, api_config):
        """Test adding tags to torrent"""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Ok."
        mock_response.status_code = 200
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session

        api = qbt_post_process.QBittorrentAPI(api_config)
        # Use valid SHA-1 hash format (40 hex characters)
        valid_hash = "1234567890abcdef1234567890abcdef12345678"
        result = api.add_tags(valid_hash, ["processing", "test"])

        assert result is True
        # Should be called twice: login + add_tags
        assert mock_session.post.call_count == 2

    @patch("requests.Session")
    def test_delete_torrent(self, mock_session_class, api_config):
        """Test deleting torrent"""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Ok."
        mock_response.status_code = 200
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session

        api = qbt_post_process.QBittorrentAPI(api_config)
        # Use valid SHA-1 hash format (40 hex characters)
        valid_hash = "1234567890abcdef1234567890abcdef12345678"
        result = api.delete_torrent(valid_hash, delete_files=True)

        assert result is True


class TestTorrentValidator:
    """Test torrent validation functionality"""

    @pytest.fixture
    def validator_config(self):
        """Configuration for validator tests"""
        return {
            "filters": {
                "require_4k": True,
                "require_dv": True,
                "excluded_categories": ["music", "software"],
                "max_seasons_per_torrent": 1,
                "allowed_extensions": [".mkv"],
            },
            "processing": {"min_file_size_gb": 1},
        }

    def test_validate_4k_dv_movie(self, validator_config, temp_dir, create_test_mkv):
        """Test validation of 4K Dolby Vision movie"""
        validator = qbt_post_process.TorrentValidator(validator_config)

        # Create test MKV file
        test_mkv = temp_dir / "Movie.2024.2160p.DV.mkv"
        create_test_mkv(test_mkv, size_gb=2.0)

        is_valid, reason, mkv_files = validator.validate(
            "Movie.2024.2160p.DV.mkv", "movies", str(test_mkv)
        )

        assert is_valid is True
        assert reason == "Valid"
        assert len(mkv_files) == 1
        assert mkv_files[0].name == "Movie.2024.2160p.DV.mkv"

    def test_validate_rejected_non_4k(self, validator_config):
        """Test rejection of non-4K content"""
        validator = qbt_post_process.TorrentValidator(validator_config)

        is_valid, reason, mkv_files = validator.validate(
            "Movie.2024.1080p.mkv", "movies", "/fake/path"
        )

        assert is_valid is False
        assert reason == "Not 4K content"
        assert len(mkv_files) == 0

    def test_validate_rejected_non_dv(self, validator_config):
        """Test rejection of non-Dolby Vision content"""
        validator = qbt_post_process.TorrentValidator(validator_config)

        is_valid, reason, mkv_files = validator.validate(
            "Movie.2024.2160p.HDR.mkv", "movies", "/fake/path"
        )

        assert is_valid is False
        assert reason == "Not Dolby Vision content"
        assert len(mkv_files) == 0

    def test_validate_rejected_excluded_category(self, validator_config):
        """Test rejection of excluded categories"""
        validator = qbt_post_process.TorrentValidator(validator_config)

        is_valid, reason, mkv_files = validator.validate(
            "Music.Album.2160p.DV.mkv", "music", "/fake/path"
        )

        assert is_valid is False
        assert reason == "Excluded category: music"
        assert len(mkv_files) == 0

    def test_validate_tv_show_single_season(
        self, validator_config, temp_dir, create_test_mkv
    ):
        """Test validation of single season TV show"""
        validator = qbt_post_process.TorrentValidator(validator_config)

        # Create test MKV files
        for i in range(1, 9):
            test_mkv = temp_dir / f"Show.S01E{i:02d}.2160p.DV.mkv"
            create_test_mkv(test_mkv, size_gb=2.0)

        is_valid, reason, mkv_files = validator.validate(
            "Show.S01.2160p.DV.mkv", "tv", str(temp_dir)
        )

        assert is_valid is True
        assert reason == "Valid"
        assert len(mkv_files) == 8

    def test_validate_rejected_multi_season(self, validator_config):
        """Test rejection of multi-season torrents"""
        validator = qbt_post_process.TorrentValidator(validator_config)

        is_valid, reason, mkv_files = validator.validate(
            "Show.S01-S05.2160p.DV.mkv", "tv", "/fake/path"
        )

        assert is_valid is False
        assert "Too many seasons" in reason
        assert len(mkv_files) == 0


class TestContentAnalyzer:
    """Test content analysis functionality"""

    @pytest.fixture
    def analyzer(self):
        """Content analyzer instance"""
        return qbt_post_process.ContentAnalyzer()

    def test_determine_movie_content_type(self, analyzer):
        """Test movie content type detection"""
        mkv_files = [Path("Movie.Name.2024.2160p.DV.mkv")]
        content_type = analyzer.determine_content_type(
            "Movie.Name.2024.2160p.DV", mkv_files
        )

        assert content_type == "movie"

    def test_determine_tv_content_type(self, analyzer):
        """Test TV show content type detection"""
        mkv_files = [
            Path("Show.S01E01.mkv"),
            Path("Show.S01E02.mkv"),
            Path("Show.S01E03.mkv"),
        ]
        content_type = analyzer.determine_content_type("Show.S01.2160p.DV", mkv_files)

        assert content_type == "tv"

    def test_parse_movie_info(self, analyzer):
        """Test movie information parsing"""
        movie_info = analyzer.parse_movie_info("Dune.Part.Two.2024.2160p.DV.mkv")

        assert movie_info["title"] == "Dune Part Two"
        assert movie_info["year"] == "2024"
        assert movie_info["quality"] == "2160p"
        assert movie_info["hdr"] == "DV"

    def test_parse_show_info(self, analyzer):
        """Test TV show information parsing"""
        show_info = analyzer.parse_show_info("House.of.the.Dragon.S02.2160p.DV")

        assert show_info["show_name"] == "House of the Dragon"
        assert show_info["season"] == 2

    def test_parse_episode_info(self, analyzer):
        """Test episode information parsing"""
        episode_info = analyzer.parse_episode_info("Show.S02E05.2160p.DV.mkv")

        assert episode_info is not None
        assert episode_info["season"] == 2
        assert episode_info["episode"] == 5

    def test_parse_episode_info_no_match(self, analyzer):
        """Test episode parsing with no match"""
        episode_info = analyzer.parse_episode_info("Movie.2024.mkv")

        assert episode_info is None


class TestFileProcessor:
    """Test file processing functionality"""

    @pytest.fixture
    def processor_config(self, temp_dir):
        """Configuration for processor tests"""
        output_dir = temp_dir / "output"
        output_dir.mkdir()

        return {
            "paths": {"output_dir": str(output_dir)},
            "processing": {
                "parallel_episodes": 2,
                "use_temp_dir": False,
                "temp_dir": "/tmp",
                "delete_after_success": False,
            },
        }

    @patch("play_dv_on_windows.qbt_post_process.FileProcessor._convert_file")
    def test_process_single_file(
        self, mock_convert, processor_config, mock_logger, temp_dir
    ):
        """Test processing single file (movie)"""
        mock_convert.return_value = True

        processor = qbt_post_process.FileProcessor(processor_config, mock_logger)

        # Create test MKV file
        test_mkv = temp_dir / "Movie.2024.2160p.DV.mkv"
        test_mkv.touch()

        results = processor.process_files("Movie.2024.2160p.DV", [test_mkv])

        assert len(results["success"]) == 1
        assert len(results["failed"]) == 0
        mock_convert.assert_called_once()

    @patch("play_dv_on_windows.qbt_post_process.FileProcessor._convert_file")
    def test_process_multiple_files_parallel(
        self, mock_convert, processor_config, mock_logger, temp_dir
    ):
        """Test processing multiple files in parallel (TV show)"""
        mock_convert.return_value = True

        processor = qbt_post_process.FileProcessor(processor_config, mock_logger)

        # Create test MKV files
        mkv_files = []
        for i in range(1, 5):
            test_mkv = temp_dir / f"Show.S01E{i:02d}.mkv"
            test_mkv.touch()
            mkv_files.append(test_mkv)

        results = processor.process_files("Show.S01.2160p.DV", mkv_files)

        assert len(results["success"]) == 4
        assert len(results["failed"]) == 0
        assert mock_convert.call_count == 4

    @patch("play_dv_on_windows.qbt_post_process.FileProcessor._convert_file")
    def test_process_files_with_failure(
        self, mock_convert, processor_config, mock_logger, temp_dir
    ):
        """Test processing with some failures"""
        # First two succeed, last two fail
        mock_convert.side_effect = [True, True, False, False]

        processor = qbt_post_process.FileProcessor(processor_config, mock_logger)

        mkv_files = []
        for i in range(1, 5):
            test_mkv = temp_dir / f"Show.S01E{i:02d}.mkv"
            test_mkv.touch()
            mkv_files.append(test_mkv)

        results = processor.process_files("Show.S01.2160p.DV", mkv_files)

        assert len(results["success"]) == 2
        assert len(results["failed"]) == 2

    def test_process_file_for_plex_folder_creation(
        self, processor_config, mock_logger, temp_dir
    ):
        """Test that proper Plex folder structure is created"""
        processor = qbt_post_process.FileProcessor(processor_config, mock_logger)

        test_mkv = temp_dir / "Movie.Name.2024.2160p.DV.FLUX.mkv"
        test_mkv.touch()

        with patch(
            "play_dv_on_windows.qbt_post_process.FileProcessor._convert_file"
        ) as mock_convert:
            mock_convert.return_value = True

            result = processor._process_file_for_plex(
                test_mkv, "Movie.Name.2024.2160p.DV.FLUX"
            )

            assert result["success"] is True

            # Check that clean folder was created
            output_dir = Path(processor_config["paths"]["output_dir"])
            expected_folder = output_dir / "Movie Name 2024"
            assert expected_folder.exists()

    @patch("shutil.move")
    @patch("subprocess.run")
    @patch("sys.executable")
    def test_convert_file_success(
        self,
        mock_executable,
        mock_subprocess,
        mock_move,
        processor_config,
        mock_logger,
        temp_dir,
    ):
        """Test successful file conversion"""
        mock_executable.__str__ = lambda: "python"
        mock_subprocess.return_value = MagicMock(returncode=0)

        processor = qbt_post_process.FileProcessor(processor_config, mock_logger)

        # Create mock source file
        test_mkv = temp_dir / "test.mkv"
        test_mkv.write_bytes(b"fake mkv content")

        output_dir = Path(processor_config["paths"]["output_dir"])
        output_base = output_dir / "test"

        # Create the mock converted file in the output directory (where convert.py
        # creates it)
        output_dir.mkdir(parents=True, exist_ok=True)
        test_mp4 = output_dir / "test.mp4"
        test_mp4.write_bytes(b"fake mp4 content")  # Simulate converted file

        # Mock the security validation methods
        with patch.object(processor, "_validate_file_path", return_value=True):
            with patch.object(processor, "_validate_converted_file", return_value=True):
                with patch.object(processor, "_secure_file_move", return_value=True):
                    with patch.object(
                        processor, "_sanitize_filename", return_value="test"
                    ):
                        with patch("play_dv_on_windows.convert.main") as mock_convert:
                            # Mock convert_main to do nothing (successful conversion)
                            mock_convert.return_value = None
                            with patch.object(
                                processor, "_check_disk_space", return_value=True
                            ):
                                result = processor._convert_file(test_mkv, output_base)

                                assert result is True
                                mock_convert.assert_called_once()


class TestMainFunction:
    """Test main function and argument handling"""

    @patch("play_dv_on_windows.qbt_post_process.ConfigManager")
    def test_main_insufficient_arguments(self, mock_config_manager):
        """Test main function with insufficient arguments"""
        with patch("sys.argv", ["qbt_post_process.py", "arg1", "arg2"]):
            with pytest.raises(SystemExit) as exc_info:
                qbt_post_process.main()

            assert exc_info.value.code == 1

    @patch("play_dv_on_windows.qbt_post_process.ConfigManager")
    @patch("play_dv_on_windows.qbt_post_process.setup_logging")
    @patch("play_dv_on_windows.qbt_post_process.QBittorrentAPI")
    @patch("play_dv_on_windows.qbt_post_process.TorrentValidator")
    @patch("play_dv_on_windows.qbt_post_process.FileProcessor")
    def test_main_successful_processing(
        self,
        mock_processor_class,
        mock_validator_class,
        mock_api_class,
        mock_logging,
        mock_config_manager,
    ):
        """Test main function with successful processing"""
        # Mock configuration manager
        mock_config_instance = MagicMock()
        mock_config_instance.config = {
            "processing": {"delete_after_success": False},
            "paths": {"output_dir": "/test/output"},
            "qbittorrent": {"host": "localhost", "port": 8080},
        }
        mock_config_instance.validate_config.return_value = True
        mock_config_manager.return_value = mock_config_instance

        # Mock logger
        mock_logger = MagicMock()
        mock_logging.return_value = mock_logger

        # Mock validator
        mock_validator = MagicMock()
        mock_validator.validate.return_value = (True, "Valid", [Path("test.mkv")])
        mock_validator_class.return_value = mock_validator

        # Mock processor
        mock_processor = MagicMock()
        mock_processor.process_files.return_value = {
            "success": [{"file": "test.mp4"}],
            "failed": [],
        }
        mock_processor_class.return_value = mock_processor

        # Mock API
        mock_api = MagicMock()
        mock_api.enabled = True
        mock_api_class.return_value = mock_api

        with patch(
            "sys.argv",
            ["qbt_post_process.py", "test_torrent", "/path/to/content", "hash123"],
        ):
            with patch(
                "play_dv_on_windows.qbt_post_process.create_status_file"
            ) as mock_status_file:
                # Should not raise any exceptions
                qbt_post_process.main()

                # Verify components were called
                mock_validator.validate.assert_called_once()
                mock_processor.process_files.assert_called_once()
