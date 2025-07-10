"""
Integration tests for the MKV to MP4 converter system
Tests the interaction between modules and end-to-end workflows
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from play_dv_on_windows import convert, qbt_post_process


class TestIntegration:
    """Test integration between convert.py and qbt_post_process.py"""

    @pytest.fixture
    def integration_config(self, temp_dir):
        """Configuration for integration tests"""
        output_dir = temp_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        return {
            "qbittorrent": {
                "host": "localhost",
                "port": 8080,
                "username": "admin",
                "password": "test",
            },
            "paths": {"output_dir": str(output_dir)},
            "processing": {
                "parallel_episodes": 1,
                "delete_after_success": False,
                "use_temp_dir": False,
                "min_file_size_gb": 1,
            },
            "filters": {
                "require_4k": True,
                "require_dv": True,
                "excluded_categories": [],
                "max_seasons_per_torrent": 1,
                "allowed_extensions": [".mkv"],
            },
        }

    @patch("play_dv_on_windows.convert.find_ffmpeg_tools")
    @patch("play_dv_on_windows.convert.analyze_streams")
    @patch("play_dv_on_windows.convert.select_streams")
    @patch("play_dv_on_windows.convert.extract_subtitle")
    @patch("play_dv_on_windows.convert.remux_to_mp4")
    def test_end_to_end_movie_processing(
        self,
        mock_remux,
        mock_extract,
        mock_select,
        mock_analyze,
        mock_find_tools,
        integration_config,
        temp_dir,
        create_test_mkv,
    ):
        """Test complete movie processing workflow"""
        # Setup mocks
        mock_find_tools.return_value = ("/usr/bin/ffmpeg", "/usr/bin/ffprobe")
        mock_analyze.return_value = {"streams": []}
        mock_select.return_value = (
            0,
            1,
            [{"index": 3, "tags": {"title": "English"}}],
            {},
        )
        mock_remux.return_value = True

        # Create test MKV file
        test_mkv = temp_dir / "Dune.Part.Two.2024.2160p.DV.mkv"
        create_test_mkv(test_mkv, size_gb=2.0)

        # Test torrent validation
        validator = qbt_post_process.TorrentValidator(integration_config)
        is_valid, reason, mkv_files = validator.validate(
            "Dune.Part.Two.2024.2160p.DV", "", str(test_mkv)
        )

        assert is_valid is True
        assert len(mkv_files) == 1

        # Test file processing
        logger = MagicMock()
        processor = qbt_post_process.FileProcessor(integration_config, logger)

        with patch(
            "play_dv_on_windows.qbt_post_process.FileProcessor._convert_file"
        ) as mock_convert:
            mock_convert.return_value = True

            results = processor.process_files("Dune.Part.Two.2024.2160p.DV", mkv_files)

            assert len(results["success"]) == 1
            assert len(results["failed"]) == 0

            # Verify output folder was created
            expected_folder = (
                Path(integration_config["paths"]["output_dir"]) / "Dune Part Two 2024"
            )
            assert expected_folder.exists()

    @patch("play_dv_on_windows.convert.find_ffmpeg_tools")
    @patch("play_dv_on_windows.convert.analyze_streams")
    @patch("play_dv_on_windows.convert.select_streams")
    @patch("play_dv_on_windows.convert.extract_subtitle")
    @patch("play_dv_on_windows.convert.remux_to_mp4")
    def test_end_to_end_tv_show_processing(
        self,
        mock_remux,
        mock_extract,
        mock_select,
        mock_analyze,
        mock_find_tools,
        integration_config,
        temp_dir,
        create_test_mkv,
    ):
        """Test complete TV show processing workflow"""
        # Setup mocks
        mock_find_tools.return_value = ("/usr/bin/ffmpeg", "/usr/bin/ffprobe")
        mock_analyze.return_value = {"streams": []}
        mock_select.return_value = (
            0,
            1,
            [{"index": 3, "tags": {"title": "English"}}],
            {},
        )
        mock_remux.return_value = True

        # Create test TV show files
        mkv_files = []
        for i in range(1, 4):
            test_mkv = temp_dir / f"House.of.the.Dragon.S02E{i:02d}.2160p.DV.mkv"
            create_test_mkv(test_mkv, size_gb=2.0)
            mkv_files.append(test_mkv)

        # Test torrent validation
        validator = qbt_post_process.TorrentValidator(integration_config)
        is_valid, reason, validated_files = validator.validate(
            "House.of.the.Dragon.S02.2160p.DV", "", str(temp_dir)
        )

        assert is_valid is True
        assert len(validated_files) == 3

        # Test file processing
        logger = MagicMock()
        processor = qbt_post_process.FileProcessor(integration_config, logger)

        with patch(
            "play_dv_on_windows.qbt_post_process.FileProcessor._convert_file"
        ) as mock_convert:
            mock_convert.return_value = True

            results = processor.process_files(
                "House.of.the.Dragon.S02.2160p.DV", validated_files
            )

            assert len(results["success"]) == 3
            assert len(results["failed"]) == 0

            # Verify output folder was created
            expected_folder = (
                Path(integration_config["paths"]["output_dir"])
                / "House of the Dragon S02"
            )
            assert expected_folder.exists()

    def test_dolby_vision_detection_integration(self, integration_config):
        """Test that Dolby Vision detection works correctly in both modules"""
        # Test validation module
        validator = qbt_post_process.TorrentValidator(integration_config)

        # Should accept DV content
        assert validator.dv_patterns[0].search("Movie.2024.2160p.DV.mkv")
        assert validator.dv_patterns[1].search("Movie.2024.2160p.DoVi.mkv")
        assert validator.dv_patterns[2].search("Movie.2024.2160p.Dolby.Vision.mkv")

        # Should reject non-DV content
        assert not any(
            pattern.search("Movie.2024.2160p.HDR.mkv")
            for pattern in validator.dv_patterns
        )
        assert not any(
            pattern.search("Movie.2024.1080p.DV.mkv")
            for pattern in validator.resolution_patterns
        )

    def test_stream_selection_integration(self, sample_streams_info):
        """Test stream selection works with realistic data"""
        (
            video_idx,
            audio_streams,
            sub_streams,
            video_info,
            audio_streams_info,
        ) = convert.select_streams(sample_streams_info)

        # Should select video stream with DV
        assert video_idx == 0
        assert video_info["codec_name"] == "hevc"
        assert video_info["color_transfer"] == "smpte2084"

        # Should select all audio streams
        assert len(audio_streams) == 2
        assert audio_streams[0]["index"] == 1  # English
        assert audio_streams[1]["index"] == 2  # Spanish

        # Should select ALL text-based subtitles (English and Spanish)
        assert len(sub_streams) == 2
        assert sub_streams[0]["index"] == 3  # English
        assert sub_streams[1]["index"] == 4  # Spanish

    def test_filename_cleaning_integration(self, integration_config, temp_dir):
        """Test filename cleaning works correctly"""
        processor = qbt_post_process.FileProcessor(integration_config, MagicMock())

        # Test movie name cleaning
        test_cases = [
            ("Dune.Part.Two.2024.2160p.DV.FLUX", "Dune Part Two 2024"),
            ("House.of.the.Dragon.S02.2160p.DV.HMAX", "House of the Dragon S02"),
            ("Movie.Name.2024.4K.DoVi.x265-GROUP", "Movie Name 2024"),
        ]

        for input_name, expected_clean in test_cases:
            with patch(
                "play_dv_on_windows.qbt_post_process.FileProcessor._convert_file"
            ) as mock_convert:
                mock_convert.return_value = True

                test_mkv = temp_dir / f"{input_name}.mkv"
                test_mkv.touch()

                result = processor._process_file_for_plex(test_mkv, input_name)

                assert result["success"] is True

                # Check that clean folder was created
                output_dir = Path(integration_config["paths"]["output_dir"])
                expected_folder = output_dir / expected_clean
                assert (
                    expected_folder.exists()
                ), f"Expected folder {expected_folder} was not created"
