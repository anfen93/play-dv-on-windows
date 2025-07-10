import argparse
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Import config manager
try:
    from .config_manager import ConfigManager

    _config_manager = ConfigManager()
    _config = _config_manager.config
except ImportError:
    # Fallback if config_manager is not available
    _config = None

# Removed OpenSubtitles integration (no longer free)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("conversion.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def get_allowed_base_dirs() -> List[Path]:
    """
    Get allowed base directories from configuration.
    Falls back to secure defaults if configuration is not available.
    """
    allowed_dirs = []

    # Try to get from configuration
    if _config and "paths" in _config and "allowed_base_dirs" in _config["paths"]:
        config_dirs = _config["paths"]["allowed_base_dirs"]
        for dir_path in config_dirs:
            if dir_path == ".":
                allowed_dirs.append(Path.cwd())
            elif dir_path == "~":
                allowed_dirs.append(Path.home())
            else:
                # Expand user path and resolve
                expanded_path = Path(dir_path).expanduser().resolve()
                if expanded_path.exists():
                    allowed_dirs.append(expanded_path)
                else:
                    logger.warning(
                        f"Configured allowed directory does not exist: {dir_path}"
                    )
    else:
        # Fallback to secure defaults
        logger.warning(
            "No allowed_base_dirs configuration found, using secure defaults"
        )
        allowed_dirs = [Path.cwd(), Path.home()]

    # Allow tests to add temporary directories via environment variable
    if os.environ.get("PYTEST_CURRENT_TEST"):
        # Only during test runs, add common temp directories
        import tempfile

        temp_dir = Path(tempfile.gettempdir())
        if temp_dir not in allowed_dirs:
            allowed_dirs.append(temp_dir)

    return allowed_dirs


def validate_file_path(file_path: str) -> Path:
    """
    Validate and resolve file path to prevent directory traversal attacks.

    Args:
        file_path: The file path to validate

    Returns:
        Resolved Path object

    Raises:
        ValueError: If path is invalid or outside allowed directories
        FileNotFoundError: If file doesn't exist
    """
    try:
        # Convert to Path and resolve to absolute path
        path = Path(file_path).resolve()

        # Check if file exists
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Get allowed directories from configuration
        allowed_base_dirs = get_allowed_base_dirs()

        # Check if path is within allowed directories
        is_allowed = any(
            str(path).startswith(str(allowed_dir.resolve()))
            for allowed_dir in allowed_base_dirs
        )

        if not is_allowed:
            # Allow files in subdirectories of current working directory
            cwd = Path.cwd().resolve()
            if not str(path).startswith(str(cwd)):
                raise ValueError(f"File path not in allowed directory: {file_path}")

        # Validate file extension
        if path.suffix.lower() != ".mkv":
            raise ValueError(f"Invalid file type. Expected .mkv, got: {path.suffix}")

        # Basic file size check (not empty, not too large)
        file_size = path.stat().st_size
        if file_size == 0:
            raise ValueError(f"File is empty: {file_path}")

        # Warn if file is very large (> 100GB)
        if file_size > 100 * 1024**3:
            logger.warning(f"Very large file detected: {file_size / 1024**3:.1f} GB")

        return path

    except (OSError, PermissionError) as e:
        raise ValueError(f"Cannot access file: {file_path} - {e}")


def find_ffmpeg_tools() -> Tuple[str, str]:
    """
    Checks for the presence of ffmpeg and ffprobe in common locations.
    Returns the paths to ffmpeg and ffprobe if found, otherwise raises an error.
    """
    try:
        # Use absolute paths and timeout for security
        ffmpeg_result = subprocess.run(
            ["where" if os.name == "nt" else "which", "ffmpeg"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        ffprobe_result = subprocess.run(
            ["where" if os.name == "nt" else "which", "ffprobe"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )

        ffmpeg_path = ffmpeg_result.stdout.strip()
        ffprobe_path = ffprobe_result.stdout.strip()

        # Validate the tools exist and are executable
        if not Path(ffmpeg_path).is_file():
            raise FileNotFoundError(f"FFmpeg not found at: {ffmpeg_path}")
        if not Path(ffprobe_path).is_file():
            raise FileNotFoundError(f"FFprobe not found at: {ffprobe_path}")

        logger.info(f"Found ffmpeg at: {ffmpeg_path}")
        logger.info(f"Found ffprobe at: {ffprobe_path}")

        return ffmpeg_path, ffprobe_path

    except subprocess.TimeoutExpired:
        raise FileNotFoundError("Timeout while searching for FFmpeg tools")
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise FileNotFoundError(
            "ERROR: ffmpeg and ffprobe not found in the system's PATH.\n"
            "Please make sure FFmpeg is installed and that its 'bin' "
            "directory is added to your system's environment variables."
        )


def analyze_streams(ffprobe_path: str, file_path) -> Dict[str, Any]:
    """
    Uses ffprobe to get detailed information about all streams in a video file.

    Args:
        ffprobe_path: Path to ffprobe executable
        file_path: Path to the media file (str or Path object)

    Returns:
        Dictionary parsed from the JSON output

    Raises:
        subprocess.CalledProcessError: If ffprobe fails
        json.JSONDecodeError: If output is not valid JSON
        subprocess.TimeoutExpired: If operation times out
    """
    # Convert to Path object if it's a string
    if isinstance(file_path, str):
        file_path = Path(file_path)

    logger.info(f"Analyzing streams for: {file_path.name}")

    # Build command with validated paths
    command = [
        ffprobe_path,
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",  # Also get format info for better detection
        str(file_path),  # Convert Path to string safely
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            timeout=60,  # 60 second timeout for analysis
        )

        # Validate JSON output
        if not result.stdout.strip():
            raise ValueError("FFprobe returned empty output")

        stream_data = json.loads(result.stdout)

        # Validate expected structure
        if "streams" not in stream_data:
            raise ValueError("Invalid FFprobe output: missing 'streams' key")

        logger.debug(f"Found {len(stream_data['streams'])} streams")
        return stream_data

    except subprocess.TimeoutExpired:
        logger.error(f"FFprobe analysis timed out for: {file_path.name}")
        raise
    except subprocess.CalledProcessError as e:
        logger.error(f"FFprobe failed: {e.stderr}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON from FFprobe: {e}")
        raise ValueError(f"FFprobe returned invalid JSON: {e}")


def select_streams(
    streams_info: Dict[str, Any],
) -> Tuple[int, List[Dict], List[Dict], Optional[Dict], List[Dict]]:
    """
    Selects the best video, ALL audio streams, and text-based subtitle streams.
    Detects Dolby Vision and HDR content.

    Args:
        streams_info: Stream information from FFprobe

    Returns:
        Tuple of (video_index, audio_streams, subtitle_streams,
                  video_info, audio_streams_info)

    Raises:
        ValueError: If no video stream is found
    """
    video_stream_index = None
    video_stream_info = None
    audio_streams = []  # List to hold all audio streams
    subtitle_streams = []  # List to hold text-based subtitle streams only

    # Only text-based subtitles that can be extracted to SRT
    # (Windows Media Player compatible)
    text_subtitle_codecs = ["subrip", "ass", "mov_text"]

    for stream in streams_info["streams"]:
        stream_index = stream.get("index")
        codec_type = stream.get("codec_type")

        if codec_type == "video" and video_stream_index is None:
            video_stream_index = stream_index
            video_stream_info = stream
            logger.info(f"Found video stream at index: {video_stream_index}")

            # Check for Dolby Vision
            if "side_data_list" in stream:
                for side_data in stream["side_data_list"]:
                    if side_data.get("side_data_type") == "DOVI configuration record":
                        logger.info("Dolby Vision detected!")

            # Check color info
            color_transfer = stream.get("color_transfer")
            if color_transfer == "smpte2084":
                logger.info("HDR10 transfer function detected")
            elif color_transfer == "arib-std-b67":
                logger.info("HLG transfer function detected")

        elif codec_type == "audio":
            # Include ALL audio streams, not just English
            codec_name = stream.get("codec_name", "unknown")
            language = stream.get("tags", {}).get("language", "unknown")
            title = stream.get("tags", {}).get("title", f"Audio {stream_index}")

            audio_streams.append(stream)
            logger.info(
                f"Found audio stream at index: {stream_index} "
                f"(Language: {language}, Codec: {codec_name}, Title: {title})"
            )

        elif codec_type == "subtitle":
            language = stream.get("tags", {}).get("language", "").lower()
            codec_name = stream.get("codec_name")
            title = stream.get("tags", {}).get("title", f"Track {stream_index}")

            # Only include text-based subtitles that can be converted
            if codec_name in text_subtitle_codecs:
                subtitle_streams.append(stream)
                logger.info(
                    f"Found text-based subtitle stream at index: {stream_index} "
                    f"(Language: {language}, Title: {title}, Codec: {codec_name})"
                )
            else:
                # Log incompatible subtitle types as warnings
                logger.warning(
                    f"Skipping incompatible subtitle stream at index: {stream_index} "
                    f"(Language: {language}, Title: {title}, Codec: {codec_name}) - "
                    f"PGS/image subtitles not supported"
                )

    if video_stream_index is None:
        raise ValueError("No video stream found in the file.")
    if not audio_streams:
        logger.warning("No audio streams found. The output file will have no audio.")
    if not subtitle_streams:
        logger.warning(
            "No compatible text-based subtitle streams found. "
            "The output file will have no subtitles."
        )

    logger.info(
        f"Selected {len(audio_streams)} audio stream(s) and "
        f"{len(subtitle_streams)} subtitle stream(s)"
    )

    return (
        video_stream_index,
        audio_streams,
        subtitle_streams,
        video_stream_info,
        audio_streams,  # Return audio streams info as well
    )


# OpenSubtitles integration removed - API no longer free


def safe_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal and invalid characters.

    Args:
        filename: The original filename

    Returns:
        Sanitized filename safe for filesystem use
    """
    # Remove path separators and invalid/dangerous characters
    # Include command injection characters
    invalid_chars = r'[\\/*?:"<>|;$`&\n\r]'
    safe_name = re.sub(invalid_chars, "", filename)

    # Remove leading/trailing dots and spaces
    safe_name = safe_name.strip(". ")

    # Ensure filename is not empty
    if not safe_name:
        safe_name = "subtitle"

    # Limit length to prevent filesystem issues
    if len(safe_name) > 200:
        safe_name = safe_name[:200]

    return safe_name


def extract_subtitle(
    ffmpeg_path: str,
    input_file,
    srt_output_file,
    sub_idx: int,
) -> bool:
    """
    Extracts a text-based subtitle stream to an external .srt file.
    Only works with text-based formats (SRT, ASS, MOV_TEXT).

    Args:
        ffmpeg_path: Path to ffmpeg executable
        input_file: Validated input file path (str or Path)
        srt_output_file: Output subtitle file path (str or Path)
        sub_idx: Subtitle stream index

    Returns:
        True if extraction successful, False otherwise
    """
    # Convert to Path objects if they're strings
    if isinstance(input_file, str):
        input_file = Path(input_file)
    if isinstance(srt_output_file, str):
        srt_output_file = Path(srt_output_file)

    logger.info(f"Extracting subtitle stream {sub_idx} to: {srt_output_file.name}")

    # Validate output directory exists and is writable
    output_dir = srt_output_file.parent
    if not output_dir.exists():
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as e:
            logger.error(f"Cannot create output directory: {e}")
            return False

    # Standard text subtitle extraction
    command = [
        ffmpeg_path,
        "-i",
        str(input_file),
        "-map",
        f"0:{sub_idx}",
        "-c:s",
        "srt",
        "-y",
        str(srt_output_file),
    ]

    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=120,  # 2 minute timeout for subtitle extraction
        )
        logger.info(f"Successfully created subtitle file: {srt_output_file.name}")
        return True

    except subprocess.TimeoutExpired:
        logger.error(f"Subtitle extraction timed out for stream {sub_idx}")
        return False
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to extract subtitle from stream {sub_idx}: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during subtitle extraction: {e}")
        return False


def remux_to_mp4(
    ffmpeg_path: str,
    input_file,
    output_file,
    video_idx: int,
    audio_streams: List[Dict],
    sub_streams: List[Dict],
    video_info: Optional[Dict] = None,
) -> bool:
    """
    Constructs and runs the ffmpeg command to remux the selected streams into an
    MP4 file.
    Preserves Dolby Vision and HDR metadata.

    Args:
        ffmpeg_path: Path to ffmpeg executable
        input_file: Validated input file path (str or Path)
        output_file: Output MP4 file path (str or Path)
        video_idx: Video stream index
        audio_streams: List of audio stream dictionaries
        sub_streams: List of subtitle stream dictionaries
        video_info: Optional video stream information

    Returns:
        True if conversion successful, False otherwise
    """
    # Convert to Path objects if they're strings
    if isinstance(input_file, str):
        input_file = Path(input_file)
    if isinstance(output_file, str):
        output_file = Path(output_file)

    logger.info(f"Starting remux process for: {input_file.name}")

    # Validate output directory
    output_dir = output_file.parent
    if not output_dir.exists():
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as e:
            logger.error(f"Cannot create output directory: {e}")
            return False

    # Build command with validated inputs
    command = [ffmpeg_path, "-i", str(input_file)]

    # Map video stream
    command.extend(["-map", f"0:{video_idx}"])

    # Map all audio streams
    for audio_stream in audio_streams:
        audio_idx = audio_stream.get("index")
        if audio_idx is not None:
            command.extend(["-map", f"0:{audio_idx}"])

    # Map all selected subtitle streams (text-based only)
    for sub_stream in sub_streams:
        stream_idx = sub_stream.get("index")
        if stream_idx is not None:
            command.extend(["-map", f"0:{stream_idx}"])

    # Set codecs for each stream type
    command.extend(["-c:v", "copy"])  # Always copy video to preserve DV/HDR

    # Handle audio codec conversion for Windows Media Player compatibility
    if audio_streams:
        # Check if we need to convert any audio streams
        needs_conversion = False
        for audio_stream in audio_streams:
            codec_name = audio_stream.get("codec_name", "").lower()
            if codec_name in ["dts", "dts-hd", "truehd"] or codec_name.startswith(
                "pcm"
            ):
                needs_conversion = True
                break

        if needs_conversion:
            # Convert incompatible audio to EAC3
            command.extend(["-c:a", "eac3", "-b:a", "768k"])
            logger.info(
                "Converting incompatible audio streams to EAC3 for "
                "Windows Media Player compatibility"
            )
        else:
            # Copy compatible audio streams
            command.extend(["-c:a", "copy"])
            logger.info("Copying compatible audio streams")

    if sub_streams:
        command.extend(["-c:s", "mov_text"])

    # Preserve metadata
    command.extend(["-map_metadata", "0"])  # Copy all metadata
    command.extend(["-map_metadata:s:v", "0:s:v"])  # Copy video stream metadata
    command.extend(["-map_metadata:s:a", "0:s:a"])  # Copy audio stream metadata

    # MP4 specific flags for better compatibility
    command.extend(["-movflags", "+faststart"])  # Place moov atom at beginning
    command.extend(["-strict", "unofficial"])  # Allow unofficial codecs

    command.extend(["-y", str(output_file)])

    # Log command without exposing full paths (security)
    safe_command = [ffmpeg_path, "-i", "<input>", "...", str(output_file)]
    logger.info(f"Executing FFmpeg command: {' '.join(safe_command)}")

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )

        # Process output with timeout
        import signal

        def timeout_handler(signum, frame):
            process.terminate()
            raise subprocess.TimeoutExpired(command, 1800)  # 30 minute timeout

        if hasattr(signal, "SIGALRM"):  # Unix systems
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(1800)  # 30 minute timeout

        try:
            output_lines = []
            for line in process.stdout:
                line_clean = line.strip()
                if line_clean:
                    logger.debug(f"FFmpeg: {line_clean}")
                    output_lines.append(line_clean)

            process.wait()

            if hasattr(signal, "SIGALRM"):
                signal.alarm(0)  # Cancel timeout

            if process.returncode == 0:
                logger.info(f"Successfully created: {output_file.name}")
                return True
            else:
                logger.error(
                    f"FFmpeg process failed with return code: {process.returncode}"
                )
                # Log last few lines of output for debugging
                if output_lines:
                    logger.error(f"Last FFmpeg output: {' '.join(output_lines[-3:])}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("FFmpeg process timed out")
            process.terminate()
            return False

    except Exception as e:
        logger.error(f"Unexpected error during FFmpeg process: {e}")
        return False


def main():
    """
    Main function to orchestrate the conversion process.
    """
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Convert 4K Dolby Vision MKV files to MP4 format", prog="convert"
    )
    parser.add_argument("files", nargs="+", help="MKV files to convert")
    parser.add_argument(
        "--output-dir", "-o", help="Output directory (default: same as input file)"
    )
    parser.add_argument("--config", "-c", help="Path to configuration file")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually converting",
    )

    args = parser.parse_args()

    # Load configuration with optional config file override
    global _config_manager, _config
    if args.config:
        try:
            _config_manager = ConfigManager(config_file=args.config)
            _config = _config_manager.config
        except Exception as e:
            logger.error(f"Failed to load config file {args.config}: {e}")
            sys.exit(1)

    # Validate output directory - use config if not specified
    output_base_dir = None
    if args.output_dir:
        output_base_dir = Path(args.output_dir).expanduser().resolve()
    elif _config and "paths" in _config and "output_dir" in _config["paths"]:
        output_base_dir = Path(_config["paths"]["output_dir"]).expanduser().resolve()
        logger.info(f"Using configured output directory: {output_base_dir}")

    if output_base_dir and not args.dry_run:
        try:
            output_base_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create output directory {output_base_dir}: {e}")
            sys.exit(1)

    try:
        ffmpeg_path, ffprobe_path = find_ffmpeg_tools()
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error finding FFmpeg tools: {e}")
        sys.exit(1)

    input_files = args.files
    success_count = 0
    fail_count = 0

    logger.info(f"Processing {len(input_files)} file(s)")
    if args.dry_run:
        logger.info("DRY RUN MODE - No files will be converted")

    for input_file_str in input_files:
        try:
            # Validate input file path for security
            input_file = validate_file_path(input_file_str)

        except (ValueError, FileNotFoundError) as e:
            logger.error(f"Invalid input file {input_file_str}: {e}")
            fail_count += 1
            continue
        except Exception as e:
            logger.error(f"Error validating file {input_file_str}: {e}")
            fail_count += 1
            continue

        # Generate safe output paths
        base_name = input_file.stem
        safe_base_name = safe_filename(base_name)

        # Use output directory override if specified, otherwise same as input
        if output_base_dir:
            output_dir = output_base_dir
        else:
            output_dir = input_file.parent

        mp4_output_file = output_dir / f"{safe_base_name}.mp4"

        if mp4_output_file.exists():
            logger.info(
                f"Skipping: Output file already exists -> {mp4_output_file.name}"
            )
            continue

        # If dry-run mode, just show what would be done
        if args.dry_run:
            logger.info(f"Would convert: {input_file.name} -> {mp4_output_file}")
            success_count += 1
            continue

        try:
            # Analyze streams
            streams_info = analyze_streams(ffprobe_path, input_file)
            (
                video_idx,
                audio_streams,
                sub_streams,
                video_info,
                audio_streams_info,
            ) = select_streams(streams_info)

            # Extract all found text-based subtitles to separate .srt files
            subtitle_success_count = 0
            for sub_stream in sub_streams:
                sub_idx = sub_stream.get("index")
                if sub_idx is None:
                    continue

                # Sanitize title for use in filename
                title = sub_stream.get("tags", {}).get("title", f"sub.{sub_idx}")
                safe_title = safe_filename(title)
                srt_output_file = output_dir / f"{safe_base_name}.{safe_title}.srt"

                # Extract text-based subtitle
                if extract_subtitle(ffmpeg_path, input_file, srt_output_file, sub_idx):
                    subtitle_success_count += 1

            if subtitle_success_count > 0:
                logger.info(f"Extracted {subtitle_success_count} subtitle file(s)")

            # Proceed with remuxing to MP4 (continue even if subtitles failed)
            success = remux_to_mp4(
                ffmpeg_path,
                input_file,
                mp4_output_file,
                video_idx,
                audio_streams,
                sub_streams,
                video_info,
            )

            if success:
                success_count += 1
                logger.info(f"Successfully processed: {input_file.name}")
            else:
                fail_count += 1
                logger.error(f"Failed to process: {input_file.name}")

        except subprocess.TimeoutExpired:
            logger.error(f"Processing timed out for: {input_file.name}")
            fail_count += 1
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error processing {input_file.name}: {e}")
            fail_count += 1
        except (ValueError, json.JSONDecodeError) as e:
            logger.error(f"Invalid file or data for {input_file.name}: {e}")
            fail_count += 1
        except Exception as e:
            logger.error(f"Unexpected error processing {input_file.name}: {e}")
            logger.debug(f"Exception details: {type(e).__name__}: {e}")
            fail_count += 1

        logger.info("-" * 60)

    # Final summary
    logger.info(f"Processing complete: {success_count} succeeded, {fail_count} failed")

    # Exit with appropriate code for post-processor
    if fail_count > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
