# Play DV on Windows

Converts 4K Dolby Vision MKV files to MP4 format while preserving DV metadata and extracting subtitles. Designed for Windows users who need MP4 files for proper Dolby Vision playback in Windows Media Player.

## Why This Exists

Windows Dolby Vision playback is limited. While both MKV and MP4 can contain DV metadata, Windows Media Player only properly handles DV in MP4 containers. This tool converts your MKV files to MP4 without re-encoding, preserving quality and DV metadata while making them compatible with Windows DV playback.

Additionally, it extracts embedded subtitles to external SRT files, which is often necessary for proper subtitle display in Windows Media Player.

## Who This Is For

- Windows users with Dolby Vision displays (OLED TVs, monitors)
- People who download 4K DV content in MKV format
- Anyone wanting automated conversion through qBittorrent
- Users who need reliable subtitle extraction

## Features

- Preserves Dolby Vision metadata during conversion
- No re-encoding (fast, lossless quality)
- Extracts English subtitles to SRT files
- **Smart subtitle handling**: Extracts compatible text-based subtitles, warns about incompatible PGS/image formats
- Automatic detection of 4K DV content
- qBittorrent integration for automated processing
- Handles both movies and TV show episodes
- Configurable output organization

## Installation

**Requirements:**
- Python 3.7+
- FFmpeg with ffprobe (must be installed separately)
- qBittorrent (optional, for automation)

### Quick Installation (Recommended)

```bash
pip install play-dv-on-windows
play-dv-setup
```

### Development Installation

```bash
git clone https://github.com/anfen93/play-dv-on-windows.git
cd play-dv-on-windows
pip install -e .
play-dv-setup
```

## Usage

### Command Line Interface

After installation, you have access to these commands:

**Setup and Configuration:**
```bash
play-dv-setup                # Initial setup and dependency checking
play-dv-config --init        # Initialize configuration
play-dv-config --show        # Show current configuration
play-dv-config --validate    # Validate configuration
```

**Convert files directly:**
```bash
play-dv-convert movie.mkv                           # Convert single file
play-dv-convert file1.mkv file2.mkv                # Convert multiple files
play-dv-convert movie.mkv --output-dir /tmp/output  # Specify output directory
play-dv-convert movie.mkv --dry-run                 # See what would be done
play-dv-convert movie.mkv --config custom.json     # Use custom config
```

> **⚠️ Important Security Note**: Before converting files, you must configure allowed source directories. The tool will reject files outside of these directories for security. See the Configuration section below for setup details.

**qBittorrent automation:**
1. Enable Web UI in qBittorrent
2. Configure credentials: `play-dv-config --init` then edit `config/local.json`
3. Set post-execution script: `play-dv-qbt "%N" "%F" "%I"`

The script automatically detects 4K Dolby Vision content by analyzing torrent names for keywords like "2160p", "4K", "DV", "DoVi", etc.

## Configuration

### ⚠️ Required First Step: Configure Allowed Directories

For security, the tool only processes files from explicitly allowed directories. **You must configure this before converting any files:**

1. **Initialize configuration:**
   ```bash
   play-dv-config --init
   ```

2. **Edit your config file** (`C:\Users\USERNAME\.play-dv-on-windows\local.json` on Windows):
   ```bash
   # Windows
   notepad "C:\Users\%USERNAME%\.play-dv-on-windows\local.json"

   # Or use any editor
   code "C:\Users\%USERNAME%\.play-dv-on-windows\local.json"
   ```

3. **Add your source directories:**
   ```json
   {
     "paths": {
       "allowed_base_dirs": [
         "C:\\torrents",
         "C:\\Downloads",
         "D:\\Media"
       ]
     }
   }
   ```

4. **Validate your config:**
   ```bash
   play-dv-config --validate
   ```

If you try to convert files from directories not in `allowed_base_dirs`, you'll get an error like:
```
ERROR - Invalid input file: File path not in allowed directory
```

### Full Configuration Options

The tool uses a layered configuration system. Your `local.json` can contain:

```json
{
  "paths": {
    "output_dir": "./converted",
    "log_dir": "./logs",
    "allowed_base_dirs": [".", "~", "/path/to/downloads"]
  },
  "processing": {
    "delete_after_success": false,
    "max_parallel_episodes": 2
  },
  "filters": {
    "require_4k": true,
    "require_dv": true
  },
  "qbittorrent": {
    "enabled": true,
    "host": "localhost",
    "port": 8080,
    "username": "admin",
    "password": "your_password"
  }
}
```

Environment variables are also supported via `.env` file:
```bash
QBT_HOST=localhost
QBT_PORT=8080
QBT_USERNAME=admin
QBT_PASSWORD=your_password
```

## How It Works

**Detection:** Analyzes torrent names for 4K and Dolby Vision indicators
**Conversion:** Uses FFmpeg to remux streams without re-encoding
**Organization:** Creates clean folder structures for media libraries
**Cleanup:** Optionally removes source files after successful conversion

The conversion process:
1. Analyze MKV streams with ffprobe
2. Select video stream, ALL audio streams, and compatible subtitle streams
3. Extract text-based subtitles to separate SRT files (SRT, ASS, MOV_TEXT only)
4. Remux selected streams to MP4 container with Windows Media Player compatible audio conversion
5. Preserve all metadata including Dolby Vision

## Audio & Subtitle Handling

### Audio Processing
- **Includes ALL audio streams** from source (not just English)
- **Automatic conversion** of incompatible formats (DTS, TrueHD, PCM) to EAC3 for Windows Media Player compatibility
- **Preserves compatible formats** (EAC3, AC3, AAC) without re-encoding

### Subtitle Processing
- **Text-based subtitles** (SRT, ASS, MOV_TEXT): Direct extraction to external SRT files
- **Image-based subtitles** (PGS, DVD): Shows warning and skips (not compatible with Windows Media Player)
- **Conversion continues** even if some subtitle extraction fails

**Note**: For PGS/image subtitle conversion, use Subtitle Edit (free software): https://www.nikse.dk/subtitleedit

## Testing

```bash
python run_tests.py all      # Full test suite
python run_tests.py quick    # Quick validation
python run_tests.py convert  # Core conversion tests
python run_tests.py qbt      # qBittorrent integration tests
```

## Project Structure

```
src/play_dv_on_windows/
├── convert.py          # Core MKV to MP4 conversion
├── qbt_post_process.py # qBittorrent post-execution handler
├── config_manager.py   # Configuration management
├── cli.py              # Command-line interface
└── config/             # Package configuration files

config/                 # User configuration directory
└── local.json          # User configuration overrides

tests/                  # Comprehensive test suite
docs/                   # Additional documentation
```

## Technical Details

- Uses stream copying (`-c:v copy`, `-c:a copy`) for lossless conversion
- Preserves Dolby Vision RPU and metadata
- Supports multiple subtitle tracks
- Handles both single files and batch processing
- Thread-safe parallel processing for TV episodes
- Comprehensive error handling and logging

## Troubleshooting

**"File path not in allowed directory" error:** Add your source directory to `allowed_base_dirs` in your config file. See Configuration section above.

**FFmpeg not found:** Install FFmpeg and ensure it's in system PATH

**Conversion fails:** Check logs in `logs/` directory for detailed error information

**qBittorrent issues:** Verify Web UI is enabled and credentials are correct

**No files processed:** Ensure content matches 4K DV detection criteria

**Config file not found:** Run `play-dv-config --init` to create the initial configuration

## Development

**Setup for development:**
```bash
git clone https://github.com/anfen93/play-dv-on-windows.git
cd play-dv-on-windows
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
pip install -r requirements-test.txt
pre-commit install
```


## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

---

A practical solution for Windows Dolby Vision compatibility issues.
