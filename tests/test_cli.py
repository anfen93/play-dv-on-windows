"""
Tests for CLI functionality using best practices
"""

import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from play_dv_on_windows.cli import config_cli, convert_cli, qbt_cli, setup_cli


class TestConvertCLI:
    """Test the convert CLI entry point"""

    @patch("play_dv_on_windows.convert.find_ffmpeg_tools")
    def test_convert_cli_help(self, mock_find):
        """Test that help works via CLI wrapper"""
        mock_find.return_value = ("/usr/bin/ffmpeg", "/usr/bin/ffprobe")

        with patch("sys.argv", ["play-dv-convert", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                convert_cli()

            # argparse exits with 0 for help
            assert exc_info.value.code == 0

    @patch("play_dv_on_windows.convert.find_ffmpeg_tools")
    def test_convert_cli_dry_run(self, mock_find):
        """Test dry-run mode through CLI"""
        mock_find.return_value = ("/usr/bin/ffmpeg", "/usr/bin/ffprobe")

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test MKV file
            test_mkv = Path(temp_dir) / "test.mkv"
            test_mkv.write_bytes(b"fake mkv content")

            # Test dry-run via CLI wrapper
            with patch("sys.argv", ["play-dv-convert", str(test_mkv), "--dry-run"]):
                with pytest.raises(SystemExit) as exc_info:
                    convert_cli()

                # Should exit successfully
                assert exc_info.value.code == 0

    @patch("play_dv_on_windows.convert.find_ffmpeg_tools")
    def test_convert_cli_output_dir(self, mock_find):
        """Test output directory override"""
        mock_find.return_value = ("/usr/bin/ffmpeg", "/usr/bin/ffprobe")

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            input_dir = Path(temp_dir) / "input"
            input_dir.mkdir()
            output_dir = Path(temp_dir) / "output"

            test_mkv = input_dir / "test.mkv"
            test_mkv.write_bytes(b"fake mkv content")

            # Test with output directory
            with patch(
                "sys.argv",
                [
                    "play-dv-convert",
                    str(test_mkv),
                    "--output-dir",
                    str(output_dir),
                    "--dry-run",
                ],
            ):
                with pytest.raises(SystemExit) as exc_info:
                    convert_cli()

                # Should exit successfully
                assert exc_info.value.code == 0

                # In dry-run mode, output directory should not be created
                # (dry-run doesn't actually create anything)

    def test_convert_cli_no_args(self):
        """Test convert CLI with no arguments"""
        with patch("sys.argv", ["play-dv-convert"]):
            with pytest.raises(SystemExit) as exc_info:
                convert_cli()

            # argparse exits with 2 for missing required arguments
            assert exc_info.value.code == 2

    def test_convert_cli_error_handling(self):
        """Test CLI error handling"""
        with patch("sys.argv", ["play-dv-convert", "nonexistent.mkv"]):
            with pytest.raises(SystemExit) as exc_info:
                convert_cli()

            # Should exit with error code
            assert exc_info.value.code == 1


class TestQbtCLI:
    """Test the qBittorrent CLI command"""

    def test_qbt_cli_help(self):
        """Test that help works"""
        with patch("sys.argv", ["play-dv-qbt", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                qbt_cli()

            # argparse exits with 0 for help
            assert exc_info.value.code == 0

    @patch("play_dv_on_windows.qbt_post_process.main")
    def test_qbt_cli_with_args(self, mock_main):
        """Test qbt CLI with proper arguments"""
        with patch(
            "sys.argv", ["play-dv-qbt", "torrent_name", "/path/to/content", "hash123"]
        ):
            qbt_cli()

            mock_main.assert_called_once()

    def test_qbt_cli_insufficient_args(self):
        """Test qbt CLI with insufficient arguments"""
        with patch("sys.argv", ["play-dv-qbt", "only_one_arg"]):
            with pytest.raises(SystemExit) as exc_info:
                qbt_cli()

            # Should exit with error for missing args
            assert exc_info.value.code == 2

    @patch("play_dv_on_windows.qbt_post_process.main")
    def test_qbt_cli_with_test_file(self, mock_main):
        """Test qbt CLI with test file path"""
        test_file = Path(__file__).parent / "data"

        with patch(
            "sys.argv",
            ["play-dv-qbt", "Test.4K.DV.2160p.mkv", str(test_file), "hash123"],
        ):
            qbt_cli()

            mock_main.assert_called_once()


class TestConfigCLI:
    """Test the config CLI command"""

    def test_config_cli_help(self):
        """Test that help works"""
        with patch("sys.argv", ["play-dv-config", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                config_cli()

            # argparse exits with 0 for help
            assert exc_info.value.code == 0

    @patch("play_dv_on_windows.config_manager.ConfigManager")
    def test_config_cli_validate(self, mock_config_manager):
        """Test config validation via CLI"""
        mock_instance = MagicMock()
        mock_instance.validate_config.return_value = True
        mock_config_manager.return_value = mock_instance

        with patch("sys.argv", ["play-dv-config", "--validate"]):
            config_cli()

            mock_instance.validate_config.assert_called_once()

    @patch("play_dv_on_windows.config_manager.ConfigManager")
    def test_config_cli_show(self, mock_config_manager):
        """Test config show via CLI"""
        mock_instance = MagicMock()
        mock_config_manager.return_value = mock_instance

        with patch("sys.argv", ["play-dv-config", "--show"]):
            config_cli()

            mock_instance.print_config_summary.assert_called_once()

    @patch("builtins.open")
    @patch("play_dv_on_windows.config_manager.ConfigManager")
    def test_config_cli_init(self, mock_config_manager, mock_open):
        """Test config initialization"""
        # Mock the ConfigManager instance
        mock_instance = MagicMock()
        mock_config_manager.return_value = mock_instance

        # Mock the local_config path to not exist
        mock_instance.local_config.exists.return_value = False
        mock_instance.config_dir.mkdir = MagicMock()

        with patch("sys.argv", ["play-dv-config", "--init"]):
            config_cli()

            # Should try to create config file
            mock_open.assert_called()


class TestSetupCLI:
    """Test the setup CLI command"""

    def test_setup_cli_help(self):
        """Test that help works"""
        with patch("sys.argv", ["play-dv-setup", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                setup_cli()

            # argparse exits with 0 for help
            assert exc_info.value.code == 0

    @patch("subprocess.run")
    @patch("pathlib.Path.mkdir")
    def test_setup_cli_check_deps(self, mock_mkdir, mock_run):
        """Test dependency checking"""
        # Mock successful ffmpeg check
        mock_run.return_value = MagicMock(returncode=0)

        with patch("sys.argv", ["play-dv-setup", "--check-deps"]):
            setup_cli()

            # Should check for both ffmpeg and ffprobe
            assert mock_run.call_count >= 2

    @patch("pathlib.Path.mkdir")
    def test_setup_cli_create_dirs(self, mock_mkdir):
        """Test directory creation"""
        with patch("sys.argv", ["play-dv-setup", "--create-dirs"]):
            setup_cli()

            # Should create directories
            mock_mkdir.assert_called()


class TestCLIIntegration:
    """Integration tests for CLI commands with real package installation"""

    def test_installed_commands_available(self):
        """Test that the installed CLI commands are available"""
        # Test that our entry points work when called via subprocess
        try:
            result = subprocess.run(
                ["play-dv-convert", "--help"], capture_output=True, text=True
            )
            assert result.returncode == 0
            assert "Convert 4K Dolby Vision MKV files" in result.stdout
        except FileNotFoundError:
            pytest.skip("Package not installed in current environment")

    def test_convert_real_file_dry_run(self):
        """Test converting a real test file in dry-run mode"""
        test_file = Path(__file__).parent / "data" / "DV8_TEST_with_audio_subs.mkv"
        if not test_file.exists():
            pytest.skip("Test MKV file not found")

        # Test via installed command
        try:
            result = subprocess.run(
                ["play-dv-convert", str(test_file), "--dry-run"],
                capture_output=True,
                text=True,
            )

            # Should succeed
            assert result.returncode == 0
            assert "Would convert" in result.stderr or "DRY RUN" in result.stderr
        except FileNotFoundError:
            pytest.skip("Package not installed in current environment")
