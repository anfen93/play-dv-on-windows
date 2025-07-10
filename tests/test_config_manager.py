"""
Tests for config_manager.py module - configuration management system
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from play_dv_on_windows.config_manager import ConfigManager


class TestConfigManager:
    """Test configuration manager functionality"""

    def test_load_default_config(self):
        """Test loading default configuration"""
        # Mock the default.json file
        default_config = {
            "paths": {"output_dir": "./converted"},
            "qbittorrent": {"host": "localhost", "port": 8080},
            "processing": {"parallel_episodes": 2},
        }

        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = True
            with patch(
                "builtins.open", mock_open(read_data=json.dumps(default_config))
            ):
                config_manager = ConfigManager()

                assert config_manager.config["qbittorrent"]["host"] == "localhost"
                assert config_manager.config["processing"]["parallel_episodes"] == 2

    def test_environment_variable_override(self):
        """Test that environment variables override config values"""
        default_config = {
            "paths": {"output_dir": "./converted"},
            "qbittorrent": {"host": "localhost", "port": 8080, "password": None},
            "processing": {"parallel_episodes": 2},
        }

        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = True
            with patch(
                "builtins.open", mock_open(read_data=json.dumps(default_config))
            ):
                with patch.dict(
                    "os.environ",
                    {"QBT_PASSWORD": "test_password", "QBT_HOST": "remote_host"},
                ):
                    config_manager = ConfigManager()

                    assert (
                        config_manager.config["qbittorrent"]["password"]
                        == "test_password"
                    )
                    assert config_manager.config["qbittorrent"]["host"] == "remote_host"

    def test_get_method(self):
        """Test the get method for accessing nested config values"""
        config = {
            "qbittorrent": {"host": "localhost", "port": 8080},
            "paths": {"output_dir": "./converted"},
        }

        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = True
            with patch("builtins.open", mock_open(read_data=json.dumps(config))):
                config_manager = ConfigManager()

                assert config_manager.get("qbittorrent.host") == "localhost"
                assert config_manager.get("qbittorrent.port") == 8080
                assert config_manager.get("nonexistent.key", "default") == "default"

    def test_validation_success(self):
        """Test successful configuration validation"""
        config = {
            "paths": {"output_dir": "./test_output"},
            "qbittorrent": {"host": "localhost", "port": 8080, "password": "test"},
            "processing": {"parallel_episodes": 2},
            "filters": {"require_4k": True},
        }

        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = True
            with patch("builtins.open", mock_open(read_data=json.dumps(config))):
                with patch("pathlib.Path.mkdir") as mock_mkdir:
                    config_manager = ConfigManager()

                    assert config_manager.validate_config() is True
                    mock_mkdir.assert_called_once()

    def test_validation_failure(self):
        """Test configuration validation failure"""
        config = {
            "paths": {"output_dir": "/invalid/path/that/cannot/be/created"},
            "qbittorrent": {"host": "localhost"},
            "processing": {"parallel_episodes": 2},
        }

        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = True
            with patch("builtins.open", mock_open(read_data=json.dumps(config))):
                with patch("pathlib.Path.mkdir") as mock_mkdir:
                    mock_mkdir.side_effect = PermissionError("Permission denied")
                    config_manager = ConfigManager()

                    assert config_manager.validate_config() is False


class TestConfigManagerHelpers:
    """Test configuration manager helper methods"""

    def test_convert_type(self):
        """Test type conversion utility"""
        config_manager = ConfigManager.__new__(ConfigManager)  # Create without __init__

        assert config_manager._convert_type("8080", int) == 8080
        assert config_manager._convert_type("true", bool) is True
        assert config_manager._convert_type("false", bool) is False
        assert config_manager._convert_type("invalid", int) is None

    def test_remove_none_values(self):
        """Test removing None values from config"""
        config_manager = ConfigManager.__new__(ConfigManager)  # Create without __init__

        test_dict = {
            "key1": "value1",
            "key2": None,
            "nested": {"key3": "value3", "key4": None},
        }

        result = config_manager._remove_none_values(test_dict)

        assert "key1" in result
        assert "key2" not in result
        assert "key3" in result["nested"]
        assert "key4" not in result["nested"]
