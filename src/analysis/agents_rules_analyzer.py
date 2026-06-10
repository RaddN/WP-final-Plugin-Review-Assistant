"""AGENTS.md rule-based static analyzer for WordPress plugins."""
import re
import logging
from pathlib import Path
from typing import List, Tuple, Optional

from models import (
    ReviewIssue,
    IssueSeverity,
    IssueCategory,
    StaticAnalysisResult,
    PluginMetadata,
)


logger = logging.getLogger(__name__)

EXCLUDE_DIRS = {
    "vendor", "node_modules", "tests", "test", ".git", "docs",
    "build", "dist", "languages",
}


class AgentsRulesAnalyzer:
    """Comprehensive rule-based analysis aligned with AGENTS.md standards."""

    def __init__(self, plugin_root: str, metadata: Optional[PluginMetadata] = None):
        self.plugin_root = Path(plugin_root)
        self.metadata = metadata
        self.issues: List[ReviewIssue] = []
        self.files_scanned = 0

    def analyze(self) -> StaticAnalysisResult:
        logger.info("Starting AGENTS.md rule-based analysis of %s", self.plugin_root)
        self.issues = []
        self.files_scanned = 0

        php_files = self._collect_files("*.php")
        js_files = self._collect_files("*.js")
        css_files = self._collect_files("*.css")
        all_files = php_files + js_files + css_files

        # Scan for WooCommerce integration dependencies in bootstrap files
        self._check_bootstrap_loading(php_files)

        for file_path in all_files:
            try:
                self._analyze_file(file_path)
                self.files_scanned += 1
            except Exception as exc:
                logger.warning("Error analyzing %s: %s", file_path, exc)

        self._check_plugin_header()
        self._check_readme()
        self._check_zip_artifacts()
        self._check_uninstall()

        logger.info(
            "Rule-based analysis complete: %d issues in %d files",
            len(self.issues),
            self.files_scanned,
        )
        return StaticAnalysisResult(issues=self.issues, files_scanned=self.files_scanned)

    def _is_hidden_or_dot(self, path: Path) -> bool:
        """Check if path is a hidden file/folder or starts with a dot."""
        from utils import is_hidden_or_dot
        return is_hidden_or_dot(path, self.plugin_root)

    def _collect_files(self, pattern: str) -> List[Path]:
        import os
        import fnmatch
        from utils import is_hidden_or_dot
        filtered = []
        for root, dirs, files in os.walk(self.plugin_root):
            # Prune directories in-place (stops os.walk from entering them)
            pruned_dirs = []
            for d in dirs:
                dir_path = Path(root) / d
                if d.startswith('.') or d == "__MACOSX" or d in EXCLUDE_DIRS:
                    continue
                try:
                    import ctypes
                    attrs = ctypes.windll.kernel32.GetFileAttributesW(str(dir_path))
                    if attrs != -1 and (attrs & 2):  # FILE_ATTRIBUTE_HIDDEN
                        continue
                except Exception:
                    pass
                pruned_dirs.append(d)
            dirs[:] = pruned_dirs

            for f in files:
                if f.startswith('.') or f == "__MACOSX":
                    continue
                file_path = Path(root) / f
                try:
                    import ctypes
                    attrs = ctypes.windll.kernel32.GetFileAttributesW(str(file_path))
                    if attrs != -1 and (attrs & 2):  # FILE_ATTRIBUTE_HIDDEN
                        continue
                except Exception:
                    pass
                
                if fnmatch.fnmatch(f, pattern):
                    filtered.append(file_path)
        return filtered

    def _read_file(self, file_path: Path) -> str:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as handle:
            return handle.read()

    def _rel(self, file_path: Path) -> str:
        return str(file_path.relative_to(self.plugin_root))

    def _add(
        self,
        severity: IssueSeverity,
        category: IssueCategory,
        title: str,
        description: str,
        file_path: str,
        line_number: Optional[int] = None,
        code_snippet: Optional[str] = None,
        suggestion: Optional[str] = None,
        check_id: Optional[str] = None,
    ):
        self.issues.append(
            ReviewIssue(
                severity=severity,
                category=category,
                title=title,
                description=description,
                file_path=file_path,
                line_number=line_number,
                code_snippet=code_snippet,
                suggestion=suggestion,
                check_id=check_id,
            )
        )

    def _line_number(self, content: str, pos: int) -> int:
        return content[:pos].count("\n") + 1

    def _analyze_file(self, file_path: Path):
        content = self._read_file(file_path)
        rel = self._rel(file_path)

        if file_path.suffix == ".php":
            self._check_php_security(content, rel)
            self._check_php_defensive(content, rel)
            self._check_php_standards(content, rel)
            self._check_php_rest_ajax(content, rel)
            self._check_php_database(content, rel)
            self._check_php_filesystem(content, rel)
            self._check_php_woo(content, rel)
            self._check_php_i18n(content, rel)
            self._check_php_performance(content, rel)
            self._check_php_admin_notices(content, rel)
            self._check_php_emails(content, rel)
            self._check_php_privacy(content, rel)
            self._check_php_multisite(content, rel)
        elif file_path.suffix == ".js":
            self._check_js_standards(content, rel)
            self._check_js_accessibility(content, rel)
        elif file_path.suffix == ".css":
            self._check_css_standards(content, rel)

    def _check_bootstrap_loading(self, php_files: List[Path]):
        """Verify WooCommerce dependencies are checked before loading classes."""
        if not self.metadata or not self.metadata.woo_compatible:
            return

        # Find main file or bootstrap files
        bootstrap_files = [f for f in php_files if f.name == self.metadata.main_file or f.parent == self.plugin_root]
        for f in bootstrap_files:
            content = self._read_file(f)
            rel = self._rel(f)
            # If calls woo functions or instantiates WooCommerce but lacks check
            if re.search(r'\bWC\s*\(|class_exists\s*\(\s*[\'"]WooCommerce[\'"]\s*\)', content):
                # Has a WooCommerce check
                continue
            if re.search(r'\bwc_|[A-Z_]+_Order\b|WC_[A-Za-z_]+', content):
                self._add(
                    IssueSeverity.HIGH, IssueCategory.WP_STANDARDS,
                    "Missing WooCommerce loading guard",
                    "Plugin references WooCommerce objects or functions directly in bootstrap without checking if WooCommerce is active",
                    rel, None, None,
                    "Wrap WooCommerce integration initialization in functions loaded on plugins_loaded / woocommerce_loaded or guard with class_exists('WooCommerce')",
                    "wp_standards_dependencies"
                )

    def _check_php_security(self, content: str, rel: str):
        # 1. Superglobal access without validation/sanitization
        for match in re.finditer(r'\$_(?:POST|GET|REQUEST|FILES)\b', content):
            snippet = content[max(0, match.start() - 10):min(len(content), match.end() + 25)].strip().replace("\n", " ")
            self._add(
                IssueSeverity.HIGH, IssueCategory.WP_SECURITY,
                "Direct superglobal access",
                "Direct request superglobal access should be avoided. Restrict to a sanitization boundary.",
                rel, self._line_number(content, match.start()),
                snippet,
                "Sanitize input using wp_unslash() and sanitize_text_field(), and validate types/allowed values.",
                "wp_security_sanitization"
            )

        # 2. Output escaping
        for match in re.finditer(r'\becho\s+\$[^;]+', content):
            snippet = match.group(0)
            if any(esc in snippet for esc in ["esc_html", "esc_attr", "esc_url", "wp_kses", "absint", "intval"]):
                continue
            self._add(
                IssueSeverity.HIGH, IssueCategory.WP_SECURITY,
                "Unescaped dynamic output",
                "Echoing dynamic variables without escaping is a security risk (XSS).",
                rel, self._line_number(content, match.start()),
                snippet[:120],
                "Wrap the output in esc_html(), esc_attr(), esc_url(), or wp_kses_post().",
                "wp_security_escaping"
            )

        # 3. Dynamic SQL queries
        for match in re.finditer(r'\$wpdb->(?:query|get_results|get_row|get_var|get_col)\s*\(\s*["\'].*\$[^)]+\)', content):
            snippet = match.group(0)
            if "prepare" in snippet:
                continue
            self._add(
                IssueSeverity.CRITICAL, IssueCategory.WP_SECURITY,
                "Dynamic SQL query",
                "Dynamic values in SQL queries must be prepared using $wpdb->prepare() to prevent SQL injection.",
                rel, self._line_number(content, match.start()),
                snippet[:120],
                "Use $wpdb->prepare() to securely bind variables in SQL queries.",
                "wp_security_sql_prepared"
            )

        # 4. eval()
        for match in re.finditer(r'\beval\s*\(', content):
            self._add(
                IssueSeverity.CRITICAL, IssueCategory.RELEASE_READINESS,
                "Arbitrary code execution via eval()",
                "The eval() function is extremely dangerous and must not be used.",
                rel, self._line_number(content, match.start()),
                "eval(...)",
                "Remove eval() completely and rewrite logic using standard PHP structures.",
                "release_no_eval_settings"
            )

        # 5. base64_decode of user input
        for match in re.finditer(r'base64_decode\s*\(\s*\$_(?:POST|GET|REQUEST|FILES)', content):
            self._add(
                IssueSeverity.CRITICAL, IssueCategory.WP_SECURITY,
                "Decoding user input",
                "base64_decode on request input can bypass firewalls and lead to code injection.",
                rel, self._line_number(content, match.start()),
                match.group(0),
                "Avoid decoding and executing arbitrary user-provided data.",
                "wp_security_sanitization"
            )

        # 6. ABSPATH guard on PHP files
        if "ABSPATH" not in content[:1200]:
            self._add(
                IssueSeverity.HIGH, IssueCategory.WP_SECURITY,
                "Missing ABSPATH guard",
                "PHP file lacks direct access protection (ABSPATH guard).",
                rel, 1, None,
                "Add: if ( ! defined( 'ABSPATH' ) ) { exit; }",
                "wp_security_abspath"
            )

        # 7. Hardcoded admin-ajax.php
        if re.search(r'/wp-admin/admin-ajax\.php', content):
            self._add(
                IssueSeverity.MEDIUM, IssueCategory.WP_AJAX,
                "Hardcoded admin-ajax.php URL",
                "AJAX URL should not be hardcoded. Use localized variables.",
                rel, None, None,
                "Pass admin_url('admin-ajax.php') to scripts via wp_localize_script() or wp_add_inline_script().",
                "ajax_localization"
            )

        # 8. CDN assets
        cdn_pattern = r'https?://(?:ajax\.googleapis|code\.jquery|cdn\.|cdnjs|maxcdn|unpkg|jsdelivr|fonts\.googleapis)'
        for match in re.finditer(cdn_pattern, content, re.IGNORECASE):
            self._add(
                IssueSeverity.HIGH, IssueCategory.RELEASE_READINESS,
                "CDN asset reference",
                "Assets should be bundled locally, not loaded from external CDNs.",
                rel, self._line_number(content, match.start()),
                match.group(0)[:100],
                "Download the asset, bundle it with the plugin, and enqueue via WP APIs.",
                "release_no_cdn"
            )

        # 9. WP core file includes
        for core_file in ["wp-load.php", "wp-blog-header.php", "wp-config.php"]:
            if re.search(rf'require.*{re.escape(core_file)}', content) or re.search(rf'include.*{re.escape(core_file)}', content):
                self._add(
                    IssueSeverity.CRITICAL, IssueCategory.WP_STANDARDS,
                    f"Direct inclusion of {core_file}",
                    "Do not include WordPress core loading files directly.",
                    rel, None, None,
                    "Use standard hook-based bootstrap initialization.",
                    "wp_standards_no_direct_core_load"
                )

        # 10. Custom cURL usage instead of WP HTTP API
        if re.search(r'\bcurl_(?:init|exec)\b', content):
            self._add(
                IssueSeverity.MEDIUM, IssueCategory.WP_SECURITY,
                "Custom cURL usage detected",
                "Use the WordPress HTTP API instead of raw PHP cURL functions where possible for better portability, hook compatibility, and proxy support.",
                rel, None, None,
                "Replace raw curl_init/curl_exec calls with wp_remote_get() or wp_remote_post().",
                "wp_security_http_api"
            )

        # 11. Raw json_encode instead of wp_json_encode
        for match in re.finditer(r'\bjson_encode\b', content):
            self._add(
                IssueSeverity.LOW, IssueCategory.WP_SECURITY,
                "Use of raw json_encode()",
                "WordPress plugins should use wp_json_encode() instead of raw PHP json_encode() to ensure proper charset escaping and error handling.",
                rel, self._line_number(content, match.start()),
                "json_encode(...)",
                "Replace raw json_encode() calls with wp_json_encode().",
                "wp_security_json_encode"
            )

        # 12. Whole superglobal array processing
        if re.search(r'(?:update_option|update_user_meta|update_post_meta)\s*\(\s*[^,]+,\s*\$_(?:POST|GET|REQUEST)\s*\)', content) or re.search(r'\$[a-zA-Z_]\w*\s*=\s*\$_(?:POST|GET|REQUEST)\s*;', content):
            self._add(
                IssueSeverity.HIGH, IssueCategory.WP_SECURITY,
                "Whole superglobal array processing",
                "Processing or saving whole superglobal request arrays directly is insecure. Never trust the entire input structure without key-by-key allowlisting.",
                rel, None, None,
                "Sanitize and validate specific request parameters instead of assigning or updating options with the whole $_POST/$_GET array.",
                "wp_security_superglobal_arrays"
            )

    def _check_php_defensive(self, content: str, rel: str):
        # 1. WooCommerce objects return guards
        patterns = [
            (r'wc_get_product\s*\([^)]+\)\s*->', "wc_get_product() may return false - guard before method call", "defensive_woo_objects"),
            (r'wc_get_order\s*\([^)]+\)\s*->', "wc_get_order() may return false - guard before method call", "defensive_woo_objects"),
            (r'get_post\s*\([^)]+\)\s*->', "get_post() may return null/false - guard before property access", "defensive_null_checks"),
        ]
        for pattern, message, check_id in patterns:
            for match in re.finditer(pattern, content):
                context_start = max(0, match.start() - 80)
                context = content[context_start:match.start()]
                if re.search(r'if\s*\(', context):
                    continue
                self._add(
                    IssueSeverity.HIGH, IssueCategory.DEFENSIVE_CODING,
                    "Unguarded API return value", message, rel,
                    self._line_number(content, match.start()),
                    match.group(0)[:80],
                    "Add null/false checks before calling methods or accessing properties on the returned object.",
                    check_id
                )

        # 2. WP_Error checks
        if "is_wp_error" not in content and re.search(r'wp_remote_|get_term\(|wp_insert_post\(', content):
            self._add(
                IssueSeverity.MEDIUM, IssueCategory.DEFENSIVE_CODING,
                "Possible missing WP_Error check",
                "WP API calls that may return a WP_Error object should be checked with is_wp_error().",
                rel, None, None,
                "Wrap the API call result in an is_wp_error() guard: if ( is_wp_error( $result ) ) { ... }",
                "defensive_wp_error"
            )

        # 3. Array operations and array_merge guards
        for match in re.finditer(r'array_merge\s*\(\s*(?!\(array\))\$([a-zA-Z0-9_]+)\b', content):
            var_name = match.group(1)
            if var_name in ["args", "defaults", "options"]:
                continue
            self._add(
                IssueSeverity.MEDIUM, IssueCategory.DEFENSIVE_CODING,
                "Unguarded array_merge operation",
                f"Calling array_merge() on variable ${var_name} without casting can trigger PHP errors if it is null/false.",
                rel, self._line_number(content, match.start()),
                match.group(0),
                f"Cast the variable to an array: array_merge( (array) ${var_name}, ... ) or guard it.",
                "defensive_invalid_types"
            )

        # 4. Undefined properties/indexes checks
        for match in re.finditer(r'if\s*\(\s*\$_(?:POST|GET|REQUEST)\s*\[\s*[\'"][a-zA-Z0-9_-]+[\'"]\s*\]\s*(?:==|!=|===|!==|\))', content):
            self._add(
                IssueSeverity.LOW, IssueCategory.DEFENSIVE_CODING,
                "Potential undefined index usage",
                "Superglobal array values should be verified with isset() or empty() before direct comparison.",
                rel, self._line_number(content, match.start()),
                match.group(0),
                "Use: if ( isset( $_POST['key'] ) && $_POST['key'] === ... )",
                "defensive_undefined_indexes"
            )

    def _check_php_standards(self, content: str, rel: str):
        # 1. Inline scripts
        if re.search(r'<script', content, re.IGNORECASE):
            self._add(
                IssueSeverity.MEDIUM, IssueCategory.WP_STANDARDS,
                "Inline script tags",
                "Avoid writing inline script tags. Enqueue them through WP enqueue APIs.",
                rel, None, None,
                "Enqueue files via wp_enqueue_script() using handles.",
                "wp_standards_no_inline_scripts"
            )

        # 2. Inline styles
        if re.search(r'<style', content, re.IGNORECASE):
            self._add(
                IssueSeverity.MEDIUM, IssueCategory.WP_STANDARDS,
                "Inline style tags",
                "Avoid writing inline style tags. Enqueue them through WP enqueue APIs.",
                rel, None, None,
                "Enqueue files via wp_enqueue_style() using handles.",
                "wp_standards_no_inline_styles"
            )

        # 3. Heredoc/Nowdoc syntax
        for match in re.finditer(r'<<<([A-Z0-9_]+)', content):
            self._add(
                IssueSeverity.LOW, IssueCategory.WP_STANDARDS,
                "Heredoc/Nowdoc syntax detected",
                f"Use of heredoc/nowdoc syntax (<<< {match.group(1)}) is discouraged in WordPress plugins.",
                rel, self._line_number(content, match.start()),
                match.group(0),
                "Rewrite the output using standard double/single quoted strings or separate template PHP files.",
                "wp_standards_no_heredoc_nowdoc"
            )

        # 4. Unprefixed options
        for match in re.finditer(
            r'(?:add_option|update_option|get_option)\s*\(\s*["\'](?!wp_)([a-z_]{1,15})["\']',
            content,
        ):
            option = match.group(1)
            if option in {"active_plugins", "home", "siteurl", "admin_email", "blogname", "permalink_structure"}:
                continue
            self._add(
                IssueSeverity.MEDIUM, IssueCategory.WP_SETTINGS,
                "Potentially unprefixed option name",
                f"Option '{option}' lacks a plugin-specific prefix and might cause naming collisions.",
                rel, self._line_number(content, match.start()),
                match.group(0)[:80],
                f"Prefix option names with your plugin slug: {option} -> my_plugin_{option}",
                "settings_prefixing"
            )

    def _check_php_rest_ajax(self, content: str, rel: str):
        # 1. REST permission callbacks
        rest_routes = list(re.finditer(r'register_rest_route\s*\(', content))
        for match in rest_routes:
            block = content[match.start():match.start() + 600]
            if "permission_callback" not in block:
                self._add(
                    IssueSeverity.CRITICAL, IssueCategory.WP_REST_API,
                    "REST route missing permission_callback",
                    "Every REST API route registered via register_rest_route() must define a permission_callback.",
                    rel, self._line_number(content, match.start()),
                    block[:120].strip().replace("\n", " "),
                    "Add 'permission_callback' => function() { return current_user_can('manage_options'); }",
                    "rest_permission_callback"
                )

        # 2. AJAX Nonces
        ajax_handlers = list(re.finditer(r'add_action\s*\(\s*["\']wp_ajax', content))
        for match in ajax_handlers:
            block = content[match.start():match.start() + 800]
            if "wp_verify_nonce" not in block and "check_ajax_referer" not in block:
                self._add(
                    IssueSeverity.HIGH, IssueCategory.WP_AJAX,
                    "AJAX handler lacks nonce verification",
                    "State-changing or database-updating AJAX action handlers must verify nonces to prevent CSRF.",
                    rel, self._line_number(content, match.start()),
                    None,
                    "Verify nonces using check_ajax_referer('my-ajax-nonce') or wp_verify_nonce() in the AJAX handler.",
                    "ajax_security"
                )

    def _check_php_database(self, content: str, rel: str):
        # 1. Unbounded queries
        if re.search(r'posts_per_page\s*=>\s*[-]?\s*1\b', content) is None:
            if re.search(r"'posts_per_page'\s*=>\s*-1", content) or re.search(r'"posts_per_page"\s*=>\s*-1', content):
                self._add(
                    IssueSeverity.HIGH, IssueCategory.WP_DATABASE,
                    "Unbounded query (posts_per_page = -1)",
                    "Running queries without pagination limits (-1) can crash database connections on large WooCommerce sites.",
                    rel, None, None,
                    "Apply pagination, limits, or fetch in batches (e.g. posts_per_page => 50).",
                    "db_unbounded_queries"
                )

        # 2. Custom tables creation
        if re.search(r'CREATE\s+TABLE', content, re.IGNORECASE) and "dbDelta" not in content:
            self._add(
                IssueSeverity.MEDIUM, IssueCategory.WP_DATABASE,
                "CREATE TABLE without dbDelta()",
                "Custom database tables should be created and migrated using the WordPress dbDelta() API.",
                rel, None, None,
                "Use dbDelta() and store a DB schema version in settings for tracking table upgrades.",
                "db_custom_tables"
            )

    def _check_php_filesystem(self, content: str, rel: str):
        # 1. Direct filesystem writes
        if re.search(r'file_put_contents\s*\(|fwrite\s*\(', content) and "WP_Filesystem" not in content:
            self._add(
                IssueSeverity.MEDIUM, IssueCategory.WP_FILESYSTEM,
                "Direct filesystem write",
                "Writing directly to files is risky and non-portable. Consider the WP_Filesystem API.",
                rel, None, None,
                "Initialize and use the WP_Filesystem API for writing files.",
                "fs_api_usage"
            )

        # 2. Path traversal
        if re.search(r'\.\./', content) or re.search(r'\$_FILES.*\.\.', content):
            self._add(
                IssueSeverity.HIGH, IssueCategory.WP_FILESYSTEM,
                "Potential path traversal",
                "Detecting directory traversal character sequences in filesystem or uploads logic.",
                rel, None, None,
                "Normalize paths using realpath(), check paths against a directory allowlist, or use validate_file().",
                "fs_path_traversal"
            )

    def _check_php_woo(self, content: str, rel: str):
        if not self.metadata or not self.metadata.woo_compatible:
            return

        # 1. Direct post table access for orders
        if re.search(r"wp_posts.*shop_order|post_type.*shop_order", content):
            self._add(
                IssueSeverity.HIGH, IssueCategory.WOO_COMPATIBILITY,
                "Direct order post queries",
                "Querying orders directly from the wp_posts table breaks WooCommerce High-Performance Order Storage (HPOS).",
                rel, None, None,
                "Use wc_get_orders() or the WC_Order_Query API instead of direct post queries.",
                "woo_crud_usage"
            )

        # 2. HPOS compatibility declaration
        if "woocommerce" in content.lower() and "hpos" not in content.lower() and "custom_order_tables" not in content.lower():
            if re.search(r'wc_get_order|WC_Order', content):
                self._add(
                    IssueSeverity.LOW, IssueCategory.WOO_COMPATIBILITY,
                    "HPOS compatibility not declared",
                    "WooCommerce integration should explicitly declare HPOS compatibility or incompatibility.",
                    rel, None, None,
                    "Add: add_action( 'before_woocommerce_init', function() { wcs_declare_compatibility(); } ); using FeaturesUtil::declare_compatibility.",
                    "woo_hpos_compatibility"
                )

    def _check_php_i18n(self, content: str, rel: str):
        # 1. Non-literal gettext strings
        gettext_calls = re.findall(r'__\s*\(\s*(\$|[\'"][^\'"]*[\'"]\s*,\s*\$)', content)
        if gettext_calls:
            self._add(
                IssueSeverity.MEDIUM, IssueCategory.ACCESSIBILITY_I18N,
                "Non-literal gettext string/domain",
                "Gettext functions (__, _e, etc.) require literal string arguments to be scanned by translation tools.",
                rel, None, None,
                "Do not pass variables, constants, or functions to gettext. Use: __( 'Translated Text', 'text-domain' )",
                "i18n_literal_gettext"
            )

        # 2. Text domain mismatch
        if self.metadata and self.metadata.text_domain:
            domain = self.metadata.text_domain
            if domain and f"'{domain}'" not in content and f'"{domain}"' not in content:
                if re.search(r'__\(|_e\(|esc_html__\(|esc_html_e\(', content):
                    self._add(
                        IssueSeverity.LOW, IssueCategory.ACCESSIBILITY_I18N,
                        "Possible text domain mismatch",
                        f"Gettext calls in this file do not match the header text domain '{domain}'.",
                        rel, None, None,
                        f"Ensure all translation functions use the plugin text domain: '{domain}'.",
                        "i18n_text_domain"
                    )

    def _check_php_performance(self, content: str, rel: str):
        # 1. Query on init
        if re.search(r"add_action\s*\(\s*['\"]init['\"]", content) and re.search(r'get_posts|WP_Query', content):
            self._add(
                IssueSeverity.MEDIUM, IssueCategory.WP_DATABASE,
                "Query executed on init hook",
                "Executing database queries on the init hook runs them on every single page load, affecting performance.",
                rel, None, None,
                "Defer queries to specific admin screens, page requests, or use transients to cache results.",
                "perf_page_load"
            )

        # 2. Autoloading large options
        if re.search(r"add_option\s*\([^)]+,\s*[^)]+,\s*['\"]yes['\"]", content):
            self._add(
                IssueSeverity.MEDIUM, IssueCategory.WP_SETTINGS,
                "Autoloading option",
                "Options should not be autoloaded (autoload => 'yes') if they store large objects, caches, or logs.",
                rel, None, None,
                "Pass 'no' (or false in newer WP) as the autoload parameter for large option values.",
                "perf_autoload"
            )

        # 3. Repeated meta/option/DB query in loop (N+1 query problem)
        loop_matches = re.finditer(r'(?:foreach|while)\s*\([^)]+\)\s*\{[^}]*\b(?:get_post_meta|get_option|update_option|get_posts|wp_query)\b', content, re.IGNORECASE | re.DOTALL)
        for match in loop_matches:
            self._add(
                IssueSeverity.HIGH, IssueCategory.WP_PERFORMANCE,
                "Repeated query inside loop",
                "Database, option, or post meta queries executed inside loops cause major performance degradation (N+1 query problem).",
                rel, self._line_number(content, match.start()),
                match.group(0)[:120].strip().replace("\n", " ") + "...",
                "Batch load meta values, cache results, or fetch data with custom SQL joins instead of query in loops.",
                "perf_queries_in_loops"
            )

    def _check_js_standards(self, content: str, rel: str):
        # 1. jQuery shorthands
        for pattern, name in [
            (r'\.click\s*\(', ".click() shorthand"),
            (r'\.bind\s*\(', ".bind() shorthand"),
            (r'\.hover\s*\(', ".hover() shorthand"),
            (r'\.submit\s*\(', ".submit() shorthand"),
        ]:
            if re.search(pattern, content):
                self._add(
                    IssueSeverity.LOW, IssueCategory.WP_STANDARDS,
                    f"jQuery {name} detected",
                    "Use delegated event handlers (.on()) instead of obsolete jQuery shorthands.",
                    rel, None, None,
                    "Replace with delegated binding: $(document).on('click', selector, handler)",
                    "wp_standards_assets"
                )

        # 2. Strict mode
        if "use strict" not in content and "jQuery" in content:
            self._add(
                IssueSeverity.LOW, IssueCategory.WP_STANDARDS,
                "Missing JS strict mode",
                "JavaScript scripts should enforce strict mode inside jQuery closures.",
                rel, None, None,
                'Wrap JavaScript in an IIFE and add strict mode: (function($) { "use strict"; ... })(jQuery);',
                "wp_standards_assets"
            )

    def _check_js_accessibility(self, content: str, rel: str):
        """Check for accessibility violations in JavaScript interaction code."""
        # Find click handlers bound to non-interactive elements (div, span, p)
        matches = re.finditer(r'\$\(\s*[\'"](?:div|span|p|li|i|img|section|article)[^\'"]*[\'"]\s*\)\s*\.\s*(?:click|on\s*\(\s*[\'"]click[\'"])', content)
        for match in matches:
            self._add(
                IssueSeverity.LOW, IssueCategory.ACCESSIBILITY_I18N,
                "Non-interactive click handler",
                "Attaching click event handlers to non-interactive elements (div, span, etc.) makes them inaccessible to screen readers and keyboard users.",
                rel, self._line_number(content, match.start()),
                match.group(0),
                "Use <button> or <a> tags for interactive clicks, or add tabindex='0' and keyboard keydown event support.",
                "a11y_keyboard"
            )

    def _check_plugin_header(self):
        if not self.metadata:
            return

        main_file = self.plugin_root / self.metadata.main_file
        if not main_file.exists():
            self._add(
                IssueSeverity.CRITICAL, IssueCategory.RELEASE_READINESS,
                "Main plugin file missing",
                f"Expected entry file {self.metadata.main_file} was not found at plugin root.",
                self.metadata.main_file, None, None,
                "Ensure the main plugin file exists with the plugin header comments.",
                "wp_standards_header"
            )
            return

        content = self._read_file(main_file)
        required = ["Plugin Name:", "Version:"]
        for field in required:
            if field not in content[:3000]:
                self._add(
                    IssueSeverity.HIGH, IssueCategory.RELEASE_READINESS,
                    f"Missing header field: {field}",
                    f"The required plugin header field '{field}' is missing.",
                    self.metadata.main_file, None, None,
                    f"Add the '{field}' comment line inside your main plugin file header block.",
                    "wp_standards_header"
                )

    def _check_readme(self):
        readme = self.plugin_root / "readme.txt"
        if not readme.exists():
            self._add(
                IssueSeverity.MEDIUM, IssueCategory.RELEASE_READINESS,
                "Missing readme.txt file",
                "WordPress.org plugins require a readme.txt file for directory details.",
                "readme.txt", None, None,
                "Create a valid readme.txt file including stable tag and changelog.",
                "release_readme_version"
            )
            return

        content = self._read_file(readme)
        if "Stable tag:" not in content:
            self._add(
                IssueSeverity.MEDIUM, IssueCategory.RELEASE_READINESS,
                "readme.txt missing Stable tag",
                "Stable tag in readme.txt must match the current stable release version.",
                "readme.txt", None, None,
                "Add a 'Stable tag: x.y.z' line to readme.txt.",
                "release_readme_version"
            )

        if self.metadata and "Stable tag:" in content:
            match = re.search(r"Stable tag:\s*(.+)", content)
            if match and match.group(1).strip() != self.metadata.version:
                self._add(
                    IssueSeverity.MEDIUM, IssueCategory.RELEASE_READINESS,
                    "readme stable tag mismatch",
                    f"Plugin header Version '{self.metadata.version}' does not match readme.txt Stable tag '{match.group(1).strip()}'.",
                    "readme.txt", None, None,
                    "Align the Stable tag version with the Plugin Version header.",
                    "release_readme_version"
                )

    def _check_zip_artifacts(self):
        # 1. Dev artifacts
        for suffix in [".bak", ".tmp", ".log", ".zip", ".orig", ".old"]:
            for f in self.plugin_root.rglob(f"*{suffix}"):
                if self._is_hidden_or_dot(f):
                    continue
                if any(part in EXCLUDE_DIRS for part in f.parts):
                    continue
                self._add(
                    IssueSeverity.MEDIUM, IssueCategory.RELEASE_READINESS,
                    f"Backup/development file: {f.name}",
                    "Development leftovers and backups must be removed from the release package.",
                    self._rel(f), None, None,
                    f"Delete the temporary file '{f.name}' from the plugin folder.",
                    "release_no_dev_artifacts"
                )

        # 2. Excluded directories/files
        for name in [".git", ".github", "node_modules", ".env", "debug.log"]:
            if (self.plugin_root / name).exists():
                self._add(
                    IssueSeverity.HIGH, IssueCategory.RELEASE_READINESS,
                    f"Release artifact present: {name}",
                    f"The directory/file '{name}' is a build/dev artifact and must be excluded from the release ZIP.",
                    name, None, None,
                    f"Delete or exclude '{name}' before archiving the plugin.",
                    "release_no_dev_artifacts"
                )

        # 3. Source maps
        for f in self.plugin_root.rglob("*.map"):
            if self._is_hidden_or_dot(f):
                continue
            if any(part in EXCLUDE_DIRS for part in f.parts):
                continue
            self._add(
                IssueSeverity.LOW, IssueCategory.RELEASE_READINESS,
                "Source map file in package",
                "JS/CSS source maps should not be shipped in release archives.",
                self._rel(f), None, None,
                "Exclude source map (.map) files from your release build zip.",
                "release_no_dev_artifacts"
            )

    def _check_uninstall(self):
        uninstall = self.plugin_root / "uninstall.php"
        has_uninstall_hook = False
        for php in self._collect_files("*.php"):
            content = self._read_file(php)
            if "register_uninstall_hook" in content:
                has_uninstall_hook = True
                break

        if not uninstall.exists() and not has_uninstall_hook:
            self._add(
                IssueSeverity.LOW, IssueCategory.WP_STANDARDS,
                "No uninstall cleanup handler",
                "The plugin lacks an uninstall.php file or register_uninstall_hook() registration to clean up options on uninstall.",
                "uninstall.php", None, None,
                "Create an uninstall.php file to clean up options, transients, and database tables.",
                "wp_standards_uninstall"
            )
        elif uninstall.exists():
            content = self._read_file(uninstall)
            if "WP_UNINSTALL_PLUGIN" not in content:
                self._add(
                    IssueSeverity.MEDIUM, IssueCategory.WP_STANDARDS,
                    "uninstall.php missing WP_UNINSTALL_PLUGIN guard",
                    "uninstall.php must check WP_UNINSTALL_PLUGIN before executing to prevent direct file execution.",
                    "uninstall.php", None, None,
                    "Add: if ( ! defined( 'WP_UNINSTALL_PLUGIN' ) ) { exit; } at the top of uninstall.php.",
                    "wp_standards_uninstall"
                )

    def _check_php_admin_notices(self, content: str, rel: str):
        if "admin_notices" in content:
            if "current_user_can" not in content:
                self._add(
                    IssueSeverity.HIGH, IssueCategory.WP_ADMIN_NOTICES,
                    "Capability check missing for admin notice",
                    "Admin notices should only be rendered for authorized users. Verify if current_user_can() is used near hook execution.",
                    rel, None, None,
                    "Wrap notice output in current_user_can('manage_options') or check capabilities before rendering.",
                    "admin_notices_caps"
                )
            if not any(x in content for x in ["get_user_meta", "update_user_meta", "get_option", "update_option", "get_transient"]):
                self._add(
                    IssueSeverity.MEDIUM, IssueCategory.WP_ADMIN_NOTICES,
                    "Notice dismissal state tracking missing",
                    "Admin notices should be dismissible, and the dismissal state should be saved in user meta or options to avoid persistent nagging.",
                    rel, None, None,
                    "Implement AJAX notice dismissal or store dismissal state via user meta or transients.",
                    "admin_notices_dismissal"
                )
            if "get_current_screen" not in content:
                self._add(
                    IssueSeverity.LOW, IssueCategory.WP_ADMIN_NOTICES,
                    "Global admin notice usage",
                    "Admin notices should be limited to specific pages/screens using get_current_screen() to avoid cluttering other plugin menus.",
                    rel, None, None,
                    "Check get_current_screen() inside the admin notices handler to only show the notice where relevant.",
                    "admin_notices_global"
                )
            if re.search(r'\b(?:rate|pricing|upgrade|nag|review|pro-version)\b', content, re.IGNORECASE):
                self._add(
                    IssueSeverity.LOW, IssueCategory.WP_ADMIN_NOTICES,
                    "Potential promotional or nag notice",
                    "Promotional review requests or marketing nags in admin notices are discouraged without user consent.",
                    rel, None, None,
                    "Avoid automatic non-dismissible nags; keep promotional notifications quiet and strictly dismissible.",
                    "admin_notices_nags"
                )

    def _check_php_emails(self, content: str, rel: str):
        for match in re.finditer(r'\bmail\s*\(', content):
            self._add(
                IssueSeverity.HIGH, IssueCategory.WP_EMAILS,
                "Use of PHP mail()",
                "Do not use raw PHP mail(). Use wp_mail() or WooCommerce mail classes.",
                rel, self._line_number(content, match.start()),
                "mail(...)",
                "Replace raw mail() calls with wp_mail().",
                "emails_api"
            )
        if "wp_mail" in content or "wc_mail" in content:
            if re.search(r'(?:password|secret|key|token|credentials)', content, re.IGNORECASE):
                self._add(
                    IssueSeverity.HIGH, IssueCategory.WP_EMAILS,
                    "Sensitive data in email body",
                    "Sensitive credentials, keys, or passwords should not be sent in plain text emails.",
                    rel, None, None,
                    "Only send password reset links or secure checkout links; avoid sending cleartext passwords or keys in emails.",
                    "emails_secrets"
                )

    def _check_php_privacy(self, content: str, rel: str):
        if "error_log" in content or "wp_plugin_review" in content:
            for match in re.finditer(r'error_log\s*\(\s*.*\$_(?:POST|GET|REQUEST)\b', content):
                self._add(
                    IssueSeverity.HIGH, IssueCategory.WP_PRIVACY,
                    "Superglobals logged directly",
                    "Logging request superglobals directly can expose personal details or secrets in web server logs.",
                    rel, self._line_number(content, match.start()),
                    match.group(0),
                    "Sanitize/redact inputs and only log specific, non-sensitive keys/values.",
                    "privacy_logging"
                )

    def _check_php_multisite(self, content: str, rel: str):
        if "get_sites" in content or "wp_get_sites" in content:
            if "switch_to_blog" in content and not re.search(r'\bis_multisite\b', content):
                self._add(
                    IssueSeverity.MEDIUM, IssueCategory.WP_MULTISITE,
                    "Multisite loop without safety guard",
                    "Looping through all multisite networks or blogs should check is_multisite() first to avoid runtime errors on standard sites.",
                    rel, None, None,
                    "Guard multisite database actions with if ( is_multisite() ) checks.",
                    "multisite_guards"
                )

    def _check_css_standards(self, content: str, rel: str):
        cdn_pattern = r'https?://(?:ajax\.googleapis|code\.jquery|cdn\.|cdnjs|maxcdn|unpkg|jsdelivr|fonts\.googleapis)'
        for match in re.finditer(cdn_pattern, content, re.IGNORECASE):
            self._add(
                IssueSeverity.HIGH, IssueCategory.RELEASE_READINESS,
                "CDN asset reference in CSS",
                "CSS file references external CDNs/fonts directly instead of loading local resources.",
                rel, self._line_number(content, match.start()),
                match.group(0)[:100],
                "Download the font/asset, bundle it locally, and load it via a local path.",
                "release_no_cdn"
            )

