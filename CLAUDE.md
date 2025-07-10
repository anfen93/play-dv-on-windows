# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a comprehensive Python utility for converting 4K Dolby Vision MKV files to MP4 format, designed for automated processing with qBittorrent integration. It preserves video quality while creating Windows Media Player and Plex-compatible files.

## Core Functionality

The project consists of multiple components:

### Core Converter (`src/play_dv_on_windows/convert.py`)
1. Locates FFmpeg and FFprobe in the system PATH
2. Analyzes MKV files to identify streams (video, audio, subtitles)
3. Selects English audio tracks and English subtitles
4. Extracts all English subtitles to separate SRT files
5. Remuxes selected streams into MP4 container format with DV preservation

### qBittorrent Integration (`src/play_dv_on_windows/qbt_post_process.py`)
1. Validates 4K Dolby Vision content automatically
2. Processes multiple files in parallel (TV episodes)
3. Organizes output into clean folder structures
4. Manages torrent lifecycle (tagging, deletion)
5. Comprehensive logging and error handling

### Configuration Management (`src/play_dv_on_windows/config_manager.py`)
1. Layered configuration system (default → local → env → runtime)
2. Environment variable support with .env files
3. Automatic path resolution and validation
4. Multiple environment support (dev/prod)
5. **Security**: Configurable allowed directories for input file validation

### CLI Interface (`src/play_dv_on_windows/cli.py`)
1. Professional command-line entry points
2. Proper argument parsing and validation
3. Clean error handling and user feedback
4. Installable console scripts via pip

## Key Technical Details

### Dependencies
- **Python 3.7+** (standard library only for core functionality)
- **FFmpeg with FFprobe** (must be installed separately)
- **Optional**: `requests` (qBittorrent API), `psutil` (disk space checks)


### Project Structure
```
src/
└── play_dv_on_windows/      # Main package
    ├── __init__.py          # Package initialization and version
    ├── cli.py               # CLI entry points
    ├── convert.py           # Core conversion logic
    ├── qbt_post_process.py  # qBittorrent integration
    ├── config_manager.py    # Configuration management
    ├── config/              # Default configurations
    │   ├── default.json     # Base configuration
    │   └── local.json       # Package-level config
    └── examples/            # Example configurations
        └── local.json.example
config/                      # User configuration files
├── default.json            # User overrides
└── local.json              # Local user config (optional)
tests/                      # Comprehensive test suite
docs/                       # Documentation
.github/                    # GitHub automation
├── workflows/
│   ├── test.yml           # CI/CD pipeline
│   └── release.yml        # Automated releases
└── settings.yml           # Repository settings
```

### Installation and Setup
```bash
# Create virtual environment (IMPORTANT: Use .venv as default)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode
pip install -e .

# Install development dependencies
pip install -r requirements-test.txt

# Initial setup
play-dv-setup

# Verify installation
play-dv-config --validate
```

### Command Usage
```bash
# Manual conversion
play-dv-convert <file1.mkv> <file2.mkv> ...
play-dv-convert --output-dir /path/to/output file.mkv

# qBittorrent integration (configured automatically)
play-dv-qbt <torrent_name> <content_path> <hash>

# Configuration management
play-dv-config --show
play-dv-config --validate
play-dv-config --init

# Initial setup
play-dv-setup --check-deps
play-dv-setup --create-dirs
```

### Development Commands

**Environment Setup:**
```bash
# ALWAYS use .venv as the virtual environment name
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
pip install -r requirements-test.txt
```

**Testing:**
- **Test All**: `python run_tests.py all` (comprehensive pytest-based test suite)
- **Test Specific**: `python run_tests.py convert` or `python run_tests.py qbt`
- **Test with Coverage**: `python run_tests.py coverage`
- **Quick Test**: `python run_tests.py quick`

**Code Quality:**
- **Format Code**: `black src/ tests/`
- **Sort Imports**: `isort src/ tests/`
- **Lint Code**: `flake8 src/ tests/`
- **Security Scan**: `bandit -r src/`
- **Pre-commit All**: `pre-commit run --all-files`

**Version Management (Semantic Versioning):**
- **Patch Release** (bug fixes): `python bump_version.py patch`
- **Minor Release** (new features): `python bump_version.py minor`
- **Major Release** (breaking changes): `python bump_version.py major`
- **Preview Changes**: `python bump_version.py --dry-run patch`

**Release Process:**
```bash
# 1. Bump version and commit
python bump_version.py minor
git add .
git commit -m "Bump version to $(grep version pyproject.toml | cut -d'"' -f2)"

# 2. Create and push tag (triggers automated release)
VERSION=$(grep version pyproject.toml | cut -d'"' -f2)
git tag v$VERSION
git push origin main
git push origin v$VERSION

# 3. GitHub Actions will automatically:
#    - Run tests
#    - Build package
#    - Create GitHub release
#    - Upload release assets
```


## Architecture

The script follows a simple procedural design with clear function separation:

1. **find_ffmpeg_tools()**: Locates FFmpeg binaries using platform-specific commands
2. **analyze_streams()**: Uses FFprobe to get JSON metadata about video streams
3. **select_streams()**: Identifies appropriate video, audio, and subtitle streams based on language tags
4. **extract_subtitle()**: Extracts subtitle streams to external SRT files
5. **remux_to_mp4()**: Constructs and executes the FFmpeg remux command
6. **main()**: Orchestrates the conversion process for multiple files

## Important Implementation Notes

- The core converter processes multiple files in batch but sequentially
- The qBittorrent post-processor can handle parallel episode processing
- Output files are organized in Plex-compatible directory structure
- Existing output files are skipped to prevent overwrites
- All English subtitle tracks are extracted (not just the first one)
- Subtitle filenames include the track title for identification
- Video and audio streams are copied without re-encoding (`-c:v copy`, `-c:a copy`)
- Uses `mov_text` codec for subtitles in MP4 container
- Preserves Dolby Vision metadata through careful stream mapping

## Security Features

The project implements several security measures to prevent common attacks:

### Path Validation
- **Configurable allowed directories**: Only files within specified base directories can be processed
- **Directory traversal prevention**: Blocks `../` and similar path manipulation attempts
- **File extension validation**: Only `.mkv` files are accepted for processing
- **Path resolution**: All paths are resolved to absolute paths for consistent validation

### Input Sanitization
- **Filename sanitization**: Removes dangerous characters that could be used for command injection
- **Command injection prevention**: All subprocess calls use lists instead of shell commands
- **Timeout protection**: All external commands have timeouts to prevent hangs

### Configuration
The application automatically detects the platform and uses appropriate defaults:

**Windows**: Configuration stored in `C:\Users\USERNAME\.play-dv-on-windows\`
**Linux/macOS**: Configuration stored in `config/` directory

Add allowed directories to your local configuration file:
```json
{
  "paths": {
    "allowed_base_dirs": [
      ".",
      "~",
      "C:\\torrents",
      "C:\\Users\\%USERNAME%\\Downloads"
    ]
  }
}
```

Environment variables like `%USERNAME%` are automatically expanded on Windows.

## Testing

The project includes comprehensive pytest-based tests organized in the `tests/` directory:
- **Unit Tests**: `test_convert.py`, `test_qbt_post_process.py` - Test individual modules in isolation
- **Integration Tests**: `test_integration.py` - Test end-to-end workflows and module interactions
- **Security Tests**: `test_security.py` - Test security features and vulnerability prevention
- **Functional Tests**: `test_functional.py` - Test real behavior with minimal mocking
- **Real File Tests**: `test_integration_real.py` - Test with actual Dolby Vision MKV files
- **Configuration Tests**: `test_logging_config.py` - Test configuration system functionality
- **Test Configuration**: `conftest.py` - Shared fixtures and pytest configuration
- **Test Runner**: `run_tests.py` - Convenient script for running different test suites

### Running Tests
- All tests: `python run_tests.py all`
- Unit tests only: `python run_tests.py unit`
- Integration tests: `python run_tests.py integration`
- With coverage: `python run_tests.py coverage`
- Quick smoke test: `python run_tests.py quick`

### Test Dependencies
Install test dependencies with: `pip install -r requirements-test.txt`

## Development Workflow

### Setting Up Development Environment
1. **Clone and setup**:
   ```bash
   git clone <repository-url>
   cd play-dv-on-windows
   python -m venv .venv  # CRITICAL: Use .venv name
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -e .
   pip install -r requirements-test.txt
   ```

2. **Install pre-commit hooks**:
   ```bash
   pre-commit install
   ```

3. **Verify setup**:
   ```bash
   play-dv-setup --check-deps
   python run_tests.py quick
   ```

### Making Changes
1. **Create feature branch**: `git checkout -b feature/my-feature`
2. **Make changes and test**: `python run_tests.py all`
3. **Format code**: `pre-commit run --all-files`
4. **Commit**: Git hooks will auto-format and validate

### Releasing

#### Test Releases (Optional)
```bash
# For testing PyPI publishing before official release
python bump_version.py patch
VERSION=$(grep version pyproject.toml | cut -d'"' -f2)
git tag v$VERSION-test
git push origin v$VERSION-test
# This publishes to Test PyPI for verification
```

#### Official Releases
1. **Update CHANGELOG.md** with new features/fixes
2. **Bump version**: `python bump_version.py [major|minor|patch]`
3. **Commit and tag**:
   ```bash
   git add .
   git commit -m "Release v$(grep version pyproject.toml | cut -d'"' -f2)"
   VERSION=$(grep version pyproject.toml | cut -d'"' -f2)
   git tag v$VERSION
   git push origin main v$VERSION
   ```
4. **GitHub Actions automatically**:
   - Runs all tests
   - Builds the package
   - Publishes to PyPI
   - Creates GitHub release
   - Makes it available via `pip install play-dv-on-windows`

### Dependency Management

**Dependabot Configuration:**
- **Weekly updates** every Monday at 9:00 AM
- **Smart grouping**: Related dependencies updated together
- **Security prioritization**: Security updates get immediate attention
- **Automatic labeling**: PRs properly categorized and assigned

**Review Process:**
```bash
# Review Dependabot PRs weekly
# 1. Check the changelog/release notes
# 2. Run tests: python run_tests.py all
# 3. Verify no breaking changes
# 4. Merge if all checks pass
```

**Dependency Groups:**
- **Testing**: pytest, coverage tools
- **Security**: bandit, safety
- **Code Quality**: black, flake8, isort, pre-commit
- **GitHub Actions**: All workflow dependencies

### Important Notes
- **ALWAYS use `.venv`** as virtual environment name (tooling expects this)
- **Follow semantic versioning** strictly
- **Update CHANGELOG.md** before each release
- **Let GitHub Actions handle releases** - don't manual upload
- **All code must pass pre-commit hooks** before commit
- **Test coverage should remain above 80%**
- **Dependabot manages dependency updates** - review and merge weekly PRs
- **Security updates are automatically prioritized** via Dependabot grouping
