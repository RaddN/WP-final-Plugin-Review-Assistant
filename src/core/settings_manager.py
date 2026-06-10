"""Settings manager for WP Plugin Review Assistant."""
import json
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


class SettingsManager:
    """Manages application settings, primarily AI and scanning options."""

    DEFAULT_SETTINGS = {
        "ai_provider": "Ollama",  # Ollama / LM Studio / Disabled
        "model_name": "llama3:latest",
        "api_url": "http://localhost:11434",
        "ai_timeout": 180,
        "max_context_size": 4096,
        "enable_reasoning": True,
        "last_plugin_path": "",
        "last_site_path": "",
    }

    def __init__(self, settings_file: str = "settings.json"):
        self.settings_file = Path(settings_file)
        self.settings = self.DEFAULT_SETTINGS.copy()
        self.load()

    def load(self) -> Dict[str, Any]:
        """Load settings from JSON file."""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    for k, v in self.DEFAULT_SETTINGS.items():
                        if k not in loaded:
                            loaded[k] = v
                    self.settings = loaded
            except Exception as e:
                logger.error(f"Error loading settings: {e}")
        else:
            self.save()
        return self.settings

    def save(self) -> bool:
        """Save settings to JSON file."""
        try:
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=4)
            return True
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        return self.settings.get(key, default)

    def set(self, key: str, value: Any):
        """Set a setting value and save."""
        self.settings[key] = value
        self.save()
