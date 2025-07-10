"""
Tests for convert.py module - core MKV to MP4 conversion functionality
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from play_dv_on_windows import convert


class TestFFmpegTools:
    """Test FFmpeg tool detection"""

    @patch("subprocess.run")
    @patch("pathlib.Path.is_file")
    def test_find_ffmpeg_tools_success(self, mock_is_file, mock_run):
        """Test successful FFmpeg detection"""
        # Mock subprocess.run for both ffmpeg and ffprobe
        mock_ffmpeg_result = MagicMock()
        mock_ffmpeg_result.stdout = "/usr/bin/ffmpeg\n"
        mock_ffprobe_result = MagicMock()
        mock_ffprobe_result.stdout = "/usr/bin/ffprobe\n"

        mock_run.side_effect = [mock_ffmpeg_result, mock_ffprobe_result]
        mock_is_file.return_value = True

        ffmpeg_path, ffprobe_path = convert.find_ffmpeg_tools()

        assert ffmpeg_path == "/usr/bin/ffmpeg"
        assert ffprobe_path == "/usr/bin/ffprobe"
        assert mock_run.call_count == 2

    @patch("subprocess.run")
    def test_find_ffmpeg_tools_not_found(self, mock_run):
        """Test FFmpeg not found raises appropriate error"""
        mock_run.side_effect = subprocess.CalledProcessError(1, "which")

        with pytest.raises(FileNotFoundError) as exc_info:
            convert.find_ffmpeg_tools()

        assert "ffmpeg and ffprobe not found" in str(exc_info.value)


class TestStreamAnalysis:
    """Test stream analysis functionality"""

    @patch("subprocess.run")
    def test_analyze_streams_success(self, mock_run, sample_streams_info, temp_dir):
        """Test successful stream analysis"""
        # Create test file
        test_file = temp_dir / "test.mkv"
        test_file.write_bytes(b"fake mkv content")

        mock_result = MagicMock()
        mock_result.stdout = json.dumps(sample_streams_info)
        mock_run.return_value = mock_result

        result = convert.analyze_streams("/usr/bin/ffprobe", test_file)

        assert result == sample_streams_info
        mock_run.assert_called_once()

        # Verify timeout was set
        args, kwargs = mock_run.call_args
        assert kwargs.get("timeout") == 60

    def test_select_streams_with_dv_content(self, sample_streams_info):
        """Test stream selection with Dolby Vision content"""
        (
            video_idx,
            audio_streams,
            sub_streams,
            video_info,
            audio_streams_info,
        ) = convert.select_streams(sample_streams_info)

        # Should select first video stream
        assert video_idx == 0

        # Should select ALL audio streams (not just English)
        assert len(audio_streams) == 2  # English and Spanish
        assert audio_streams[0]["index"] == 1  # English
        assert audio_streams[1]["index"] == 2  # Spanish

        # Should select ALL text-based subtitles (English and Spanish)
        assert len(sub_streams) == 2
        assert sub_streams[0]["index"] == 3  # English SRT
        assert sub_streams[1]["index"] == 4  # Spanish SRT

        # Should return video info
        assert video_info["index"] == 0
        assert video_info["codec_name"] == "hevc"

    def test_select_streams_no_english_audio(self):
        """Test stream selection includes all audio regardless of language"""
        streams_no_eng_audio = {
            "streams": [
                {"index": 0, "codec_type": "video", "codec_name": "hevc"},
                {
                    "index": 1,
                    "codec_type": "audio",
                    "codec_name": "ac3",
                    "tags": {"language": "fra", "title": "French"},
                },
            ]
        }

        (
            video_idx,
            audio_streams,
            sub_streams,
            video_info,
            audio_streams_info,
        ) = convert.select_streams(streams_no_eng_audio)

        assert video_idx == 0
        assert len(audio_streams) == 1  # Should include French audio
        assert audio_streams[0]["index"] == 1
        assert len(sub_streams) == 0

    def test_select_streams_no_video_raises_error(self):
        """Test that missing video stream raises ValueError"""
        streams_no_video = {
            "streams": [
                {
                    "index": 1,
                    "codec_type": "audio",
                    "codec_name": "ac3",
                    "tags": {"language": "eng"},
                }
            ]
        }

        with pytest.raises(ValueError) as exc_info:
            convert.select_streams(streams_no_video)

        assert "No video stream found" in str(exc_info.value)


class TestSubtitleExtraction:
    """Test subtitle extraction functionality"""

    @patch("subprocess.run")
    def test_extract_subtitle_success(self, mock_run, temp_dir):
        """Test successful subtitle extraction"""
        input_file = temp_dir / "input.mkv"
        output_file = temp_dir / "output.srt"
        input_file.write_bytes(b"fake mkv content")

        mock_run.return_value = MagicMock(returncode=0)

        # Should return True for success
        result = convert.extract_subtitle("/usr/bin/ffmpeg", input_file, output_file, 3)
        assert result is True

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]

        # Verify FFmpeg command structure
        assert "/usr/bin/ffmpeg" in args
        assert "-i" in args
        assert str(input_file) in args
        assert "-map" in args
        assert "0:3" in args
        assert "-c:s" in args
        assert "srt" in args
        assert str(output_file) in args

    @patch("subprocess.run")
    def test_extract_subtitle_failure(self, mock_run, temp_dir):
        """Test subtitle extraction failure handling"""
        input_file = temp_dir / "input.mkv"
        output_file = temp_dir / "output.srt"
        input_file.write_bytes(b"fake mkv content")

        mock_run.side_effect = subprocess.CalledProcessError(
            1, "ffmpeg", stderr="FFmpeg error"
        )

        # Should return False for failure (not raise)
        result = convert.extract_subtitle("/usr/bin/ffmpeg", input_file, output_file, 3)
        assert result is False

        mock_run.assert_called_once()


class TestRemuxToMP4:
    """Test MP4 remuxing functionality"""

    @patch("subprocess.Popen")
    def test_remux_to_mp4_success(self, mock_popen, temp_dir):
        """Test successful MP4 remuxing"""
        # Create test files
        input_file = temp_dir / "input.mkv"
        output_file = temp_dir / "output.mp4"
        input_file.write_bytes(b"fake content")

        # Mock successful FFmpeg process
        mock_process = MagicMock()
        mock_process.stdout = ["Progress: 50%\n", "Progress: 100%\n"]
        mock_process.wait.return_value = None
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        audio_streams = [{"index": 1, "codec_name": "eac3"}]
        sub_streams = [{"index": 3}]
        video_info = {"codec_name": "hevc"}

        result = convert.remux_to_mp4(
            "/usr/bin/ffmpeg",
            input_file,
            output_file,
            0,
            audio_streams,
            sub_streams,
            video_info,
        )

        assert result is True
        mock_popen.assert_called_once()

        # Verify command structure
        args = mock_popen.call_args[0][0]
        assert "/usr/bin/ffmpeg" in args
        assert "-i" in args
        assert str(input_file) in args
        assert "-c:v" in args
        assert "copy" in args
        assert "-map_metadata" in args
        assert str(output_file) in args

    @patch("subprocess.Popen")
    def test_remux_to_mp4_failure(self, mock_popen, temp_dir):
        """Test MP4 remuxing failure handling"""
        # Create test files
        input_file = temp_dir / "input.mkv"
        output_file = temp_dir / "output.mp4"
        input_file.write_bytes(b"fake content")

        # Mock failed FFmpeg process
        mock_process = MagicMock()
        mock_process.stdout = ["Error occurred\n"]
        mock_process.wait.return_value = None
        mock_process.returncode = 1
        mock_popen.return_value = mock_process

        result = convert.remux_to_mp4(
            "/usr/bin/ffmpeg", input_file, output_file, 0, [], [], None
        )

        assert result is False

    @patch("subprocess.Popen")
    def test_remux_preserves_dolby_vision_metadata(self, mock_popen, temp_dir):
        """Test that remuxing preserves Dolby Vision metadata"""
        # Create test files
        input_file = temp_dir / "input.mkv"
        output_file = temp_dir / "output.mp4"
        input_file.write_bytes(b"fake content")

        mock_process = MagicMock()
        mock_process.stdout = []
        mock_process.wait.return_value = None
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        video_info = {
            "codec_name": "hevc",
            "side_data_list": [{"side_data_type": "DOVI configuration record"}],
        }

        convert.remux_to_mp4(
            "/usr/bin/ffmpeg", input_file, output_file, 0, [], [], video_info
        )

        # Verify metadata preservation flags are included
        args = mock_popen.call_args[0][0]
        assert "-map_metadata" in args
        assert "0" in args
        assert "-map_metadata:s:v" in args
        assert "0:s:v" in args


class TestMainFunction:
    """Test main function and argument handling"""

    def test_main_no_arguments(self, temp_dir):
        """Test main function with no arguments"""
        with patch("play_dv_on_windows.convert.find_ffmpeg_tools") as mock_find_tools:
            mock_find_tools.return_value = ("/usr/bin/ffmpeg", "/usr/bin/ffprobe")

            with patch("sys.argv", ["convert"]):  # argparse expects prog name only
                with pytest.raises(SystemExit) as exc_info:
                    convert.main()

                # argparse exits with 2 for missing required arguments
                assert exc_info.value.code == 2

    def test_main_file_not_found(self, temp_dir):
        """Test main function with non-existent file"""
        with patch("play_dv_on_windows.convert.find_ffmpeg_tools") as mock_find_tools:
            mock_find_tools.return_value = ("/usr/bin/ffmpeg", "/usr/bin/ffprobe")

            with patch("sys.argv", ["convert.py", "nonexistent.mkv"]):
                with patch("builtins.print"):
                    with pytest.raises(SystemExit) as exc_info:
                        convert.main()

                    # Should exit with error code due to failed conversion
                    assert exc_info.value.code == 1

    @patch("play_dv_on_windows.convert.find_ffmpeg_tools")
    @patch("play_dv_on_windows.convert.analyze_streams")
    @patch("play_dv_on_windows.convert.select_streams")
    @patch("play_dv_on_windows.convert.extract_subtitle")
    @patch("play_dv_on_windows.convert.remux_to_mp4")
    def test_main_successful_conversion(
        self, mock_remux, mock_extract, mock_select, mock_analyze, mock_find_tools
    ):
        """Test main function with successful conversion using temp file"""
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test MKV file in temp directory
            test_mkv = Path(temp_dir) / "test_file.mkv"
            test_mkv.write_bytes(b"fake mkv content")

            # Mock all dependencies
            mock_find_tools.return_value = ("/usr/bin/ffmpeg", "/usr/bin/ffprobe")
            mock_analyze.return_value = {"streams": []}
            mock_select.return_value = (
                0,
                1,
                [{"index": 3, "tags": {"title": "English"}}],
                {},
                {"codec_name": "eac3"},
            )
            mock_extract.return_value = True
            mock_remux.return_value = True

            with patch("sys.argv", ["convert", str(test_mkv)]):
                with pytest.raises(SystemExit) as exc_info:
                    convert.main()

                # Should exit with success code
                assert exc_info.value.code == 0

                # Verify functions were called
                mock_analyze.assert_called_once()
                mock_select.assert_called_once()
                mock_extract.assert_called_once()
                mock_remux.assert_called_once()


# OpenSubtitles integration removed - API no longer free
