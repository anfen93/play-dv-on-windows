#!/usr/bin/env python3
"""
Setup script for MKV to MP4 Converter
Helps users configure the application for first-time use
"""
import shutil
import sys
from pathlib import Path


def main():
    """Main setup function"""
    print("MKV to MP4 Converter - Setup")
    print("=" * 40)

    project_root = Path(__file__).parent

    # Check if .env file exists
    env_file = project_root / ".env"
    env_example = project_root / ".env.example"

    if not env_file.exists() and env_example.exists():
        print("Creating .env file from template...")
        try:
            shutil.copy(env_example, env_file)
            print(f"✅ Created .env file at {env_file}")
            print("Please edit this file with your qBittorrent credentials!")
        except Exception as e:
            print(f"❌ Failed to create .env file: {e}")
            return False
    elif env_file.exists():
        print(f"✅ .env file already exists at {env_file}")
    else:
        print("❌ No .env.example file found!")
        return False

    # Create config directories
    config_dir = project_root / "config"
    config_dir.mkdir(exist_ok=True)
    print(f"✅ Config directory: {config_dir}")

    # Create default directories
    dirs_to_create = [project_root / "converted", project_root / "logs"]

    for directory in dirs_to_create:
        directory.mkdir(exist_ok=True)
        print(f"✅ Created directory: {directory}")

    # Check for FFmpeg
    print("\nChecking dependencies...")
    try:
        import subprocess

        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        print("✅ FFmpeg found")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ FFmpeg not found!")
        print("Please install FFmpeg and ensure it's in your PATH")
        print("Download from: https://ffmpeg.org/download.html")

    try:
        subprocess.run(["ffprobe", "-version"], capture_output=True, check=True)
        print("✅ FFprobe found")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ FFprobe not found!")
        print("FFprobe is usually included with FFmpeg")

    # Test configuration
    print("\nTesting configuration...")
    try:
        sys.path.insert(0, str(project_root / "src"))
        from play_dv_on_windows.config_manager import ConfigManager

        config_manager = ConfigManager()
        if config_manager.validate_config():
            print("✅ Configuration is valid")
            config_manager.print_config_summary()
        else:
            print("❌ Configuration validation failed")
            return False
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False

    print("\n" + "=" * 40)
    print("Setup completed successfully! 🎉")
    print("\nNext steps:")
    print("1. Edit .env file with your qBittorrent credentials")
    print("2. Optionally create config/local.json for custom settings")
    print("3. Test configuration: python src/config_manager.py")
    print("4. Run tests: python run_tests.py quick")
    print("\nFor qBittorrent integration:")
    print(
        f"Set post-execution script to: python {project_root}/src/qbt_post_process.py"
    )

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
