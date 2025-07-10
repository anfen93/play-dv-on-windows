# Test Suite

Comprehensive tests for the Play DV on Windows converter covering unit tests, integration tests, and real-world scenarios.

## Test Data

The `tests/data/` directory can contain real Dolby Vision test files for enhanced testing:

- `DV8_TEST_with_subs.mkv` - Video with embedded subtitles (optional)
- `DV8_TEST_with_audio_subs.mkv` - Video with FLAC audio and subtitles (optional)

**Note**: Large test files have been removed from the repository to avoid Git LFS bandwidth limits.
Tests requiring these files will automatically skip when files are not present.
For local testing, you can add your own MKV files with these names.

## Test Modules

- `conftest.py` - Pytest configuration and shared fixtures
- `test_convert.py` - Core conversion functionality
- `test_qbt_post_process.py` - qBittorrent integration
- `test_integration.py` - End-to-end workflow testing
- `test_integration_real.py` - Real FFmpeg operations with test files
- `test_config_manager.py` - Configuration system validation

## Running Tests

**Install test dependencies:**
```bash
pip install -r requirements-test.txt
```

**Run all tests:**
```bash
python3 run_tests.py all
```

**Run specific test suites:**
```bash
python3 run_tests.py convert      # Core conversion tests
python3 run_tests.py qbt          # qBittorrent integration
python3 run_tests.py integration  # End-to-end tests
python3 run_tests.py quick        # Quick validation
```

**Run with coverage:**
```bash
python3 run_tests.py coverage
```

**Direct pytest usage:**
```bash
pytest tests/test_convert.py                                    # Specific module
pytest tests/test_convert.py::TestFFmpegTools                   # Specific class
pytest -k "test_dolby_vision"                                   # Pattern matching
pytest -v                                                       # Verbose output
```

## Test Categories

**Unit Tests:**
- Test individual functions and classes in isolation
- Use mocking to avoid external dependencies
- Fast execution, no file I/O

**Integration Tests:**
- Test module interactions and workflows
- Use temporary files and directories
- Validate end-to-end functionality

## Test Fixtures

Common fixtures available in `conftest.py`:

- `temp_dir` - Temporary directory for test files
- `sample_config` - Pre-configured test settings
- `mock_logger` - Mock logger instance
- `sample_streams_info` - Sample FFprobe output data
- `create_test_mkv` - Factory for creating test MKV files

## Mocking Strategy

Tests use mocking extensively to:
- Eliminate FFmpeg dependency during testing
- Prevent actual file system operations
- Control external API behavior
- Ensure fast test execution

## Coverage Focus

Priority areas for test coverage:
- Stream analysis and selection logic
- File validation and filtering
- Error handling and recovery
- Configuration loading and validation
- qBittorrent API interactions
