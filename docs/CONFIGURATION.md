# Configuration Guide

Configuration for the MKV to MP4 Converter uses a layered system that allows flexible customization without modifying core files.

## Configuration System

Configuration is loaded in order of precedence (highest to lowest):

1. **Environment Variables** - Runtime overrides
2. **Custom Config File** - Via `CONFIG_FILE` environment variable
3. **Local Config** - `config/local.json`
4. **Default Config** - `config/default.json`
5. **Environment File** - `.env` file

The `ConfigManager` class handles automatic merging, validation, and path resolution.

## Quick Setup

1. **Install the package**
   ```bash
   pip install play-dv-on-windows
   ```

2. **Initialize configuration**
   ```bash
   play-dv-setup          # Initial setup
   play-dv-config --init  # Create default config
   ```

3. **Edit configuration**
   ```bash
   # Edit config/local.json with your settings
   # Or use environment variables in .env
   ```

4. **Validate configuration**
   ```bash
   play-dv-config --validate
   play-dv-config --show
   ```

## Configuration Sections

### Paths

Controls where files are processed and stored:

```json
{
  "paths": {
    "output_dir": "./converted",    // Where converted files go
    "temp_dir": null,              // Optional temp directory
    "log_dir": "./logs",           // Log file location
    "allowed_base_dirs": [         // Security: directories where input files are allowed
      ".",                         // Current directory
      "~",                         // User home directory
      "C:\\torrents",              // Windows torrent directory
      "/home/user/torrents",       // Linux torrent directory
      "/Downloads"                 // Common downloads directory
    ]
  }
}
```

**Environment Overrides:**
- `OUTPUT_DIR` - Override output directory
- `TEMP_DIR` - Override temp directory
- `LOG_DIR` - Override log directory

**Security Note:** The `allowed_base_dirs` setting controls which directories the application can read input files from. This prevents directory traversal attacks. Only directories in this list (and their subdirectories) are allowed. Non-existent directories are automatically filtered out.

### qBittorrent Connection

API connection settings:

```json
{
  "qbittorrent": {
    "host": "localhost",
    "port": 8080,
    "username": "admin",
    "password": null,              // Set via .env file
    "timeout": 30
  }
}
```

**Environment Variables:**
- `QBT_HOST` - qBittorrent host
- `QBT_PORT` - qBittorrent port
- `QBT_USERNAME` - qBittorrent username
- `QBT_PASSWORD` - qBittorrent password

### Processing Options

How files are processed:

```json
{
  "processing": {
    "parallel_episodes": 2,        // Concurrent episode processing
    "delete_after_success": false, // Delete source files after conversion
    "use_temp_dir": false,         // Use temporary directory
    "min_file_size_gb": 1.0,       // Skip files smaller than this
    "max_retries": 3,              // Retry failed conversions
    "retry_delay": 5               // Seconds between retries
  }
}
```

### Content Filters

What content gets processed:

```json
{
  "filters": {
    "require_4k": true,            // Only process 4K content
    "require_dv": true,            // Only process Dolby Vision
    "excluded_categories": [       // Skip these categories
      "music", "software", "books"
    ],
    "max_seasons_per_torrent": 1,  // Skip multi-season packs
    "allowed_extensions": [".mkv"], // Process these file types
    "keywords": {
      "resolution": ["2160p", "4K", "UHD"],
      "dolby_vision": ["DV", "DoVi", "Dolby.Vision"]
    }
  }
}
```

### FFmpeg Settings

Conversion parameters:

```json
{
  "ffmpeg": {
    "video_codec": "copy",         // Don't re-encode video
    "audio_codec": "copy",         // Don't re-encode audio
    "subtitle_codec": "mov_text",  // Subtitle format for MP4
    "extra_flags": ["-movflags", "+faststart"],
    "preserve_metadata": true      // Keep DV/HDR metadata
  }
}
```

### Logging

Log file management:

```json
{
  "logging": {
    "level": "INFO",               // DEBUG, INFO, WARNING, ERROR
    "keep_days": 30,              // Auto-delete old logs
    "max_file_size_mb": 50,       // Rotate large log files
    "console_output": true        // Print to console
  }
}
```

## Local Configuration

Create `config/local.json` to override defaults without modifying the base config:

```json
{
  "paths": {
    "output_dir": "/mnt/media/converted",
    "allowed_base_dirs": [
      ".",
      "~",
      "/mnt/torrents",
      "/home/user/Downloads"
    ]
  },
  "processing": {
    "parallel_episodes": 4,
    "delete_after_success": true
  },
  "logging": {
    "level": "DEBUG"
  }
}
```

## Environment File (.env)

Store sensitive information in `.env`:

```bash
# qBittorrent credentials
QBT_HOST=192.168.1.100
QBT_PORT=8080
QBT_USERNAME=admin
QBT_PASSWORD=secure_password

# Path overrides
OUTPUT_DIR=/mnt/plex/converted
TEMP_DIR=/tmp/mkv-conversion
LOG_DIR=/var/log/mkv-converter

# Custom config
CONFIG_FILE=/etc/mkv-converter/production.json
```

## Multiple Environments

### Development Setup
```bash
# .env.dev
QBT_HOST=localhost
QBT_PASSWORD=dev_password
OUTPUT_DIR=./dev_output
```

### Production Setup
```bash
# .env.prod
QBT_HOST=production-server
QBT_PASSWORD=strong_password
OUTPUT_DIR=/mnt/storage/media
```

Use different environments:
```bash
# Development
cp .env.dev .env
python src/qbt_post_process.py

# Production
cp .env.prod .env
python src/qbt_post_process.py
```

## Validation

The configuration is automatically validated on startup. Common issues:

**Invalid output directory**
```
Error: Cannot create output directory /invalid/path: Permission denied
```
*Solution: Check permissions or change output_dir*

**Missing qBittorrent password**
```
Warning: qBittorrent password not set. Some features may not work.
```
*Solution: Set QBT_PASSWORD in .env file*

**FFmpeg not found**
```
Error: ffmpeg and ffprobe not found in PATH
```
*Solution: Install FFmpeg and add to system PATH*

**File path not allowed**
```
Error: File path not in allowed directory: /unauthorized/path/movie.mkv
```
*Solution: Add the directory to `allowed_base_dirs` in your local.json configuration*

## Advanced Usage

### Custom Config Location

```bash
CONFIG_FILE=/path/to/custom.json python src/qbt_post_process.py
```

### Runtime Overrides

```bash
OUTPUT_DIR=/tmp/test python src/convert.py movie.mkv
```

### Config Debugging

```bash
# Test config loading
play-dv-config --validate
play-dv-config --show

# Verbose output with Python
python3 -c "
from play_dv_on_windows.config_manager import ConfigManager
config = ConfigManager()
import json
print(json.dumps(config.config, indent=2))
"
```

## Best Practices

1. **Never commit .env files** - Keep credentials secure
2. **Use local.json for customization** - Don't modify default.json
3. **Test config changes** - Run `play-dv-config --validate` after changes
4. **Backup your config** - Save working configurations
5. **Document custom settings** - Comment your local.json changes
