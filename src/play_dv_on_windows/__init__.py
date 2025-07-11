"""
Play DV on Windows - A comprehensive 4K Dolby Vision MKV to MP4 converter

This package provides tools for converting 4K Dolby Vision MKV files to MP4 format,
designed for automated processing with qBittorrent integration.
"""

__version__ = "1.0.12"
__author__ = "anfen"
__email__ = "anfen93@gmail.com"

from .config_manager import ConfigManager
from .convert import main as convert_main
from .qbt_post_process import main as qbt_main

__all__ = ["convert_main", "qbt_main", "ConfigManager"]
