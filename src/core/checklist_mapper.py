"""Map review findings to AGENTS.md category checklist."""
import logging
from datetime import datetime
from typing import Dict, List, Optional

from models import (
    CategoryCheck,
    CategoryResult,
    CategoryReviewResult,
    CheckStatus,
    IssueCategory,
    PluginCheckResult,
    PluginMetadata,
    LocalWPSite,
    ReviewIssue,
    StaticAnalysisResult,
    IssueSeverity,
)
from comprehensive_review import ChecklistBuilder, CheckItem


logger = logging.getLogger(__name__)

CATEGORY_MAP = {
    "Plugin Check Results": IssueCategory.PLUGIN_CHECK,
    "WP Standards": IssueCategory.WP_STANDARDS,
    "WP Security": IssueCategory.WP_SECURITY,
    "Defensive Coding": IssueCategory.DEFENSIVE_CODING,
    "Settings & Options": IssueCategory.WP_SETTINGS,
    "AJAX": IssueCategory.WP_AJAX,
    "REST API": IssueCategory.WP_REST_API,
    "Database": IssueCategory.WP_DATABASE,
    "Filesystem": IssueCategory.WP_FILESYSTEM,
    "WooCommerce": IssueCategory.WOO_COMPATIBILITY,
    "Accessibility & i18n": IssueCategory.ACCESSIBILITY_I18N,
    "Release Readiness": IssueCategory.RELEASE_READINESS,
    "WP Admin Notices": IssueCategory.WP_ADMIN_NOTICES,
    "WP Emails": IssueCategory.WP_EMAILS,
    "WP Privacy": IssueCategory.WP_PRIVACY,
    "WP Performance": IssueCategory.WP_PERFORMANCE,
    "WP Multisite": IssueCategory.WP_MULTISITE,
}



class ChecklistMapper:
    """Build category-wise checklist from review results."""

    def build(
        self,
        plugin: PluginMetadata,
        site: LocalWPSite,
        plugin_check: PluginCheckResult,
        static_analysis: StaticAnalysisResult,
    ) -> CategoryReviewResult:
        checklist = ChecklistBuilder.build_complete_checklist(plugin.name, site.name)
        all_issues = (
            plugin_check.errors + plugin_check.warnings + plugin_check.info + static_analysis.issues
        )

        # 1. Clean up WooCommerce compatibility checks if WooCommerce is not used
        if not plugin.woo_compatible:
            for item in checklist.woo_compatibility:
                item.status = CheckStatus.NOT_APPLICABLE
                item.message = "Plugin does not declare WooCommerce compatibility/usage"
                item.issues = []

        # 2. Map issues to checklist items
        for issue in all_issues:
            check_item = self._find_check_by_id(checklist, issue.check_id)
            if not check_item:
                # Fallback to category-based matching
                check_item = self._fallback_find_check(checklist, issue)

            if check_item and check_item.status != CheckStatus.NOT_APPLICABLE:
                check_item.issues.append(issue)

        # 3. Resolve status for each check item
        all_categories_list = self._iter_categories(checklist)
        for cat_name, items in all_categories_list:
            for item in items:
                if item.status == CheckStatus.NOT_APPLICABLE:
                    continue

                if item.issues:
                    # Determine status based on highest severity issue
                    severities = [i.severity for i in item.issues]
                    if IssueSeverity.CRITICAL in severities or IssueSeverity.HIGH in severities:
                        item.status = CheckStatus.FAILED
                    else:
                        item.status = CheckStatus.WARNING

                    # Populate message and details
                    item.message = f"{len(item.issues)} issue(s) detected"
                    item.details = [
                        f"[{i.severity.value.upper()}] {i.title} in {i.file_path or 'unknown'}"
                        f"{f':{i.line_number}' if i.line_number else ''}"
                        for i in item.issues
                    ]
                else:
                    # No issues mapped
                    if item.id in ["a11y_keyboard", "a11y_structure"]:
                        item.status = CheckStatus.SKIPPED
                        item.message = "Requires manual code/UI verification"
                    else:
                        item.status = CheckStatus.PASSED
                        item.message = "No issues detected"

        # 4. Construct final result structure
        result = CategoryReviewResult(plugin=plugin, site=site, timestamp=datetime.now())
        for cat_name, items in all_categories_list:
            enum_cat = CATEGORY_MAP.get(cat_name)
            if not enum_cat:
                continue

            category_result = CategoryResult(
                category=enum_cat,
                category_name=cat_name,
                checks=[self._to_category_check(item) for item in items],
            )
            result.add_category(category_result)

        return result

    def _find_check_by_id(self, checklist, check_id: Optional[str]) -> Optional[CheckItem]:
        if not check_id:
            return None
        for _, items in self._iter_categories(checklist):
            for item in items:
                if item.id == check_id:
                    return item
        return None

    def _fallback_find_check(self, checklist, issue: ReviewIssue) -> Optional[CheckItem]:
        """Find a fallback check item based on category if check_id is missing or unmatched."""
        cat = issue.category
        category_items = {
            IssueCategory.WP_STANDARDS: checklist.wp_standards,
            IssueCategory.WP_SECURITY: checklist.wp_security,
            IssueCategory.DEFENSIVE_CODING: checklist.wp_defensive_coding,
            IssueCategory.WP_SETTINGS: checklist.wp_settings_options,
            IssueCategory.WP_AJAX: checklist.wp_ajax,
            IssueCategory.WP_REST_API: checklist.wp_rest_api,
            IssueCategory.WP_DATABASE: checklist.wp_database,
            IssueCategory.WP_FILESYSTEM: checklist.wp_filesystem,
            IssueCategory.WOO_COMPATIBILITY: checklist.woo_compatibility,
            IssueCategory.ACCESSIBILITY_I18N: checklist.accessibility_i18n,
            IssueCategory.RELEASE_READINESS: checklist.release_readiness,
            IssueCategory.WP_ADMIN_NOTICES: checklist.wp_admin_notices,
            IssueCategory.WP_EMAILS: checklist.wp_emails,
            IssueCategory.WP_PRIVACY: checklist.wp_privacy,
            IssueCategory.WP_PERFORMANCE: checklist.wp_performance,
            IssueCategory.WP_MULTISITE: checklist.wp_multisite,
        }

        items = category_items.get(cat)
        if items:
            # Fallback to the first item of the category
            return items[0]

        # Or put under Plugin Check fallback items
        for item in checklist.plugin_check_results:
            if cat == IssueCategory.WP_SECURITY and item.id == "plugin_check_security":
                return item
            if cat == IssueCategory.WP_STANDARDS and item.id == "plugin_check_standards":
                return item
            if cat == IssueCategory.WP_DATABASE and item.id == "plugin_check_performance":
                return item

        # Ultimate fallback
        if checklist.plugin_check_results:
            return checklist.plugin_check_results[-1]

        return None

    def _iter_categories(self, checklist):
        return [
            ("Plugin Check Results", checklist.plugin_check_results),
            ("WP Standards", checklist.wp_standards),
            ("WP Security", checklist.wp_security),
            ("Defensive Coding", checklist.wp_defensive_coding),
            ("Settings & Options", checklist.wp_settings_options),
            ("AJAX", checklist.wp_ajax),
            ("REST API", checklist.wp_rest_api),
            ("Database", checklist.wp_database),
            ("Filesystem", checklist.wp_filesystem),
            ("WooCommerce", checklist.woo_compatibility),
            ("Accessibility & i18n", checklist.accessibility_i18n),
            ("Release Readiness", checklist.release_readiness),
            ("WP Admin Notices", checklist.wp_admin_notices),
            ("WP Emails", checklist.wp_emails),
            ("WP Privacy", checklist.wp_privacy),
            ("WP Performance", checklist.wp_performance),
            ("WP Multisite", checklist.wp_multisite),
        ]

    def _to_category_check(self, item: CheckItem) -> CategoryCheck:
        # Wrap ReviewIssue instances into models.ReviewIssue for compatibility
        return CategoryCheck(
            id=item.id,
            name=item.name,
            status=item.status,
            message=item.message,
            details=item.details,
            severity=item.severity,
            issues=item.issues,
        )
