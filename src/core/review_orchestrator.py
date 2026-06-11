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
from core.settings_manager import SettingsManager
from core.summary_builder import RuleSummaryBuilder


logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str], None]
ProgressValueCallback = Callable[[int], None]


@dataclass
class FullReviewResult:
    """Complete review output including checklist and deterministic summary."""
    review: ReviewResult
    checklist: CategoryReviewResult
    wp_cli_info: str = ""
    plugin_check_status: str = ""
    summary_engine: str = "Rule-based"


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

        site_ok, site_url = cli.verify_wordpress_site()
        if not site_ok:
            raise RuntimeError(
                "WP-CLI is installed, but the selected WordPress site could not be loaded: "
                f"{site_url}"
            )
        site.wp_url = site_url
        site.wordpress_version = cli.get_wp_version() or ""
        site.php_version = cli.get_php_version() or ""
        site.is_valid = True
        pct(15)

        plugin_check = PluginCheckResult(success=False, raw_output="Plugin Check disabled in settings")
        plugin_check_status = "Plugin Check disabled in settings"
        if self.settings.get("run_plugin_check", True):
            progress("Checking Plugin Check installation...")
            checker = PluginCheckRunner(cli)
            pc_ready, pc_msg = checker.ensure_installed()
            plugin_check_status = pc_msg
            if not pc_ready:
                raise RuntimeError(pc_msg)
            progress(f"Plugin Check ready: {pc_msg}")
            pct(25)

            progress("Running WordPress Plugin Check (may take 1-2 minutes)...")
            pc_success, plugin_check = checker.run(plugin.root_path, ensure_ready=False)
            pct(55)
            if pc_success:
                progress(
                    f"Plugin Check complete: {len(plugin_check.errors)} errors, "
                    f"{len(plugin_check.warnings)} warnings"
                )
            else:
                raise RuntimeError(f"Plugin Check failed: {plugin_check.raw_output}")
        else:
            progress("Plugin Check skipped by settings.")
            pct(55)

        static_result = StaticAnalysisResult()
        if self.settings.get("run_static_analysis", True):
            progress("Running deterministic static review rules...")
            analyzer = AgentsRulesAnalyzer(plugin.root_path, plugin)
            static_result = analyzer.analyze()
            progress(
                f"Static analysis: {len(static_result.issues)} issues in "
                f"{static_result.files_scanned} files"
            )
        else:
            progress("Static analysis skipped by settings.")
        pct(75)

        progress("Building category checklist...")
        checklist = ChecklistMapper().build(plugin, site, plugin_check, static_result)
        pct(85)

        review = ReviewResult(
            plugin=plugin,
            site=site,
            plugin_check=plugin_check,
            static_analysis=static_result,
        )

        progress("Generating deterministic review summary...")
        review.analysis_summary = RuleSummaryBuilder().generate(review, checklist)
        pct(95)

        progress("Review complete!")
        pct(100)

        return FullReviewResult(
            review=review,
            checklist=checklist,
            wp_cli_info=wp_info,
            plugin_check_status=plugin_check_status,
            summary_engine="Rule-based",
        )
