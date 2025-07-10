#!/usr/bin/env python3
"""
Configuration Manager for MKV to MP4 Converter
Handles loading from multiple sources: .env, config files, environment variables
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


class ConfigManager:
    """Manages configuration from multiple sources with precedence"""

    def __init__(
        self, config_file: Optional[str] = None, env_file: Optional[str] = None
    ):
        self.project_root = Path(__file__).parent.parent.parent

        # On Windows, use user home directory for config by default
        if os.name == "nt":  # Windows
            self.config_dir = Path.home() / ".play-dv-on-windows"
        else:
            self.config_dir = self.project_root / "config"

        self.package_config_dir = Path(__file__).parent / "config"

        # Default config file locations - try package first, then project
        self.default_config = self.package_config_dir / "default.json"
        if not self.default_config.exists():
            self.default_config = self.config_dir / "default.json"

        self.local_config = self.config_dir / "local.json"
        self.user_config = Path(config_file) if config_file else None

        # Environment file
        self.env_file = Path(env_file) if env_file else self.project_root / ".env"

        # Load configuration with precedence
        self.config = self._load_config()

    def _load_env_file(self) -> Dict[str, str]:
        """Load environment variables from .env file"""
        env_vars = {}

        if self.env_file.exists():
            try:
                with open(self.env_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, value = line.split("=", 1)
                            env_vars[key.strip()] = value.strip().strip("\"'")
            except Exception as e:
                print(f"Warning: Failed to load .env file: {e}")

        return env_vars

    def _load_json_config(self, config_path: Path) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        try:
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load config {config_path}: {e}")

        return {}

    def _merge_configs(
        self, base: Dict[str, Any], override: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Recursively merge configuration dictionaries"""
        result = base.copy()

        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value

        return result

    def _apply_env_overrides(
        self, config: Dict[str, Any], env_vars: Dict[str, str]
    ) -> Dict[str, Any]:
        """Apply environment variable overrides to config"""
        # Load .env file variables into environment
        for key, value in env_vars.items():
            os.environ[key] = value

        # Apply specific overrides
        overrides = {
            "qbittorrent": {
                "host": os.getenv("QBT_HOST"),
                "port": self._convert_type(os.getenv("QBT_PORT"), int),
                "username": os.getenv("QBT_USERNAME"),
                "password": os.getenv("QBT_PASSWORD"),
            },
            "paths": {
                "output_dir": os.getenv("OUTPUT_DIR"),
                "temp_dir": os.getenv("TEMP_DIR"),
                "log_dir": os.getenv("LOG_DIR"),
            },
        }

        # Custom config file location
        if os.getenv("CONFIG_FILE"):
            custom_config = self._load_json_config(Path(os.getenv("CONFIG_FILE")))
            config = self._merge_configs(config, custom_config)

        # Remove None values and merge
        overrides = self._remove_none_values(overrides)
        return self._merge_configs(config, overrides)

    def _convert_type(self, value: Optional[str], target_type: type):
        """Convert string value to target type"""
        if value is None:
            return None

        try:
            if target_type == bool:
                return value.lower() in ("true", "1", "yes", "on")
            return target_type(value)
        except (ValueError, TypeError):
            return None

    def _remove_none_values(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively remove None values from dictionary"""
        result = {}
        for key, value in d.items():
            if value is not None:
                if isinstance(value, dict):
                    nested = self._remove_none_values(value)
                    if nested:  # Only add if the nested dict has content
                        result[key] = nested
                else:
                    result[key] = value
        return result

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration with precedence: default < local < user < env"""
        # Start with default config
        config = self._load_json_config(self.default_config)

        if not config:
            raise RuntimeError(
                f"Failed to load default config from {self.default_config}"
            )

        # Merge local config
        local_config = self._load_json_config(self.local_config)
        if local_config:
            config = self._merge_configs(config, local_config)

        # Merge user-specified config
        if self.user_config:
            user_config = self._load_json_config(self.user_config)
            if user_config:
                config = self._merge_configs(config, user_config)

        # Load environment variables
        env_vars = self._load_env_file()

        # Apply environment overrides
        config = self._apply_env_overrides(config, env_vars)

        # Resolve paths to absolute paths
        config = self._resolve_paths(config)

        return config

    def _resolve_paths(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Convert relative paths to absolute paths"""
        path_keys = ["output_dir", "temp_dir", "log_dir"]

        for key in path_keys:
            if key in config["paths"] and config["paths"][key]:
                path = Path(config["paths"][key])
                if not path.is_absolute():
                    # On Windows, use user home directory as base for relative paths
                    if os.name == "nt":  # Windows
                        config["paths"][key] = str(self.config_dir / path.name)
                    else:
                        config["paths"][key] = str(self.project_root / path)

        # Expand Windows environment variables in allowed_base_dirs
        if "allowed_base_dirs" in config["paths"]:
            expanded_dirs = []
            for dir_path in config["paths"]["allowed_base_dirs"]:
                if isinstance(dir_path, str):
                    # Expand environment variables (e.g., %USERNAME%)
                    expanded_path = os.path.expandvars(dir_path)
                    # Expand user home directory (~)
                    expanded_path = os.path.expanduser(expanded_path)
                    expanded_dirs.append(expanded_path)
                else:
                    expanded_dirs.append(dir_path)
            config["paths"]["allowed_base_dirs"] = expanded_dirs

        return config

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation"""
        keys = key.split(".")
        value = self.config

        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def __getitem__(self, key: str) -> Any:
        """Dict-like access to config"""
        return self.config[key]

    def get_qbt_config(self) -> Dict[str, Any]:
        """Get qBittorrent configuration"""
        return self.config["qbittorrent"]

    def get_processing_config(self) -> Dict[str, Any]:
        """Get processing configuration"""
        return self.config["processing"]

    def get_filter_config(self) -> Dict[str, Any]:
        """Get filter configuration"""
        return self.config["filters"]

    def save_local_config(self, config_updates: Dict[str, Any]) -> None:
        """Save updates to local config file"""
        try:
            # Load existing local config
            existing = self._load_json_config(self.local_config)

            # Merge updates
            updated = self._merge_configs(existing, config_updates)

            # Ensure config directory exists
            self.config_dir.mkdir(exist_ok=True)

            # Save to local config
            with open(self.local_config, "w", encoding="utf-8") as f:
                json.dump(updated, f, indent=2)

            print(f"Configuration saved to {self.local_config}")

        except Exception as e:
            print(f"Failed to save local config: {e}")

    def validate_config(self) -> bool:
        """Validate the loaded configuration"""
        required_sections = ["paths", "qbittorrent", "processing", "filters"]

        for section in required_sections:
            if section not in self.config:
                print(f"Error: Missing required config section: {section}")
                return False

        # Validate required paths
        output_dir = Path(self.config["paths"]["output_dir"])
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"Error: Cannot create output directory {output_dir}: {e}")
            return False

        # Validate qBittorrent config
        qbt_config = self.config["qbittorrent"]
        if not qbt_config.get("password"):
            print("Warning: qBittorrent password not set. Some features may not work.")

        return True

    def print_config_summary(self) -> None:
        """Print a summary of the loaded configuration"""
        print("Configuration Summary:")
        print(f"  Output Directory: {self.config['paths']['output_dir']}")
        print(f"  Log Directory: {self.config['paths']['log_dir']}")
        print(
            f"  qBittorrent: {self.config['qbittorrent']['host']}:"
            f"{self.config['qbittorrent']['port']}"
        )
        print(
            f"  Filters: 4K={self.config['filters']['require_4k']}, "
            f"DV={self.config['filters']['require_dv']}"
        )
        print(
            f"  Processing: {self.config['processing']['parallel_episodes']} "
            f"parallel episodes"
        )


def create_sample_env() -> None:
    """Create a sample .env file for the user"""
    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"

    if env_file.exists():
        print(f".env file already exists at {env_file}")
        return

    sample_content = """# qBittorrent Configuration
QBT_HOST=localhost
QBT_PORT=8080
QBT_USERNAME=admin
QBT_PASSWORD=your_password_here

# Paths (optional overrides)
# OUTPUT_DIR=/path/to/converted/files
# TEMP_DIR=/path/to/temp
# LOG_DIR=/path/to/logs

# Custom config file (optional)
# CONFIG_FILE=/path/to/custom/config.json
"""

    try:
        with open(env_file, "w", encoding="utf-8") as f:
            f.write(sample_content)
        print(f"Sample .env file created at {env_file}")
        print("Please edit it with your qBittorrent credentials.")
    except Exception as e:
        print(f"Failed to create .env file: {e}")


if __name__ == "__main__":
    # Test configuration loading
    config_manager = ConfigManager()

    if config_manager.validate_config():
        config_manager.print_config_summary()
    else:
        print("Configuration validation failed!")
        create_sample_env()
