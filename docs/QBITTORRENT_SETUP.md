# qBittorrent Integration Setup

Automate Play DV on Windows conversion by integrating with qBittorrent's post-execution feature. This allows automatic processing of downloaded 4K Dolby Vision content.

## Prerequisites

- qBittorrent 4.1+ installed and running
- Play DV on Windows installed **globally**: `pip install play-dv-on-windows`
- Python 3.7+ available in system PATH

**Important**: qBittorrent runs as a system service and cannot access tools installed in virtual environments. The package must be installed globally or you must use full Python paths in the post-execution script.

## Step 1: Enable qBittorrent Web UI

1. **Open qBittorrent**
2. **Go to Tools → Options**
3. **Click "Web UI" tab**
4. **Enable "Web User Interface (Remote control)"**
5. **Set authentication:**
   - Username: `admin` (or your preference)
   - Password: Choose a secure password
6. **Note the port** (default: 8080)
7. **Click OK**

## Step 2: Configure Environment

1. **Set up the package:**
   ```bash
   play-dv-setup
   play-dv-config --init
   ```

2. **Configure qBittorrent credentials:**
   ```bash
   # Edit config/local.json
   {
     "qbittorrent": {
       "enabled": true,
       "host": "localhost",
       "port": 8080,
       "username": "admin",
       "password": "your_chosen_password"
     }
   }
   ```

3. **Test the connection:**
   ```bash
   play-dv-config --validate
   ```

## Step 3: Set Post-Execution Script

1. **In qBittorrent, go to Tools → Options**
2. **Click "Downloads" tab**
3. **Scroll down to "Run external program on torrent completion"**
4. **Check the box to enable**
5. **Enter the command:**
   ```
   play-dv-qbt "%N" "%F" "%I"
   ```

### Parameter Explanation

- `%N` - Torrent name
- `%F` - Content path (file or directory)
- `%I` - Info hash

### Platform-Specific Examples

**Windows:**
```
play-dv-qbt "%N" "%F" "%I"
```

**Linux:**
```
play-dv-qbt "%N" "%F" "%I"
```

**macOS:**
```
play-dv-qbt "%N" "%F" "%I"
```

**Alternative (if pip install location issues):**
```
python -m play_dv_on_windows.cli qbt "%N" "%F" "%I"
```

## Step 4: Test the Setup

1. **Download a test torrent** (preferably a small 4K DV file)
2. **Check the logs:**
   ```bash
   tail -f logs/summary.log
   ```
3. **Verify files are created** in your output directory

## Advanced Configuration

### Category-Based Processing

You can configure different processing for different categories:

1. **In qBittorrent, create categories:**
   - 4K-Movies
   - 4K-TV
   - Regular (excluded)

2. **Update your config to exclude non-4K categories:**
   ```json
   {
     "filters": {
       "excluded_categories": ["Regular", "Music", "Software"]
     }
   }
   ```

### Conditional Execution

For more control, create a wrapper script:

**`post_process_wrapper.py`:**
```python
#!/usr/bin/env python3
import sys
import subprocess
from pathlib import Path

def should_process(torrent_name, category):
    # Only process 4K DV content
    name_lower = torrent_name.lower()
    return any(res in name_lower for res in ['2160p', '4k', 'uhd']) and \
           any(dv in name_lower for dv in ['dv', 'dovi', 'dolby'])

if __name__ == "__main__":
    torrent_name = sys.argv[1]
    content_path = sys.argv[2]
    info_hash = sys.argv[3]
    category = sys.argv[4] if len(sys.argv) > 4 else ""

    if should_process(torrent_name, category):
        script_path = Path(__file__).parent / "src" / "qbt_post_process.py"
        subprocess.run([
            "python", str(script_path),
            torrent_name, content_path, info_hash
        ])
    else:
        print(f"Skipping {torrent_name} - not 4K DV content")
```

Then use this wrapper in qBittorrent:
```
python3 "C:\path\to\post_process_wrapper.py" "%N" "%F" "%I" "%L"
```

## Troubleshooting

### Common Issues

**Script not executing**
- Check that Python is in system PATH
- Verify script path is correct and accessible
- Test script manually from command line

**Permission errors**
- Ensure qBittorrent has permission to execute scripts
- On Linux/macOS, make script executable: `chmod +x src/qbt_post_process.py`

**Connection failures**
- Verify Web UI is enabled and accessible
- Check username/password in config/local.json
- Test connection: `play-dv-config --validate`

**Files not processing**
- Check that torrents match your filter criteria
- Verify file sizes meet minimum requirements
- Check logs for detailed error messages

### Debug Mode

Enable detailed logging for troubleshooting:

1. **Create `config/local.json`:**
   ```json
   {
     "logging": {
       "level": "DEBUG"
     }
   }
   ```

2. **Check detailed logs:**
   ```bash
   tail -f logs/20231201_143022_TorrentName.log
   ```

### Manual Testing

Test the post-execution script manually:

```bash
play-dv-qbt \
  "Movie.Name.2024.2160p.DV.mkv" \
  "/path/to/downloaded/file.mkv" \
  "1234567890abcdef"
```

## Performance Considerations

### Parallel Processing

For TV shows with many episodes, increase parallel processing:

```json
{
  "processing": {
    "parallel_episodes": 4
  }
}
```

### Temporary Directory

Use a fast SSD for temporary processing:

```json
{
  "paths": {
    "temp_dir": "/fast/ssd/temp"
  }
}
```

### Automatic Cleanup

Enable automatic deletion of source files:

```json
{
  "processing": {
    "delete_after_success": true
  }
}
```

**⚠️ Warning:** This permanently deletes the original MKV files!

## Integration with Other Tools

### Plex Integration

The converter creates Plex-compatible folder structures:

```
output_dir/
├── Movie Name 2024/
│   ├── Movie Name 2024.mp4
│   └── Movie Name 2024.English.srt
└── TV Show S01/
    ├── TV Show S01E01.mp4
    ├── TV Show S01E01.English.srt
    └── ...
```

### Sonarr/Radarr Integration

If using Sonarr/Radarr with qBittorrent:

1. **Let Sonarr/Radarr handle the import first**
2. **Set up a separate "Converted" category**
3. **Use category-based filtering** to only process specific content

## Security Notes

1. **Secure your qBittorrent Web UI** with a strong password
2. **Consider binding Web UI to localhost only**
3. **Use environment variables** for sensitive configuration
4. **Never commit .env files** to version control
5. **Limit script permissions** to necessary directories only

## Monitoring

### Log Rotation

Logs are automatically rotated, but you can monitor disk usage:

```bash
du -sh logs/
```

### Success Rates

Check processing statistics:

```bash
grep "Processing complete" logs/summary.log | tail -10
```

### Failed Conversions

Monitor for failures:

```bash
grep "failed" logs/summary.log
```
