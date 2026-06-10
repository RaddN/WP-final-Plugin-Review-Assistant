"""WP-CLI integration for WordPress site management."""
import json
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from utils import detect_localwp_runtime, detect_php_binary, normalize_path, run_command


logger = logging.getLogger(__name__)


class WPCLIRunner:
    """Execute WP-CLI commands from a LocalWP WordPress root."""

    def __init__(self, wp_root: str, php_binary: Optional[str] = None):
        self.wp_root = normalize_path(wp_root)
        self.localwp_runtime = detect_localwp_runtime(self.wp_root)
        self.php_binary = (
            php_binary
            or self.localwp_runtime.get("php_binary")
            or detect_php_binary(self.wp_root)
        )
        self.php_ini = self.localwp_runtime.get("php_ini")
        self.wp_cli_binary = self._detect_wp_cli()
        self.wp_phar = self._find_wp_phar()
        self.base_command = self._build_base_command()
        logger.debug("WP root: %s", self.wp_root)
        logger.debug("PHP binary: %s", self.php_binary)
        logger.debug("PHP config: %s", self.php_ini)
        logger.debug("WP-CLI binary: %s", self.wp_cli_binary)
        logger.debug("WP-CLI PHAR: %s", self.wp_phar)

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
        return None

    def _find_wp_phar(self) -> Optional[Path]:
        """Find wp-cli.phar in common locations."""
        candidates = [
            Path(self.wp_cli_binary).with_name("wp-cli.phar") if self.wp_cli_binary else None,
            Path.home() / "wp-cli.phar",
            Path.home() / ".wp-cli" / "wp-cli.phar",
            Path("C:/wp-cli/wp-cli.phar"),
        ]
        for path in candidates:
            if path and path.exists():
                return path
        return None

    def _build_base_command(self) -> List[str]:
        """Choose one trustworthy WP-CLI invocation for this site."""
        if self.php_binary and self.wp_phar:
            command = [self.php_binary]
            if self.php_ini:
                command.extend(["-c", self.php_ini])
            command.append(str(self.wp_phar))
            return command
        if self.wp_cli_binary:
            return [self.wp_cli_binary]
        return []

    def _normalize_args(self, args: List[str]) -> List[str]:
        if args and args[0] == "wp":
            return args[1:]
        return args

    def run(
        self,
        args: List[str],
    ) -> Tuple[bool, str, str]:
        """Execute a WP-CLI command using the selected site-aware runtime."""
        args = self._normalize_args(args)
        if not self.base_command:
            return False, "", "WP-CLI was not found. Install WP-CLI or configure a WP-CLI PHAR."

        cmd = self.base_command + args
        logger.debug("Running: %s", " ".join(cmd))
        return run_command(cmd, self.wp_root)

    def verify_wp_cli(self) -> Tuple[bool, str]:
        """Verify WP-CLI is available and working."""
        success, stdout, stderr = self.run(["--info"])
        if success:
            return True, stdout
        return False, f"WP-CLI error: {stderr or stdout}"

    def verify_wordpress_site(self) -> Tuple[bool, str]:
        """Verify WP-CLI can bootstrap WordPress and connect to the site database."""
        success, stdout, stderr = self.run(["option", "get", "siteurl"])
        if success and stdout.strip():
            return True, stdout.strip()
        return False, stderr or stdout or "WP-CLI could not read the site URL."

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
        state, _ = self.get_plugin_installation_state(plugin_slug)
        return state is True

    def plugin_is_active(self, plugin_slug: str) -> bool:
        state, _ = self.get_plugin_activation_state(plugin_slug)
        return state is True

    def get_plugin_installation_state(self, plugin_slug: str) -> Tuple[Optional[bool], str]:
        """Return True/False for installed state, or None when WP-CLI failed."""
        return self._get_plugin_state(["plugin", "is-installed", plugin_slug])

    def get_plugin_activation_state(self, plugin_slug: str) -> Tuple[Optional[bool], str]:
        """Return True/False for active state, or None when WP-CLI failed."""
        return self._get_plugin_state(["plugin", "is-active", plugin_slug])

    def _get_plugin_state(self, args: List[str]) -> Tuple[Optional[bool], str]:
        success, stdout, stderr = self.run(args)
        if success:
            return True, ""
        detail = stderr or stdout
        if detail:
            return None, detail
        return False, ""

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
                parsed = self._extract_json(stdout)
                return (True, parsed) if isinstance(parsed, list) else (False, [])
            except json.JSONDecodeError:
                return False, []
        return False, []

    def run_plugin_check(self, plugin_path: str) -> Tuple[bool, Any, str]:
        plugin_path = str(normalize_path(plugin_path))
        logger.info("Running Plugin Check on: %s", plugin_path)

        success, stdout, stderr = self.run(
            [
                "plugin",
                "check",
                plugin_path,
                "--format=strict-json",
                "--fields=file,line,column,type,severity,code,message,docs",
            ],
        )

        if success:
            try:
                parsed = self._extract_json(stdout)
                if isinstance(parsed, (list, dict)):
                    return True, parsed, ""
            except json.JSONDecodeError:
                if "Checks complete. No errors found." in stdout:
                    return True, [], ""
                return False, {}, "Plugin Check returned output that was not valid strict JSON."

        return False, {}, stderr or stdout or "Plugin Check command failed without output."

    @staticmethod
    def _extract_json(output: str) -> Any:
        """Extract one JSON value from otherwise clean or warning-prefixed output."""
        decoder = json.JSONDecoder()
        positions = [pos for pos in (output.find("["), output.find("{")) if pos >= 0]
        if not positions:
            raise json.JSONDecodeError("No JSON value found", output, 0)
        value, _ = decoder.raw_decode(output[min(positions):])
        return value

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
