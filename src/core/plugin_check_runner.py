"""WordPress Plugin Check integration."""
import logging
from typing import Tuple, Any, Dict, List, Optional

from models import PluginCheckResult, ReviewIssue, IssueSeverity, IssueCategory
from core.wp_cli_runner import WPCLIRunner


logger = logging.getLogger(__name__)


class PluginCheckRunner:
    """Run WordPress Plugin Check on a plugin."""

    def __init__(self, wp_cli_runner: WPCLIRunner):
        self.cli = wp_cli_runner

    def ensure_installed(self) -> Tuple[bool, str]:
        """Ensure Plugin Check plugin is installed and activated."""
        logger.info("Ensuring Plugin Check is installed and activated...")
        actions = []

        installed, detail = self.cli.get_plugin_installation_state("plugin-check")
        if installed is None:
            return False, f"Could not determine whether Plugin Check is installed: {detail}"

        if not installed:
            success, msg = self.cli.install_plugin("plugin-check")
            if not success:
                return False, f"Failed to install Plugin Check: {msg}"
            actions.append("installed and activated")

            installed, detail = self.cli.get_plugin_installation_state("plugin-check")
            if installed is not True:
                return False, f"Plugin Check installation could not be verified: {detail}"

        active, detail = self.cli.get_plugin_activation_state("plugin-check")
        if active is None:
            return False, f"Could not determine whether Plugin Check is active: {detail}"

        if not active:
            success, msg = self.cli.activate_plugin("plugin-check")
            if not success:
                return False, f"Failed to activate Plugin Check: {msg}"
            actions.append("activated")

            active, detail = self.cli.get_plugin_activation_state("plugin-check")
            if active is not True:
                return False, f"Plugin Check activation could not be verified: {detail}"

        if actions:
            return True, f"Plugin Check was {' and '.join(actions)} and verified"
        return True, "Plugin Check is installed, active, and verified"

    def run(self, plugin_path: str, ensure_ready: bool = True) -> Tuple[bool, PluginCheckResult]:
        logger.info("Running Plugin Check on %s", plugin_path)

        if ensure_ready:
            success, msg = self.ensure_installed()
            if not success:
                return False, PluginCheckResult(success=False, raw_output=msg)

        success, result, error = self.cli.run_plugin_check(plugin_path)
        if not success:
            return False, PluginCheckResult(success=False, raw_output=error)

        check_result = self._parse_results(result)
        logger.info(
            "Plugin Check complete: %d errors, %d warnings",
            len(check_result.errors),
            len(check_result.warnings),
        )
        return True, check_result

    def _parse_results(self, result: Any) -> PluginCheckResult:
        check_result = PluginCheckResult(success=True)

        if isinstance(result, list):
            for item in result:
                self._add_parsed_item(check_result, item)
            return check_result

        if not isinstance(result, dict):
            return check_result

        for key, severity in [
            ("errors", IssueSeverity.CRITICAL),
            ("warnings", IssueSeverity.HIGH),
            ("info", IssueSeverity.INFO),
        ]:
            for item in result.get(key, []):
                issue = self._parse_issue(item, severity)
                if issue:
                    if severity == IssueSeverity.CRITICAL:
                        check_result.errors.append(issue)
                    elif severity == IssueSeverity.HIGH:
                        check_result.warnings.append(issue)
                    else:
                        check_result.info.append(issue)

        # Plugin Check JSON may use 'files' or 'results' structure
        for item in result.get("files", []) + result.get("results", []):
            self._add_parsed_item(check_result, item)

        return check_result

    def _add_parsed_item(self, check_result: PluginCheckResult, item: Any):
        if isinstance(item, dict):
            type_name = str(item.get("type", "")).lower()
            severity = self._map_severity(item.get("severity"), type_name)
            if "error" in type_name or "fail" in type_name:
                target = check_result.errors
            elif "warn" in type_name:
                target = check_result.warnings
            else:
                target = check_result.info

            issue = self._parse_issue(item, severity)
            if issue:
                target.append(issue)

    def _map_severity(self, numeric_severity: Any, type_name: str) -> IssueSeverity:
        """Map Plugin Check's 1-10 severity scale without conflating type and severity."""
        try:
            value = int(numeric_severity)
        except (TypeError, ValueError):
            if "error" in type_name or "fail" in type_name:
                return IssueSeverity.HIGH
            if "warn" in type_name:
                return IssueSeverity.MEDIUM
            return IssueSeverity.INFO

        if value >= 9:
            return IssueSeverity.CRITICAL
        if value >= 7:
            return IssueSeverity.HIGH
        if value >= 4:
            return IssueSeverity.MEDIUM
        if value >= 1:
            return IssueSeverity.LOW
        return IssueSeverity.INFO

    def _parse_issue(self, issue_data: Dict, severity: IssueSeverity) -> ReviewIssue:
        title = (
            issue_data.get("title")
            or issue_data.get("code")
            or issue_data.get("check")
            or issue_data.get("message")
            or "Plugin Check finding"
        )
        description = issue_data.get("message") or issue_data.get("description") or str(title)
        file_path = issue_data.get("file") or issue_data.get("path")
        line_number = issue_data.get("line") or issue_data.get("line_number")

        if isinstance(line_number, str) and line_number.isdigit():
            line_number = int(line_number)

        title_str = str(title)
        desc_str = str(description)

        category = self._determine_category(title_str, desc_str)
        check_id = self._determine_check_id(title_str, desc_str, category)

        return ReviewIssue(
            severity=severity,
            category=category,
            title=title_str,
            description=desc_str,
            file_path=file_path,
            line_number=line_number,
            code_snippet=issue_data.get("snippet"),
            suggestion=issue_data.get("docs"),
            check_id=check_id,
        )

    def _determine_category(self, title: str, description: str) -> IssueCategory:
        title_lower = title.lower()
        text_lower = f"{title} {description}".lower()

        if any(w in text_lower for w in ["textdomain", "text domain", "gettext", "i18n", "translation"]):
            return IssueCategory.ACCESSIBILITY_I18N
        if any(w in text_lower for w in ["security", "nonce", "sanitize", "escape", "sql", "capability", "permission"]):
            return IssueCategory.WP_SECURITY
        if any(w in title_lower for w in ["ajax", "admin-ajax", "wp_ajax"]):
            return IssueCategory.WP_AJAX
        if any(w in title_lower for w in ["rest", "permission_callback"]):
            return IssueCategory.WP_REST_API
        if any(w in text_lower for w in ["woocommerce", "hpos", "cart", "checkout", "wc_order", "wc_product"]):
            return IssueCategory.WOO_COMPATIBILITY
        if any(w in text_lower for w in ["performance", "query", "autoload", "unbounded"]):
            return IssueCategory.WP_DATABASE
        if any(w in text_lower for w in ["accessibility", "a11y", "aria", "keyboard"]):
            return IssueCategory.ACCESSIBILITY_I18N
        if any(w in text_lower for w in ["readme", "release", "version", "zip", "cdn", "stable tag"]):
            return IssueCategory.RELEASE_READINESS
        if any(w in text_lower for w in ["upload", "filesystem", "traversal"]):
            return IssueCategory.WP_FILESYSTEM
        if any(w in text_lower for w in ["option", "setting", "register_setting"]):
            return IssueCategory.WP_SETTINGS
        if any(w in text_lower for w in ["wpdb", "database", "dbdelta", "prepare"]):
            return IssueCategory.WP_DATABASE
        if any(w in text_lower for w in ["null", "wp_error", "guard", "is_wp_error"]):
            return IssueCategory.DEFENSIVE_CODING

        return IssueCategory.PLUGIN_CHECK

    def _determine_check_id(self, title: str, desc: str, category: IssueCategory) -> Optional[str]:
        title_lower = title.lower()
        text_lower = (title + " " + desc).lower()

        # Direct checks mapping
        if "abspath" in text_lower:
            return "wp_security_abspath"
        if "nonce" in text_lower or "verify_nonce" in text_lower:
            return "wp_security_nonces"
        if "capability" in text_lower or "current_user_can" in text_lower:
            return "wp_security_capabilities"
        if "sanitize" in text_lower or "sanitization" in text_lower:
            return "wp_security_sanitization"
        if "escape" in text_lower or "escaping" in text_lower:
            return "wp_security_escaping"
        if "prepare" in text_lower or "wpdb->prepare" in text_lower or "sql injection" in text_lower:
            return "wp_security_sql_prepared"
        if "permission_callback" in text_lower:
            return "rest_permission_callback"
        if "textdomain" in text_lower or "text domain" in text_lower or "gettext" in text_lower:
            return "i18n_text_domain"
        if "ajax" in title_lower or "wp_ajax" in title_lower or "admin-ajax" in title_lower:
            return "ajax_security"
        if "traversal" in text_lower or "path traversal" in text_lower:
            return "fs_path_traversal"
        if "upload" in text_lower:
            return "fs_upload_security"
        if "secret" in text_lower or "password" in text_lower:
            return "wp_security_secrets"
        if "prefix" in text_lower or "naming" in text_lower:
            return "wp_standards_prefixing"
        if "readme" in text_lower or "stable tag" in text_lower:
            return "release_readme_version"
        if "cdn" in text_lower or "external" in text_lower or "google-fonts" in text_lower:
            return "release_no_cdn"
        if "hpos" in text_lower or "custom_order_tables" in text_lower:
            return "woo_hpos_compatibility"
        if "woocommerce" in text_lower or "woo_" in text_lower:
            return "woo_crud_usage"
        if "performance" in text_lower or "unbounded" in text_lower:
            return "db_unbounded_queries"
        if "eval" in text_lower:
            return "release_no_eval_settings"
        if "uninstall" in text_lower or "uninstall.php" in text_lower:
            return "wp_standards_uninstall"
        if "header" in text_lower or "plugin name" in text_lower:
            return "wp_standards_header"
        if "is_wp_error" in text_lower or "wp_error" in text_lower:
            return "defensive_wp_error"
        if "dbdelta" in text_lower or "create table" in text_lower:
            return "db_custom_tables"
        if "keyboard" in text_lower or "accessibility" in text_lower or "a11y" in text_lower:
            return "a11y_keyboard"

        # Fallback based on category
        if category == IssueCategory.WP_SECURITY:
            return "plugin_check_security"
        if category == IssueCategory.WP_STANDARDS:
            return "plugin_check_standards"
        if category == IssueCategory.WP_DATABASE:
            return "plugin_check_performance"

        return "plugin_check_other"
