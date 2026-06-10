"""Plugin detection and metadata extraction."""
import re
from pathlib import Path
from typing import Optional, Tuple
import logging

from models import PluginMetadata
from utils import (
    cleanup_temp_directory,
    create_temp_directory,
    is_hidden_or_dot,
    normalize_path,
    safe_extract_zip,
    validate_zip_file,
)


logger = logging.getLogger(__name__)


class PluginDetector:
    """Detect and extract WordPress plugin metadata."""

    # WordPress plugin header pattern
    HEADER_PATTERN = re.compile(
        r'^\s*\*?\s*(?P<key>[^:]+?):\s*(?P<value>.+?)$',
        re.MULTILINE | re.IGNORECASE
    )

    # Mapping of header keys to normalized names
    HEADER_KEYS = {
        'Plugin Name': 'name',
        'Version': 'version',
        'Text Domain': 'text_domain',
        'Requires PHP': 'requires_php',
        'Requires at least': 'requires_wp',
        'Requires Plugins': 'requires_plugins',
        'Author': 'author',
        'Author URI': 'author_uri',
        'Plugin URI': 'plugin_uri',
        'License': 'license',
        'Description': 'description',
    }

    def __init__(self, plugin_path: str):
        """Initialize detector with plugin path."""
        self.plugin_path = normalize_path(plugin_path)
        self.is_zip = False
        self.temp_dir: Optional[Path] = None
        self.root_path: Optional[Path] = None

    def detect(self) -> Tuple[bool, Optional[PluginMetadata], str]:
        """Detect plugin metadata. Returns (success, metadata, error_message)."""
        try:
            if self.plugin_path.suffix.lower() == '.zip':
                return self._detect_from_zip()
            elif self.plugin_path.is_dir():
                return self._detect_from_directory()
            else:
                return False, None, "Plugin path is neither a directory nor a ZIP file"
        except Exception as e:
            logger.error(f"Error detecting plugin: {e}")
            return False, None, str(e)

    def _detect_from_directory(self) -> Tuple[bool, Optional[PluginMetadata], str]:
        """Detect plugin from directory."""
        if not self.plugin_path.is_dir():
            return False, None, "Path is not a directory"

        # Find main plugin file
        main_file = self._find_main_plugin_file(self.plugin_path)
        if not main_file:
            return False, None, "No plugin file found in directory"

        metadata = self._extract_metadata(main_file, self.plugin_path)
        if not metadata:
            return False, None, "Could not extract plugin metadata"

        return True, metadata, ""

    def _detect_from_zip(self) -> Tuple[bool, Optional[PluginMetadata], str]:
        """Detect plugin from ZIP file."""
        is_valid, msg = validate_zip_file(self.plugin_path)
        if not is_valid:
            return False, None, msg

        # Extract to temp directory
        self.temp_dir = create_temp_directory()
        try:
            safe_extract_zip(self.plugin_path, self.temp_dir)

            # Find plugin root in extracted files
            plugin_root = self._find_plugin_root_in_zip()
            if not plugin_root:
                return False, None, "Could not find plugin root in ZIP"

            main_file = self._find_main_plugin_file(plugin_root)
            if not main_file:
                return False, None, "No plugin file found in extracted ZIP"

            metadata = self._extract_metadata(main_file, plugin_root)
            if not metadata:
                return False, None, "Could not extract plugin metadata"

            return True, metadata, ""
        except Exception as e:
            return False, None, f"Error extracting ZIP: {e}"

    def _find_plugin_root_in_zip(self) -> Optional[Path]:
        """Find the plugin root directory in extracted ZIP."""
        if not self.temp_dir:
            return None

        # Look for a single directory containing plugin files, ignoring hidden/dot files
        entries = []
        for entry in self.temp_dir.iterdir():
            if is_hidden_or_dot(entry, self.temp_dir):
                continue
            entries.append(entry)

        if len(entries) == 1 and entries[0].is_dir():
            return entries[0]

        # Otherwise, assume temp_dir is the root
        return self.temp_dir

    def _find_main_plugin_file(self, directory: Path) -> Optional[Path]:
        """Find the main plugin PHP file."""
        if not directory.is_dir():
            return None

        # Look for common patterns
        patterns = [
            directory.name + ".php",
            "plugin.php",
            "index.php",
        ]

        for pattern in patterns:
            candidate = directory / pattern
            if candidate.exists() and not is_hidden_or_dot(candidate, directory) and self._is_plugin_file(candidate):
                return candidate

        # Search all PHP files for plugin header, ignoring hidden/dot files
        for php_file in directory.glob("*.php"):
            if not is_hidden_or_dot(php_file, directory) and self._is_plugin_file(php_file):
                return php_file

        return None

    def _is_plugin_file(self, file_path: Path) -> bool:
        """Check if a PHP file has a WordPress plugin header."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(2000)  # Read first 2KB
                return 'Plugin Name:' in content
        except Exception:
            return False

    def _extract_metadata(self, plugin_file: Path, root_path: Path) -> Optional[PluginMetadata]:
        """Extract plugin metadata from main file and readme.txt."""
        try:
            # Read plugin file header
            header_data = self._read_plugin_header(plugin_file)
            if not header_data:
                return None

            # Read readme.txt if it exists
            readme_file = root_path / "readme.txt"
            readme_data = {}
            if readme_file.exists():
                readme_data = self._read_readme(readme_file)

            metadata_dict = {**readme_data, **header_data}

            # Create metadata object
            metadata = PluginMetadata(
                name=metadata_dict.get('name', 'Unknown'),
                version=metadata_dict.get('version', '1.0.0'),
                stable_tag=metadata_dict.get('stable_tag', ''),
                text_domain=metadata_dict.get('text_domain', ''),
                requires_php=metadata_dict.get('requires_php', '7.4'),
                requires_wp=metadata_dict.get('requires_wp', '5.0'),
                requires_plugins=metadata_dict.get('requires_plugins', []),
                author=metadata_dict.get('author', ''),
                author_uri=metadata_dict.get('author_uri', ''),
                plugin_uri=metadata_dict.get('plugin_uri', ''),
                license=metadata_dict.get('license', 'GPL v2 or later'),
                description=metadata_dict.get('description', ''),
                main_file=str(plugin_file.name),
                root_path=str(root_path),
            )

            # Detect WooCommerce compatibility
            metadata.woo_compatible = self._detect_woo_usage(root_path)

            self.root_path = root_path
            return metadata

        except Exception as e:
            logger.error(f"Error extracting metadata: {e}")
            return None

    def _read_plugin_header(self, file_path: Path) -> dict:
        """Read WordPress plugin header."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(5000)  # Read first 5KB

            # Extract header block (between <?php and first non-comment line)
            header_block = content.split('<?php', 1)[-1]
            header_lines = []
            for line in header_block.split('\n'):
                if line.strip().startswith('*') or line.strip().startswith('//'):
                    header_lines.append(line)
                elif header_lines and not line.strip().startswith('*'):
                    break

            header_text = '\n'.join(header_lines)

            # Parse headers
            metadata = {}
            for line in header_text.split('\n'):
                for key, normalized_key in self.HEADER_KEYS.items():
                    if key.lower() in line.lower():
                        match = re.search(rf'{re.escape(key)}\s*:\s*(.+?)(?=\n|$)', line, re.IGNORECASE)
                        if match:
                            value = match.group(1).strip()
                            if normalized_key == 'requires_plugins':
                                value = [p.strip() for p in value.split(',')]
                            metadata[normalized_key] = value

            return metadata
        except Exception as e:
            logger.error(f"Error reading plugin header: {e}")
            return {}

    def _read_readme(self, readme_path: Path) -> dict:
        """Read WordPress readme.txt metadata."""
        try:
            with open(readme_path, 'r', encoding='utf-8') as f:
                content = f.read()

            metadata = {}
            lines = content.split('\n')

            # Extract stable tag
            for line in lines:
                if line.startswith('Stable tag:'):
                    metadata['stable_tag'] = line.replace('Stable tag:', '').strip()

            return metadata
        except Exception as e:
            logger.error(f"Error reading readme.txt: {e}")
            return {}

    def _detect_woo_usage(self, root_path: Path) -> bool:
        """Check if plugin mentions WooCommerce."""
        try:
            # Check readme.txt
            readme_file = root_path / "readme.txt"
            if readme_file.exists():
                with open(readme_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().lower()
                    if 'woocommerce' in content:
                        return True

            # Check main PHP file for woocommerce references
            main_file = self._find_main_plugin_file(root_path)
            if main_file:
                with open(main_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().lower()
                    if 'woocommerce' in content or 'wc_get_' in content or 'wc_' in content:
                        return True

            return False
        except Exception:
            return False

    def cleanup(self):
        """Clean up temporary files."""
        if self.temp_dir:
            cleanup_temp_directory(self.temp_dir)
