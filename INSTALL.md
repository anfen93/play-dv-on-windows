# Installation Guide

## Quick Start

1. **Install the package:**
   ```bash
   pip install play-dv-on-windows
   ```

2. **Set up the tool:**
   ```bash
   play-dv-setup
   ```

3. **Initialize configuration:**
   ```bash
   play-dv-config --init
   ```

4. **Convert your first file:**
   ```bash
   play-dv-convert your_file.mkv
   ```

## Requirements

- **Python 3.8+**
- **FFmpeg** (must be installed separately and available in PATH)
- **FFprobe** (usually comes with FFmpeg)

## Available Commands

After installation, you'll have access to these commands:

### `play-dv-setup`
Initial setup and dependency checking
```bash
play-dv-setup                # Full setup
play-dv-setup --check-deps   # Check dependencies only
play-dv-setup --create-dirs  # Create directories only
```

### `play-dv-convert`
Convert MKV files to MP4
```bash
play-dv-convert file.mkv                           # Convert single file
play-dv-convert file1.mkv file2.mkv                # Convert multiple files
play-dv-convert file.mkv --output-dir /tmp/output  # Specify output directory
play-dv-convert file.mkv --dry-run                 # See what would be done
play-dv-convert file.mkv --config custom.json     # Use custom config file
```

### `play-dv-config`
Manage configuration
```bash
play-dv-config --show      # Show current configuration
play-dv-config --validate  # Validate configuration
play-dv-config --init      # Create default configuration
```

### `play-dv-qbt`
qBittorrent post-processing (for automated use)
```bash
play-dv-qbt "torrent_name" "/path/to/content" "hash"
```

## Configuration

The tool uses a layered configuration system:

1. **Package defaults** (built-in)
2. **User configuration** (`config/local.json`)
3. **Environment variables** (`.env` file)

### Creating Custom Configuration

```bash
# Create default configuration
play-dv-config --init

# Edit the configuration file
nano config/local.json
```

Example `config/local.json`:
```json
{
  "paths": {
    "output_dir": "./converted",
    "log_dir": "./logs",
    "allowed_base_dirs": [".", "~", "/media/downloads"]
  },
  "qbittorrent": {
    "enabled": true,
    "host": "localhost",
    "port": 8080,
    "username": "admin",
    "password": "password"
  },
  "processing": {
    "max_parallel_episodes": 2
  }
}
```

## qBittorrent Integration

For automated processing with qBittorrent:

1. **Install and configure** the package as above
2. **Set up qBittorrent** post-processing:
   - Go to Tools → Options → Downloads
   - Check "Run external program on torrent completion"
   - Set the command to: `play-dv-qbt "%N" "%F" "%I"`

## Troubleshooting

### FFmpeg not found
```bash
# Check if FFmpeg is installed
ffmpeg -version

# If not installed, download from https://ffmpeg.org/download.html
# Make sure it's in your PATH
```

### Configuration issues
```bash
# Validate your configuration
play-dv-config --validate

# Show current configuration
play-dv-config --show
```

### Permission issues
Make sure the output directory is writable and input files are accessible.

## Development Installation

For development or testing:

```bash
# Clone the repository
git clone https://github.com/anfen93/play-dv-on-windows.git
cd play-dv-on-windows

# Install in development mode
pip install -e .

# Run tests
pytest
```
