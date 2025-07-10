#!/usr/bin/env python3
"""
Semantic versioning utility for play-dv-on-windows
Automatically bumps version numbers following semantic versioning rules
"""
import argparse
import re
import sys
from pathlib import Path
from typing import Tuple


def get_current_version() -> str:
    """Get current version from pyproject.toml"""
    pyproject_path = Path(__file__).parent / "pyproject.toml"

    if not pyproject_path.exists():
        raise FileNotFoundError("pyproject.toml not found")

    content = pyproject_path.read_text()
    version_match = re.search(r'version = "([^"]+)"', content)

    if not version_match:
        raise ValueError("Version not found in pyproject.toml")

    return version_match.group(1)


def parse_version(version: str) -> Tuple[int, int, int]:
    """Parse semantic version string into components"""
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        raise ValueError(f"Invalid semantic version: {version}")

    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def bump_version(current_version: str, bump_type: str) -> str:
    """Bump version according to semantic versioning rules"""
    major, minor, patch = parse_version(current_version)

    if bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "patch":
        patch += 1
    else:
        raise ValueError(f"Invalid bump type: {bump_type}")

    return f"{major}.{minor}.{patch}"


def update_version_in_file(file_path: Path, old_version: str, new_version: str) -> None:
    """Update version in a file"""
    if not file_path.exists():
        return

    content = file_path.read_text()

    # Update version in pyproject.toml
    if file_path.name == "pyproject.toml":
        content = re.sub(r'version = "[^"]+"', f'version = "{new_version}"', content)

    # Update version in __init__.py
    elif file_path.name == "__init__.py":
        content = re.sub(
            r'__version__ = "[^"]+"', f'__version__ = "{new_version}"', content
        )

    file_path.write_text(content)


def main():
    """Main entry point for version bumping"""
    parser = argparse.ArgumentParser(
        description="Bump version following semantic versioning"
    )
    parser.add_argument(
        "bump_type", choices=["major", "minor", "patch"], help="Type of version bump"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )

    args = parser.parse_args()

    try:
        current_version = get_current_version()
        new_version = bump_version(current_version, args.bump_type)

        print(f"Current version: {current_version}")
        print(f"New version: {new_version}")

        if args.dry_run:
            print("DRY RUN - No changes made")
            return

        # Update version in files
        project_root = Path(__file__).parent
        files_to_update = [
            project_root / "pyproject.toml",
            project_root / "src" / "play_dv_on_windows" / "__init__.py",
        ]

        for file_path in files_to_update:
            update_version_in_file(file_path, current_version, new_version)
            print(f"Updated version in {file_path.name}")

        print(f"Version bumped from {current_version} to {new_version}")
        print(f"Don't forget to commit and tag: git tag v{new_version}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
