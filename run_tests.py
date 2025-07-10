#!/usr/bin/env python3
"""
Test runner script for the MKV to MP4 converter project
Provides convenient ways to run different test suites
"""
import subprocess
import sys
from pathlib import Path


def get_python_command():
    """Get the correct Python command for the current platform"""
    # Use sys.executable to get the current Python interpreter
    # This works correctly in virtual environments on all platforms
    return sys.executable


def run_command(cmd, description):
    """Run a command and handle the result"""
    print(f"\n{'=' * 60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print("=" * 60)

    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode == 0
    except Exception as e:
        print(f"Error running command: {e}")
        return False


def main():
    """Main test runner"""
    if len(sys.argv) < 2:
        print("Usage: python run_tests.py <test_type>")
        print("\nAvailable test types:")
        print("  all         - Run all tests")
        print("  unit        - Run unit tests only")
        print("  integration - Run integration tests only")
        print("  convert     - Run convert.py tests only")
        print("  qbt         - Run qbt_post_process.py tests only")
        print("  coverage    - Run tests with coverage report")
        print("  quick       - Run a quick smoke test")
        sys.exit(1)

    test_type = sys.argv[1].lower()
    project_root = Path(__file__).parent

    # Change to project directory
    import os

    os.chdir(project_root)

    success = True

    python_cmd = get_python_command()

    if test_type == "all":
        success = run_command([python_cmd, "-m", "pytest", "tests/", "-v"], "All tests")

    elif test_type == "unit":
        success = run_command(
            [
                python_cmd,
                "-m",
                "pytest",
                "tests/test_convert.py",
                "tests/test_qbt_post_process.py",
                "tests/test_logging_config.py",
                "-v",
            ],
            "Unit tests",
        )

    elif test_type == "integration":
        success = run_command(
            [python_cmd, "-m", "pytest", "tests/test_integration.py", "-v"],
            "Integration tests",
        )

    elif test_type == "convert":
        success = run_command(
            [python_cmd, "-m", "pytest", "tests/test_convert.py", "-v"],
            "Convert module tests",
        )

    elif test_type == "qbt":
        success = run_command(
            [python_cmd, "-m", "pytest", "tests/test_qbt_post_process.py", "-v"],
            "qBittorrent post-process tests",
        )

    elif test_type == "coverage":
        success = run_command(
            [
                python_cmd,
                "-m",
                "pytest",
                "tests/",
                "--cov=.",
                "--cov-report=html",
                "--cov-report=term",
            ],
            "Tests with coverage",
        )
        if success:
            print("\nCoverage report generated in htmlcov/index.html")

    elif test_type == "quick":
        success = run_command(
            [
                python_cmd,
                "-m",
                "pytest",
                "tests/test_convert.py::TestFFmpegTools",
                "-v",
            ],
            "Quick smoke test",
        )

    else:
        print(f"Unknown test type: {test_type}")
        sys.exit(1)

    if success:
        print(f"\n✅ {test_type.capitalize()} tests completed successfully!")
        sys.exit(0)
    else:
        print(f"\n❌ {test_type.capitalize()} tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
