"""Deterministic WordPress review rule analyzer for plugins."""
import logging
import os
import re
import time
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from models import (
    IssueCategory,
    IssueSeverity,
    PluginMetadata,
    ReviewIssue,
    StaticAnalysisResult,
)


logger = logging.getLogger(__name__)

EXCLUDE_DIRS = {
    ".git",
    "assets/vendor",
    "bower_components",
    "build",
    "dist",
    "docs",
    "languages",
    "node_modules",
    "test",
    "tests",
    "vendor",
}

CORE_OPTION_NAMES = {
    "active_plugins",
    "admin_email",
    "blogdescription",
    "blogname",
    "home",
    "page_on_front",
    "page_for_posts",
    "permalink_structure",
    "show_on_front",
    "siteurl",
    "stylesheet",
    "template",
    "woocommerce_db_version",
}

WORDPRESS_HOOK_PREFIXES = (
    "admin_",
    "after_",
    "before_",
    "comment_",
    "customize_",
    "delete_",
    "deleted_",
    "edit_",
    "enqueue_",
    "init",
    "load-",
    "manage_",
    "plugin_",
    "plugins_",
    "pre_",
    "rest_",
    "save_",
    "template_",
    "the_",
    "transition_",
    "updated_",
    "user_",
    "wp_",
    "woocommerce_",
)

SANITIZERS = (
    "absint",
    "array_map",
    "boolval",
    "esc_url_raw",
    "filter_var",
    "floatval",
    "intval",
    "sanitize_",
    "sanitize_text_field",
    "sanitize_textarea_field",
    "sanitize_key",
    "sanitize_email",
    "sanitize_file_name",
    "sanitize_title",
    "wc_clean",
    "wp_kses",
    "wp_parse_id_list",
)

VALIDATORS = (
    "in_array",
    "is_array",
    "is_bool",
    "is_email",
    "is_numeric",
    "is_scalar",
    "is_string",
    "preg_match",
    "validate_file",
    "wp_verify_nonce",
)

STATE_CHANGE_PATTERNS = re.compile(
    r"\b(?:"
    r"add_option|update_option|delete_option|update_(?:post|user|term|comment)_meta|"
    r"delete_(?:post|user|term|comment)_meta|wp_insert_|wp_update_|wp_delete_|"
    r"wc_create_|wc_update_|wc_delete_|WC_Cart|add_to_cart|remove_cart_item|"
    r"file_put_contents|fwrite|unlink|rmdir|rename|copy|move_uploaded_file|"
    r"wp_remote_(?:post|request)|wp_mail|as_schedule_|wp_schedule_event"
    r")\b",
    re.IGNORECASE,
)

QUERY_IN_LOOP_PATTERN = re.compile(
    r"(?:foreach|while)\s*\([^)]+\)\s*\{(?:(?!\n\s*\}).){0,1200}"
    r"\b(?:get_post_meta|get_user_meta|get_term_meta|get_option|update_option|"
    r"WP_Query|get_posts|wc_get_orders|wc_get_products|\$wpdb->)\b",
    re.IGNORECASE | re.DOTALL,
)

TRANSLATION_FUNCTIONS = (
    "__",
    "_e",
    "_x",
    "esc_html__",
    "esc_html_e",
    "esc_attr__",
    "esc_attr_e",
    "printf",
    "sprintf",
)

STATIC_CHECK_IDS = {
    "admin_notices_caps",
    "admin_notices_dismissal",
    "admin_notices_global",
    "admin_notices_nags",
    "ajax_localization",
    "ajax_prefixing",
    "ajax_security",
    "a11y_keyboard",
    "a11y_structure",
    "db_custom_tables",
    "db_prepared_sql",
    "db_unbounded_queries",
    "defensive_array_guards",
    "defensive_integration_checks",
    "defensive_invalid_types",
    "defensive_null_checks",
    "defensive_remote_requests",
    "defensive_undefined_indexes",
    "defensive_woo_objects",
    "defensive_wp_error",
    "emails_api",
    "emails_duplicates",
    "emails_secrets",
    "fs_api_usage",
    "fs_path_traversal",
    "fs_temp_cleanup",
    "fs_upload_security",
    "i18n_escaped_output",
    "i18n_literal_gettext",
    "i18n_text_domain",
    "multisite_guards",
    "multisite_loop_sites",
    "multisite_options",
    "perf_autoload",
    "perf_enqueue_screens",
    "perf_queries_in_loops",
    "perf_transient_caching",
    "privacy_exporter_eraser",
    "privacy_logging",
    "privacy_policy",
    "release_no_bundled_core",
    "release_no_cdn",
    "release_no_dev_artifacts",
    "release_no_eval_settings",
    "release_readme_version",
    "rest_data_leak",
    "rest_permission_callback",
    "rest_validation",
    "settings_prefixing",
    "settings_register",
    "settings_rest_api",
    "woo_checkout_compatibility",
    "woo_crud_usage",
    "woo_hpos_compatibility",
    "woo_object_safety",
    "wp_security_capabilities",
    "wp_security_nonces",
    "wp_security_path_traversal",
    "wp_security_ajax_auth",
    "wp_security_rest_auth",
    "wp_security_sanitization",
    "wp_security_secrets",
    "wp_security_sql_prepared",
    "wp_standards_activation",
    "wp_standards_dependencies",
    "wp_standards_hooks",
    "wp_standards_prefixing",
    "wp_standards_uninstall",
}

NO_SURFACE_NA_CHECKS = {
    "admin_notices_caps",
    "admin_notices_dismissal",
    "admin_notices_global",
    "admin_notices_nags",
    "ajax_prefixing",
    "ajax_security",
    "db_custom_tables",
    "defensive_remote_requests",
    "emails_api",
    "emails_duplicates",
    "emails_secrets",
    "fs_api_usage",
    "fs_path_traversal",
    "fs_temp_cleanup",
    "fs_upload_security",
    "multisite_guards",
    "multisite_loop_sites",
    "multisite_options",
    "privacy_exporter_eraser",
    "privacy_policy",
    "rest_data_leak",
    "rest_permission_callback",
    "rest_validation",
    "wp_security_ajax_auth",
    "wp_security_rest_auth",
    "settings_register",
    "settings_rest_api",
    "woo_checkout_compatibility",
    "woo_crud_usage",
    "woo_hpos_compatibility",
    "woo_object_safety",
}


class AgentsRulesAnalyzer:
    """Static WordPress plugin analyzer aligned with review checklist IDs."""

    def __init__(self, plugin_root: str, metadata: Optional[PluginMetadata] = None):
        self.plugin_root = Path(plugin_root)
        self.metadata = metadata
        self.issues: List[ReviewIssue] = []
        self.files_scanned = 0
        self.automated_checks: Set[str] = set(STATIC_CHECK_IDS)
        self.applicable_checks: Set[str] = set()
        self.not_applicable_checks: Set[str] = set()
        self.prefixes: Set[str] = set()
        self._seen: Set[Tuple[str, str, Optional[int], str]] = set()
        self._woo_checkout_needs_review = False
        self._privacy_needs_review = False

    def analyze(self) -> StaticAnalysisResult:
        started = time.perf_counter()
        logger.info("Starting deterministic static analysis of %s", self.plugin_root)

        self.issues = []
        self.files_scanned = 0
        self.applicable_checks = set()
        self.not_applicable_checks = set()
        self._seen = set()
        self._woo_checkout_needs_review = False
        self._privacy_needs_review = False

        php_files = self._collect_files("*.php")
        js_files = self._collect_files("*.js")
        css_files = self._collect_files("*.css")
        self.prefixes = self._infer_prefixes(php_files)

        self._check_cross_file_prefixing(php_files, js_files)
        self._check_bootstrap_loading(php_files)
        self._check_activation_deactivation(php_files)

        for file_path in php_files:
            try:
                content = self._read_file(file_path)
                rel = self._rel(file_path)
                self._check_php_security(content, rel)
                self._check_php_defensive(content, rel)
                self._check_php_rest_ajax(content, rel)
                self._check_php_database(content, rel)
                self._check_php_filesystem(content, rel)
                self._check_php_woo(content, rel)
                self._check_php_i18n(content, rel)
                self._check_php_accessibility(content, rel)
                self._check_php_performance(content, rel)
                self._check_php_admin_notices(content, rel)
                self._check_php_emails(content, rel)
                self._check_php_privacy(content, rel)
                self._check_php_multisite(content, rel)
                self.files_scanned += 1
            except Exception as exc:
                logger.warning("Error analyzing %s: %s", file_path, exc)

        for file_path in js_files:
            try:
                content = self._read_file(file_path)
                rel = self._rel(file_path)
                self._check_js_standards(content, rel)
                self._check_js_accessibility(content, rel)
                self.files_scanned += 1
            except Exception as exc:
                logger.warning("Error analyzing %s: %s", file_path, exc)

        for file_path in css_files:
            try:
                content = self._read_file(file_path)
                rel = self._rel(file_path)
                self._check_css_release(content, rel)
                self.files_scanned += 1
            except Exception as exc:
                logger.warning("Error analyzing %s: %s", file_path, exc)

        self._check_plugin_header()
        self._check_readme()
        self._check_release_artifacts()
        self._check_uninstall()
        self._add_deferred_plugin_level_findings()
        self._finalize_not_applicable()

        elapsed = time.perf_counter() - started
        logger.info(
            "Rule-based analysis complete: %d issues in %d files",
            len(self.issues),
            self.files_scanned,
        )
        return StaticAnalysisResult(
            issues=self.issues,
            files_scanned=self.files_scanned,
            analysis_time=elapsed,
            automated_checks=sorted(self.automated_checks),
            applicable_checks=sorted(self.applicable_checks),
            not_applicable_checks=sorted(self.not_applicable_checks),
        )

    def _collect_files(self, pattern: str) -> List[Path]:
        import fnmatch
        from utils import is_hidden_or_dot

        filtered: List[Path] = []
        for root, dirs, files in os.walk(self.plugin_root):
            pruned_dirs = []
            for dirname in dirs:
                dir_path = Path(root) / dirname
                rel = self._safe_relative_parts(dir_path)
                rel_path = "/".join(rel).lower()
                if dirname.startswith(".") or dirname == "__MACOSX":
                    continue
                if dirname in EXCLUDE_DIRS or rel_path in EXCLUDE_DIRS:
                    continue
                if is_hidden_or_dot(dir_path, self.plugin_root):
                    continue
                pruned_dirs.append(dirname)
            dirs[:] = pruned_dirs

            for filename in files:
                file_path = Path(root) / filename
                if filename.startswith(".") or filename == "__MACOSX":
                    continue
                if is_hidden_or_dot(file_path, self.plugin_root):
                    continue
                if fnmatch.fnmatch(filename, pattern):
                    filtered.append(file_path)
        return filtered

    def _safe_relative_parts(self, path: Path) -> Tuple[str, ...]:
        try:
            return path.relative_to(self.plugin_root).parts
        except ValueError:
            return path.parts

    def _read_file(self, file_path: Path) -> str:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as handle:
            return handle.read()

    def _rel(self, file_path: Path) -> str:
        return str(file_path.relative_to(self.plugin_root))

    def _line_number(self, content: str, pos: int) -> int:
        return content[:pos].count("\n") + 1

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
    ) -> None:
        if check_id:
            self.applicable_checks.add(check_id)
            self.automated_checks.add(check_id)

        dedupe_key = (check_id or "", file_path, line_number, title)
        if dedupe_key in self._seen:
            return
        self._seen.add(dedupe_key)

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

    def _mark_applicable(self, *check_ids: str) -> None:
        self.applicable_checks.update(check_ids)
        self.automated_checks.update(check_ids)

    def _finalize_not_applicable(self) -> None:
        for check_id in NO_SURFACE_NA_CHECKS:
            if check_id not in self.applicable_checks:
                self.not_applicable_checks.add(check_id)

        if not self.metadata or not self.metadata.woo_compatible:
            self.not_applicable_checks.update(
                {
                    "woo_checkout_compatibility",
                    "woo_crud_usage",
                    "woo_hpos_compatibility",
                    "woo_object_safety",
                }
            )

    def _add_deferred_plugin_level_findings(self) -> None:
        if self._woo_checkout_needs_review:
            self._add(
                IssueSeverity.LOW,
                IssueCategory.WOO_COMPATIBILITY,
                "Checkout Blocks compatibility not evident",
                "Checkout-related code was found, but static analysis did not see Blocks or Store API integration.",
                self.metadata.main_file if self.metadata else "",
                None,
                None,
                "Document classic-only behavior or verify/add Cart and Checkout Blocks compatibility.",
                "woo_checkout_compatibility",
            )

        if self._privacy_needs_review:
            self._add(
                IssueSeverity.LOW,
                IssueCategory.WP_PRIVACY,
                "Privacy disclosure/export coverage needs review",
                "Code appears to store or log personal data; privacy policy text and exporter/eraser callbacks were not clearly visible across the scanned files.",
                self.metadata.main_file if self.metadata else "",
                None,
                None,
                "Add privacy policy text and data exporter/eraser callbacks when plugin-owned personal data is stored.",
                "privacy_policy",
            )
            self._add(
                IssueSeverity.LOW,
                IssueCategory.WP_PRIVACY,
                "Personal data exporter/eraser not evident",
                "Plugin-owned personal data should be exportable and erasable when appropriate.",
                self.metadata.main_file if self.metadata else "",
                None,
                None,
                "Register personal data exporters and erasers for plugin-owned customer/user data.",
                "privacy_exporter_eraser",
            )

    def _clean_identifier(self, value: str) -> str:
        return re.sub(r"[^a-z0-9_]", "_", value.lower()).strip("_")

    def _infer_prefixes(self, php_files: Sequence[Path]) -> Set[str]:
        counts: Counter = Counter()
        prefixes: Set[str] = set()

        if self.metadata:
            for source in [
                self.metadata.text_domain,
                self.metadata.main_file.replace(".php", ""),
                self.metadata.name,
            ]:
                cleaned = self._clean_identifier(source)
                if cleaned:
                    prefixes.add(cleaned)
                    parts = [part for part in cleaned.split("_") if part and part not in {"for", "the", "and", "wp", "woocommerce"}]
                    if parts:
                        initials = "".join(part[0] for part in parts if part)
                        if len(initials) >= 3:
                            prefixes.add(initials)

        for php in php_files:
            content = self._read_file(php)
            for name in re.findall(r"^\s*function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", content, re.MULTILINE):
                if "_" in name:
                    counts[name.split("_", 1)[0].lower()] += 1
            for name in re.findall(r"\b(?:add|update|get|delete)_option\s*\(\s*['\"]([A-Za-z0-9_\-]+)['\"]", content):
                if "_" in name:
                    counts[name.split("_", 1)[0].lower()] += 1
            for name in re.findall(r"\badd_shortcode\s*\(\s*['\"]([A-Za-z0-9_\-]+)['\"]", content):
                if "_" in name:
                    counts[name.split("_", 1)[0].lower()] += 1
            for name in re.findall(r"\bdefine\s*\(\s*['\"]([A-Z][A-Z0-9_]{3,})['\"]", content):
                if "_" in name:
                    counts[name.split("_", 1)[0].lower()] += 1
            for name in re.findall(r"wp_ajax(?:_nopriv)?_([A-Za-z0-9_\-]+)", content):
                if "_" in name:
                    counts[name.split("_", 1)[0].lower()] += 1

        stop = {"ajax", "admin", "class", "get", "load", "plugin", "render", "save", "set", "wp", "wc"}
        for prefix, count in counts.most_common(10):
            if count >= 2 and len(prefix) >= 3 and prefix not in stop:
                prefixes.add(prefix)

        return {prefix for prefix in prefixes if len(prefix) >= 3}

    def _is_prefixed(self, name: str) -> bool:
        normalized = self._clean_identifier(name)
        if not normalized:
            return True
        return any(normalized == prefix or normalized.startswith(prefix + "_") or normalized.startswith(prefix) for prefix in self.prefixes)

    def _is_probably_core_hook(self, hook: str) -> bool:
        if hook.startswith(("litespeed_", "elementor/", "elementor_", "woocommerce_")):
            return True
        return hook.startswith(WORDPRESS_HOOK_PREFIXES) or hook in {
            "init",
            "wp",
            "shutdown",
            "template_redirect",
            "safe_style_css",
            "the_content",
            "widgets_init",
        }

    def _is_comment_line(self, line: str) -> bool:
        stripped = line.strip()
        return stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*")

    def _iter_php_statements(self, content: str) -> Iterable[Tuple[int, str]]:
        buffer: List[str] = []
        start_line = 1
        depth = 0
        for line_no, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            if not buffer:
                start_line = line_no
            buffer.append(line)
            depth += line.count("(") + line.count("[") - line.count(")") - line.count("]")
            if stripped.endswith(";") or stripped.endswith("{") or stripped.endswith("}") or depth <= 0:
                statement = "\n".join(buffer)
                yield start_line, statement
                buffer = []
                depth = 0
        if buffer:
            yield start_line, "\n".join(buffer)

    def _has_sanitizer(self, text: str) -> bool:
        lower = text.lower()
        if re.search(r"\(\s*(?:int|float|bool|string|array)\s*\)", lower):
            return True
        return any(token in lower for token in SANITIZERS)

    def _has_validator(self, text: str) -> bool:
        lower = text.lower()
        return any(token in lower for token in VALIDATORS)

    def _window(self, content: str, pos: int, before: int = 300, after: int = 500) -> str:
        return content[max(0, pos - before): min(len(content), pos + after)]

    def _extract_braced_block(self, content: str, brace_pos: int) -> str:
        if brace_pos < 0 or brace_pos >= len(content) or content[brace_pos] != "{":
            return ""

        depth = 0
        for index in range(brace_pos, len(content)):
            char = content[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return content[brace_pos + 1:index]
        return content[brace_pos + 1:]

    def _find_function_body(self, content: str, name: str) -> str:
        if not name:
            return ""
        pattern = re.compile(
            rf"(?:public|private|protected|static|\s)*function\s+{re.escape(name)}\s*\([^)]*\)\s*\{{",
            re.IGNORECASE,
        )
        match = pattern.search(content)
        if not match:
            return ""
        brace_pos = content.find("{", match.start())
        return self._extract_braced_block(content, brace_pos)

    def _parse_callback_name(self, callback_expr: str) -> str:
        callback_expr = callback_expr.strip()
        patterns = [
            r"array\s*\(\s*\$this\s*,\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s*\)",
            r"\[\s*\$this\s*,\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s*\]",
            r"array\s*\(\s*__CLASS__\s*,\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s*\)",
            r"\[\s*__CLASS__\s*,\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s*\]",
            r"['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]",
        ]
        for pattern in patterns:
            match = re.search(pattern, callback_expr)
            if match:
                return match.group(1)
        return ""

    def _split_top_level_args(self, text: str, limit: int = 3) -> List[str]:
        args: List[str] = []
        current: List[str] = []
        depth = 0
        quote = ""
        escape = False
        for char in text:
            if quote:
                current.append(char)
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == quote:
                    quote = ""
                continue
            if char in {"'", '"'}:
                quote = char
                current.append(char)
                continue
            if char in "([{":
                depth += 1
            elif char in ")]}":
                depth -= 1
            if char == "," and depth == 0:
                args.append("".join(current).strip())
                current = []
                if len(args) >= limit:
                    break
                continue
            current.append(char)
        if current:
            args.append("".join(current).strip())
        return args

    def _iter_add_action_calls(self, content: str) -> Iterable[Tuple[re.Match, List[str]]]:
        for match in re.finditer(r"\badd_action\s*\(", content):
            start = match.end()
            depth = 1
            quote = ""
            escape = False
            for index in range(start, len(content)):
                char = content[index]
                if quote:
                    if escape:
                        escape = False
                    elif char == "\\":
                        escape = True
                    elif char == quote:
                        quote = ""
                    continue
                if char in {"'", '"'}:
                    quote = char
                    continue
                if char == "(":
                    depth += 1
                elif char == ")":
                    depth -= 1
                    if depth == 0:
                        yield match, self._split_top_level_args(content[start:index])
                        break

    def _check_cross_file_prefixing(self, php_files: Sequence[Path], js_files: Sequence[Path]) -> None:
        self._mark_applicable("wp_standards_prefixing", "settings_prefixing", "wp_standards_hooks")

        for php in php_files:
            content = self._read_file(php)
            rel = self._rel(php)
            has_namespace = bool(re.search(r"^\s*namespace\s+[A-Za-z0-9_\\]+", content, re.MULTILINE))

            for match in re.finditer(r"^function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", content, re.MULTILINE):
                name = match.group(1)
                if name.startswith("__") or self._is_prefixed(name):
                    continue
                self._add(
                    IssueSeverity.MEDIUM,
                    IssueCategory.WP_STANDARDS,
                    "Unprefixed global function",
                    f"Global function '{name}' does not appear to use the plugin prefix.",
                    rel,
                    self._line_number(content, match.start()),
                    match.group(0),
                    "Prefix global functions or place code inside a plugin namespace/class.",
                    "wp_standards_prefixing",
                )

            if not has_namespace:
                for match in re.finditer(r"^\s*(?:final\s+|abstract\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)\b", content, re.MULTILINE):
                    name = match.group(1)
                    if name.startswith("WC_") or name.startswith("WP_") or self._is_prefixed(name):
                        continue
                    self._add(
                        IssueSeverity.MEDIUM,
                        IssueCategory.WP_STANDARDS,
                        "Unprefixed global class",
                        f"Class '{name}' is in the global namespace without an obvious plugin prefix.",
                        rel,
                        self._line_number(content, match.start()),
                        match.group(0),
                        "Prefix global class names or declare a plugin namespace.",
                        "wp_standards_prefixing",
                    )

            for match in re.finditer(r"\b(?:add|update|get|delete)_option\s*\(\s*['\"]([A-Za-z0-9_\-]+)['\"]", content):
                option_name = match.group(1)
                if option_name in CORE_OPTION_NAMES or self._is_prefixed(option_name):
                    continue
                self._add(
                    IssueSeverity.MEDIUM,
                    IssueCategory.WP_SETTINGS,
                    "Potentially unprefixed option name",
                    f"Option '{option_name}' lacks an obvious plugin-specific prefix.",
                    rel,
                    self._line_number(content, match.start()),
                    match.group(0)[:120],
                    "Use a plugin-prefixed option name to avoid collisions.",
                    "settings_prefixing",
                )

            for match in re.finditer(r"\badd_shortcode\s*\(\s*['\"]([A-Za-z0-9_\-]+)['\"]", content):
                shortcode = match.group(1)
                if self._is_prefixed(shortcode):
                    continue
                self._add(
                    IssueSeverity.MEDIUM,
                    IssueCategory.WP_STANDARDS,
                    "Unprefixed shortcode",
                    f"Shortcode '{shortcode}' is not plugin-prefixed.",
                    rel,
                    self._line_number(content, match.start()),
                    match.group(0),
                    "Prefix shortcode names to avoid conflicts with other plugins/themes.",
                    "wp_standards_prefixing",
                )

            for match in re.finditer(r"\b(?:do_action|apply_filters)\s*\(\s*['\"]([A-Za-z0-9_\-\/]+)['\"]", content):
                hook = match.group(1)
                if self._is_probably_core_hook(hook) or self._is_prefixed(hook):
                    continue
                self._add(
                    IssueSeverity.LOW,
                    IssueCategory.WP_STANDARDS,
                    "Possibly unprefixed custom hook",
                    f"Custom hook/filter '{hook}' does not appear to use the plugin prefix.",
                    rel,
                    self._line_number(content, match.start()),
                    match.group(0),
                    "Prefix public custom hooks and filters to prevent collisions.",
                    "wp_standards_hooks",
                )

        for js in js_files:
            content = self._read_file(js)
            rel = self._rel(js)
            if re.search(r"/wp-admin/admin-ajax\.php", content):
                self._add(
                    IssueSeverity.MEDIUM,
                    IssueCategory.WP_AJAX,
                    "Hardcoded admin-ajax.php URL",
                    "AJAX URLs should be passed through localized script data, not hardcoded.",
                    rel,
                    None,
                    None,
                    "Pass admin_url('admin-ajax.php') via wp_localize_script() or wp_add_inline_script().",
                    "ajax_localization",
                )

    def _check_bootstrap_loading(self, php_files: Sequence[Path]) -> None:
        self._mark_applicable("wp_standards_dependencies", "defensive_integration_checks")
        if not self.metadata or not self.metadata.woo_compatible:
            return

        has_dependency_header = any(
            plugin.lower() == "woocommerce" for plugin in self.metadata.requires_plugins
        )
        bootstrap_files = [
            path for path in php_files
            if path.parent == self.plugin_root or (self.metadata and path.name == self.metadata.main_file)
        ]
        for path in bootstrap_files:
            content = self._read_file(path)
            rel = self._rel(path)
            uses_woo = re.search(r"\b(?:wc_get_|WC_|WooCommerce|woocommerce_)", content)
            has_guard = (
                "class_exists('WooCommerce')" in content
                or 'class_exists("WooCommerce")' in content
                or "woocommerce_loaded" in content
                or has_dependency_header
            )
            if uses_woo and not has_guard:
                self._add(
                    IssueSeverity.HIGH,
                    IssueCategory.WP_STANDARDS,
                    "Missing WooCommerce loading guard",
                    "Bootstrap code references WooCommerce APIs without a dependency header or runtime guard.",
                    rel,
                    None,
                    None,
                    "Load WooCommerce integrations after WooCommerce is available or declare Requires Plugins: woocommerce.",
                    "wp_standards_dependencies",
                )

    def _check_activation_deactivation(self, php_files: Sequence[Path]) -> None:
        self._mark_applicable("wp_standards_activation")
        saw_activation = False
        saw_deactivation = False

        for path in php_files:
            content = self._read_file(path)
            rel = self._rel(path)
            for match in re.finditer(r"\bregister_activation_hook\s*\(([^;]+)\);", content, re.DOTALL):
                saw_activation = True
                callback = self._parse_callback_name(match.group(1))
                body = self._find_function_body(content, callback)
                if not body:
                    body = self._window(content, match.start(), 0, 1200)
                if re.search(r"\b(?:WP_Query|get_posts|wc_get_products|wc_get_orders|foreach|wp_remote_|curl_)\b", body, re.IGNORECASE):
                    self._add(
                        IssueSeverity.HIGH,
                        IssueCategory.WP_STANDARDS,
                        "Heavy activation callback",
                        "Activation callbacks should only set lightweight defaults and schedule/defer heavy work.",
                        rel,
                        self._line_number(content, match.start()),
                        match.group(0)[:160],
                        "Move catalog scans, remote calls, and cache builds to a batched background job.",
                        "wp_standards_activation",
                    )

            for match in re.finditer(r"\bregister_deactivation_hook\s*\(([^;]+)\);", content, re.DOTALL):
                saw_deactivation = True
                callback = self._parse_callback_name(match.group(1))
                body = self._find_function_body(content, callback)
                if not body:
                    body = self._window(content, match.start(), 0, 1200)
                if re.search(r"\b(?:delete_option|DROP\s+TABLE|delete_post_meta|delete_user_meta)\b", body, re.IGNORECASE):
                    self._add(
                        IssueSeverity.HIGH,
                        IssueCategory.WP_STANDARDS,
                        "Destructive deactivation callback",
                        "Deactivation should not delete saved settings, tables, or user data.",
                        rel,
                        self._line_number(content, match.start()),
                        match.group(0)[:160],
                        "Move permanent cleanup to uninstall.php or register_uninstall_hook().",
                        "wp_standards_activation",
                    )

        if not saw_activation and not saw_deactivation:
            self.not_applicable_checks.add("wp_standards_activation")

    def _check_php_security(self, content: str, rel: str) -> None:
        self._mark_applicable(
            "wp_security_sanitization",
            "wp_security_secrets",
        )

        for line_no, statement in self._iter_php_statements(content):
            if "$_" not in statement:
                continue
            if "phpcs:ignore WordPress.Security.ValidatedSanitizedInput" in statement:
                continue
            if not re.search(r"\$_(?:POST|GET|REQUEST|FILES|SERVER|COOKIE)\b", statement):
                continue

            compact = " ".join(
                line.strip() for line in statement.splitlines()
                if line.strip() and not self._is_comment_line(line)
            )
            if not compact:
                continue
            if compact.startswith("unset("):
                continue
            if re.match(r"\$_(?:GET|REQUEST|POST)\s*\[[^\]]+\]\s*=", compact) and (
                self._has_sanitizer(compact)
                or re.search(r"=\s*(?:'[^']*'|\"[^\"]*\"|\(string\)\s*\$[A-Za-z_][A-Za-z0-9_]*|\$[A-Za-z_][A-Za-z0-9_]*)\s*;", compact)
            ):
                continue

            guard_only = (
                re.search(r"\b(?:isset|empty|array_key_exists|is_scalar|is_array|is_string)\s*\(", compact)
                and not re.search(r"\b(?:update_|insert_|delete_|add_option|wp_insert_|file_put_contents|fwrite)\b", compact)
                and not re.search(r"=\s*\$_(?:POST|GET|REQUEST|FILES|COOKIE|SERVER)\b", compact)
            )
            if guard_only and "foreach" not in compact:
                continue

            line_has_unslash = "wp_unslash" in compact or "$_SERVER" in compact
            safe_boundary = (
                (line_has_unslash and (self._has_sanitizer(compact) or self._has_validator(compact)))
                or "wp_verify_nonce" in compact
                or "check_ajax_referer" in compact
                or "filter_input" in compact
                or re.search(r"\b[A-Za-z0-9_]*(?:sanitize|normalize|request_has_filters|query_values|get_filters_query|get_first_non_empty_query)\w*\s*\([^)]*\$_", compact)
            )
            if safe_boundary:
                continue

            if re.search(r"\bforeach\s*\(\s*(?:\$_(?:POST|GET|REQUEST|FILES|COOKIE)|array_keys\s*\(\s*\$_(?:POST|GET|REQUEST|FILES|COOKIE)\s*\))", compact):
                self._add(
                    IssueSeverity.MEDIUM,
                    IssueCategory.WP_SECURITY,
                    "Request array iteration needs allowlist",
                    "Iterating over a whole request array requires per-key allowlisting and per-value sanitization.",
                    rel,
                    line_no,
                    compact[:180],
                    "Allowlist expected keys, wp_unslash each value, sanitize by expected type, and reject unknown input.",
                    "wp_security_sanitization",
                )
                continue

            severity = IssueSeverity.HIGH if re.search(r"=\s*\$_|update_|insert_|delete_", compact) else IssueSeverity.MEDIUM
            self._add(
                severity,
                IssueCategory.WP_SECURITY,
                "Unsanitized request input",
                "Request data is read without an obvious wp_unslash() plus sanitizer/validator boundary on the same line.",
                rel,
                line_no,
                compact[:180],
                "Use wp_unslash(), sanitize/validate by expected type, and only read expected request keys.",
                "wp_security_sanitization",
            )

        for match in re.finditer(r"\beval\s*\(", content):
            self._add(
                IssueSeverity.CRITICAL,
                IssueCategory.RELEASE_READINESS,
                "Arbitrary code execution via eval()",
                "eval() must not be used in WordPress plugin code.",
                rel,
                self._line_number(content, match.start()),
                "eval(...)",
                "Remove eval() and use explicit parser/dispatch logic instead.",
                "release_no_eval_settings",
            )

        secret_pattern = re.compile(
            r"\$[A-Za-z0-9_]*(?:secret|token|api_key|apikey|password)[A-Za-z0-9_]*\s*=\s*['\"][A-Za-z0-9_\-]{24,}['\"]",
            re.IGNORECASE,
        )
        for match in secret_pattern.finditer(content):
            self._add(
                IssueSeverity.HIGH,
                IssueCategory.WP_SECURITY,
                "Possible hardcoded secret",
                "Secret-looking tokens or credentials should not be committed to plugin source.",
                rel,
                self._line_number(content, match.start()),
                match.group(0)[:120],
                "Move secrets to user-configured settings, environment configuration, or external setup steps.",
                "wp_security_secrets",
            )

    def _check_php_defensive(self, content: str, rel: str) -> None:
        self._mark_applicable(
            "defensive_array_guards",
            "defensive_invalid_types",
            "defensive_null_checks",
            "defensive_undefined_indexes",
            "defensive_wp_error",
        )

        guarded_returns = [
            (r"wc_get_product\s*\([^)]+\)\s*->", "wc_get_product() can return false", "defensive_woo_objects"),
            (r"wc_get_order\s*\([^)]+\)\s*->", "wc_get_order() can return false", "defensive_woo_objects"),
            (r"wc_get_customer\s*\([^)]+\)\s*->", "wc_get_customer() can return false", "defensive_woo_objects"),
            (r"get_post\s*\([^)]+\)\s*->", "get_post() can return null", "defensive_null_checks"),
            (r"get_term\s*\([^)]+\)\s*->", "get_term() can return null or WP_Error", "defensive_null_checks"),
            (r"get_user_by\s*\([^)]+\)\s*->", "get_user_by() can return false", "defensive_null_checks"),
        ]
        for pattern, message, check_id in guarded_returns:
            for match in re.finditer(pattern, content):
                context = self._window(content, match.start(), 220, 40)
                if re.search(r"\b(?:if|empty|is_a|instanceof|is_wp_error)\b", context):
                    continue
                self._add(
                    IssueSeverity.HIGH,
                    IssueCategory.DEFENSIVE_CODING,
                    "Unguarded API return value",
                    message + "; guard the result before dereferencing it.",
                    rel,
                    self._line_number(content, match.start()),
                    match.group(0),
                    "Assign the return value to a variable, check false/null/WP_Error, then call methods.",
                    check_id,
                )

        wp_error_calls = ["wp_remote_get", "wp_remote_post", "wp_remote_request", "get_term", "wp_insert_post", "wp_update_post", "media_handle_upload"]
        for call in wp_error_calls:
            if call not in content:
                continue
            self._mark_applicable("defensive_wp_error")
            for match in re.finditer(rf"\b{call}\s*\(", content):
                context = self._window(content, match.start(), 400, 800)
                if "is_wp_error" in context:
                    continue
                self._add(
                    IssueSeverity.MEDIUM,
                    IssueCategory.DEFENSIVE_CODING,
                    "Possible missing WP_Error check",
                    f"{call}() may return WP_Error and should be checked before use.",
                    rel,
                    self._line_number(content, match.start()),
                    match.group(0),
                    "Check is_wp_error() and handle the failure before continuing.",
                    "defensive_wp_error",
                )

        for match in re.finditer(r"array_merge\s*\(\s*(?!\(array\))\$([A-Za-z_][A-Za-z0-9_]*)\b", content):
            var_name = match.group(1)
            if var_name in {"args", "defaults", "options", "settings", "styles", "links", "sections"}:
                continue
            context = self._window(content, match.start(), 350, 80)
            if (
                re.search(rf"function\s*\([^)]*\${re.escape(var_name)}\b", context)
                or re.search(rf"function\s+[A-Za-z_][A-Za-z0-9_]*\s*\([^)]*\${re.escape(var_name)}\b", context)
                or re.search(rf"is_array\s*\(\s*\${re.escape(var_name)}\s*\)", context)
                or re.search(rf"\(array\)\s*\${re.escape(var_name)}", context)
                or re.search(rf"\${re.escape(var_name)}\s*=\s*array\s*\(", context)
                or re.search(rf"\${re.escape(var_name)}\s*=\s*\[", context)
            ):
                continue
            origin_context = self._window(content, match.start(), 900, 80)
            if not re.search(
                rf"\${re.escape(var_name)}\s*=.*(?:get_option|get_post_meta|get_user_meta|get_term_meta|\$_(?:POST|GET|REQUEST)|json_decode)",
                origin_context,
                re.IGNORECASE | re.DOTALL,
            ):
                continue
            self._add(
                IssueSeverity.MEDIUM,
                IssueCategory.DEFENSIVE_CODING,
                "Unguarded array_merge operation",
                f"array_merge() receives ${var_name} without a nearby array guard or cast.",
                rel,
                self._line_number(content, match.start()),
                match.group(0),
                f"Cast ${var_name} to array or check is_array() before merging.",
                "defensive_invalid_types",
            )

        for match in re.finditer(r"\$_(?:POST|GET|REQUEST)\s*\[\s*['\"][A-Za-z0-9_\-]+['\"]\s*(?:==|!=|===|!==)", content):
            context = self._window(content, match.start(), 180, 80)
            if re.search(r"\b(?:isset|empty|array_key_exists)\s*\(", context):
                continue
            self._add(
                IssueSeverity.LOW,
                IssueCategory.DEFENSIVE_CODING,
                "Potential undefined request index",
                "Request array keys should be checked before direct comparisons.",
                rel,
                self._line_number(content, match.start()),
                match.group(0),
                "Guard request keys with isset() or array_key_exists() before comparison.",
                "defensive_undefined_indexes",
            )

    def _check_php_rest_ajax(self, content: str, rel: str) -> None:
        rest_matches = list(re.finditer(r"\bregister_rest_route\s*\(", content))
        if rest_matches:
            self._mark_applicable("rest_permission_callback", "rest_validation", "rest_data_leak", "wp_security_rest_auth")
        for match in rest_matches:
            block = self._window(content, match.start(), 0, 1600)
            if "permission_callback" not in block:
                self._add(
                    IssueSeverity.CRITICAL,
                    IssueCategory.WP_REST_API,
                    "REST route missing permission_callback",
                    "Every register_rest_route() endpoint must define permission_callback.",
                    rel,
                    self._line_number(content, match.start()),
                    block[:180].strip().replace("\n", " "),
                    "Add a permission_callback that checks capabilities or intentionally returns true for public read-only data.",
                    "rest_permission_callback",
                )
            elif "__return_true" in block and re.search(r"WP_REST_Server::(?:CREATABLE|EDITABLE|DELETABLE)|['\"]POST['\"]|['\"]PUT['\"]|['\"]DELETE['\"]", block):
                self._add(
                    IssueSeverity.HIGH,
                    IssueCategory.WP_REST_API,
                    "Public REST mutation endpoint",
                    "A state-changing REST route appears to use __return_true for permissions.",
                    rel,
                    self._line_number(content, match.start()),
                    block[:180].strip().replace("\n", " "),
                    "Require authentication/capability checks for mutating REST endpoints.",
                    "rest_permission_callback",
                )

            if "args" not in block and re.search(r"WP_REST_Server::(?:CREATABLE|EDITABLE|DELETABLE)|['\"]POST['\"]|['\"]PUT['\"]|['\"]DELETE['\"]", block):
                self._add(
                    IssueSeverity.MEDIUM,
                    IssueCategory.WP_REST_API,
                    "REST route lacks argument schema",
                    "Mutating REST routes should declare args with sanitize_callback and validate_callback.",
                    rel,
                    self._line_number(content, match.start()),
                    block[:180].strip().replace("\n", " "),
                    "Define REST args with type, required, sanitize_callback, and validate_callback.",
                    "rest_validation",
                )

            if "__return_true" in block and re.search(r"\b(?:get_option|get_user|wc_get_order|license|token|secret|path)\b", block, re.IGNORECASE):
                self._add(
                    IssueSeverity.HIGH,
                    IssueCategory.WP_REST_API,
                    "Potential public REST data leak",
                    "Public REST routes should not expose private options, users, orders, paths, tokens, or license data.",
                    rel,
                    self._line_number(content, match.start()),
                    block[:180].strip().replace("\n", " "),
                    "Restrict permissions and explicitly shape the public response.",
                    "rest_data_leak",
                )

        ajax_actions = list(self._iter_add_action_calls(content))
        for match, args in ajax_actions:
            if not args:
                continue
            hook = args[0].strip().strip("'\"")
            if not hook.startswith("wp_ajax"):
                continue
            self._mark_applicable("ajax_prefixing", "ajax_security", "wp_security_ajax_auth", "wp_security_capabilities", "wp_security_nonces")
            action_name = hook.replace("wp_ajax_nopriv_", "").replace("wp_ajax_", "")
            is_public = hook.startswith("wp_ajax_nopriv_")
            if not self._is_prefixed(action_name):
                self._add(
                    IssueSeverity.MEDIUM,
                    IssueCategory.WP_AJAX,
                    "Unprefixed AJAX action",
                    f"AJAX action '{action_name}' is not plugin-prefixed.",
                    rel,
                    self._line_number(content, match.start()),
                    hook,
                    "Prefix AJAX action names with the plugin prefix.",
                    "ajax_prefixing",
                )

            callback = self._parse_callback_name(args[1]) if len(args) > 1 else ""
            body = self._find_function_body(content, callback)
            if not body:
                body = self._window(content, match.start(), 0, 1400)

            mutates = bool(STATE_CHANGE_PATTERNS.search(body))
            if mutates and "check_ajax_referer" not in body and "wp_verify_nonce" not in body:
                self._add(
                    IssueSeverity.HIGH,
                    IssueCategory.WP_AJAX,
                    "AJAX handler lacks nonce verification",
                    "State-changing AJAX handlers must verify a nonce to prevent CSRF.",
                    rel,
                    self._line_number(content, match.start()),
                    hook,
                    "Verify nonces in the handler with check_ajax_referer() or wp_verify_nonce().",
                    "ajax_security",
                )
            if mutates and not is_public and "current_user_can" not in body:
                self._add(
                    IssueSeverity.HIGH,
                    IssueCategory.WP_SECURITY,
                    "AJAX handler lacks capability check",
                    "Privileged AJAX handlers must check current_user_can() before state changes.",
                    rel,
                    self._line_number(content, match.start()),
                    hook,
                    "Add a capability check matching the operation before changing data.",
                    "wp_security_capabilities",
                )
            if "wp_send_json" not in body and "wp_die" not in body and "die(" not in body:
                self._add(
                    IssueSeverity.LOW,
                    IssueCategory.WP_AJAX,
                    "AJAX handler response not explicit",
                    "AJAX handlers should terminate with wp_send_json_success/error() or wp_die().",
                    rel,
                    self._line_number(content, match.start()),
                    hook,
                    "Return responses with wp_send_json_success() / wp_send_json_error() and status codes where useful.",
                    "ajax_security",
                )

        for match in re.finditer(r"\b(?:wp_localize_script|wp_add_inline_script)\s*\(", content):
            self._mark_applicable("ajax_localization")
            break

    def _check_php_database(self, content: str, rel: str) -> None:
        if "$wpdb" in content:
            self._mark_applicable("db_prepared_sql")
        for match in re.finditer(r"\$wpdb->(?:query|get_results|get_row|get_var|get_col)\s*\((.*?)\)", content, re.DOTALL):
            expression = match.group(1)
            if "$" in expression and "prepare" not in expression:
                self._add(
                    IssueSeverity.CRITICAL,
                    IssueCategory.WP_DATABASE,
                    "Unprepared database query",
                    "Dynamic database queries must use $wpdb->prepare().",
                    rel,
                    self._line_number(content, match.start()),
                    match.group(0)[:180].strip().replace("\n", " "),
                    "Use $wpdb->prepare() and allowlist dynamic fragments.",
                    "db_prepared_sql",
                )

        if re.search(r"\bCREATE\s+TABLE\b", content, re.IGNORECASE):
            self._mark_applicable("db_custom_tables")
            if "dbDelta" not in content:
                self._add(
                    IssueSeverity.MEDIUM,
                    IssueCategory.WP_DATABASE,
                    "CREATE TABLE without dbDelta()",
                    "Custom table creation should use dbDelta() and schema versioning.",
                    rel,
                    None,
                    None,
                    "Use dbDelta() and store a plugin-prefixed DB schema version option.",
                    "db_custom_tables",
                )
            if not re.search(r"(?:db|schema)_version|version", content, re.IGNORECASE):
                self._add(
                    IssueSeverity.LOW,
                    IssueCategory.WP_DATABASE,
                    "Custom table schema version unclear",
                    "Custom tables should have an explicit schema version for incremental migrations.",
                    rel,
                    None,
                    None,
                    "Store a plugin-prefixed database schema version option and run idempotent migrations.",
                    "db_custom_tables",
                )

        for match in re.finditer(
            r"['\"](?:posts_per_page|numberposts|limit)['\"]\s*=>\s*-1|\b(?:posts_per_page|numberposts|limit)\s*=\s*-1",
            content,
        ):
            self._add(
                IssueSeverity.HIGH,
                IssueCategory.WP_DATABASE,
                "Unbounded query limit",
                "Unbounded queries can fail on large stores and should be batched or paginated.",
                rel,
                self._line_number(content, match.start()),
                match.group(0),
                "Use explicit limits, pagination, seek iteration, Action Scheduler, or WP-CLI jobs.",
                "db_unbounded_queries",
            )

    def _check_php_filesystem(self, content: str, rel: str) -> None:
        if re.search(r"\b(?:file_put_contents|fwrite|fopen|unlink|rename|copy|mkdir|rmdir)\s*\(", content):
            self._mark_applicable("fs_api_usage")
            if "WP_Filesystem" not in content and "wp_filesystem" not in content.lower():
                self._add(
                    IssueSeverity.MEDIUM,
                    IssueCategory.WP_FILESYSTEM,
                    "Direct filesystem write",
                    "Filesystem writes should use WP Filesystem APIs where credentials/transports may matter.",
                    rel,
                    None,
                    None,
                    "Use WP_Filesystem for writes or document why direct writes are safe for plugin-owned temp paths.",
                    "fs_api_usage",
                )

        if "$_FILES" in content or "wp_handle_upload" in content:
            self._mark_applicable("fs_upload_security")
            if not re.search(r"\b(?:wp_check_filetype|wp_handle_upload|sanitize_file_name|wp_verify_nonce|check_admin_referer)\b", content):
                self._add(
                    IssueSeverity.HIGH,
                    IssueCategory.WP_FILESYSTEM,
                    "Upload handling lacks validation",
                    "Upload handlers need nonce/capability checks plus file type, extension, size, and filename validation.",
                    rel,
                    None,
                    None,
                    "Use WP upload APIs, validate MIME/extension/size, sanitize filenames, and reject unsafe archives/executables.",
                    "fs_upload_security",
                )

        if re.search(r"\$_(?:POST|GET|REQUEST|FILES).{0,120}(?:file|path|dir|unlink|fopen|file_put_contents)", content, re.DOTALL):
            self._mark_applicable("fs_path_traversal", "wp_security_path_traversal")
            if not re.search(r"\b(?:realpath|validate_file|wp_normalize_path|sanitize_file_name)\b", content):
                self._add(
                    IssueSeverity.HIGH,
                    IssueCategory.WP_FILESYSTEM,
                    "Request-controlled filesystem path",
                    "Filesystem paths derived from request data must be normalized and checked against an allowlist.",
                    rel,
                    None,
                    None,
                    "Normalize with realpath()/wp_normalize_path(), use validate_file(), and enforce plugin-owned directories.",
                    "fs_path_traversal",
                )

        if re.search(r"\b(?:tempnam|wp_tempnam)\s*\(", content):
            self._mark_applicable("fs_temp_cleanup")
            if "unlink" not in content:
                self._add(
                    IssueSeverity.LOW,
                    IssueCategory.WP_FILESYSTEM,
                    "Temporary file cleanup unclear",
                    "Temporary files should be deleted after imports/exports complete or fail.",
                    rel,
                    None,
                    None,
                    "Delete temp files in success and failure paths.",
                    "fs_temp_cleanup",
                )

    def _check_php_woo(self, content: str, rel: str) -> None:
        if not self.metadata or not self.metadata.woo_compatible:
            return

        if re.search(r"\b(?:wc_get_order|WC_Order|shop_order|checkout|cart|wc_get_product|WC_Product)", content):
            self._mark_applicable("woo_crud_usage", "woo_hpos_compatibility", "woo_checkout_compatibility", "woo_object_safety")

        if re.search(r"(?:wp_posts|post_type).{0,120}shop_order|shop_order.{0,120}(?:wp_posts|post_type)", content, re.IGNORECASE | re.DOTALL):
            self._add(
                IssueSeverity.HIGH,
                IssueCategory.WOO_COMPATIBILITY,
                "Direct order post query",
                "Direct shop_order queries are not HPOS-safe.",
                rel,
                None,
                None,
                "Use wc_get_orders() or WC_Order_Query for orders.",
                "woo_crud_usage",
            )

        if re.search(r"\b(?:wc_get_order|WC_Order|shop_order)\b", content):
            if "custom_order_tables" not in content and "FeaturesUtil::declare_compatibility" not in content:
                self._add(
                    IssueSeverity.MEDIUM,
                    IssueCategory.WOO_COMPATIBILITY,
                    "HPOS compatibility declaration missing near order usage",
                    "Plugins that work with orders should declare HPOS compatibility after verifying the order code path.",
                    rel,
                    None,
                    None,
                    "Declare compatibility with Automattic\\WooCommerce\\Utilities\\FeaturesUtil for custom_order_tables after real verification.",
                    "woo_hpos_compatibility",
                )

        if re.search(r"\b(?:checkout|woocommerce_checkout|woocommerce_after_checkout|woocommerce_before_checkout)\b", content, re.IGNORECASE):
            if "woocommerce_blocks" not in content.lower() and "store_api" not in content.lower() and "cart-checkout-block" not in content.lower():
                self._woo_checkout_needs_review = True

    def _check_php_i18n(self, content: str, rel: str) -> None:
        if re.search(r"\b(?:__|_e|esc_html__|esc_attr__|esc_html_e|esc_attr_e|_x)\s*\(", content):
            self._mark_applicable("i18n_literal_gettext", "i18n_text_domain", "i18n_escaped_output")

        gettext_pattern = re.compile(r"\b(?:__|_e|_x|esc_html__|esc_html_e|esc_attr__|esc_attr_e)\s*\(\s*([^,\)]+)")
        for match in gettext_pattern.finditer(content):
            first_arg = match.group(1).strip()
            if not (first_arg.startswith("'") or first_arg.startswith('"')):
                self._add(
                    IssueSeverity.MEDIUM,
                    IssueCategory.ACCESSIBILITY_I18N,
                    "Non-literal gettext string",
                    "Translation tools require literal gettext strings.",
                    rel,
                    self._line_number(content, match.start()),
                    match.group(0)[:120],
                    "Pass literal strings to gettext functions.",
                    "i18n_literal_gettext",
                )

        for match in re.finditer(r"\b_e\s*\(", content):
            self._add(
                IssueSeverity.LOW,
                IssueCategory.ACCESSIBILITY_I18N,
                "Unescaped translated output",
                "_e() echoes output directly. Prefer escaped translation helpers for UI output.",
                rel,
                self._line_number(content, match.start()),
                match.group(0),
                "Use esc_html_e(), esc_attr_e(), or echo esc_html__(...).",
                "i18n_escaped_output",
            )

    def _check_php_accessibility(self, content: str, rel: str) -> None:
        if re.search(r"<(?:button|a|input|select|textarea|div|span)", content, re.IGNORECASE):
            self._mark_applicable("a11y_keyboard", "a11y_structure")

        for match in re.finditer(r"<(?:div|span|li)\b[^>]*(?:onclick=|role=['\"]button['\"])[^>]*>", content, re.IGNORECASE):
            tag = match.group(0)
            if "tabindex" in tag and ("keydown" in tag or "keyup" in tag):
                continue
            self._add(
                IssueSeverity.LOW,
                IssueCategory.ACCESSIBILITY_I18N,
                "Non-semantic interactive element",
                "Clickable non-button elements need keyboard support and accessible semantics.",
                rel,
                self._line_number(content, match.start()),
                tag[:160],
                "Use <button> for actions or add role, tabindex, and keyboard handlers.",
                "a11y_keyboard",
            )

        for match in re.finditer(r"<a\b[^>]*href=['\"]#['\"][^>]*>", content, re.IGNORECASE):
            self._add(
                IssueSeverity.LOW,
                IssueCategory.ACCESSIBILITY_I18N,
                "Anchor used as button",
                "Links with href=\"#\" used for actions can be inaccessible and break expected navigation.",
                rel,
                self._line_number(content, match.start()),
                match.group(0)[:160],
                "Use <button type=\"button\"> for actions and real links for navigation.",
                "a11y_structure",
            )

    def _check_php_performance(self, content: str, rel: str) -> None:
        self._mark_applicable("perf_queries_in_loops", "perf_transient_caching", "perf_enqueue_screens", "perf_autoload")

        for match in QUERY_IN_LOOP_PATTERN.finditer(content):
            snippet = match.group(0)[:180].strip().replace("\n", " ")
            self._add(
                IssueSeverity.HIGH,
                IssueCategory.WP_PERFORMANCE,
                "Database/API query inside loop",
                "Queries inside loops cause N+1 behavior and degrade large stores.",
                rel,
                self._line_number(content, match.start()),
                snippet,
                "Batch load data, prime caches, or move work to a single query.",
                "perf_queries_in_loops",
            )

        if re.search(r"add_action\s*\(\s*['\"]init['\"]", content) and re.search(r"\b(?:WP_Query|get_posts|wc_get_products|wc_get_orders|\$wpdb->)", content):
            self._add(
                IssueSeverity.MEDIUM,
                IssueCategory.WP_PERFORMANCE,
                "Query work attached to init",
                "Heavy queries on init can run on every request.",
                rel,
                None,
                None,
                "Move work to targeted screens, request-specific hooks, cached lookups, CLI, or scheduled jobs.",
                "perf_queries_in_loops",
            )

        for match in re.finditer(r"\badd_option\s*\([^)]*,[^)]*,[^)]*,\s*['\"]yes['\"]", content, re.DOTALL):
            self._add(
                IssueSeverity.MEDIUM,
                IssueCategory.WP_PERFORMANCE,
                "Autoloaded option",
                "Large caches, logs, generated data, or remote payloads should not autoload.",
                rel,
                self._line_number(content, match.start()),
                match.group(0)[:140].strip().replace("\n", " "),
                "Set autoload to false/no for large options.",
                "perf_autoload",
            )

        if "admin_enqueue_scripts" in content:
            for match, args in self._iter_add_action_calls(content):
                if not args or args[0].strip().strip("'\"") != "admin_enqueue_scripts":
                    continue
                callback = self._parse_callback_name(args[1]) if len(args) > 1 else ""
                body = self._find_function_body(content, callback)
                if body and "get_current_screen" not in body and "$hook" not in body:
                    self._add(
                        IssueSeverity.LOW,
                        IssueCategory.WP_PERFORMANCE,
                        "Admin assets not screen-limited",
                        "Admin assets should only enqueue on relevant plugin/WooCommerce screens.",
                        rel,
                        self._line_number(content, match.start()),
                        args[0],
                        "Use the $hook parameter or get_current_screen() to target plugin screens.",
                        "perf_enqueue_screens",
                    )

    def _check_php_admin_notices(self, content: str, rel: str) -> None:
        notice_hooks = [
            (match, args) for match, args in self._iter_add_action_calls(content)
            if args and args[0].strip().strip("'\"") in {"admin_notices", "network_admin_notices", "all_admin_notices"}
        ]
        if not notice_hooks:
            return

        self._mark_applicable("admin_notices_caps", "admin_notices_dismissal", "admin_notices_global", "admin_notices_nags")
        for match, args in notice_hooks:
            callback = self._parse_callback_name(args[1]) if len(args) > 1 else ""
            body = self._find_function_body(content, callback) or self._window(content, match.start(), 0, 1400)
            if "current_user_can" not in body:
                self._add(
                    IssueSeverity.MEDIUM,
                    IssueCategory.WP_ADMIN_NOTICES,
                    "Admin notice capability check missing",
                    "Privileged notices should only render for users who can act on them.",
                    rel,
                    self._line_number(content, match.start()),
                    args[0],
                    "Check current_user_can() before rendering admin notices with actions or settings links.",
                    "admin_notices_caps",
                )
            if "get_current_screen" not in body:
                self._add(
                    IssueSeverity.LOW,
                    IssueCategory.WP_ADMIN_NOTICES,
                    "Global admin notice",
                    "Admin notices should be limited to relevant plugin/admin screens where possible.",
                    rel,
                    self._line_number(content, match.start()),
                    args[0],
                    "Use get_current_screen() or a plugin page condition to avoid global noise.",
                    "admin_notices_global",
                )
            if re.search(r"\b(?:rate|review|upgrade|pricing|pro|discount|offer)\b", body, re.IGNORECASE):
                self._add(
                    IssueSeverity.LOW,
                    IssueCategory.WP_ADMIN_NOTICES,
                    "Potential promotional admin notice",
                    "Marketing/review/upgrade notices should be intentional, dismissible, and not globally noisy.",
                    rel,
                    self._line_number(content, match.start()),
                    args[0],
                    "Keep promotional notices scoped, dismissible, and consent-aware.",
                    "admin_notices_nags",
                )
            if "is-dismissible" in body and not re.search(r"\b(?:update_user_meta|add_user_meta|update_option|get_user_meta|get_option|set_transient)\b", body):
                self._add(
                    IssueSeverity.LOW,
                    IssueCategory.WP_ADMIN_NOTICES,
                    "Dismissible notice state not persisted",
                    "Dismissible notices should store dismissal state intentionally.",
                    rel,
                    self._line_number(content, match.start()),
                    args[0],
                    "Persist dismissals with plugin-prefixed user meta, options, or transients.",
                    "admin_notices_dismissal",
                )

    def _check_php_emails(self, content: str, rel: str) -> None:
        if re.search(r"\b(?:mail|wp_mail|WC_Email|woocommerce_email)\b", content):
            self._mark_applicable("emails_api", "emails_secrets", "emails_duplicates")

        for match in re.finditer(r"(?<!wp_)\bmail\s*\(", content):
            self._add(
                IssueSeverity.HIGH,
                IssueCategory.WP_EMAILS,
                "Raw PHP mail() call",
                "Use wp_mail() or WooCommerce email APIs instead of PHP mail().",
                rel,
                self._line_number(content, match.start()),
                "mail(...)",
                "Replace with wp_mail() or WooCommerce email hooks/templates.",
                "emails_api",
            )

        if "wp_mail" in content or "WC_Email" in content:
            if re.search(r"\b(?:password|secret|token|license|api[_-]?key|credentials)\b", content, re.IGNORECASE):
                self._add(
                    IssueSeverity.HIGH,
                    IssueCategory.WP_EMAILS,
                    "Sensitive data near email sending",
                    "Emails should not include secrets, passwords, license keys, or debug payloads.",
                    rel,
                    None,
                    None,
                    "Send links or non-sensitive status text instead of secrets or credentials.",
                    "emails_secrets",
                )
            if STATE_CHANGE_PATTERNS.search(content) and not re.search(r"\b(?:sent|lock|transient|meta|idempot)\b", content, re.IGNORECASE):
                self._add(
                    IssueSeverity.LOW,
                    IssueCategory.WP_EMAILS,
                    "Email idempotency unclear",
                    "Emails sent from retryable hooks or state changes should avoid duplicate sends.",
                    rel,
                    None,
                    None,
                    "Use sent flags, locks, or idempotency keys for retryable email paths.",
                    "emails_duplicates",
                )

    def _check_php_privacy(self, content: str, rel: str) -> None:
        personal_data_terms = r"\b(?:email|phone|address|customer|user_id|order_id|first_name|last_name|ip_address)\b"
        stores_personal = bool(re.search(personal_data_terms, content, re.IGNORECASE) and re.search(r"\b(?:update_option|update_post_meta|update_user_meta|insert|log|error_log)\b", content))
        if stores_personal:
            self._mark_applicable("privacy_policy", "privacy_exporter_eraser")
            if (
                "wp_add_privacy_policy_content" not in content
                or (
                    "wp_privacy_personal_data_exporters" not in content
                    and "wp_privacy_personal_data_erasers" not in content
                )
            ):
                self._privacy_needs_review = True

        for match in re.finditer(r"\berror_log\s*\([^;]*\$_(?:POST|GET|REQUEST|SERVER|COOKIE)", content, re.DOTALL):
            self._mark_applicable("privacy_logging")
            self._add(
                IssueSeverity.HIGH,
                IssueCategory.WP_PRIVACY,
                "Request data logged directly",
                "Logging raw request data can expose personal data or secrets.",
                rel,
                self._line_number(content, match.start()),
                match.group(0)[:160].strip().replace("\n", " "),
                "Log only non-sensitive, redacted diagnostic fields.",
                "privacy_logging",
            )

    def _check_php_multisite(self, content: str, rel: str) -> None:
        if re.search(r"\b(?:get_sites|wp_get_sites|switch_to_blog|restore_current_blog|network_admin_url)\b", content):
            self._mark_applicable("multisite_guards", "multisite_options", "multisite_loop_sites")

        if re.search(r"\b(?:get_sites|wp_get_sites|switch_to_blog)\b", content) and "is_multisite" not in content:
            self._add(
                IssueSeverity.MEDIUM,
                IssueCategory.WP_MULTISITE,
                "Multisite API use without guard",
                "Multisite-only APIs should be guarded by is_multisite().",
                rel,
                None,
                None,
                "Guard network-wide logic with is_multisite() and avoid normal-request site loops.",
                "multisite_guards",
            )

        if re.search(r"\bget_sites\s*\(", content) and not re.search(r"\b(?:number|fields|site__in)\b", content):
            self._add(
                IssueSeverity.MEDIUM,
                IssueCategory.WP_MULTISITE,
                "Unbounded multisite loop",
                "Looping all sites can be expensive and should be batched or limited.",
                rel,
                None,
                None,
                "Batch network-wide work and avoid site loops on normal requests.",
                "multisite_loop_sites",
            )

    def _check_js_standards(self, content: str, rel: str) -> None:
        if "jQuery" in content or "$(" in content:
            self._mark_applicable("wp_standards_hooks")

        for pattern, name in [
            (r"\.click\s*\(", ".click() shorthand"),
            (r"\.bind\s*\(", ".bind() shorthand"),
            (r"\.hover\s*\(", ".hover() shorthand"),
            (r"\.submit\s*\(", ".submit() shorthand"),
        ]:
            for match in re.finditer(pattern, content):
                self._add(
                    IssueSeverity.LOW,
                    IssueCategory.WP_STANDARDS,
                    f"jQuery {name} detected",
                    "Use delegated .on() handlers instead of obsolete jQuery shorthands.",
                    rel,
                    self._line_number(content, match.start()),
                    match.group(0),
                    "Use $(document).on(event, selector, handler) where delegation is appropriate.",
                    "wp_standards_hooks",
                )

        if "jQuery" in content and "use strict" not in content:
            self._add(
                IssueSeverity.LOW,
                IssueCategory.WP_STANDARDS,
                "Missing JavaScript strict mode",
                "Plugin JavaScript should use strict mode inside its wrapper.",
                rel,
                None,
                None,
                'Wrap plugin JavaScript in an IIFE and include "use strict";.',
                "wp_standards_hooks",
            )

    def _check_js_accessibility(self, content: str, rel: str) -> None:
        if re.search(r"\.on\s*\(\s*['\"]click|\.click\s*\(", content):
            self._mark_applicable("a11y_keyboard")

        for match in re.finditer(r"\$\(\s*['\"](?:div|span|li|i|img|section|article)[^'\"]*['\"]\s*\)\s*\.\s*(?:click|on\s*\(\s*['\"]click)", content):
            context = self._window(content, match.start(), 0, 300)
            if "keydown" in context or "keypress" in context or "tabindex" in context:
                continue
            self._add(
                IssueSeverity.LOW,
                IssueCategory.ACCESSIBILITY_I18N,
                "Click handler on non-interactive element",
                "Non-interactive elements need keyboard support or should be replaced with buttons/links.",
                rel,
                self._line_number(content, match.start()),
                match.group(0),
                "Bind actions to <button> elements or add keyboard/focus support.",
                "a11y_keyboard",
            )

    def _check_css_release(self, content: str, rel: str) -> None:
        self._mark_applicable("release_no_cdn")
        cdn_pattern = r"https?://(?:ajax\.googleapis|code\.jquery|cdn\.|cdnjs|maxcdn|unpkg|jsdelivr|fonts\.googleapis)"
        for match in re.finditer(cdn_pattern, content, re.IGNORECASE):
            self._add(
                IssueSeverity.HIGH,
                IssueCategory.RELEASE_READINESS,
                "CDN asset reference in CSS",
                "Release packages should not load assets from external CDNs.",
                rel,
                self._line_number(content, match.start()),
                match.group(0)[:120],
                "Bundle assets locally and enqueue local files.",
                "release_no_cdn",
            )

    def _check_plugin_header(self) -> None:
        self._mark_applicable("release_readme_version")
        if not self.metadata:
            return
        main_file = self.plugin_root / self.metadata.main_file
        if not main_file.exists():
            self._add(
                IssueSeverity.CRITICAL,
                IssueCategory.RELEASE_READINESS,
                "Main plugin file missing",
                f"Expected entry file {self.metadata.main_file} was not found at plugin root.",
                self.metadata.main_file,
                None,
                None,
                "Ensure the plugin root contains the main file with a WordPress plugin header.",
                "release_readme_version",
            )

    def _check_readme(self) -> None:
        self._mark_applicable("release_readme_version")
        readme = self.plugin_root / "readme.txt"
        if not readme.exists():
            self._add(
                IssueSeverity.MEDIUM,
                IssueCategory.RELEASE_READINESS,
                "Missing readme.txt",
                "WordPress.org-style releases need readme.txt metadata.",
                "readme.txt",
                None,
                None,
                "Add readme.txt with stable tag, changelog, requirements, and tested compatibility.",
                "release_readme_version",
            )
            return

        content = self._read_file(readme)
        match = re.search(r"^Stable tag:\s*(.+)$", content, re.MULTILINE | re.IGNORECASE)
        if not match:
            self._add(
                IssueSeverity.MEDIUM,
                IssueCategory.RELEASE_READINESS,
                "readme.txt missing Stable tag",
                "Stable tag should match the release version or trunk.",
                "readme.txt",
                None,
                None,
                "Add a Stable tag line.",
                "release_readme_version",
            )
        elif self.metadata and self.metadata.version and match.group(1).strip() != self.metadata.version:
            self._add(
                IssueSeverity.MEDIUM,
                IssueCategory.RELEASE_READINESS,
                "Stable tag/version mismatch",
                f"Plugin header Version '{self.metadata.version}' does not match Stable tag '{match.group(1).strip()}'.",
                "readme.txt",
                None,
                None,
                "Align readme.txt Stable tag with the plugin header version.",
                "release_readme_version",
            )

    def _check_release_artifacts(self) -> None:
        self._mark_applicable("release_no_dev_artifacts", "release_no_bundled_core")
        artifact_suffixes = (".bak", ".tmp", ".log", ".zip", ".orig", ".old", "~")
        for path in self.plugin_root.rglob("*"):
            if self._is_hidden_or_dot(path):
                continue
            rel_parts = set(part.lower() for part in self._safe_relative_parts(path))
            if rel_parts & {"vendor", "node_modules"}:
                continue
            if path.is_file() and (path.name.endswith(artifact_suffixes) or path.suffix == ".map"):
                self._add(
                    IssueSeverity.MEDIUM,
                    IssueCategory.RELEASE_READINESS,
                    f"Development artifact present: {path.name}",
                    "Release packages should exclude backups, logs, archives, source maps, and temp files.",
                    self._rel(path),
                    None,
                    None,
                    "Remove or exclude this file from the release package.",
                    "release_no_dev_artifacts",
                )

        for name in [".env", "debug.log", "node_modules"]:
            if (self.plugin_root / name).exists():
                self._add(
                    IssueSeverity.HIGH,
                    IssueCategory.RELEASE_READINESS,
                    f"Release artifact present: {name}",
                    f"{name} should not be shipped in the release package.",
                    name,
                    None,
                    None,
                    "Exclude development files from release archives.",
                    "release_no_dev_artifacts",
                )

        bundled_core_patterns = [
            "wp-includes",
            "wp-admin",
            "jquery.js",
            "jquery.min.js",
        ]
        for pattern in bundled_core_patterns:
            for path in self.plugin_root.rglob(pattern):
                if self._is_hidden_or_dot(path):
                    continue
                if "node_modules" in self._safe_relative_parts(path):
                    continue
                self._add(
                    IssueSeverity.HIGH,
                    IssueCategory.RELEASE_READINESS,
                    f"Bundled WordPress core asset: {path.name}",
                    "Plugins should not bundle WordPress core files or core libraries such as jQuery.",
                    self._rel(path),
                    None,
                    None,
                    "Use WordPress-bundled dependencies via wp_enqueue_script/style handles.",
                    "release_no_bundled_core",
                )

    def _check_uninstall(self) -> None:
        self._mark_applicable("wp_standards_uninstall")
        uninstall = self.plugin_root / "uninstall.php"
        has_uninstall_hook = False
        for php in self._collect_files("*.php"):
            content = self._read_file(php)
            if "register_uninstall_hook" in content:
                has_uninstall_hook = True
                break

        if not uninstall.exists() and not has_uninstall_hook:
            self._add(
                IssueSeverity.LOW,
                IssueCategory.WP_STANDARDS,
                "No uninstall cleanup handler",
                "The plugin does not declare uninstall.php or register_uninstall_hook().",
                "uninstall.php",
                None,
                None,
                "Add uninstall cleanup for plugin-owned options/transients/jobs/tables when appropriate.",
                "wp_standards_uninstall",
            )
        elif uninstall.exists():
            content = self._read_file(uninstall)
            if "WP_UNINSTALL_PLUGIN" not in content:
                self._add(
                    IssueSeverity.MEDIUM,
                    IssueCategory.WP_STANDARDS,
                    "uninstall.php missing WP_UNINSTALL_PLUGIN guard",
                    "uninstall.php must guard direct execution.",
                    "uninstall.php",
                    None,
                    None,
                    "Add if ( ! defined( 'WP_UNINSTALL_PLUGIN' ) ) { exit; } before cleanup.",
                    "wp_standards_uninstall",
                )

    def _is_hidden_or_dot(self, path: Path) -> bool:
        from utils import is_hidden_or_dot

        return is_hidden_or_dot(path, self.plugin_root)
