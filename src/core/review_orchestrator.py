"""Orchestrates the full plugin review workflow."""
import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

from models import (
    CategoryReviewResult,
    PluginMetadata,
    LocalWPSite,
    ReviewResult,
    StaticAnalysisResult,
    PluginCheckResult,
)
from core.wp_cli_runner import WPCLIRunner
from core.plugin_check_runner import PluginCheckRunner
from analysis.agents_rules_analyzer import AgentsRulesAnalyzer
from core.checklist_mapper import ChecklistMapper
from core.ai_analyzer import AIAnalyzer
from core.settings_manager import SettingsManager


logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str], None]
ProgressValueCallback = Callable[[int], None]


@dataclass
class FullReviewResult:
    """Complete review output including checklist and AI summary."""
    review: ReviewResult
    checklist: CategoryReviewResult
    wp_cli_info: str = ""
    plugin_check_status: str = ""
    ai_available: bool = False


class ReviewOrchestrator:
    """Runs the complete review pipeline."""

    def __init__(self, settings: Optional[SettingsManager] = None):
        self.settings = settings or SettingsManager()

    def run(
        self,
        plugin: PluginMetadata,
        site: LocalWPSite,
        on_progress: Optional[ProgressCallback] = None,
        on_progress_value: Optional[ProgressValueCallback] = None,
    ) -> FullReviewResult:
        def progress(msg: str):
            logger.info(msg)
            if on_progress:
                on_progress(msg)

        def pct(value: int):
            if on_progress_value:
                on_progress_value(value)

        progress("Initializing WP-CLI...")
        cli = WPCLIRunner(site.path)
        pct(5)

        wp_ok, wp_info = cli.verify_wp_cli()
        if not wp_ok:
            raise RuntimeError(f"WP-CLI not available: {wp_info}")
        progress("WP-CLI verified")
        pct(10)

        site_url = cli.get_site_url()
        if site_url:
            site.wp_url = site_url
        site.wordpress_version = cli.get_wp_version() or ""
        site.php_version = cli.get_php_version() or ""
        site.is_valid = True
        pct(15)

        progress("Checking Plugin Check installation...")
        checker = PluginCheckRunner(cli)
        pc_ready, pc_msg = checker.ensure_installed()
        plugin_check_status = pc_msg
        if not pc_ready:
            raise RuntimeError(pc_msg)
        progress(f"Plugin Check ready: {pc_msg}")
        pct(25)

        progress("Running WordPress Plugin Check (may take 1-2 minutes)...")
        pc_success, plugin_check = checker.run(plugin.root_path)
        pct(55)
        if pc_success:
            progress(
                f"Plugin Check complete: {len(plugin_check.errors)} errors, "
                f"{len(plugin_check.warnings)} warnings"
            )
        else:
            progress(f"Plugin Check warning: {plugin_check.raw_output}")

        progress("Running AGENTS.md rule-based static analysis...")
        analyzer = AgentsRulesAnalyzer(plugin.root_path, plugin)
        static_result = analyzer.analyze()
        pct(75)
        progress(f"Static analysis: {len(static_result.issues)} issues in {static_result.files_scanned} files")

        progress("Building category checklist...")
        checklist = ChecklistMapper().build(plugin, site, plugin_check, static_result)
        pct(85)

        review = ReviewResult(
            plugin=plugin,
            site=site,
            plugin_check=plugin_check,
            static_analysis=static_result,
        )

        ai_analyzer = AIAnalyzer(self.settings.settings)
        ai_available = ai_analyzer.is_available()
        if self.settings.get("enable_reasoning", True):
            if ai_available:
                progress(f"Generating AI summary via {self.settings.get('ai_provider')}...")
            else:
                progress("AI unavailable - generating rule-based summary...")
            review.ai_summary = ai_analyzer.generate_summary(review)
        pct(95)

        progress("Review complete!")
        pct(100)

        return FullReviewResult(
            review=review,
            checklist=checklist,
            wp_cli_info=wp_info,
            plugin_check_status=plugin_check_status,
            ai_available=ai_available,
        )
