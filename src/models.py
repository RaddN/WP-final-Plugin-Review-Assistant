"""Data models for WP Plugin Review Assistant."""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime


class IssueSeverity(Enum):
    """Issue severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class CheckStatus(Enum):
    """Check result status - aligned with comprehensive_review.py."""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"
    NOT_APPLICABLE = "n/a"


class IssueCategory(Enum):
    """Issue categories aligned with WordPress review standards."""
    PLUGIN_CHECK = "plugin_check_results"
    WP_STANDARDS = "wp_standards"
    WP_SECURITY = "wp_security"
    DEFENSIVE_CODING = "defensive_coding"
    WP_SETTINGS = "wp_settings_options"
    WP_AJAX = "wp_ajax"
    WP_REST_API = "wp_rest_api"
    WP_DATABASE = "wp_database"
    WP_FILESYSTEM = "wp_filesystem"
    WOO_COMPATIBILITY = "woo_compatibility"
    ACCESSIBILITY_I18N = "accessibility_i18n"
    RELEASE_READINESS = "release_readiness"
    WP_ADMIN_NOTICES = "wp_admin_notices"
    WP_EMAILS = "wp_emails"
    WP_PRIVACY = "wp_privacy"
    WP_PERFORMANCE = "wp_performance"
    WP_MULTISITE = "wp_multisite"



@dataclass
class CategoryCheck:
    """Single check item within a category."""
    id: str
    name: str
    status: CheckStatus
    message: str
    details: List[str] = field(default_factory=list)
    severity: str = "medium"
    issues: List["ReviewIssue"] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'status': self.status.value,
            'message': self.message,
            'details': self.details,
            'severity': self.severity,
            'issues': [i.to_dict() for i in self.issues],
        }


@dataclass
class CategoryResult:
    """Results for a single category."""
    category: IssueCategory
    category_name: str
    checks: List[CategoryCheck] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.checks)

    @property
    def passed(self) -> int:
        return len([c for c in self.checks if c.status == CheckStatus.PASSED])

    @property
    def failed(self) -> int:
        return len([c for c in self.checks if c.status == CheckStatus.FAILED])

    @property
    def warnings(self) -> int:
        return len([c for c in self.checks if c.status == CheckStatus.WARNING])

    @property
    def skipped(self) -> int:
        return len([c for c in self.checks if c.status == CheckStatus.SKIPPED])

    @property
    def not_applicable(self) -> int:
        return len([c for c in self.checks if c.status == CheckStatus.NOT_APPLICABLE])

    def to_dict(self) -> Dict[str, Any]:
        return {
            'category': self.category.value,
            'category_name': self.category_name,
            'total': self.total,
            'passed': self.passed,
            'failed': self.failed,
            'warnings': self.warnings,
            'skipped': self.skipped,
            'not_applicable': self.not_applicable,
            'checks': [c.to_dict() for c in self.checks],
        }



@dataclass
class ReviewIssue:
    """Represents a single review issue."""
    severity: IssueSeverity
    category: IssueCategory
    title: str
    description: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    code_snippet: Optional[str] = None
    suggestion: Optional[str] = None
    check_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'severity': self.severity.value,
            'category': self.category.value,
            'title': self.title,
            'description': self.description,
            'file': self.file_path,
            'line': self.line_number,
            'code': self.code_snippet,
            'suggestion': self.suggestion,
            'check_id': self.check_id,
        }


@dataclass
class PluginMetadata:
    """WordPress plugin metadata."""
    name: str
    version: str
    text_domain: str
    requires_php: str
    requires_wp: str
    stable_tag: str = ""
    requires_plugins: List[str] = field(default_factory=list)
    woo_compatible: bool = False
    description: str = ""
    author: str = ""
    author_uri: str = ""
    plugin_uri: str = ""
    license: str = ""
    main_file: str = ""
    root_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'version': self.version,
            'stable_tag': self.stable_tag,
            'text_domain': self.text_domain,
            'requires_php': self.requires_php,
            'requires_wp': self.requires_wp,
            'requires_plugins': self.requires_plugins,
            'woo_compatible': self.woo_compatible,
            'main_file': self.main_file,
            'root_path': self.root_path,
        }


@dataclass
class LocalWPSite:
    """LocalWP WordPress site."""
    name: str
    path: str
    wp_url: str
    php_version: str = ""
    mysql_version: str = ""
    wordpress_version: str = ""
    is_valid: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'path': self.path,
            'url': self.wp_url,
            'php': self.php_version,
            'mysql': self.mysql_version,
            'wordpress': self.wordpress_version,
        }


@dataclass
class PluginCheckResult:
    """Result from WordPress Plugin Check."""
    success: bool
    errors: List[ReviewIssue] = field(default_factory=list)
    warnings: List[ReviewIssue] = field(default_factory=list)
    info: List[ReviewIssue] = field(default_factory=list)
    raw_output: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "info": len(self.info),
        }


@dataclass
class StaticAnalysisResult:
    """Result from static code analysis."""
    issues: List[ReviewIssue] = field(default_factory=list)
    files_scanned: int = 0
    analysis_time: float = 0.0
    automated_checks: List[str] = field(default_factory=list)
    applicable_checks: List[str] = field(default_factory=list)
    not_applicable_checks: List[str] = field(default_factory=list)


@dataclass
class ReviewResult:
    """Complete review result."""
    plugin: PluginMetadata
    site: LocalWPSite
    plugin_check: PluginCheckResult
    static_analysis: StaticAnalysisResult
    analysis_summary: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def all_issues(self) -> List[ReviewIssue]:
        """Combine all issues from all sources."""
        all_issues = (
            self.plugin_check.errors +
            self.plugin_check.warnings +
            self.plugin_check.info +
            self.static_analysis.issues
        )
        severity_order = {
            IssueSeverity.CRITICAL: 0,
            IssueSeverity.HIGH: 1,
            IssueSeverity.MEDIUM: 2,
            IssueSeverity.LOW: 3,
            IssueSeverity.INFO: 4,
        }
        return sorted(all_issues, key=lambda x: (severity_order[x.severity], x.category.value))

    @property
    def issue_count_by_severity(self) -> Dict[str, int]:
        """Count issues by severity."""
        counts = {s.value: 0 for s in IssueSeverity}
        for issue in self.all_issues:
            counts[issue.severity.value] += 1
        return counts

    def to_dict(self) -> Dict[str, Any]:
        return {
            'plugin': self.plugin.to_dict(),
            'site': self.site.to_dict(),
            'plugin_check': self.plugin_check.to_dict(),
            'static_analysis': {
                'files_scanned': self.static_analysis.files_scanned,
                'issues': len(self.static_analysis.issues),
                'automated_checks': sorted(self.static_analysis.automated_checks),
                'applicable_checks': sorted(self.static_analysis.applicable_checks),
                'not_applicable_checks': sorted(self.static_analysis.not_applicable_checks),
            },
            'issues': [i.to_dict() for i in self.all_issues],
            'summary': self.issue_count_by_severity,
            'analysis_summary': self.analysis_summary,
            'timestamp': self.timestamp.isoformat(),
        }


@dataclass
class CategoryReviewResult:
    """Professional category-wise review results."""
    plugin: PluginMetadata
    site: LocalWPSite
    timestamp: datetime = field(default_factory=datetime.now)
    categories: Dict[IssueCategory, CategoryResult] = field(default_factory=dict)

    def add_category(self, category_result: CategoryResult):
        """Add a category result."""
        self.categories[category_result.category] = category_result

    @property
    def all_category_results(self) -> List[CategoryResult]:
        """Get all category results in order."""
        order = [
            IssueCategory.PLUGIN_CHECK,
            IssueCategory.WP_STANDARDS,
            IssueCategory.WP_SECURITY,
            IssueCategory.DEFENSIVE_CODING,
            IssueCategory.WP_SETTINGS,
            IssueCategory.WP_AJAX,
            IssueCategory.WP_REST_API,
            IssueCategory.WP_DATABASE,
            IssueCategory.WP_FILESYSTEM,
            IssueCategory.WOO_COMPATIBILITY,
            IssueCategory.ACCESSIBILITY_I18N,
            IssueCategory.RELEASE_READINESS,
            IssueCategory.WP_ADMIN_NOTICES,
            IssueCategory.WP_EMAILS,
            IssueCategory.WP_PRIVACY,
            IssueCategory.WP_PERFORMANCE,
            IssueCategory.WP_MULTISITE,
        ]
        return [self.categories[cat] for cat in order if cat in self.categories]

    @property
    def total_checks(self) -> int:
        """Total checks across all categories."""
        return sum(cat.total for cat in self.categories.values())

    @property
    def total_passed(self) -> int:
        """Total passed checks."""
        return sum(cat.passed for cat in self.categories.values())

    @property
    def total_failed(self) -> int:
        """Total failed checks."""
        return sum(cat.failed for cat in self.categories.values())

    @property
    def total_warnings(self) -> int:
        """Total warning checks."""
        return sum(cat.warnings for cat in self.categories.values())

    def to_dict(self) -> Dict[str, Any]:
        return {
            'plugin': self.plugin.to_dict(),
            'site': self.site.to_dict(),
            'timestamp': self.timestamp.isoformat(),
            'summary': {
                'total_checks': self.total_checks,
                'passed': self.total_passed,
                'failed': self.total_failed,
                'warnings': self.total_warnings,
            },
            'categories': {cat.category.value: cat.to_dict() for cat in self.all_category_results},
        }
