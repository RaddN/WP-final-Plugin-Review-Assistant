"""Focused regression tests for the desktop review tool core."""
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from comprehensive_review import CheckStatus as ChecklistStatus
from core.checklist_mapper import ChecklistMapper
from core.plugin_check_runner import PluginCheckRunner
from core.plugin_detector import PluginDetector
from core.wp_cli_runner import WPCLIRunner
from models import (
    CheckStatus,
    IssueCategory,
    IssueSeverity,
    LocalWPSite,
    PluginCheckResult,
    PluginMetadata,
    StaticAnalysisResult,
)
from utils import safe_extract_zip, validate_zip_file


class WPCLIRunnerTests(unittest.TestCase):
    def make_runner(self) -> WPCLIRunner:
        runner = object.__new__(WPCLIRunner)
        runner.wp_root = ROOT
        runner.base_command = ["wp.bat"]
        return runner

    @patch("core.wp_cli_runner.run_command")
    def test_failed_wp_command_is_not_retried_through_php(self, run_command):
        run_command.return_value = (False, "", "database error")
        runner = self.make_runner()

        result = runner.run(["plugin", "is-installed", "plugin-check"])

        self.assertEqual((False, "", "database error"), result)
        run_command.assert_called_once()
        self.assertEqual(
            ["wp.bat", "plugin", "is-installed", "plugin-check"],
            run_command.call_args.args[0],
        )
        self.assertEqual(2, len(run_command.call_args.args))

    def test_plugin_state_distinguishes_absent_from_command_failure(self):
        runner = self.make_runner()
        runner.run = Mock(side_effect=[
            (False, "", ""),
            (False, "", "Error establishing a database connection."),
        ])

        self.assertEqual((False, ""), runner.get_plugin_installation_state("missing"))
        self.assertEqual(
            (None, "Error establishing a database connection."),
            runner.get_plugin_installation_state("plugin-check"),
        )

    def test_plugin_check_uses_strict_json_and_parses_findings(self):
        runner = self.make_runner()
        payload = [
            {
                "file": "plugin.php",
                "line": 10,
                "column": 2,
                "type": "ERROR",
                "code": "WordPress.Security.Test",
                "message": "Example error",
                "docs": "https://example.test/docs",
            }
        ]
        runner.run = Mock(return_value=(True, json.dumps(payload), ""))

        success, result, error = runner.run_plugin_check(str(ROOT))

        self.assertTrue(success)
        self.assertEqual(payload, result)
        self.assertEqual("", error)
        args = runner.run.call_args.args[0]
        self.assertIn("--format=strict-json", args)
        self.assertIn("--fields=file,line,column,type,severity,code,message,docs", args)

    def test_plugin_check_recognizes_known_clean_output(self):
        runner = self.make_runner()
        runner.run = Mock(return_value=(True, "Success: Checks complete. No errors found.", ""))

        success, result, error = runner.run_plugin_check(str(ROOT))

        self.assertTrue(success)
        self.assertEqual([], result)
        self.assertEqual("", error)

    def test_plugin_check_rejects_unparseable_success_output(self):
        runner = self.make_runner()
        runner.run = Mock(return_value=(True, "unexpected output", ""))

        success, result, error = runner.run_plugin_check(str(ROOT))

        self.assertFalse(success)
        self.assertEqual({}, result)
        self.assertIn("not valid strict JSON", error)


class PluginCheckRunnerTests(unittest.TestCase):
    def test_parses_strict_json_error_and_warning(self):
        cli = Mock()
        checker = PluginCheckRunner(cli)
        result = checker._parse_results([
            {
                "file": "plugin.php",
                "line": 12,
                "type": "ERROR",
                "severity": 9,
                "code": "WordPress.Security.Bad",
                "message": "Bad security call",
                "docs": "https://example.test/error",
            },
            {
                "file": "readme.txt",
                "line": 2,
                "type": "WARNING",
                "severity": 5,
                "code": "readme_mismatch",
                "message": "Readme mismatch",
                "docs": "https://example.test/warning",
            },
        ])

        self.assertEqual(1, len(result.errors))
        self.assertEqual(1, len(result.warnings))
        self.assertEqual("plugin.php", result.errors[0].file_path)
        self.assertEqual(IssueSeverity.CRITICAL, result.errors[0].severity)
        self.assertEqual(IssueSeverity.MEDIUM, result.warnings[0].severity)
        self.assertEqual("https://example.test/error", result.errors[0].suggestion)

    def test_text_domain_finding_is_not_misclassified_by_plugin_slug(self):
        checker = PluginCheckRunner(Mock())
        result = checker._parse_results([
            {
                "file": "admin.php",
                "line": 3,
                "type": "ERROR",
                "code": "WordPress.WP.I18n.TextDomainMismatch",
                "message": (
                    "Expected 'dynamic-ajax-product-filters-for-woocommerce-pro' "
                    "but got another domain."
                ),
            }
        ])

        issue = result.errors[0]
        self.assertEqual(IssueCategory.ACCESSIBILITY_I18N, issue.category)
        self.assertEqual("i18n_text_domain", issue.check_id)

    def test_ensure_installed_verifies_install_and_activation(self):
        cli = Mock()
        cli.get_plugin_installation_state.side_effect = [(False, ""), (True, "")]
        cli.install_plugin.return_value = (True, "installed")
        cli.get_plugin_activation_state.return_value = (True, "")

        success, message = PluginCheckRunner(cli).ensure_installed()

        self.assertTrue(success)
        self.assertIn("verified", message)
        cli.install_plugin.assert_called_once_with("plugin-check")

    def test_ensure_installed_stops_on_wp_cli_failure(self):
        cli = Mock()
        cli.get_plugin_installation_state.return_value = (
            None,
            "Error establishing a database connection.",
        )

        success, message = PluginCheckRunner(cli).ensure_installed()

        self.assertFalse(success)
        self.assertIn("Could not determine", message)
        cli.install_plugin.assert_not_called()


class PluginDetectorAndZipTests(unittest.TestCase):
    def test_plugin_header_version_is_not_overwritten_by_stable_tag(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "example-plugin"
            root.mkdir()
            (root / "example-plugin.php").write_text(
                "<?php\n/**\n * Plugin Name: Example Plugin\n * Version: 2.0.0\n"
                " * Text Domain: example-plugin\n */\n",
                encoding="utf-8",
            )
            (root / "readme.txt").write_text("Stable tag: 1.9.0\n", encoding="utf-8")

            success, metadata, error = PluginDetector(str(root)).detect()

            self.assertTrue(success, error)
            self.assertEqual("2.0.0", metadata.version)
            self.assertEqual("1.9.0", metadata.stable_tag)

    def test_zip_path_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "unsafe.zip"
            with zipfile.ZipFile(archive, "w") as handle:
                handle.writestr("..\\outside.php", "<?php")

            success, message = validate_zip_file(archive)

            self.assertFalse(success)
            self.assertIn("traversal", message)

    def test_safe_zip_extracts_benign_double_dot_filename(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "safe.zip"
            destination = Path(temp) / "out"
            with zipfile.ZipFile(archive, "w") as handle:
                handle.writestr("plugin/file..name.php", "<?php")

            success, message = validate_zip_file(archive)
            self.assertTrue(success, message)
            safe_extract_zip(archive, destination)
            self.assertTrue((destination / "plugin" / "file..name.php").is_file())


class SharedModelTests(unittest.TestCase):
    def test_checklist_and_result_models_share_check_status_enum(self):
        self.assertIs(ChecklistStatus, CheckStatus)

    def test_checklist_does_not_mark_manual_checks_as_passed(self):
        plugin = PluginMetadata(
            name="Example",
            version="1.0.0",
            text_domain="example",
            requires_php="7.4",
            requires_wp="6.0",
        )
        site = LocalWPSite(name="Local", path=str(ROOT), wp_url="http://local.test")

        result = ChecklistMapper().build(
            plugin,
            site,
            PluginCheckResult(success=True),
            StaticAnalysisResult(),
        )

        settings = result.categories[IssueCategory.WP_SETTINGS]
        register_check = next(check for check in settings.checks if check.id == "settings_register")
        self.assertEqual(CheckStatus.SKIPPED, register_check.status)
        self.assertLess(result.total_passed, result.total_checks)

    def test_plugin_check_findings_appear_in_plugin_check_summary(self):
        plugin = PluginMetadata(
            name="Example",
            version="1.0.0",
            text_domain="example",
            requires_php="7.4",
            requires_wp="6.0",
        )
        site = LocalWPSite(name="Local", path=str(ROOT), wp_url="http://local.test")
        checker = PluginCheckRunner(Mock())
        plugin_check = checker._parse_results([
            {
                "file": "plugin.php",
                "line": 2,
                "type": "ERROR",
                "severity": 8,
                "code": "WordPress.Security.Bad",
                "message": "Security problem",
            }
        ])

        result = ChecklistMapper().build(plugin, site, plugin_check, StaticAnalysisResult())
        summary = result.categories[IssueCategory.PLUGIN_CHECK]

        self.assertEqual(1, sum(len(check.issues) for check in summary.checks))
        self.assertEqual(1, summary.failed)


if __name__ == "__main__":
    unittest.main()
