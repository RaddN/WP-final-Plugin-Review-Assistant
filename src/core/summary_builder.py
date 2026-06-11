"""Deterministic review summary generation."""
from collections import Counter
from typing import Optional

from models import CategoryReviewResult, IssueSeverity, ReviewResult


class RuleSummaryBuilder:
    """Build a concise, deterministic summary from review findings."""

    def generate(
        self,
        result: ReviewResult,
        checklist: Optional[CategoryReviewResult] = None,
    ) -> str:
        issues = result.all_issues
        counts = result.issue_count_by_severity

        if counts["critical"] > 0:
            verdict = "Do not release until critical findings are fixed."
        elif counts["high"] > 0:
            verdict = "High-priority fixes are required before release."
        elif counts["medium"] > 0:
            verdict = "Release needs targeted cleanup and regression verification."
        elif counts["low"] > 0:
            verdict = "No blocking findings detected; minor cleanup remains."
        else:
            verdict = "No automated issues detected."

        lines = [
            f"# Review Summary: {result.plugin.name} v{result.plugin.version}",
            "",
            f"**Verdict:** {verdict}",
            "",
            "## Automated Findings",
            f"- Total issues: {len(issues)}",
            f"- Critical: {counts['critical']}",
            f"- High: {counts['high']}",
            f"- Medium: {counts['medium']}",
            f"- Low: {counts['low']}",
        ]

        if checklist:
            lines.extend([
                "",
                "## Checklist Coverage",
                (
                    f"- Checks: {checklist.total_checks}; "
                    f"passed {checklist.total_passed}, failed {checklist.total_failed}, "
                    f"warnings {checklist.total_warnings}"
                ),
            ])

        priority = [
            issue for issue in issues
            if issue.severity in {IssueSeverity.CRITICAL, IssueSeverity.HIGH, IssueSeverity.MEDIUM}
        ][:8]
        if priority:
            lines.extend(["", "## Fix First"])
            for idx, issue in enumerate(priority, 1):
                location = issue.file_path or "unknown"
                if issue.line_number:
                    location += f":{issue.line_number}"
                lines.append(
                    f"{idx}. [{issue.severity.value.upper()}] {issue.title} - {location}"
                )

        category_counts = Counter(issue.category.value for issue in issues)
        if category_counts:
            lines.extend(["", "## Heaviest Areas"])
            for category, count in category_counts.most_common(5):
                lines.append(f"- {category}: {count}")

        if checklist:
            manual = []
            for category in checklist.all_category_results:
                for check in category.checks:
                    if check.status.value == "skipped":
                        manual.append(check.name)
            if manual:
                lines.extend(["", "## Still Needs Runtime Review"])
                for name in manual[:8]:
                    lines.append(f"- {name}")

        return "\n".join(lines)
