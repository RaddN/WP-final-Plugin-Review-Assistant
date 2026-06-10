"""WP-CLI integration for WordPress site management."""
import json
import logging
import os
import shutil
from pathlib import Path
from typing import List, Optional, Tuple, Dict

from utils import detect_php_binary, run_command, normalize_path


logger = logging.getLogger(__name__)


class WPCLIRunner:
    """Execute WP-CLI commands from a LocalWP WordPress root."""

    def __init__(self, wp_root: str, php_binary: Optional[str] = None):
        self.wp_root = normalize_path(wp_root)
        self.php_binary = php_binary or detect_php_binary(self.wp_root)
        self.wp_cli_binary = self._detect_wp_cli()
        logger.debug("WP root: %s", self.wp_root)
        logger.debug("PHP binary: %s", self.php_binary)
        logger.debug("WP-CLI binary: %s", self.wp_cli_binary)

    def _detect_wp_cli(self) -> Optional[str]:
        """Detect WP-CLI executable or phar."""
        candidates = [
            shutil.which("wp"),
            shutil.which("wp.bat"),
            str(Path.home() / "AppData" / "Roaming" / "Local" / "lightning-services" / "wp-cli" / "wp.bat"),
        ]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return candidate
        return shutil.which("wp") or "wp"

    def _find_wp_phar(self) -> Optional[Path]:
        """Find wp-cli.phar in common locations."""
        candidates = [
            Path.home() / "wp-cli.phar",
            Path.home() / ".wp-cli" / "wp-cli.phar",
            Path("C:/wp-cli/wp-cli.phar"),
        ]
        for path in candidates:
            if path.exists():
                return path
        return None

    def _normalize_args(self, args: List[str]) -> List[str]:
        if args and args[0] == "wp":
            return args[1:]
        return args

    def run(
        self,
        args: List[str],
        timeout: int = 30,
    ) -> Tuple[bool, str, str]:
        """Execute a WP-CLI command with LocalWP-friendly fallbacks."""
        args = self._normalize_args(args)
        strategies: List[List[str]] = []

        if self.wp_cli_binary:
            strategies.append([self.wp_cli_binary] + args)

        if self.php_binary:
            wp_phar = self._find_wp_phar()
            if wp_phar:
                strategies.append([self.php_binary, str(wp_phar)] + args)
            strategies.append([self.php_binary, self.wp_cli_binary or "wp"] + args)

        strategies.append(["wp"] + args)

        last_stdout = ""
        last_stderr = ""
        for cmd in strategies:
            logger.debug("Running: %s", " ".join(cmd))
            success, stdout, stderr = run_command(cmd, self.wp_root, timeout)
            last_stdout, last_stderr = stdout, stderr
            if success:
                return True, stdout, stderr

        return False, last_stdout, last_stderr

    def verify_wp_cli(self) -> Tuple[bool, str]:
        """Verify WP-CLI is available and working."""
        success, stdout, stderr = self.run(["--info"])
        if success:
            return True, stdout
        return False, f"WP-CLI error: {stderr or stdout}"

    def get_wp_version(self) -> Optional[str]:
        success, stdout, _ = self.run(["core", "version"])
        return stdout.strip() if success else None

    def get_php_version(self) -> Optional[str]:
        success, stdout, _ = self.run(["eval", "echo phpversion();"])
        return stdout.strip() if success else None

    def get_site_url(self) -> Optional[str]:
        success, stdout, _ = self.run(["option", "get", "siteurl"])
        return stdout.strip() if success else None

    def plugin_is_installed(self, plugin_slug: str) -> bool:
        success, _, _ = self.run(["plugin", "is-installed", plugin_slug])
        return success

    def plugin_is_active(self, plugin_slug: str) -> bool:
        success, _, _ = self.run(["plugin", "is-active", plugin_slug])
        return success

    def install_plugin(self, plugin_slug: str) -> Tuple[bool, str]:
        logger.info("Installing plugin: %s", plugin_slug)
        success, stdout, stderr = self.run(["plugin", "install", plugin_slug, "--activate"])
        if success:
            return True, f"Plugin {plugin_slug} installed and activated"
        return False, stderr or stdout

    def activate_plugin(self, plugin_slug: str) -> Tuple[bool, str]:
        logger.info("Activating plugin: %s", plugin_slug)
        success, stdout, stderr = self.run(["plugin", "activate", plugin_slug])
        if success:
            return True, f"Plugin {plugin_slug} activated"
        return False, stderr or stdout

    def list_plugins(self) -> Tuple[bool, List[Dict]]:
        success, stdout, _ = self.run(["plugin", "list", "--format=json"])
        if success:
            try:
                return True, json.loads(stdout)
            except json.JSONDecodeError:
                return False, []
        return False, []

    def run_plugin_check(self, plugin_path: str) -> Tuple[bool, dict, str]:
        plugin_path = str(normalize_path(plugin_path))
        logger.info("Running Plugin Check on: %s", plugin_path)

        success, stdout, stderr = self.run(
            ["plugin", "check", plugin_path, "--format=json"],
            timeout=120,
        )

        if success and stdout.strip():
            try:
                return True, json.loads(stdout), ""
            except json.JSONDecodeError:
                pass

        # Fallback: try without --format=json and parse text output
        success2, stdout2, stderr2 = self.run(
            ["plugin", "check", plugin_path],
            timeout=120,
        )
        if success2 or stdout2.strip():
            return True, self._parse_text_plugin_check(stdout2), stderr2

        return False, {}, stderr or stderr2 or stdout

    def _parse_text_plugin_check(self, output: str) -> dict:
        """Parse plain-text Plugin Check output into a dict."""
        result = {"errors": [], "warnings": [], "info": []}
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            lower = line.lower()
            if "error" in lower or "fail" in lower:
                result["errors"].append({"title": line, "message": line})
            elif "warn" in lower:
                result["warnings"].append({"title": line, "message": line})
            else:
                result["info"].append({"title": line, "message": line})
        return result

    def get_site_info(self) -> dict:
        info = {
            "wp_version": self.get_wp_version(),
            "php_version": self.get_php_version(),
            "site_url": self.get_site_url(),
        }
        success, plugins = self.list_plugins()
        if success:
            info["plugins_total"] = len(plugins)
            info["plugins_active"] = len([p for p in plugins if p.get("status") == "active"])
        return info
