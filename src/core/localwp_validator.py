"""LocalWP site detection and validation."""
import logging
import re
from pathlib import Path
from typing import Optional, Tuple

from models import LocalWPSite
from utils import normalize_path, is_valid_wordpress_root, find_localwp_sites
from core.wp_cli_runner import WPCLIRunner


logger = logging.getLogger(__name__)


class LocalWPValidator:
    """Detect and validate LocalWP WordPress sites."""

    def __init__(self):
        self.sites: list = []
        self.refresh_sites()

    def refresh_sites(self):
        self.sites = find_localwp_sites()
        logger.info("Found %d LocalWP sites", len(self.sites))

    def get_available_sites(self) -> list:
        return self.sites

    def validate_path(self, path: str) -> Tuple[bool, Optional[LocalWPSite], str]:
        try:
            wp_root = normalize_path(path)
            is_valid, msg = is_valid_wordpress_root(wp_root)
            if not is_valid:
                return False, None, msg

            site_name = self._detect_site_name(wp_root)
            site = LocalWPSite(name=site_name, path=str(wp_root), wp_url="", is_valid=False)
            return True, site, "Valid WordPress root"
        except Exception as exc:
            logger.error("Error validating path: %s", exc)
            return False, None, str(exc)

    def _detect_site_name(self, wp_root: Path) -> str:
        parts = wp_root.parts
        if "Local Sites" in parts:
            idx = parts.index("Local Sites")
            if idx + 1 < len(parts):
                return parts[idx + 1]
        return wp_root.parent.name if wp_root.name == "public" else wp_root.name

    def get_site_url(self, wp_root: Path) -> Optional[str]:
        try:
            wp_config = wp_root / "wp-config.php"
            if wp_config.exists():
                with open(wp_config, "r", encoding="utf-8", errors="ignore") as handle:
                    content = handle.read()
                for pattern in [
                    r"define\(\s*['\"]WP_HOME['\"]\s*,\s*['\"](.+?)['\"]",
                    r"define\(\s*['\"]WP_SITEURL['\"]\s*,\s*['\"](.+?)['\"]",
                ]:
                    match = re.search(pattern, content)
                    if match:
                        return match.group(1)
        except Exception as exc:
            logger.debug("Could not read wp-config URL: %s", exc)
        return None

    def validate_site(self, site: LocalWPSite, use_wp_cli: bool = True) -> Tuple[bool, str]:
        try:
            site.is_valid = False
            wp_root = Path(site.path)
            is_valid, msg = is_valid_wordpress_root(wp_root)
            if not is_valid:
                return False, msg

            site_url = self.get_site_url(wp_root)
            if site_url:
                site.wp_url = site_url
            elif site.name and site.name != "WordPress":
                site.wp_url = f"http://{site.name}.local"

            if use_wp_cli:
                try:
                    cli = WPCLIRunner(str(wp_root))
                    wp_ok, wp_message = cli.verify_wp_cli()
                    if not wp_ok:
                        return False, wp_message
                    site_ok, live_url = cli.verify_wordpress_site()
                    if not site_ok:
                        return False, f"WP-CLI cannot load this WordPress site: {live_url}"
                    site.wp_url = live_url
                    site.wordpress_version = cli.get_wp_version() or ""
                    site.php_version = cli.get_php_version() or ""
                except Exception as exc:
                    return False, f"WP-CLI validation failed: {exc}"

            site.is_valid = True
            return True, "Site is valid"
        except Exception as exc:
            logger.error("Error validating site: %s", exc)
            return False, str(exc)

    def select_site_by_name(self, name: str) -> Optional[LocalWPSite]:
        for site_info in self.sites:
            if site_info["name"] == name:
                site = LocalWPSite(
                    name=site_info["name"],
                    path=site_info["path"],
                    wp_url="",
                )
                self.validate_site(site, use_wp_cli=False)
                return site
        return None

    def select_site_by_path(self, path: str) -> Optional[LocalWPSite]:
        is_valid, site, _ = self.validate_path(path)
        if is_valid and site:
            self.validate_site(site, use_wp_cli=False)
            return site
        return None

    def find_site_for_plugin(self, plugin_path: str) -> Optional[LocalWPSite]:
        """Auto-detect LocalWP site when plugin lives under wp-content/plugins."""
        plugin_path = normalize_path(plugin_path)
        plugins_marker = Path("wp-content") / "plugins"

        for site_info in self.sites:
            site_root = normalize_path(site_info["path"])
            try:
                if plugin_path.is_relative_to(site_root):
                    return self.select_site_by_path(str(site_root))
            except ValueError:
                if str(plugin_path).startswith(str(site_root)):
                    return self.select_site_by_path(str(site_root))

            plugins_dir = site_root / plugins_marker
            try:
                if plugin_path.is_relative_to(plugins_dir):
                    return self.select_site_by_path(str(site_root))
            except ValueError:
                if str(plugin_path).startswith(str(plugins_dir)):
                    return self.select_site_by_path(str(site_root))

        return None
