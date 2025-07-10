"""
Real integration tests - tests actual file conversion with FFmpeg
No mocking - these tests verify the complete conversion pipeline works
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from play_dv_on_windows.config_manager import ConfigManager
from play_dv_on_windows.convert import (
    analyze_streams,
    extract_subtitle,
    find_ffmpeg_tools,
    remux_to_mp4,
    select_streams,
)
from play_dv_on_windows.qbt_post_process import ContentAnalyzer, FileProcessor


@pytest.fixture
def real_mkv_file():
    """Get the real MKV test file"""
    # Try enhanced file first, fall back to original
    enhanced_file = Path(__file__).parent / "data" / "DV8_TEST_with_audio_subs.mkv"
    original_file = Path(__file__).parent / "data" / "DV8_TEST_with_subs.mkv"

    if enhanced_file.exists():
        return enhanced_file
    elif original_file.exists():
        return original_file
    else:
        pytest.skip(f"Test file not found: {enhanced_file} or {original_file}")
        return original_file


@pytest.fixture
def temp_output_dir():
    """Create temporary output directory with proper cleanup"""
    temp_dir_path = None
    try:
        temp_dir_path = tempfile.mkdtemp(prefix="mkv_test_")
        yield Path(temp_dir_path)
    finally:
        # Ensure cleanup even if test fails
        if temp_dir_path and os.path.exists(temp_dir_path):
            shutil.rmtree(temp_dir_path, ignore_errors=True)


@pytest.fixture
def ffmpeg_tools():
    """Get FFmpeg tools - required for tests"""
    ffmpeg, ffprobe = find_ffmpeg_tools()
    assert ffmpeg and ffprobe, "FFmpeg and FFprobe are required for tests"
    return ffmpeg, ffprobe


class TestRealFileConversion:
    """Integration tests using real MKV file"""

    def test_ffmpeg_tools_detection(self, ffmpeg_tools):
        """Test that FFmpeg tools are properly detected"""
        ffmpeg, ffprobe = ffmpeg_tools

        # Test ffmpeg
        result = subprocess.run([ffmpeg, "-version"], capture_output=True, text=True)
        assert result.returncode == 0
        assert "ffmpeg version" in result.stdout

        # Test ffprobe
        result = subprocess.run([ffprobe, "-version"], capture_output=True, text=True)
        assert result.returncode == 0
        assert "ffprobe version" in result.stdout

    def test_analyze_real_mkv_streams(self, real_mkv_file, ffmpeg_tools):
        """Test stream analysis on real MKV file"""
        ffmpeg, ffprobe = ffmpeg_tools

        streams_data = analyze_streams(ffprobe, str(real_mkv_file))

        # Verify we got valid stream data
        assert streams_data is not None
        assert isinstance(streams_data, dict)
        assert "streams" in streams_data

        streams = streams_data["streams"]
        assert len(streams) > 0

        # Check for expected stream types
        video_streams = [s for s in streams if s.get("codec_type") == "video"]
        audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
        subtitle_streams = [s for s in streams if s.get("codec_type") == "subtitle"]

        assert len(video_streams) > 0, "Should have at least one video stream"
        print(
            f"Found {len(video_streams)} video, {len(audio_streams)} audio, "
            f"{len(subtitle_streams)} subtitle streams"
        )

    def test_stream_selection(self, real_mkv_file, ffmpeg_tools):
        """Test stream selection logic on real file"""
        ffmpeg, ffprobe = ffmpeg_tools

        streams_data = analyze_streams(ffprobe, str(real_mkv_file))
        (
            video_idx,
            audio_streams,
            subtitle_streams,
            video_info,
            audio_streams_info,
        ) = select_streams(streams_data)

        # Should select a video stream
        assert video_idx is not None
        assert isinstance(video_idx, int)

        # Audio streams should be a list
        assert isinstance(audio_streams, list)

        # Subtitle streams should be a list (might be empty)
        assert isinstance(subtitle_streams, list)

        print(
            f"Selected: video={video_idx}, audio={len(audio_streams)} streams, "
            f"{len(subtitle_streams)} subtitles"
        )

    def test_subtitle_extraction(self, real_mkv_file, temp_output_dir, ffmpeg_tools):
        """Test subtitle extraction from real file"""
        ffmpeg, ffprobe = ffmpeg_tools

        streams_data = analyze_streams(ffprobe, str(real_mkv_file))
        (
            video_idx,
            audio_streams,
            subtitle_streams,
            video_info,
            audio_streams_info,
        ) = select_streams(streams_data)

        if not subtitle_streams:
            pytest.skip("No subtitle streams found in test file")

        # Extract first subtitle
        subtitle_stream = subtitle_streams[0]
        output_srt = temp_output_dir / "test_movie.srt"

        # The function doesn't return success, it just runs
        extract_subtitle(
            ffmpeg, str(real_mkv_file), str(output_srt), subtitle_stream["index"]
        )

        # Check that subtitle file was created
        srt_files = list(temp_output_dir.glob("*.srt"))
        assert len(srt_files) > 0, "At least one subtitle file should be created"

        # Verify subtitle file has content
        for srt_file in srt_files:
            assert (
                srt_file.stat().st_size > 0
            ), f"Subtitle file {srt_file} should not be empty"
            print(
                f"Created subtitle: {srt_file.name} ({srt_file.stat().st_size} bytes)"
            )

    def test_full_conversion_pipeline(
        self, real_mkv_file, temp_output_dir, ffmpeg_tools
    ):
        """Test complete conversion pipeline on real file"""
        ffmpeg, ffprobe = ffmpeg_tools

        # Copy test file to temp directory to avoid modifying original
        temp_mkv = temp_output_dir / real_mkv_file.name
        shutil.copy2(real_mkv_file, temp_mkv)

        output_mp4 = temp_output_dir / "converted_movie.mp4"

        # Analyze streams first
        streams_data = analyze_streams(ffprobe, str(temp_mkv))
        (
            video_idx,
            audio_streams,
            subtitle_streams,
            video_info,
            audio_streams_info,
        ) = select_streams(streams_data)

        # Run the complete conversion
        success = remux_to_mp4(
            ffmpeg,
            str(temp_mkv),
            str(output_mp4),
            video_idx,
            audio_streams,
            subtitle_streams,
            video_info,
        )

        assert success is True, "Conversion should succeed"

        # Check output files
        assert output_mp4.exists(), "MP4 file should be created"
        assert output_mp4.stat().st_size > 0, "MP4 file should not be empty"

        print(f"Created MP4: {output_mp4.name} ({output_mp4.stat().st_size} bytes)")

        # Verify MP4 file is valid by checking with ffprobe
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                str(output_mp4),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, "ffprobe should be able to read the output MP4"

        format_info = json.loads(result.stdout)
        assert "format" in format_info
        assert format_info["format"]["format_name"] in [
            "mov,mp4,m4a,3gp,3g2,mj2"
        ], "Should be valid MP4 format"

        duration = float(format_info["format"].get("duration", 0))
        assert duration > 0, "MP4 should have valid duration"
        print(f"Output MP4 duration: {duration:.2f} seconds")


class TestFileProcessorIntegration:
    """Integration tests for FileProcessor with real files"""

    def test_file_processor_with_real_file(self, real_mkv_file, temp_output_dir):
        """Test FileProcessor with real file"""
        # Create minimal config
        config = {
            "paths": {"output_dir": str(temp_output_dir)},
            "processing": {
                "parallel_episodes": 1,
                "use_temp_dir": False,
                "delete_after_success": False,
            },
        }

        # Mock logger
        class MockLogger:
            def info(self, msg):
                print(f"INFO: {msg}")

            def warning(self, msg):
                print(f"WARN: {msg}")

            def error(self, msg):
                print(f"ERROR: {msg}")

        logger = MockLogger()
        processor = FileProcessor(config, logger)

        # Copy test file to temp directory
        temp_mkv = temp_output_dir / real_mkv_file.name
        shutil.copy2(real_mkv_file, temp_mkv)

        # Process the file
        results = processor.process_files("DV8_TEST_with_subs", [temp_mkv])

        # Check results
        assert (
            len(results["success"]) > 0
        ), "Should have at least one successful conversion"
        assert len(results["failed"]) == 0, "Should have no failed conversions"

        # Check output files exist (FileProcessor creates subdirectories for Plex)
        output_files = list(temp_output_dir.glob("**/*.mp4"))
        assert len(output_files) > 0, "Should create MP4 files"

        for mp4_file in output_files:
            assert (
                mp4_file.stat().st_size > 0
            ), f"MP4 file {mp4_file} should not be empty"
            print(
                f"Created: {mp4_file.relative_to(temp_output_dir)} "
                f"({mp4_file.stat().st_size} bytes)"
            )


class TestContentAnalyzerIntegration:
    """Integration tests for ContentAnalyzer"""

    def test_content_analyzer_with_real_file(self, real_mkv_file):
        """Test ContentAnalyzer with real file"""
        analyzer = ContentAnalyzer()

        # Test content type determination
        content_type = analyzer.determine_content_type(
            "DV8_TEST_with_subs", [real_mkv_file]
        )

        # Should detect as movie (single file)
        assert content_type == "movie"

        # Test movie info parsing
        movie_info = analyzer.parse_movie_info(real_mkv_file.name)
        assert movie_info is not None
        assert "title" in movie_info
        print(f"Parsed movie info: {movie_info}")


@pytest.mark.slow
class TestEndToEndConversion:
    """End-to-end integration tests (marked as slow)"""

    def test_complete_qbt_workflow(self, real_mkv_file, temp_output_dir):
        """Test complete qBittorrent workflow simulation"""
        # Ensure FFmpeg is available - required for this test
        ffmpeg, ffprobe = find_ffmpeg_tools()
        assert ffmpeg and ffprobe, "FFmpeg and FFprobe are required for this test"

        # Create realistic test config
        config = {
            "paths": {"output_dir": str(temp_output_dir)},
            "processing": {
                "parallel_episodes": 1,
                "delete_after_success": False,
                "min_file_size_gb": 0.001,  # Very small for test file
                "use_temp_dir": False,
                "temp_dir": "/tmp",
            },
            "filters": {
                "require_4k": False,  # Relax for test
                "require_dv": False,  # Relax for test
                "excluded_categories": [],
                "allowed_extensions": [".mkv"],
            },
        }

        # Copy test file to simulate download
        download_dir = temp_output_dir / "downloads"
        download_dir.mkdir()
        temp_mkv = download_dir / real_mkv_file.name
        shutil.copy2(real_mkv_file, temp_mkv)

        # Import the main components (minimal mocking)
        from play_dv_on_windows.qbt_post_process import FileProcessor, TorrentValidator

        class MockLogger:
            def info(self, msg):
                print(f"INFO: {msg}")

            def warning(self, msg):
                print(f"WARN: {msg}")

            def error(self, msg):
                print(f"ERROR: {msg}")

        logger = MockLogger()

        # Step 1: Validate torrent
        validator = TorrentValidator(config)
        is_valid, reason, mkv_files = validator.validate(
            real_mkv_file.name, "movies", str(download_dir)
        )

        print(
            f"Validation result: {is_valid}, reason: {reason}, files: {len(mkv_files)}"
        )
        assert is_valid is True, f"Validation failed: {reason}"
        assert len(mkv_files) > 0, "Should find MKV files"

        # Step 2: Process files
        processor = FileProcessor(config, logger)
        results = processor.process_files("DV8_TEST_with_subs", mkv_files)

        # Step 3: Verify results
        assert len(results["success"]) > 0, "Should have successful conversions"
        assert len(results["failed"]) == 0, "Should have no failures"

        # Step 4: Check output structure
        output_files = list(temp_output_dir.glob("**/*.mp4"))
        subtitle_files = list(temp_output_dir.glob("**/*.srt"))

        assert len(output_files) > 0, "Should create MP4 files"
        print(
            f"Created {len(output_files)} MP4 files and "
            f"{len(subtitle_files)} subtitle files"
        )

        # Verify file integrity
        for mp4_file in output_files:
            assert (
                mp4_file.stat().st_size > 0
            ), f"MP4 file should not be empty: {mp4_file}"

            # Quick ffprobe check
            result = subprocess.run(
                [
                    ffprobe,
                    "-v",
                    "quiet",
                    "-print_format",
                    "json",
                    "-show_format",
                    str(mp4_file),
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                format_info = json.loads(result.stdout)
                duration = float(format_info["format"].get("duration", 0))
                print(
                    f"✅ {mp4_file.name}: {duration:.2f}s, "
                    f"{mp4_file.stat().st_size} bytes"
                )
            else:
                print(f"⚠️ Could not verify {mp4_file.name} with ffprobe")
