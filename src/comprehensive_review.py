"""
Comprehensive plugin review checklist aligned with AGENTS.md categories.
"""
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any
from pathlib import Path

from models import CheckStatus


@dataclass
class CheckItem:
    """Single check item result."""
    id: str
    name: str
    category: str
    status: CheckStatus
    message: str
    details: List[str] = field(default_factory=list)
    severity: str = "medium"
    issues: List[Any] = field(default_factory=list)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category,
            'status': self.status.value,
            'message': self.message,
            'details': self.details,
            'severity': self.severity,
            'issues': [i.to_dict() if hasattr(i, 'to_dict') else i for i in self.issues],
        }


@dataclass
class ReviewChecklist:
    """Comprehensive review checklist by AGENTS.md category."""
    plugin_name: str
    site_name: str
    timestamp: str

    plugin_check_results: List[CheckItem] = field(default_factory=list)
    wp_standards: List[CheckItem] = field(default_factory=list)
    wp_security: List[CheckItem] = field(default_factory=list)
    wp_defensive_coding: List[CheckItem] = field(default_factory=list)
    wp_settings_options: List[CheckItem] = field(default_factory=list)
    wp_ajax: List[CheckItem] = field(default_factory=list)
    wp_rest_api: List[CheckItem] = field(default_factory=list)
    wp_database: List[CheckItem] = field(default_factory=list)
    wp_filesystem: List[CheckItem] = field(default_factory=list)
    woo_compatibility: List[CheckItem] = field(default_factory=list)
    accessibility_i18n: List[CheckItem] = field(default_factory=list)
    release_readiness: List[CheckItem] = field(default_factory=list)
    wp_admin_notices: List[CheckItem] = field(default_factory=list)
    wp_emails: List[CheckItem] = field(default_factory=list)
    wp_privacy: List[CheckItem] = field(default_factory=list)
    wp_performance: List[CheckItem] = field(default_factory=list)
    wp_multisite: List[CheckItem] = field(default_factory=list)

    def get_all_items(self) -> List[CheckItem]:
        """Get all check items."""
        return (
            self.plugin_check_results +
            self.wp_standards +
            self.wp_security +
            self.wp_defensive_coding +
            self.wp_settings_options +
            self.wp_ajax +
            self.wp_rest_api +
            self.wp_database +
            self.wp_filesystem +
            self.woo_compatibility +
            self.accessibility_i18n +
            self.release_readiness +
            self.wp_admin_notices +
            self.wp_emails +
            self.wp_privacy +
            self.wp_performance +
            self.wp_multisite
        )

    def get_category_summary(self) -> Dict[str, Dict]:
        """Get summary by category."""
        categories = {
            'Plugin Check Results': self.plugin_check_results,
            'WP Standards': self.wp_standards,
            'WP Security': self.wp_security,
            'Defensive Coding': self.wp_defensive_coding,
            'Settings & Options': self.wp_settings_options,
            'AJAX': self.wp_ajax,
            'REST API': self.wp_rest_api,
            'Database': self.wp_database,
            'Filesystem': self.wp_filesystem,
            'WooCommerce': self.woo_compatibility,
            'Accessibility & i18n': self.accessibility_i18n,
            'Release Readiness': self.release_readiness,
            'WP Admin Notices': self.wp_admin_notices,
            'WP Emails': self.wp_emails,
            'WP Privacy': self.wp_privacy,
            'WP Performance': self.wp_performance,
            'WP Multisite': self.wp_multisite,
        }

        summary = {}
        for cat_name, items in categories.items():
            if items:
                passed = len([i for i in items if i.status == CheckStatus.PASSED])
                failed = len([i for i in items if i.status == CheckStatus.FAILED])
                warnings = len([i for i in items if i.status == CheckStatus.WARNING])
                summary[cat_name] = {
                    'total': len(items),
                    'passed': passed,
                    'failed': failed,
                    'warnings': warnings,
                    'items': [i.to_dict() for i in items],
                }

        return summary

    def to_dict(self):
        """Convert to dictionary."""
        return {
            'plugin': self.plugin_name,
            'site': self.site_name,
            'timestamp': self.timestamp,
            'summary': self.get_category_summary(),
        }


class ChecklistBuilder:
    """Build checklist items aligned with AGENTS.md categories."""

    @staticmethod
    def create_plugin_check_category() -> List[CheckItem]:
        """Create Plugin Check category items."""
        return [
            CheckItem(
                id='plugin_check_security',
                name='Security issues (from Plugin Check)',
                category='Plugin Check Results',
                status=CheckStatus.SKIPPED,
                message='Result from WordPress Plugin Check plugin',
            ),
            CheckItem(
                id='plugin_check_standards',
                name='WordPress standards (from Plugin Check)',
                category='Plugin Check Results',
                status=CheckStatus.SKIPPED,
                message='Result from WordPress Plugin Check plugin',
            ),
            CheckItem(
                id='plugin_check_performance',
                name='Performance checks (from Plugin Check)',
                category='Plugin Check Results',
                status=CheckStatus.SKIPPED,
                message='Result from WordPress Plugin Check plugin',
            ),
            CheckItem(
                id='plugin_check_other',
                name='Other checks (from Plugin Check)',
                category='Plugin Check Results',
                status=CheckStatus.SKIPPED,
                message='Result from WordPress Plugin Check plugin',
            ),
        ]

    @staticmethod
    def create_wp_standards_category() -> List[CheckItem]:
        """WP Plugin Standards from AGENTS.md."""
        return [
            CheckItem(
                id='wp_standards_header',
                name='Plugin Header correctness (Name, Version, Requirements)',
                category='WP Standards',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='wp_standards_prefixing',
                name='Strict prefixing/namespacing (functions, classes, hooks, CPTs)',
                category='WP Standards',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='wp_standards_hooks',
                name='Proper use of hooks, actions, filters, and shortcodes',
                category='WP Standards',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='wp_standards_activation',
                name='Activation/deactivation: lightweight, deferred work only',
                category='WP Standards',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='wp_standards_uninstall',
                name='Uninstall cleanup completeness (uninstall.php, WP_UNINSTALL_PLUGIN)',
                category='WP Standards',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='wp_standards_dependencies',
                name='Dependency loading order and safeguards',
                category='WP Standards',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='wp_standards_no_direct_core_load',
                name='No direct WordPress core loading (wp-load.php, wp-config.php)',
                category='WP Standards',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='wp_standards_no_inline_scripts',
                name='No inline script tags (<script>)',
                category='WP Standards',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='wp_standards_no_inline_styles',
                name='No inline style tags (<style>)',
                category='WP Standards',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='wp_standards_no_heredoc_nowdoc',
                name='No heredoc or nowdoc syntax usage (<<<)',
                category='WP Standards',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
        ]

    @staticmethod
    def create_wp_security_category() -> List[CheckItem]:
        """WP Security Rules from AGENTS.md."""
        return [
            CheckItem(
                id='wp_security_capabilities',
                name='Capability checks before privileged actions',
                category='WP Security',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='wp_security_nonces',
                name='Nonce verification for state-change requests',
                category='WP Security',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='wp_security_sanitization',
                name='Input sanitization and validation on boundaries',
                category='WP Security',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='wp_security_escaping',
                name='Output escaping (esc_html, esc_attr, etc.)',
                category='WP Security',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='wp_security_sql_prepared',
                name='SQL injection prevention using $wpdb->prepare()',
                category='WP Security',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='wp_security_rest_auth',
                name='REST endpoint permission_callback authentication',
                category='WP Security',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='wp_security_ajax_auth',
                name='AJAX security, nonce, and capability checks',
                category='WP Security',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='wp_security_path_traversal',
                name='Path traversal prevention and upload validation',
                category='WP Security',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='wp_security_secrets',
                name='No hardcoded secrets, keys, or logs',
                category='WP Security',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='wp_security_abspath',
                name='ABSPATH guards on PHP entry points',
                category='WP Security',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
        ]

    @staticmethod
    def create_defensive_coding_category() -> List[CheckItem]:
        """WP Defensive Coding from AGENTS.md."""
        return [
            CheckItem(
                id='defensive_null_checks',
                name='Null guards on common nullable APIs (get_post, get_option)',
                category='Defensive Coding',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='defensive_wp_error',
                name='is_wp_error() checks on WP API results',
                category='Defensive Coding',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='defensive_array_guards',
                name='Array operations guarded (isset, array_key_exists)',
                category='Defensive Coding',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='defensive_woo_objects',
                name='WooCommerce object validation before dereferencing',
                category='Defensive Coding',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='defensive_integration_checks',
                name='Integration safety checks (class_exists, function_exists)',
                category='Defensive Coding',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='defensive_remote_requests',
                name='Graceful error/timeout handling on remote requests',
                category='Defensive Coding',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='defensive_undefined_indexes',
                name='Prevention of undefined property/index notices',
                category='Defensive Coding',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='defensive_invalid_types',
                name='Foreach/count/array_merge guards on invalid variables',
                category='Defensive Coding',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
        ]

    @staticmethod
    def create_settings_options_category() -> List[CheckItem]:
        """WP Settings and Options from AGENTS.md."""
        return [
            CheckItem(
                id='settings_prefixing',
                name='Option/setting names prefixed to avoid conflicts',
                category='Settings & Options',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='settings_register',
                name='Settings registered with register_setting()',
                category='Settings & Options',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='settings_rest_api',
                name='REST settings schema, types, and authorization',
                category='Settings & Options',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
        ]

    @staticmethod
    def create_ajax_category() -> List[CheckItem]:
        """WP AJAX from AGENTS.md."""
        return [
            CheckItem(
                id='ajax_prefixing',
                name='AJAX actions prefixed correctly',
                category='AJAX',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='ajax_security',
                name='Nonce and capability checks in AJAX handlers',
                category='AJAX',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='ajax_localization',
                name='Localized script URL handles (no hardcoded AJAX URLs)',
                category='AJAX',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
        ]

    @staticmethod
    def create_rest_api_category() -> List[CheckItem]:
        """WP REST API from AGENTS.md."""
        return [
            CheckItem(
                id='rest_permission_callback',
                name='permission_callback on all register_rest_route() endpoints',
                category='REST API',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='rest_validation',
                name='REST argument sanitization and validation',
                category='REST API',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='rest_data_leak',
                name='No leakage of private data in REST responses',
                category='REST API',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
        ]

    @staticmethod
    def create_database_category() -> List[CheckItem]:
        """WP Database from AGENTS.md."""
        return [
            CheckItem(
                id='db_prepared_sql',
                name='Prepared statements for all dynamic queries ($wpdb->prepare)',
                category='Database',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='db_custom_tables',
                name='Custom tables using dbDelta & schema versioning',
                category='Database',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='db_unbounded_queries',
                name='Unbounded query checks (avoid posts_per_page = -1)',
                category='Database',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
        ]

    @staticmethod
    def create_filesystem_category() -> List[CheckItem]:
        """WP Filesystem from AGENTS.md."""
        return [
            CheckItem(
                id='fs_api_usage',
                name='WP Filesystem API used for writes',
                category='Filesystem',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='fs_upload_security',
                name='Upload validation (type, size, extension checks)',
                category='Filesystem',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='fs_path_traversal',
                name='Path traversal prevention (realpath, allowlists)',
                category='Filesystem',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='fs_temp_cleanup',
                name='Temporary files and imports cleanup',
                category='Filesystem',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
        ]

    @staticmethod
    def create_woo_category() -> List[CheckItem]:
        """WooCommerce Compatibility from AGENTS.md."""
        return [
            CheckItem(
                id='woo_crud_usage',
                name='WooCommerce CRUD usage (no direct wp_posts orders access)',
                category='WooCommerce',
                status=CheckStatus.NOT_APPLICABLE,
                message='Not applicable if WooCommerce is not used',
            ),
            CheckItem(
                id='woo_hpos_compatibility',
                name='HPOS compatibility declared/supported',
                category='WooCommerce',
                status=CheckStatus.NOT_APPLICABLE,
                message='Not applicable if WooCommerce is not used',
            ),
            CheckItem(
                id='woo_checkout_compatibility',
                name='Checkout block & classic checkout support',
                category='WooCommerce',
                status=CheckStatus.NOT_APPLICABLE,
                message='Not applicable if WooCommerce is not used',
            ),
            CheckItem(
                id='woo_object_safety',
                name='Safety checks on product/variation/order objects',
                category='WooCommerce',
                status=CheckStatus.NOT_APPLICABLE,
                message='Not applicable if WooCommerce is not used',
            ),
        ]

    @staticmethod
    def create_accessibility_i18n_category() -> List[CheckItem]:
        """Accessibility and i18n from AGENTS.md."""
        return [
            CheckItem(
                id='i18n_text_domain',
                name='Correct text domain declaration and consistency',
                category='Accessibility & i18n',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='i18n_literal_gettext',
                name='Literal gettext strings (no variables/constants)',
                category='Accessibility & i18n',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='i18n_escaped_output',
                name='Escaped translated outputs',
                category='Accessibility & i18n',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='a11y_keyboard',
                name='Keyboard navigation and interactive elements',
                category='Accessibility & i18n',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='a11y_structure',
                name='Semantic HTML, focus outlines, buttons vs links',
                category='Accessibility & i18n',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
        ]

    @staticmethod
    def create_release_readiness_category() -> List[CheckItem]:
        """Release Readiness from AGENTS.md."""
        return [
            CheckItem(
                id='release_no_cdn',
                name='No external/CDN asset references',
                category='Release Readiness',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='release_no_bundled_core',
                name='No bundled WP core libraries',
                category='Release Readiness',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='release_no_eval_settings',
                name='No arbitrary code execution from settings',
                category='Release Readiness',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='release_no_dev_artifacts',
                name='No backup, debug, or dev files in package',
                category='Release Readiness',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='release_zip_structure',
                name='Valid ZIP root directory and format',
                category='Release Readiness',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='release_gpl_compatible',
                name='GPL-compatible libraries and assets',
                category='Release Readiness',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='release_readme_version',
                name='Readme.txt stable tag matching plugin header version',
                category='Release Readiness',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
        ]

    @staticmethod
    def create_wp_admin_notices_category() -> List[CheckItem]:
        """WP Admin Notices category."""
        return [
            CheckItem(
                id='admin_notices_caps',
                name='Capability checks before showing notices',
                category='WP Admin Notices',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='admin_notices_dismissal',
                name='Notice dismissals stored in user settings (meta/options)',
                category='WP Admin Notices',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='admin_notices_nags',
                name='No marketing nags, review requests, or promotional links',
                category='WP Admin Notices',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='admin_notices_global',
                name='Avoid global notices; limit notices to plugin-specific screens',
                category='WP Admin Notices',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
        ]

    @staticmethod
    def create_wp_emails_category() -> List[CheckItem]:
        """WP Email Rules category."""
        return [
            CheckItem(
                id='emails_api',
                name='Use WP mail APIs (wp_mail / Woo mail) instead of PHP mail()',
                category='WP Emails',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='emails_secrets',
                name='No passwords, secrets, credentials, or logs inside emails',
                category='WP Emails',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='emails_duplicates',
                name='Email duplicate prevention and idempotency locks',
                category='WP Emails',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
        ]

    @staticmethod
    def create_wp_privacy_category() -> List[CheckItem]:
        """WP Privacy And Data Rules category."""
        return [
            CheckItem(
                id='privacy_policy',
                name='Privacy policy text declaration (wp_add_privacy_policy_content)',
                category='WP Privacy',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='privacy_exporter_eraser',
                name='Personal data exporter and eraser callbacks registered',
                category='WP Privacy',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='privacy_logging',
                name='No logging of personal data, user parameters, or secrets',
                category='WP Privacy',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
        ]

    @staticmethod
    def create_wp_performance_category() -> List[CheckItem]:
        """WP Performance And Large-Store Rules category."""
        return [
            CheckItem(
                id='perf_queries_in_loops',
                name='No repeated meta, option, or database queries in loops',
                category='WP Performance',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='perf_transient_caching',
                name='Cache expensive queries, API requests, or computations',
                category='WP Performance',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='perf_enqueue_screens',
                name='Limit frontend/admin asset enqueuing to specific screens only',
                category='WP Performance',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='perf_autoload',
                name='Avoid autoloading large options or caches',
                category='WP Performance',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
        ]

    @staticmethod
    def create_wp_multisite_category() -> List[CheckItem]:
        """WP Multisite Rules category."""
        return [
            CheckItem(
                id='multisite_guards',
                name='Check for Multisite support (is_multisite) and network guards',
                category='WP Multisite',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='multisite_options',
                name='Separate site options from network-wide options',
                category='WP Multisite',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
            CheckItem(
                id='multisite_loop_sites',
                name='Do not loop all sites on normal page loads or requests',
                category='WP Multisite',
                status=CheckStatus.SKIPPED,
                message='Pending static analysis',
            ),
        ]

    @staticmethod
    def build_complete_checklist(plugin_name: str, site_name: str) -> ReviewChecklist:
        """Build complete checklist with all categories."""
        checklist = ReviewChecklist(
            plugin_name=plugin_name,
            site_name=site_name,
            timestamp=datetime.now().isoformat(),
        )

        checklist.plugin_check_results = ChecklistBuilder.create_plugin_check_category()
        checklist.wp_standards = ChecklistBuilder.create_wp_standards_category()
        checklist.wp_security = ChecklistBuilder.create_wp_security_category()
        checklist.wp_defensive_coding = ChecklistBuilder.create_defensive_coding_category()
        checklist.wp_settings_options = ChecklistBuilder.create_settings_options_category()
        checklist.wp_ajax = ChecklistBuilder.create_ajax_category()
        checklist.wp_rest_api = ChecklistBuilder.create_rest_api_category()
        checklist.wp_database = ChecklistBuilder.create_database_category()
        checklist.wp_filesystem = ChecklistBuilder.create_filesystem_category()
        checklist.woo_compatibility = ChecklistBuilder.create_woo_category()
        checklist.accessibility_i18n = ChecklistBuilder.create_accessibility_i18n_category()
        checklist.release_readiness = ChecklistBuilder.create_release_readiness_category()
        checklist.wp_admin_notices = ChecklistBuilder.create_wp_admin_notices_category()
        checklist.wp_emails = ChecklistBuilder.create_wp_emails_category()
        checklist.wp_privacy = ChecklistBuilder.create_wp_privacy_category()
        checklist.wp_performance = ChecklistBuilder.create_wp_performance_category()
        checklist.wp_multisite = ChecklistBuilder.create_wp_multisite_category()

        return checklist
