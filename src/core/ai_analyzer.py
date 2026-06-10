"""Local AI analyzer integration for WP Plugin Review Assistant."""
import json
import logging
import requests
from typing import Dict, Any, List, Optional
from models import ReviewResult, IssueSeverity

logger = logging.getLogger(__name__)


class AIAnalyzer:
    """Handles communication with free local AI providers (Ollama, LM Studio)."""

    def __init__(self, settings: Dict[str, Any]):
        self.settings = settings
        self.provider = settings.get("ai_provider", "Disabled")
        self.model_name = settings.get("model_name", "llama3")
        self.api_url = settings.get("api_url", "http://localhost:11434")
        self.timeout = settings.get("ai_timeout", 30)
        self.max_context = settings.get("max_context_size", 4096)
        self.enable_reasoning = settings.get("enable_reasoning", True)

    def is_available(self) -> bool:
        """Check if the selected AI provider is available."""
        if self.provider == "Disabled":
            return False

        try:
            if self.provider == "Ollama":
                # Ollama health check/tags endpoint
                url = f"{self.api_url.rstrip('/')}/api/tags"
                response = requests.get(url, timeout=15)
                return response.status_code == 200
            elif self.provider == "LM Studio":
                # LM Studio OpenAI-compatible models endpoint
                url = f"{self.api_url.rstrip('/')}/v1/models"
                response = requests.get(url, timeout=15)
                return response.status_code == 200
        except Exception as e:
            logger.debug(f"AI provider connection check failed: {e}")
        return False

    def get_installed_models(self) -> List[str]:
        """Fetch list of models available from the provider."""
        models = []
        try:
            if self.provider == "Ollama":
                url = f"{self.api_url.rstrip('/')}/api/tags"
                response = requests.get(url, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    for m in data.get("models", []):
                        models.append(m.get("name"))
            elif self.provider == "LM Studio":
                url = f"{self.api_url.rstrip('/')}/v1/models"
                response = requests.get(url, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    for m in data.get("data", []):
                        models.append(m.get("id"))
        except Exception as e:
            logger.error(f"Error fetching installed models: {e}")
        return models

    def generate_summary(self, result: ReviewResult) -> str:
        """Generate a review summary using AI or the rule-based fallback."""
        if self.provider == "Disabled" or not self.is_available():
            logger.info("AI is disabled or unavailable. Using rule-based fallback summary.")
            return self._generate_fallback_summary(result)

        prompt = self._build_prompt(result)

        try:
            if self.provider == "Ollama":
                return self._query_ollama(prompt)
            elif self.provider == "LM Studio":
                return self._query_lm_studio(prompt)
        except Exception as e:
            logger.error(f"AI generation failed: {e}. Falling back to rule-based summary.")
            return self._generate_fallback_summary(result) + f"\n\n*(Note: AI summary generation failed: {e})*"

        return self._generate_fallback_summary(result)

    def _query_ollama(self, prompt: str) -> str:
        """Query Ollama generate API."""
        url = f"{self.api_url.rstrip('/')}/api/generate"
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_ctx": self.max_context
            }
        }
        
        response = requests.post(url, json=payload, timeout=self.timeout)
        if response.status_code == 200:
            return response.json().get("response", "").strip()
        else:
            raise Exception(f"Ollama returned status code {response.status_code}: {response.text}")

    def _query_lm_studio(self, prompt: str) -> str:
        """Query LM Studio OpenAI-compatible chat API."""
        url = f"{self.api_url.rstrip('/')}/v1/chat/completions"
        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert WordPress plugin reviewer and secure code analysis architect. Provide professional, structured code review summaries."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.2,
            "stream": False
        }

        response = requests.post(url, json=payload, timeout=self.timeout)
        if response.status_code == 200:
            choices = response.json().get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()
            raise Exception("Empty choices returned from LM Studio")
        else:
            raise Exception(f"LM Studio returned status code {response.status_code}: {response.text}")

    def _build_prompt(self, result: ReviewResult) -> str:
        """Build the AI review prompt with a summary of the issues."""
        plugin_info = result.plugin
        issues = result.all_issues

        # Group issues by severity
        critical = [i for i in issues if i.severity == IssueSeverity.CRITICAL]
        high = [i for i in issues if i.severity == IssueSeverity.HIGH]
        medium = [i for i in issues if i.severity == IssueSeverity.MEDIUM]
        low = [i for i in issues if i.severity == IssueSeverity.LOW]

        issues_summary = ""
        for idx, issue in enumerate(critical[:5] + high[:5] + medium[:5], 1):
            issues_summary += f"{idx}. [{issue.severity.value.upper()}] {issue.title} in {issue.file_path or 'unknown'}"
            if issue.line_number:
                issues_summary += f" line {issue.line_number}"
            issues_summary += f"\n   Details: {issue.description}\n"
            if issue.code_snippet:
                issues_summary += f"   Code: `{issue.code_snippet.strip()}`\n"
            if issue.suggestion:
                issues_summary += f"   Suggested Fix: {issue.suggestion}\n"
            issues_summary += "\n"

        prompt = f"""Summarize the WordPress plugin review results for the plugin '{plugin_info.name}' (v{plugin_info.version}).

Overview of issues found:
- Critical severity: {len(critical)}
- High severity: {len(high)}
- Medium severity: {len(medium)}
- Low severity: {len(low)}

Here are the details of the top issues:
{issues_summary}

Please provide a professional, executive summary (Markdown format) covering:
1. **Security & Code Quality Rating**: A brief assessment of the plugin's readiness (e.g. Needs immediate security fixes, Safe to deploy with minor refactoring, etc.)
2. **Top Architectural & Security Risks**: A bulleted breakdown of the most severe vulnerabilities or violations of WordPress standards found.
3. **Actionable Fix Plan**: Clear, concise instructions on what the developer must fix first.

Keep the summary concise and focused on developer fixes. Do not include introductory conversational filler. Start directly with the markdown content.
"""
        return prompt

    def _generate_fallback_summary(self, result: ReviewResult) -> str:
        """Rule-based fallback summary generator."""
        plugin = result.plugin
        issues = result.all_issues
        counts = result.issue_count_by_severity

        # Detect main security/standards risks
        has_sqli = any("sql" in i.title.lower() or "prepare" in i.description.lower() for i in issues)
        has_nonce = any("nonce" in i.title.lower() or "csrf" in i.title.lower() for i in issues)
        has_cap = any("capability" in i.title.lower() or "permission" in i.title.lower() for i in issues)
        has_escap = any("escap" in i.title.lower() for i in issues)
        has_sanit = any("sanit" in i.title.lower() for i in issues)
        has_woo = any("woo" in i.category.value.lower() for i in issues)

        status_rating = "🟢 Excellent (Ready to Release)"
        if counts["critical"] > 0:
            status_rating = "🔴 Critical Security Issues Found (Do Not Deploy)"
        elif counts["high"] > 0:
            status_rating = "🟠 High Priority Issues Found (Action Required)"
        elif counts["medium"] > 0:
            status_rating = "🟡 Medium Priority Issues Found (Recommended Fixes)"
        elif counts["low"] > 0:
            status_rating = "🔵 Minor Issues Found (Polish Recommended)"

        summary = f"""# Executive Review Summary: {plugin.name} (v{plugin.version})

## 1. Security & Code Quality Rating
**Status:** {status_rating}

The plugin was scanned using static analysis and WordPress Plugin Check. A total of **{len(issues)}** issues were detected.

## 2. Key Risks & Findings
"""
        risks = []
        if has_sqli:
            risks.append("- **SQL Injection / Prepared Queries:** Unescaped database queries or missing `$wpdb->prepare()` calls detected, creating high-risk vulnerability entry points.")
        if has_nonce:
            risks.append("- **Missing Nonce Verification (CSRF):** AJAX, REST, or form submissions lack validation nonces, making them susceptible to Cross-Site Request Forgery.")
        if has_cap:
            risks.append("- **Missing Capability Checks:** User privileges are not validated before executing admin actions, allowing unauthorized users to perform changes.")
        if has_escap:
            risks.append("- **Output Escaping Violations:** Dynamic values are echoed directly without proper context-based escaping (like `esc_html` or `esc_attr`), posing XSS risks.")
        if has_sanit:
            risks.append("- **Input Sanitization Failures:** Superglobal inputs are processed without validation or sanitization, potentially introducing unsafe payloads.")
        if has_woo:
            risks.append("- **WooCommerce Deficiencies:** Missing object type guards or direct database access instead of WooCommerce CRUD APIs.")

        if risks:
            summary += "\n".join(risks)
        else:
            summary += "- No major security vulnerabilities or standard violations were detected in the primary categories."

        summary += """

## 3. Actionable Fix Plan
"""
        plan = []
        if counts["critical"] > 0 or counts["high"] > 0:
            plan.append("1. **Critical/High Security Fixes:** Secure all inputs/outputs, add permission checks, and ensure all SQL queries are prepared.")
        if has_nonce:
            plan.append("2. **Implement Nonce Security:** Add `wp_create_nonce()` on output and verify with `check_ajax_referer()` or `wp_verify_nonce()` in handlers.")
        if has_escap or has_sanit:
            plan.append("3. **Boundary Sanitization & Escaping:** Standardize on `sanitize_text_field()` for inputs and `esc_html()`, `esc_attr()` for output templates.")
        if len(plan) == 0:
            plan.append("1. **General Code Polish:** Review minor style guidelines and verify that the plugin header matches stable tags in `readme.txt`.")
            
        summary += "\n".join(plan)
        return summary
