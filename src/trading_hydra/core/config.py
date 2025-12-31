"""Configuration loader for YAML files"""
import os
import yaml
from typing import Any, Dict, Optional

_settings_cache: Optional[Dict[str, Any]] = None
_bots_config_cache: Optional[Dict[str, Any]] = None


def _find_config_path(filename: str) -> str:
    possible_paths = [
        os.path.join(os.getcwd(), "config", filename),
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "config", filename),
        f"/home/runner/workspace/config/{filename}",
    ]
    
    for p in possible_paths:
        if os.path.exists(p):
            return p
    
    raise FileNotFoundError(f"Config file not found: {filename}. Searched: {possible_paths}")


def load_settings(config_path: Optional[str] = None) -> Dict[str, Any]:
    global _settings_cache
    if _settings_cache is not None:
        return _settings_cache
    
    try:
        file_path = config_path or _find_config_path("settings.yaml")
        with open(file_path, "r") as f:
            _settings_cache = yaml.safe_load(f)
        
        # Validate required settings structure
        if not isinstance(_settings_cache, dict):
            raise ValueError("Settings file must contain a dictionary")
        
        # Ensure runner config exists with defaults
        if "runner" not in _settings_cache:
            _settings_cache["runner"] = {}
        if "loop_interval_seconds" not in _settings_cache["runner"]:
            _settings_cache["runner"]["loop_interval_seconds"] = 5
            
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Configuration error: {e}")
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in settings file: {e}")
    
    return _settings_cache


def load_bots_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    global _bots_config_cache
    if _bots_config_cache is not None:
        return _bots_config_cache
    
    file_path = config_path or _find_config_path("bots.yaml")
    with open(file_path, "r") as f:
        _bots_config_cache = yaml.safe_load(f)
    return _bots_config_cache


def reload_configs() -> None:
    global _settings_cache, _bots_config_cache
    _settings_cache = None
    _bots_config_cache = None
