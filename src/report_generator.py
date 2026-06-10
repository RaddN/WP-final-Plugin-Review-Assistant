"""Report generation for review results."""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from models import ReviewResult, IssueSeverity, CategoryReviewResult, CheckStatus, ReviewIssue


logger = logging.getLogger(__name__)

STATUS_ICONS = {
    CheckStatus.PASSED: "✓",
    CheckStatus.FAILED: "✗",
    CheckStatus.WARNING: "⚠",
    CheckStatus.SKIPPED: "⊘",
    CheckStatus.NOT_APPLICABLE: "—",
}


class ReportGenerator:
    """Generate professional reports from review results."""

    def __init__(
        self,
        result: ReviewResult,
        checklist: Optional[CategoryReviewResult] = None,
    ):
        self.result = result
        self.checklist = checklist

    def generate_html_report(self, output_path: Optional[str] = None) -> str:
        if not output_path:
            output_path = f"wp_plugin_review_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"

        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(self._build_html())

        logger.info("HTML report generated: %s", output_path)
        return output_path

    def generate_json_report(self, output_path: Optional[str] = None) -> str:
        if not output_path:
            output_path = f"wp_plugin_review_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        data = self.result.to_dict()
        if self.checklist:
            data["checklist"] = self.checklist.to_dict()
        if self.result.ai_summary:
            data["ai_summary"] = self.result.ai_summary

        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)

        logger.info("JSON report generated: %s", output_path)
        return output_path

    def generate_codex_prompt(self, max_issues: int = 15) -> str:
        prompt = f"""# WordPress Plugin Review Fix Request

## Plugin
- **Name:** {self.result.plugin.name}
- **Version:** {self.result.plugin.version}
- **Path:** {self.result.plugin.root_path}
- **Text Domain:** {self.result.plugin.text_domain}
- **WooCommerce:** {'Yes' if self.result.plugin.woo_compatible else 'No'}

## Site Context
- **LocalWP Site:** {self.result.site.name}
- **URL:** {self.result.site.wp_url}

## Issue Summary
- Total Issues: {len(self.result.all_issues)}
- Critical: {self.result.issue_count_by_severity['critical']}
- High: {self.result.issue_count_by_severity['high']}
- Medium: {self.result.issue_count_by_severity['medium']}
- Low: {self.result.issue_count_by_severity['low']}

"""

        if self.checklist:
            prompt += "## Checklist Findings\n\n"
            issue_idx = 1
            for cat in self.checklist.all_category_results:
                failed_checks = [c for c in cat.checks if c.issues]
                if failed_checks:
                    prompt += f"### Category: {cat.category_name}\n"
                    for check in failed_checks:
                        prompt += f"#### Topic: {check.name} ({check.status.value.upper()})\n"
                        for issue in check.issues[:5]:
                            prompt += f"{issue_idx}. **[{issue.severity.value.upper()}] {issue.title}**\n"
                            prompt += f"   - **File:** `{issue.file_path or 'unknown'}`{f' line {issue.line_number}' if issue.line_number else ''}\n"
                            prompt += f"   - **Description:** {issue.description}\n"
                            if issue.code_snippet:
                                prompt += f"   - **Code:** `{issue.code_snippet.strip()}`\n"
                            if issue.suggestion:
                                prompt += f"   - **Suggestion:** {issue.suggestion}\n"
                            prompt += "\n"
                            issue_idx += 1
                            if issue_idx > max_issues:
                                break
                        if issue_idx > max_issues:
                            break
                if issue_idx > max_issues:
                    break
        else:
            prompt += "## Priority Fixes\n\n"
            critical = [i for i in self.result.all_issues if i.severity == IssueSeverity.CRITICAL]
            high = [i for i in self.result.all_issues if i.severity == IssueSeverity.HIGH]
            medium = [i for i in self.result.all_issues if i.severity == IssueSeverity.MEDIUM]
            priority = (critical + high + medium)[:max_issues]

            for idx, issue in enumerate(priority, 1):
                prompt += f"""### {idx}. [{issue.severity.value.upper()}] {issue.title}
- **Category:** {issue.category.value}
- **File:** `{issue.file_path or 'unknown'}`{f' line {issue.line_number}' if issue.line_number else ''}
- **Problem:** {issue.description}
"""
                if issue.code_snippet:
                    prompt += f"- **Code:** `{issue.code_snippet.strip()}`\n"
                if issue.suggestion:
                    prompt += f"- **Suggested fix:** {issue.suggestion}\n"
                prompt += "\n"

        prompt += """
## Fix Instructions

Follow WordPress plugin review standards (AGENTS.md):

1. **Security:** capability checks, nonce verification, sanitization, escaping, `$wpdb->prepare()`
2. **Standards:** prefix all identifiers; enqueue assets via WP APIs; no CDN assets
3. **Defensive coding:** guard null/false/`WP_Error` returns; validate Woo objects
4. **WooCommerce:** use CRUD APIs; declare HPOS compatibility when using orders
5. **Release:** align readme.txt stable tag with version; remove dev artifacts

After fixes, re-run WordPress Plugin Check:
```powershell
wp plugin is-installed plugin-check || wp plugin install plugin-check --activate
wp plugin is-active plugin-check || wp plugin activate plugin-check
wp plugin check <plugin-path>
```
"""
        return prompt

    def _get_severity_color(self, severity: IssueSeverity) -> str:
        if severity == IssueSeverity.CRITICAL:
            return "#b32d2e"
        if severity == IssueSeverity.HIGH:
            return "#dba617"
        if severity == IssueSeverity.MEDIUM:
            return "#996800"
        return "#00a32a"

    def _build_html(self) -> str:
        summary = self.result.issue_count_by_severity
        issues = self.result.all_issues
        plugin = self.result.plugin

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WP Plugin Review - {plugin.name}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 0; background: #f0f0f1; color: #1d2327; }}
.container {{ max-width: 1100px; margin: 24px auto; background: #fff; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,.12); padding: 32px; }}
h1 {{ color: #2271b1; margin: 0 0 8px; }}
.meta {{ color: #646970; margin-bottom: 24px; }}
.summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 12px; margin: 24px 0; }}
.card {{ background: #f6f7f7; border-radius: 6px; padding: 16px; text-align: center; }}
.card .num {{ font-size: 2em; font-weight: 700; }}
.critical {{ color: #b32d2e; }} .high {{ color: #dba617; }}
.medium {{ color: #996800; }} .low {{ color: #00a32a; }}
.section {{ margin: 28px 0; }}
details.category {{ border: 1px solid #dcdcde; border-radius: 6px; margin: 16px 0; overflow: hidden; background: #fff; }}
details.category summary.cat-header {{ background: #f6f7f7; padding: 12px 16px; font-weight: 600; cursor: pointer; outline: none; list-style: none; user-select: none; }}
details.category summary.cat-header::-webkit-details-marker {{ display: none; }}
details.category summary.cat-header:hover {{ background: #f0f0f1; }}
details.category[open] summary.cat-header {{ border-bottom: 1px solid #dcdcde; }}
.cat-content {{ background: #fff; }}
.check {{ padding: 12px 16px; border-top: 1px solid #f0f0f1; display: flex; justify-content: space-between; align-items: flex-start; }}
.check.failed {{ background: #fcf0f1; }}
.check.passed {{ background: #edfaef; }}
.check-title {{ font-weight: 600; }}
.check-message {{ font-size: 0.9em; color: #555; margin-top: 4px; }}
.nested-issues {{ padding: 8px 16px 16px 32px; background: #fafafa; border-top: 1px dashed #e5e5e5; }}
.nested-issue {{ margin-top: 12px; padding-left: 8px; }}
.code {{ background: #2c3338; color: #f0f0f1; padding: 8px; border-radius: 4px; font-family: monospace; font-size: 12px; overflow-x: auto; margin-top: 6px; }}
.ai-summary {{ background: #f0f6fc; border: 1px solid #c5d9ed; border-radius: 6px; padding: 16px; white-space: pre-wrap; }}
.footer {{ margin-top: 32px; text-align: center; color: #646970; font-size: 13px; }}
</style>
</head>
<body>
<div class="container">
<h1>WordPress Plugin Review Report</h1>
<p class="meta"><strong>{plugin.name}</strong> v{plugin.version} &mdash; {self.result.timestamp.strftime('%Y-%m-%d %H:%M')}</p>
<p class="meta">Site: {self.result.site.name} ({self.result.site.wp_url})</p>

<div class="summary">
<div class="card"><div class="num">{len(issues)}</div>Total Issues</div>
<div class="card"><div class="num critical">{summary['critical']}</div>Critical</div>
<div class="card"><div class="num high">{summary['high']}</div>High</div>
<div class="card"><div class="num medium">{summary['medium']}</div>Medium</div>
<div class="card"><div class="num low">{summary['low']}</div>Low</div>
</div>
"""

        if self.result.ai_summary:
            html += f'<div class="section"><h2>Executive Summary</h2><div class="ai-summary">{self._escape(self.result.ai_summary)}</div></div>'

        if self.checklist:
            html += '<div class="section"><h2>AGENTS.md Category Checklist</h2>'
            for cat in self.checklist.all_category_results:
                html += f'<details class="category"><summary class="cat-header">{cat.category_name} — {cat.passed}/{cat.total} passed, {cat.failed} failed</summary><div class="cat-content">'
                for check in cat.checks:
                    css = "failed" if check.status == CheckStatus.FAILED else "passed" if check.status == CheckStatus.PASSED else ""
                    icon = STATUS_ICONS.get(check.status, "")
                    html += f"""
                    <div class="check {css}">
                        <div>
                            <span class="check-title">{icon} {self._escape(check.name)}</span>
                            <div class="check-message">{self._escape(check.message)}</div>
                        </div>
                        <span style="font-weight:bold; color: {self._get_status_color(check.status)};">{check.status.value.upper()}</span>
                    </div>
                    """
                    if check.issues:
                        html += '<div class="nested-issues">'
                        for issue in check.issues:
                            border_color = self._get_severity_color(issue.severity)
                            html += f"""
                            <div class="nested-issue" style="border-left: 3px solid {border_color};">
                                <strong>[{issue.severity.value.upper()}] {self._escape(issue.title)}</strong><br>
                                <span style="font-size:0.85em; color:#646970;">{self._escape(issue.file_path or '')}{f':{issue.line_number}' if issue.line_number else ''}</span><br>
                                <span style="font-size:0.9em; color:#1d2327;">{self._escape(issue.description)}</span>
                            """
                            if issue.code_snippet:
                                html += f'<div class="code">{self._escape(issue.code_snippet)}</div>'
                            if issue.suggestion:
                                html += f'<div style="font-size:0.85em; margin-top:4px; font-style:italic; color:#50575e;">Suggestion: {self._escape(issue.suggestion)}</div>'
                            html += '</div>'
                        html += '</div>'
                html += "</div></details>"
            html += "</div>"

        # Show all issues at bottom in list format
        html += '<div class="section"><h2>All Discovered Issues</h2>'
        for issue in issues:
            html += f"""<div class="nested-issue" style="border-left: 4px solid {self._get_severity_color(issue.severity)}; margin: 12px 0; padding: 12px; background: #fafafa; border-radius: 0 4px 4px 0;">
<strong>[{issue.severity.value.upper()}] {self._escape(issue.title)}</strong><br>
<span style="color:#646970; font-size:0.85em;">{self._escape(issue.category.value)} — {self._escape(issue.file_path or '')}{f':{issue.line_number}' if issue.line_number else ''}</span><br>
{self._escape(issue.description)}"""
            if issue.code_snippet:
                html += f'<div class="code">{self._escape(issue.code_snippet)}</div>'
            if issue.suggestion:
                html += f'<br><em style="font-size:0.9em; color:#50575e;">Suggestion: {self._escape(issue.suggestion)}</em>'
            html += "</div>"
        html += '</div>'

        html += '<div class="footer">Generated by WP Plugin Review Assistant</div></div></body></html>'
        return html

    def _get_status_color(self, status: CheckStatus) -> str:
        if status == CheckStatus.PASSED:
            return "#2e7d32"
        if status == CheckStatus.FAILED:
            return "#c62828"
        if status == CheckStatus.WARNING:
            return "#ef6c00"
        return "#757575"

    def _escape(self, text: str) -> str:
        return (
            str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
