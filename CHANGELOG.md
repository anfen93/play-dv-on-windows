# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Semantic versioning support with bump_version.py utility
- Enhanced pre-commit hooks with flake8, isort, and bandit
- Comprehensive GitHub Actions workflow for CI/CD
- Release automation workflow

### Changed
- Improved CLI argument handling without sys.argv manipulation
- Consolidated package structure
- Enhanced security validation throughout codebase

### Removed
- Docker references from documentation (no longer supported)
- Legacy setup scripts and unused files

## [1.0.0] - 2024-07-10

### Added
- Initial release
- 4K Dolby Vision MKV to MP4 conversion with FFmpeg
- qBittorrent post-processing integration
- Comprehensive configuration management
- Security-focused path validation and input sanitization
- Parallel episode processing for TV shows
- Automatic subtitle extraction and organization
- Comprehensive test suite with security tests
- CLI tools for easy usage

### Security
- Path traversal prevention
- Input sanitization for all user inputs
- Secure credential handling
- Timeout protection for external processes
- Directory traversal attack prevention

[Unreleased]: https://github.com/anfen93/play-dv-on-windows/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/anfen93/play-dv-on-windows/releases/tag/v1.0.0
