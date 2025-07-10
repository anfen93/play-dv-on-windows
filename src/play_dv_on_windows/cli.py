"""
CLI entry points for the play-dv-on-windows package
"""

import argparse
import sys
from pathlib import Path


def convert_cli():
    """CLI entry point for the convert command"""
    from .convert import main as convert_main

    # The convert module now handles its own argument parsing
    # Just pass through the raw arguments
    try:
        convert_main()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except SystemExit:
        # Let SystemExit pass through (it's how argparse exits)
        raise
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def qbt_cli():
    """CLI entry point for the qBittorrent post-processing command"""
    from .qbt_post_process import main as qbt_main

    parser = argparse.ArgumentParser(
        description="qBittorrent post-processing for Dolby Vision MKV files",
        prog="play-dv-qbt",
    )
    parser.add_argument("torrent_name", help="Name of the torrent")
    parser.add_argument("content_path", help="Path to the torrent content")
    parser.add_argument("hash", help="Torrent hash")
    parser.add_argument("--config", "-c", help="Path to configuration file")

    args = parser.parse_args()

    try:
        qbt_main(args.torrent_name, args.content_path, args.hash)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def config_cli():
    """CLI entry point for configuration management"""
    from .config_manager import ConfigManager

    parser = argparse.ArgumentParser(
        description="Manage play-dv-on-windows configuration", prog="play-dv-config"
    )
    parser.add_argument(
        "--validate", action="store_true", help="Validate current configuration"
    )
    parser.add_argument(
        "--show", action="store_true", help="Show current configuration"
    )
    parser.add_argument(
        "--init", action="store_true", help="Initialize default configuration"
    )

    args = parser.parse_args()

    try:
        config_manager = ConfigManager()

        if args.validate:
            if config_manager.validate_config():
                print("✅ Configuration is valid")
            else:
                print("❌ Configuration validation failed")
                sys.exit(1)
        elif args.show:
            config_manager.print_config_summary()
        elif args.init:
            # Create default config directories and files using ConfigManager
            config_manager.config_dir.mkdir(exist_ok=True)

            # Copy default configuration if it doesn't exist
            local_config = config_manager.local_config
            if not local_config.exists():
                import json

                default_config = {
                    "paths": {
                        "allowed_base_dirs": [".", "~"],
                        "output_dir": "./converted",
                        "log_dir": "./logs",
                    },
                    "qbittorrent": {
                        "enabled": False,
                        "host": "localhost",
                        "port": 8080,
                        "username": "",
                        "password": "",
                    },
                }
                with open(local_config, "w") as f:
                    json.dump(default_config, f, indent=2)
                print(f"✅ Created default configuration at {local_config}")
            else:
                print(f"✅ Configuration already exists at {local_config}")
        else:
            # Default behavior - show summary
            config_manager.print_config_summary()

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def setup_cli():
    """CLI entry point for initial setup"""
    parser = argparse.ArgumentParser(
        description="Set up play-dv-on-windows for first-time use", prog="play-dv-setup"
    )
    parser.add_argument(
        "--check-deps",
        action="store_true",
        help="Check for required dependencies (FFmpeg)",
    )
    parser.add_argument(
        "--create-dirs", action="store_true", help="Create necessary directories"
    )

    args = parser.parse_args()

    try:
        print("Play DV on Windows - Setup")
        print("=" * 40)

        # Create necessary directories using ConfigManager
        if args.create_dirs or not any([args.check_deps]):
            from .config_manager import ConfigManager

            config_manager = ConfigManager()

            dirs_to_create = [
                Path(config_manager.config["paths"]["output_dir"]),
                Path(config_manager.config["paths"]["log_dir"]),
                config_manager.config_dir,
            ]

            for directory in dirs_to_create:
                directory.mkdir(parents=True, exist_ok=True)
                print(f"✅ Created directory: {directory}")

        # Check dependencies
        if args.check_deps or not any([args.create_dirs]):
            print("\nChecking dependencies...")
            import subprocess

            try:
                subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
                print("✅ FFmpeg found")
            except (subprocess.CalledProcessError, FileNotFoundError):
                print("❌ FFmpeg not found!")
                print("Please install FFmpeg and ensure it's in your PATH")
                print("Download from: https://ffmpeg.org/download.html")
                sys.exit(1)

            try:
                subprocess.run(["ffprobe", "-version"], capture_output=True, check=True)
                print("✅ FFprobe found")
            except (subprocess.CalledProcessError, FileNotFoundError):
                print("❌ FFprobe not found!")
                print("FFprobe is usually included with FFmpeg")
                sys.exit(1)

        print("\n" + "=" * 40)
        print("Setup completed successfully! 🎉")
        print("\nNext steps:")
        print("1. Run 'play-dv-config --init' to create default configuration")
        print("2. Edit config/local.json for your specific needs")
        print("3. Test with: play-dv-convert your_file.mkv")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    print("This module provides CLI entry points. Use the installed commands:")
    print("- play-dv-convert: Convert MKV files to MP4")
    print("- play-dv-qbt: qBittorrent post-processing")
    print("- play-dv-config: Configuration management")
    print("- play-dv-setup: Initial setup")
