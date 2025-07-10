#!/usr/bin/env python3
"""
qBittorrent Post-Execution Script for Play DV on Windows
Processes downloaded 4K Dolby Vision MKV files and organizes them for Plex
"""

import json
import logging
import logging.handlers
import os
import re
import shutil
import subprocess
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Import our configuration manager
from .config_manager import ConfigManager

# Optional imports (will work without them)
try:
    import requests

    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    print(
        "Warning: requests library not installed. qBittorrent API features will be "
        "limited."
    )

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("Warning: psutil not installed. Disk space checks will be limited.")


# Remove legacy Config class - using ConfigManager directly now


class QBittorrentAPI:
    """Wrapper for qBittorrent Web API with secure credential handling"""

    def __init__(self, config):
        if not HAS_REQUESTS:
            self.enabled = False
            logging.warning("requests library not available - qBittorrent API disabled")
            return

        self.enabled = True

        # Validate configuration
        qbt_config = config.get("qbittorrent", {})
        host = qbt_config.get("host", "localhost")
        port = qbt_config.get("port", 8080)

        # Validate host and port
        if not isinstance(port, int) or port < 1 or port > 65535:
            logging.error(f"Invalid qBittorrent port: {port}")
            self.enabled = False
            return

        # Only allow localhost/127.0.0.1 or private IP ranges for security
        allowed_hosts = ["localhost", "127.0.0.1", "::1"]
        if host not in allowed_hosts and not self._is_private_ip(host):
            logging.warning(
                f"qBittorrent host {host} may not be secure - only localhost and "
                f"private IPs recommended"
            )

        self.base_url = f"http://{host}:{port}/api/v2"

        # Store credentials securely (avoid logging)
        self._username = qbt_config.get("username")
        self._password = qbt_config.get("password")

        if not self._username or not self._password:
            logging.error("qBittorrent credentials not configured")
            self.enabled = False
            return

        # Configure session with security settings
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "MKV-to-MP4-Converter/1.0"})

        # Set reasonable timeouts
        self.timeout = qbt_config.get("timeout", 30)

        self._login()

    def _is_private_ip(self, ip: str) -> bool:
        """Check if IP address is in private range"""
        try:
            import ipaddress

            addr = ipaddress.ip_address(ip)
            return addr.is_private
        except (ValueError, ImportError):
            # If we can't validate, be cautious
            return False

    def _login(self):
        """Authenticate with qBittorrent using secure practices"""
        try:
            response = self.session.post(
                f"{self.base_url}/auth/login",
                data={"username": self._username, "password": self._password},
                timeout=self.timeout,
                allow_redirects=False,  # Prevent redirect attacks
            )

            if response.status_code != 200:
                logging.error(f"qBittorrent API returned status {response.status_code}")
                self.enabled = False
                return

            if response.text.strip() != "Ok.":
                logging.error("qBittorrent authentication failed - check credentials")
                self.enabled = False
                return

            logging.info("Successfully authenticated with qBittorrent")

        except requests.exceptions.Timeout:
            logging.error("Timeout connecting to qBittorrent API")
            self.enabled = False
        except requests.exceptions.ConnectionError:
            logging.error(
                "Cannot connect to qBittorrent API - check if service is running"
            )
            self.enabled = False
        except requests.exceptions.RequestException as e:
            logging.error(f"qBittorrent API request failed: {e}")
            self.enabled = False
        except Exception as e:
            logging.error(f"Unexpected error connecting to qBittorrent: {e}")
            self.enabled = False

        # Clear credentials from memory after use
        self._password = None

    def add_tags(self, torrent_hash: str, tags: List[str]) -> bool:
        """Add tags to a torrent with input validation"""
        if not self.enabled:
            logging.debug("qBittorrent API not enabled")
            return False

        # Validate inputs
        if not self._validate_torrent_hash(torrent_hash):
            logging.error(f"Invalid torrent hash format: {torrent_hash[:8]}...")
            return False

        if not tags or not all(isinstance(tag, str) and tag.strip() for tag in tags):
            logging.error("Invalid tags provided")
            return False

        # Sanitize tags (remove potentially dangerous characters)
        safe_tags = [self._sanitize_tag(tag) for tag in tags]

        try:
            response = self.session.post(
                f"{self.base_url}/torrents/addTags",
                data={"hashes": torrent_hash, "tags": ",".join(safe_tags)},
                timeout=self.timeout,
            )

            if response.status_code == 200:
                logging.debug(f"Successfully added tags {safe_tags} to torrent")
                return True
            else:
                logging.error(
                    f"Failed to add tags - API returned {response.status_code}"
                )
                return False

        except requests.exceptions.RequestException as e:
            logging.error(f"Network error adding tags: {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error adding tags: {e}")
            return False

    def _validate_torrent_hash(self, hash_str: str) -> bool:
        """Validate torrent hash format"""
        if not hash_str or not isinstance(hash_str, str):
            return False
        # SHA-1 hash should be 40 hex characters
        return len(hash_str) == 40 and all(
            c in "0123456789abcdefABCDEF" for c in hash_str
        )

    def _sanitize_tag(self, tag: str) -> str:
        """Sanitize tag to prevent injection"""
        # Remove potentially dangerous characters
        safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        return "".join(c for c in tag if c in safe_chars)[:50]  # Limit length

    def remove_tags(self, torrent_hash: str, tags: List[str]) -> bool:
        """Remove tags from a torrent with input validation"""
        if not self.enabled:
            return False

        # Validate inputs
        if not self._validate_torrent_hash(torrent_hash):
            logging.error(f"Invalid torrent hash format: {torrent_hash[:8]}...")
            return False

        if not tags or not all(isinstance(tag, str) and tag.strip() for tag in tags):
            logging.error("Invalid tags provided")
            return False

        safe_tags = [self._sanitize_tag(tag) for tag in tags]

        try:
            response = self.session.post(
                f"{self.base_url}/torrents/removeTags",
                data={"hashes": torrent_hash, "tags": ",".join(safe_tags)},
                timeout=self.timeout,
            )
            return response.status_code == 200
        except requests.exceptions.RequestException as e:
            logging.error(f"Network error removing tags: {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error removing tags: {e}")
            return False

    def delete_torrent(self, torrent_hash: str, delete_files: bool = True) -> bool:
        """Delete a torrent and optionally its files with safety checks"""
        if not self.enabled:
            return False

        # Validate inputs
        if not self._validate_torrent_hash(torrent_hash):
            logging.error(f"Invalid torrent hash format: {torrent_hash[:8]}...")
            return False

        # Log the action for audit purposes
        logging.info(
            f"Deleting torrent {torrent_hash[:8]}... (delete_files={delete_files})"
        )

        try:
            response = self.session.post(
                f"{self.base_url}/torrents/delete",
                data={
                    "hashes": torrent_hash,
                    "deleteFiles": "true" if delete_files else "false",
                },
                timeout=self.timeout,
            )

            if response.status_code == 200:
                logging.info(f"Successfully deleted torrent {torrent_hash[:8]}...")
                return True
            else:
                logging.error(
                    f"Failed to delete torrent - API returned {response.status_code}"
                )
                return False

        except requests.exceptions.RequestException as e:
            logging.error(f"Network error deleting torrent: {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error deleting torrent: {e}")
            return False


class TorrentValidator:
    """Validates torrents based on configured criteria"""

    def __init__(self, config):
        self.filter_config = config["filters"]
        self.processing_config = config["processing"]

        # Compile regex patterns for efficiency
        self.resolution_patterns = [
            re.compile(r"2160p", re.IGNORECASE),
            re.compile(r"4K", re.IGNORECASE),
            re.compile(r"UHD", re.IGNORECASE),
        ]

        self.dv_patterns = [
            re.compile(r"\bDV\b", re.IGNORECASE),
            re.compile(r"\bDoVi\b", re.IGNORECASE),
            re.compile(r"Dolby\.?Vision", re.IGNORECASE),
        ]

        self.season_pattern = re.compile(r"S(\d+)(?:[-\s]?S(\d+))?", re.IGNORECASE)
        self.episode_pattern = re.compile(
            r"S(\d+)E(\d+)(?:[-\s]?E(\d+))?", re.IGNORECASE
        )

        # File size threshold in bytes
        self.min_file_size = self.processing_config["min_file_size_gb"] * 1024**3

    def validate(
        self, torrent_name: str, category: str, content_path: str
    ) -> Tuple[bool, str, List[Path]]:
        """
        Validate a torrent for processing
        Returns: (is_valid, reason, mkv_files)
        """
        # Check category
        if category.lower() in [
            cat.lower() for cat in self.filter_config["excluded_categories"]
        ]:
            return False, f"Excluded category: {category}", []

        # Check resolution requirement
        if self.filter_config["require_4k"]:
            if not any(
                pattern.search(torrent_name) for pattern in self.resolution_patterns
            ):
                return False, "Not 4K content", []

        # Check Dolby Vision requirement
        if self.filter_config["require_dv"]:
            if not any(pattern.search(torrent_name) for pattern in self.dv_patterns):
                return False, "Not Dolby Vision content", []

        # Check for multiple seasons
        season_matches = self.season_pattern.findall(torrent_name)
        for match in season_matches:
            if match[1]:  # Has season range (S01-S05)
                season_count = int(match[1]) - int(match[0]) + 1
                if season_count > self.filter_config["max_seasons_per_torrent"]:
                    return False, f"Too many seasons ({season_count})", []

        # Find MKV files
        mkv_files = self._find_mkv_files(content_path)

        if not mkv_files:
            return False, "No MKV files found", []

        # Validate file sizes
        valid_mkv_files = []
        for mkv_file in mkv_files:
            if mkv_file.stat().st_size >= self.min_file_size:
                valid_mkv_files.append(mkv_file)
            else:
                logging.info(
                    f"Skipping small MKV: {mkv_file.name} "
                    f"({mkv_file.stat().st_size / 1024**3:.1f} GB)"
                )

        if not valid_mkv_files:
            return False, "No MKV files meet size requirement", []

        # If we passed the torrent name checks (4K + DV), we trust it!
        # No need for complex content analysis - just process the MKVs
        return True, "Valid", valid_mkv_files

    def _find_mkv_files(self, content_path: str) -> List[Path]:
        """Find all MKV files in the content path with security validation"""
        try:
            # Resolve and validate the content path
            content_path_obj = Path(content_path).resolve()

            # Basic security check - ensure path exists and is accessible
            if not content_path_obj.exists():
                logging.error(f"Content path does not exist: {content_path}")
                return []

            # Check for suspicious path patterns
            path_str = str(content_path_obj)
            if (
                ".." in path_str
                or path_str.startswith("/etc")
                or path_str.startswith("/sys")
            ):
                logging.error(f"Suspicious path detected: {content_path}")
                return []

            mkv_files = []

            if content_path_obj.is_file():
                if content_path_obj.suffix.lower() == ".mkv":
                    # Validate file size and accessibility
                    try:
                        file_size = content_path_obj.stat().st_size
                        if file_size > 0:  # Not empty
                            mkv_files.append(content_path_obj)
                    except (OSError, PermissionError) as e:
                        logging.warning(f"Cannot access file {content_path_obj}: {e}")

            elif content_path_obj.is_dir():
                # Limit depth to prevent directory traversal attacks
                max_depth = 5
                for ext in self.filter_config["allowed_extensions"]:
                    try:
                        for mkv_file in content_path_obj.rglob(f"*{ext}"):
                            # Check depth
                            relative_path = mkv_file.relative_to(content_path_obj)
                            if len(relative_path.parts) > max_depth:
                                logging.warning(
                                    f"Skipping deeply nested file: {mkv_file}"
                                )
                                continue

                            # Validate file
                            try:
                                file_size = mkv_file.stat().st_size
                                if file_size > 0:
                                    mkv_files.append(mkv_file)
                            except (OSError, PermissionError):
                                continue

                    except Exception as e:
                        logging.error(
                            f"Error scanning directory {content_path_obj}: {e}"
                        )
                        continue

            # Limit number of files to prevent resource exhaustion
            if len(mkv_files) > 100:
                logging.warning(f"Found {len(mkv_files)} files, limiting to first 100")
                mkv_files = mkv_files[:100]

            return sorted(mkv_files)

        except Exception as e:
            logging.error(f"Error finding MKV files in {content_path}: {e}")
            return []


class ContentAnalyzer:
    """Analyzes content type and extracts metadata"""

    def __init__(self):
        # Movie patterns
        self.movie_year_pattern = re.compile(r"(.+?)[\.\s]+\(?(\d{4})\)?")

        # TV show patterns
        self.show_season_pattern = re.compile(r"^(.+?)[\.\s]+S(\d+)", re.IGNORECASE)
        self.episode_pattern = re.compile(r"S(\d+)E(\d+)", re.IGNORECASE)

        # Quality patterns
        self.quality_pattern = re.compile(r"(2160p|4K|UHD|1080p|720p)", re.IGNORECASE)
        self.hdr_pattern = re.compile(
            r"(DV|DoVi|Dolby\.?Vision|HDR10\+?|HDR)", re.IGNORECASE
        )

    def determine_content_type(self, torrent_name: str, mkv_files: List[Path]) -> str:
        """Determine if content is movie or TV show"""
        # Check for episode patterns
        if self.episode_pattern.search(torrent_name):
            return "tv"

        # Check file names for episode patterns
        for mkv_file in mkv_files:
            if self.episode_pattern.search(mkv_file.name):
                return "tv"

        # Multiple files usually means TV show
        if len(mkv_files) > 1:
            # But could be a movie collection, check filenames
            episode_count = sum(
                1 for f in mkv_files if self.episode_pattern.search(f.name)
            )
            if episode_count > len(mkv_files) / 2:
                return "tv"

        return "movie"

    def parse_movie_info(self, filename: str) -> Dict[str, str]:
        """Extract movie title and year"""
        # Clean filename
        clean_name = Path(filename).stem

        # Try to extract year
        match = self.movie_year_pattern.search(clean_name)
        if match:
            title = match.group(1).replace(".", " ").replace("_", " ").strip()
            year = match.group(2)
        else:
            # No year found, use whole name
            title = clean_name.split(".")[0].replace("_", " ")
            year = datetime.now().year

        # Extract quality info
        quality_match = self.quality_pattern.search(filename)
        quality = quality_match.group(1) if quality_match else "2160p"

        hdr_match = self.hdr_pattern.search(filename)
        hdr = hdr_match.group(1) if hdr_match else "DV"

        return {"title": title, "year": str(year), "quality": quality, "hdr": hdr}

    def parse_show_info(self, filename: str) -> Dict[str, any]:
        """Extract show name and season"""
        match = self.show_season_pattern.search(filename)
        if match:
            show_name = match.group(1).replace(".", " ").replace("_", " ").strip()
            season = int(match.group(2))
        else:
            # Fallback
            show_name = filename.split(".")[0]
            season = 1

        return {"show_name": show_name, "season": season}

    def parse_episode_info(self, filename: str) -> Optional[Dict[str, int]]:
        """Extract season and episode numbers"""
        match = self.episode_pattern.search(filename)
        if match:
            return {"season": int(match.group(1)), "episode": int(match.group(2))}
        return None


class FileProcessor:
    """Handles file conversion and organization"""

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.output_dir = Path(config["paths"]["output_dir"])

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Temp directory setup
        if config["processing"]["use_temp_dir"]:
            self.temp_dir = Path(config["processing"]["temp_dir"])
            self.temp_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.temp_dir = None

        self.analyzer = ContentAnalyzer()

    def process_files(
        self, torrent_name: str, mkv_files: List[Path]
    ) -> Dict[str, List]:
        """Process all MKV files from a torrent - let Plex figure out the"""
        """organization"""
        results = {"success": [], "failed": []}

        # Handle single file (usually movies) vs multiple files (usually TV shows)
        if len(mkv_files) == 1:
            # Single file - process directly
            self.logger.info(f"Processing single file: {mkv_files[0].name}")
            result = self._process_file_for_plex(mkv_files[0], torrent_name)
            if result["success"]:
                results["success"].append(result)
            else:
                results["failed"].append(result)
        else:
            # Multiple files - process in parallel (likely TV show episodes)
            self.logger.info(
                f"Processing {len(mkv_files)} files in parallel "
                f"(max {self.config['processing']['parallel_episodes']} concurrent)"
            )

            with ThreadPoolExecutor(
                max_workers=self.config["processing"]["parallel_episodes"]
            ) as executor:
                # Submit all files for processing
                futures = {
                    executor.submit(
                        self._process_file_for_plex, mkv_file, torrent_name
                    ): mkv_file
                    for mkv_file in mkv_files
                }

                # Collect results as they complete
                for future in as_completed(futures):
                    mkv_file = futures[future]
                    try:
                        result = future.result()
                        if result["success"]:
                            results["success"].append(result)
                            self.logger.info(f"✅ Completed: {mkv_file.name}")
                        else:
                            results["failed"].append(result)
                            self.logger.error(
                                f"❌ Failed: {mkv_file.name} - {result['error']}"
                            )
                    except Exception as e:
                        self.logger.error(
                            f"❌ Exception processing {mkv_file.name}: {str(e)}"
                        )
                        results["failed"].append(
                            {
                                "success": False,
                                "type": "file",
                                "input": str(mkv_file),
                                "output": None,
                                "error": str(e),
                            }
                        )

        return results

    def _process_file_for_plex(self, mkv_file: Path, torrent_name: str) -> Dict:
        """Process a single file and put it in output directory for auto-detection"""
        try:
            # Create a simple folder based on torrent name
            # Remove common quality indicators for cleaner folder names
            clean_name = re.sub(
                r"\.(2160p|4K|UHD|DV|DoVi|Dolby\.?Vision|HEVC|x265).*$",
                "",
                torrent_name,
                flags=re.IGNORECASE,
            )
            clean_name = clean_name.replace(".", " ").replace("_", " ").strip()

            # Create folder in output directory
            content_dir = self.output_dir / clean_name
            content_dir.mkdir(parents=True, exist_ok=True)

            # Prepare output filename
            # For TV episodes, try to clean up the filename while preserving episode
            # info
            output_name = mkv_file.stem

            # Clean up common release group tags and quality indicators from
            # individual file names
            # but preserve important episode information (SxxExx patterns)
            output_name = re.sub(
                r"[-\.\s]*(2160p|4K|UHD|DV|DoVi|Dolby\.?Vision|HEVC|x265|x264).*$",
                "",
                output_name,
                flags=re.IGNORECASE,
            )
            output_name = re.sub(
                r"[-\.\s]*\[.*?\][-\.\s]*", "", output_name
            )  # Remove [group] tags
            output_name = re.sub(
                r"[-\.\s]*\{.*?\}[-\.\s]*", "", output_name
            )  # Remove {tags}
            output_name = output_name.replace(".", " ").replace("_", " ").strip()

            # Ensure we don't end up with empty names
            if not output_name or len(output_name) < 3:
                output_name = mkv_file.stem

            output_base = content_dir / output_name

            # Convert
            success = self._convert_file(mkv_file, output_base)

            return {
                "success": success,
                "type": "file",
                "input": str(mkv_file),
                "output": str(output_base.with_suffix(".mp4")),
                "error": None if success else "Conversion failed",
            }

        except Exception as e:
            self.logger.error(f"Error processing file {mkv_file}: {str(e)}")
            return {
                "success": False,
                "type": "file",
                "input": str(mkv_file),
                "output": None,
                "error": str(e),
            }

    def _process_movie(self, mkv_file: Path, torrent_name: str) -> Dict:
        """Process a single movie file"""
        try:
            # Parse movie info
            movie_info = self.analyzer.parse_movie_info(torrent_name)

            # Create movie directory
            movie_dir = (
                self.movies_dir / f"{movie_info['title']} ({movie_info['year']})"
            )
            movie_dir.mkdir(parents=True, exist_ok=True)

            # Prepare output filename
            output_name = (
                f"{movie_info['title']}.{movie_info['year']}."
                f"{movie_info['quality']}.{movie_info['hdr']}"
            )
            output_base = movie_dir / output_name

            # Convert
            success = self._convert_file(mkv_file, output_base)

            return {
                "success": success,
                "type": "movie",
                "input": str(mkv_file),
                "output": str(output_base.with_suffix(".mp4")),
                "error": None if success else "Conversion failed",
            }

        except Exception as e:
            self.logger.error(f"Error processing movie {mkv_file}: {str(e)}")
            return {
                "success": False,
                "type": "movie",
                "input": str(mkv_file),
                "output": None,
                "error": str(e),
            }

    def _process_tv_show(
        self, mkv_files: List[Path], torrent_name: str, results: Dict
    ) -> Dict:
        """Process TV show episodes"""
        try:
            # Parse show info
            show_info = self.analyzer.parse_show_info(torrent_name)

            # Create show directory
            show_dir = (
                self.tv_dir
                / show_info["show_name"]
                / f"Season {show_info['season']:02d}"
            )
            show_dir.mkdir(parents=True, exist_ok=True)

            # Process episodes in parallel
            with ThreadPoolExecutor(
                max_workers=self.config["processing"]["parallel_episodes"]
            ) as executor:
                futures = []

                for mkv_file in mkv_files:
                    episode_info = self.analyzer.parse_episode_info(mkv_file.name)
                    if episode_info:
                        future = executor.submit(
                            self._process_episode, mkv_file, show_dir, episode_info
                        )
                        futures.append(future)
                    else:
                        self.logger.warning(
                            f"Could not parse episode info from: {mkv_file.name}"
                        )

                # Collect results
                for future in as_completed(futures):
                    result = future.result()
                    if result["success"]:
                        results["success"].append(result)
                    else:
                        results["failed"].append(result)

        except Exception as e:
            self.logger.error(f"Error processing TV show: {str(e)}")
            results["failed"].append({"success": False, "type": "tv", "error": str(e)})

        return results

    def _process_episode(
        self, mkv_file: Path, show_dir: Path, episode_info: Dict
    ) -> Dict:
        """Process a single TV episode"""
        try:
            # Prepare output filename
            episode_name = (
                f"S{episode_info['season']:02d}E{episode_info['episode']:02d}"
            )
            output_base = show_dir / episode_name

            # Convert
            success = self._convert_file(mkv_file, output_base)

            return {
                "success": success,
                "type": "episode",
                "input": str(mkv_file),
                "output": str(output_base.with_suffix(".mp4")),
                "episode": episode_name,
                "error": None if success else "Conversion failed",
            }

        except Exception as e:
            return {
                "success": False,
                "type": "episode",
                "input": str(mkv_file),
                "output": None,
                "error": str(e),
            }

    def _convert_file(self, input_path: Path, output_base: Path) -> bool:
        """Convert MKV to MP4 using the convert.py script with security validation"""
        try:
            # Validate input and output paths
            if not self._validate_file_path(input_path, "input"):
                return False
            if not self._validate_file_path(output_base.parent, "output_dir"):
                return False

            # Check disk space
            if not self._check_disk_space(input_path, output_base.parent):
                self.logger.error(f"Insufficient disk space for {input_path.name}")
                return False

            # Create safe output path
            safe_output_name = self._sanitize_filename(output_base.name)
            final_output_base = output_base.parent / safe_output_name

            # Run conversion with security measures
            self.logger.info(f"Converting: {input_path.name} -> {safe_output_name}.mp4")

            # Import and run convert function directly
            try:
                from .convert import main as convert_main

                # Set up sys.argv for convert function with output directory
                original_argv = sys.argv
                sys.argv = [
                    "convert.py",
                    str(input_path),
                    "--output-dir",
                    str(output_base.parent),
                ]

                try:
                    convert_main()
                    result_returncode = 0
                    result_stdout = b"Conversion completed successfully"
                    result_stderr = b""
                except SystemExit as e:
                    # Handle sys.exit() calls from convert_main
                    result_returncode = e.code if e.code is not None else 0
                    if result_returncode == 0:
                        result_stdout = b"Conversion completed successfully"
                        result_stderr = b""
                    else:
                        result_stdout = b""
                        result_stderr = b"Conversion failed"
                finally:
                    sys.argv = original_argv

            except Exception as e:
                self.logger.error(f"Conversion failed: {e}")
                result_returncode = 1
                result_stdout = b""
                result_stderr = str(e).encode()

            # Create a result object similar to subprocess.run
            class ConversionResult:
                def __init__(self, returncode, stdout, stderr):
                    self.returncode = returncode
                    self.stdout = stdout
                    self.stderr = stderr

            result = ConversionResult(result_returncode, result_stdout, result_stderr)

            if result.returncode != 0:
                self.logger.error(f"Conversion failed with code {result.returncode}")
                # Log stderr but limit length to prevent log flooding
                stderr_preview = (result.stderr or "")[:500]
                self.logger.error(f"Conversion error: {stderr_preview}")
                return False

            # Find and validate output files (now created in the output directory)
            input_stem = input_path.stem
            output_dir = output_base.parent

            # Look for the converted MP4 in the output directory
            converted_mp4 = output_dir / f"{input_stem}.mp4"
            if not converted_mp4.exists():
                self.logger.error(f"Converted file not found: {converted_mp4.name}")
                return False

            # Validate converted file
            if not self._validate_converted_file(converted_mp4):
                self.logger.error(
                    f"Converted file failed validation: {converted_mp4.name}"
                )
                return False

            # Rename to final location if needed
            final_mp4 = final_output_base.with_suffix(".mp4")

            if converted_mp4 != final_mp4:
                if not self._secure_file_move(converted_mp4, final_mp4):
                    return False
            else:
                self.logger.info(f"File already in correct location: {final_mp4.name}")

            # Move subtitle files securely
            subtitle_count = 0
            for srt_file in output_dir.glob(f"{input_stem}*.srt"):
                safe_srt_name = self._sanitize_filename(
                    srt_file.name.replace(input_stem, final_output_base.stem)
                )
                srt_dest = final_output_base.parent / safe_srt_name

                if srt_file != srt_dest:
                    if self._secure_file_move(srt_file, srt_dest):
                        subtitle_count += 1
                        self.logger.info(f"Moved subtitle: {srt_file.name}")
                else:
                    subtitle_count += 1
                    self.logger.info(
                        f"Subtitle already in correct location: {srt_file.name}"
                    )

            # Delete source files if configured
            if self.config["processing"]["delete_after_success"]:
                try:
                    self.logger.info(f"Deleting source file: {input_path.name}")
                    input_path.unlink()
                    self.logger.info(
                        f"Successfully deleted source file: {input_path.name}"
                    )
                except Exception as e:
                    self.logger.warning(
                        f"Failed to delete source file {input_path.name}: {e}"
                    )

            self.logger.info(
                f"Successfully processed: {input_path.name} (with {subtitle_count} "
                f"subtitles)"
            )
            return True

        except subprocess.TimeoutExpired:
            self.logger.error(f"Conversion timed out for: {input_path.name}")
            return False
        except Exception as e:
            self.logger.error(f"Error in conversion: {str(e)}")
            self.logger.debug(f"Exception details: {type(e).__name__}: {e}")
            return False

    def _validate_file_path(self, path: Path, path_type: str) -> bool:
        """Validate file path for security"""
        try:
            resolved_path = path.resolve()
            path_str = str(resolved_path)

            # Check for suspicious patterns
            if ".." in path_str or path_str.startswith(("/etc", "/sys", "/proc")):
                self.logger.error(f"Suspicious {path_type} path: {path}")
                return False

            # Check accessibility
            if path_type == "input" and not resolved_path.exists():
                self.logger.error(f"Input path does not exist: {path}")
                return False

            if path_type == "output_dir":
                try:
                    resolved_path.mkdir(parents=True, exist_ok=True)
                except (OSError, PermissionError) as e:
                    self.logger.error(f"Cannot create output directory {path}: {e}")
                    return False

            return True

        except Exception as e:
            self.logger.error(f"Error validating {path_type} path {path}: {e}")
            return False

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to prevent path traversal and invalid characters"""
        # Remove path separators and invalid characters
        invalid_chars = r'[\\/*?:"<>|]'
        safe_name = re.sub(invalid_chars, "", filename)

        # Remove leading/trailing dots and spaces
        safe_name = safe_name.strip(". ")

        # Ensure filename is not empty
        if not safe_name:
            safe_name = "converted_file"

        # Limit length
        if len(safe_name) > 200:
            safe_name = safe_name[:200]

        return safe_name

    def _validate_converted_file(self, file_path: Path) -> bool:
        """Validate that converted file is legitimate"""
        try:
            # Check file exists and has reasonable size
            if not file_path.exists():
                return False

            file_size = file_path.stat().st_size
            if file_size < 1024:  # Less than 1KB is suspicious
                self.logger.warning(
                    f"Converted file suspiciously small: {file_size} bytes"
                )
                return False

            # Check file extension
            if file_path.suffix.lower() != ".mp4":
                self.logger.error(
                    f"Converted file has wrong extension: {file_path.suffix}"
                )
                return False

            return True

        except Exception as e:
            self.logger.error(f"Error validating converted file: {e}")
            return False

    def _secure_file_move(self, source: Path, destination: Path) -> bool:
        """Securely move file with validation"""
        try:
            # Validate source exists
            if not source.exists():
                self.logger.error(f"Source file does not exist: {source}")
                return False

            # Ensure destination directory exists
            destination.parent.mkdir(parents=True, exist_ok=True)

            # Use platform-appropriate secure move
            if os.name == "nt":
                return self._robocopy_move(source, destination)
            else:
                shutil.move(str(source), str(destination))
                return True

        except Exception as e:
            self.logger.error(f"Error moving file {source} -> {destination}: {e}")
            return False

    def _check_disk_space(self, input_file: Path, output_dir: Path) -> bool:
        """Check if there's enough disk space for conversion"""
        required_space = input_file.stat().st_size * 1.2  # 20% buffer

        if HAS_PSUTIL:
            disk_usage = psutil.disk_usage(str(output_dir))
            free_space = disk_usage.free
        else:
            # Fallback for Windows
            if os.name == "nt":
                import ctypes

                free_bytes = ctypes.c_ulonglong(0)
                ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                    ctypes.c_wchar_p(str(output_dir)),
                    ctypes.pointer(free_bytes),
                    None,
                    None,
                )
                free_space = free_bytes.value
            else:
                # Basic check using os.statvfs
                stat = os.statvfs(output_dir)
                free_space = stat.f_bavail * stat.f_frsize

        return free_space > required_space

    def _robocopy_move(self, source: Path, destination: Path) -> bool:
        """Use robocopy for reliable file moves on Windows with security validation"""
        try:
            # Validate inputs
            if not source.exists():
                self.logger.error(f"Robocopy source does not exist: {source}")
                return False

            destination.parent.mkdir(parents=True, exist_ok=True)

            # Validate that robocopy is available
            try:
                subprocess.run(
                    ["robocopy", "/?"], capture_output=True, timeout=5, check=False
                )
            except (subprocess.TimeoutExpired, FileNotFoundError):
                self.logger.error("Robocopy not available, falling back to shutil")
                shutil.move(str(source), str(destination))
                return True

            cmd = [
                "robocopy",
                str(source.parent),
                str(destination.parent),
                source.name,
                "/MOV",  # Move file
                "/R:3",  # Retry 3 times
                "/W:1",  # Wait 1 second between retries
                "/NP",  # No progress
                "/NFL",  # No file list
                "/NDL",  # No directory list
                "/NJH",  # No job header
                "/NJS",  # No job summary
            ]

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300  # 5 minute timeout
            )

            # Robocopy exit codes 0-7 are success
            if result.returncode > 7:
                self.logger.error(
                    f"Robocopy failed with code {result.returncode}: {result.stderr}"
                )
                return False

            # Rename if necessary
            if destination.name != source.name:
                moved_file = destination.parent / source.name
                if moved_file.exists():
                    moved_file.rename(destination)
                else:
                    self.logger.error(
                        f"Robocopy did not create expected file: {moved_file}"
                    )
                    return False

            return True

        except subprocess.TimeoutExpired:
            self.logger.error("Robocopy operation timed out")
            return False
        except Exception as e:
            self.logger.error(f"Robocopy error: {e}")
            # Fallback to regular move
            try:
                shutil.move(str(source), str(destination))
                return True
            except Exception as fallback_e:
                self.logger.error(f"Fallback move also failed: {fallback_e}")
                return False


def setup_logging(config: Dict, torrent_name: str) -> logging.Logger:
    """Setup logging with both file and console output"""
    # Create logs directory
    log_dir = Path(config["paths"]["log_dir"])
    log_dir.mkdir(exist_ok=True)

    # Clean up old logs
    cleanup_old_logs(log_dir, config["logging"]["keep_days"])

    # Create logger
    logger = logging.getLogger("qbt_post_process")
    logger.setLevel(config["logging"]["level"])

    # Create formatters
    detailed_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    simple_formatter = logging.Formatter("%(levelname)s: %(message)s")

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    logger.addHandler(console_handler)

    # File handler for this specific torrent
    safe_name = re.sub(r'[<>:"/\\|?*]', "_", torrent_name)[:100]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"{timestamp}_{safe_name}.log"

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(config["logging"]["level"])
    file_handler.setFormatter(detailed_formatter)
    logger.addHandler(file_handler)

    # Also create/append to summary log
    summary_handler = logging.FileHandler(log_dir / "summary.log", encoding="utf-8")
    summary_handler.setLevel(logging.INFO)
    summary_handler.setFormatter(detailed_formatter)
    logger.addHandler(summary_handler)

    return logger


def cleanup_old_logs(log_dir: Path, keep_days: int) -> None:
    """Remove log files older than keep_days"""
    cutoff_date = datetime.now() - timedelta(days=keep_days)

    for log_file in log_dir.glob("*.log"):
        if log_file.stat().st_mtime < cutoff_date.timestamp():
            try:
                log_file.unlink()
            except Exception:
                pass


def create_status_file(content_path: str, status: str, details: Dict) -> None:
    """Create a status file in the torrent directory"""
    status_file = Path(content_path).parent / ".qbt_process_status.json"

    status_data = {
        "timestamp": datetime.now().isoformat(),
        "status": status,
        "details": details,
    }

    with open(status_file, "w") as f:
        json.dump(status_data, f, indent=2)


def main(torrent_name=None, content_path=None, info_hash=None):
    """Main entry point for post-execution script"""
    # If no arguments provided, read from sys.argv (for backward compatibility)
    if torrent_name is None or content_path is None or info_hash is None:
        if len(sys.argv) < 4:
            print(
                "Usage: qbt_post_process.py <torrent_name> <content_path> <info_hash>"
            )
            print(
                "This script should be called by qBittorrent's post-execution feature"
            )
            sys.exit(1)

        torrent_name = sys.argv[1]
        content_path = sys.argv[2]
        info_hash = sys.argv[3]

    # Load configuration
    try:
        config_manager = ConfigManager()
        if not config_manager.validate_config():
            print("Configuration validation failed!")
            sys.exit(1)
        config = config_manager.config  # Use config directly
    except Exception as e:
        print(f"Failed to load config: {e}")
        print("Make sure you have a valid config file and .env file set up.")
        print("Run: python src/config_manager.py to see configuration status")
        sys.exit(1)

    # Setup logging
    logger = setup_logging(config, torrent_name)
    logger.info(f"Starting post-processing for: {torrent_name}")
    logger.info(f"Content path: {content_path}")
    logger.info(f"Info hash: {info_hash}")

    # Initialize components
    qbt_api = QBittorrentAPI(config)
    validator = TorrentValidator(config)
    processor = FileProcessor(config, logger)

    # Tag as processing
    if qbt_api.enabled:
        qbt_api.add_tags(info_hash, ["processing"])

    try:
        # Validate torrent
        is_valid, reason, mkv_files = validator.validate(torrent_name, "", content_path)

        if not is_valid:
            logger.info(f"Torrent skipped: {reason}")
            if qbt_api.enabled:
                qbt_api.remove_tags(info_hash, ["processing"])
            sys.exit(0)

        logger.info(f"Found {len(mkv_files)} valid MKV files to process")

        # Process files
        results = processor.process_files(torrent_name, mkv_files)

        # Log results
        success_count = len(results["success"])
        failed_count = len(results["failed"])

        logger.info(
            f"Processing complete: {success_count} succeeded, {failed_count} failed"
        )

        # Handle failures
        if failed_count > 0:
            for failure in results["failed"]:
                logger.error(
                    f"Failed: {failure.get('input', 'Unknown')} - "
                    f"{failure.get('error', 'Unknown error')}"
                )

            # Tag as failed
            if qbt_api.enabled:
                qbt_api.remove_tags(info_hash, ["processing"])
                qbt_api.add_tags(info_hash, ["failed"])

            # Create status file
            create_status_file(content_path, "failed", results)

            sys.exit(1)

        # All successful - delete torrent if configured
        if config["processing"]["delete_after_success"] and success_count > 0:
            logger.info("Deleting torrent and source files")

            if qbt_api.enabled:
                if qbt_api.delete_torrent(info_hash, delete_files=True):
                    logger.info("Torrent deleted successfully")
                else:
                    logger.warning("Failed to delete torrent via API")
                    # Tag as completed but not deleted
                    qbt_api.remove_tags(info_hash, ["processing"])
                    qbt_api.add_tags(info_hash, ["completed"])
            else:
                logger.warning(
                    "qBittorrent API not available, manual deletion required"
                )
                create_status_file(content_path, "completed_awaiting_deletion", results)
        else:
            # Tag as completed
            if qbt_api.enabled:
                qbt_api.remove_tags(info_hash, ["processing"])
                qbt_api.add_tags(info_hash, ["completed"])

        logger.info("Post-processing completed successfully")

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        logger.error(traceback.format_exc())

        # Tag as failed
        if qbt_api.enabled:
            qbt_api.remove_tags(info_hash, ["processing"])
            qbt_api.add_tags(info_hash, ["failed"])

        # Create status file
        create_status_file(content_path, "error", {"error": str(e)})

        sys.exit(1)


if __name__ == "__main__":
    main()
