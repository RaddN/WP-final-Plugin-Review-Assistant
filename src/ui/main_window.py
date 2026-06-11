"""Professional UI for WP Plugin Review Assistant."""
import json
import sys
import logging
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QComboBox, QProgressBar, QTextEdit,
    QFileDialog, QMessageBox, QStackedWidget, QGroupBox, QHeaderView,
    QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem,
    QSplitter, QFrame, QGridLayout,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QTextCursor, QColor

from utils import setup_logging
from models import PluginMetadata, LocalWPSite, CheckStatus
from core.plugin_detector import PluginDetector
from core.localwp_validator import LocalWPValidator
from core.review_orchestrator import ReviewOrchestrator, FullReviewResult
from core.settings_manager import SettingsManager
from report_generator import ReportGenerator
from ui.settings_dialog import SettingsDialog


logger = setup_logging()

STATUS_COLORS = {
    CheckStatus.PASSED: "#2e7d32",
    CheckStatus.FAILED: "#c62828",
    CheckStatus.WARNING: "#ef6c00",
    CheckStatus.SKIPPED: "#757575",
    CheckStatus.NOT_APPLICABLE: "#9e9e9e",
}


class ReviewWorker(QThread):
    progress = Signal(str)
    progress_value = Signal(int)
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, plugin: PluginMetadata, site: LocalWPSite, settings: SettingsManager):
        super().__init__()
        self.plugin = plugin
        self.site = site
        self.settings = settings

    def run(self):
        try:
            orchestrator = ReviewOrchestrator(self.settings)
            result = orchestrator.run(
                self.plugin,
                self.site,
                on_progress=lambda m: self.progress.emit(m),
                on_progress_value=lambda v: self.progress_value.emit(v),
            )
            self.finished.emit(result)
        except Exception as exc:
            logger.error("Review worker error: %s", exc)
            self.error.emit(str(exc))


class WPPluginReviewAssistant(QMainWindow):
    """Windows desktop application for WordPress plugin review."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("WP Plugin Review Assistant")
        self.setGeometry(80, 60, 1440, 920)
        self.setMinimumSize(1100, 700)

        self.settings = SettingsManager()
        self.plugin: Optional[PluginMetadata] = None
        self.plugin_detector: Optional[PluginDetector] = None
        self.site: Optional[LocalWPSite] = None
        self.full_result: Optional[FullReviewResult] = None
        self.localwp_validator = LocalWPValidator()
        self.current_page = 0

        self._setup_ui()
        self._apply_styling()
        self._refresh_sites()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("WP Plugin Review Assistant")
        font = QFont()
        font.setPointSize(18)
        font.setBold(True)
        title.setFont(font)
        header.addWidget(title)
        header.addStretch()

        settings_btn = QPushButton("Settings")
        settings_btn.clicked.connect(self._open_settings)
        header.addWidget(settings_btn)
        main_layout.addLayout(header)

        subtitle = QLabel(
            "Review WordPress/WooCommerce plugins with Plugin Check and deterministic WordPress review rules"
        )
        subtitle.setStyleSheet("color: #555; margin-bottom: 4px;")
        main_layout.addWidget(subtitle)

        self.stacked = QStackedWidget()
        self.stacked.addWidget(self._create_plugin_page())
        self.stacked.addWidget(self._create_site_page())
        self.stacked.addWidget(self._create_review_page())
        self.stacked.addWidget(self._create_results_page())
        main_layout.addWidget(self.stacked)

        nav = QHBoxLayout()
        self.prev_btn = QPushButton("Back")
        self.prev_btn.clicked.connect(self._go_back)
        self.next_btn = QPushButton("Next")
        self.next_btn.clicked.connect(self._go_next)
        nav.addStretch()
        nav.addWidget(self.prev_btn)
        nav.addWidget(self.next_btn)
        main_layout.addLayout(nav)
        self._update_nav_buttons()

    def _create_plugin_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        layout.addWidget(self._step_title("Step 1: Select Plugin"))
        layout.addWidget(self._hint(
            "Choose a plugin folder or ZIP file. Metadata is extracted automatically."
        ))

        row = QHBoxLayout()
        self.plugin_path_input = QLineEdit()
        self.plugin_path_input.setPlaceholderText("C:\\path\\to\\plugin or plugin.zip")
        self.plugin_path_input.setMinimumHeight(38)
        folder_btn = QPushButton("Folder")
        folder_btn.clicked.connect(self._browse_plugin_folder)
        zip_btn = QPushButton("ZIP")
        zip_btn.clicked.connect(self._browse_plugin_zip)
        row.addWidget(self.plugin_path_input)
        row.addWidget(folder_btn)
        row.addWidget(zip_btn)
        layout.addLayout(row)

        info_group = QGroupBox("Detected Plugin Information")
        info_layout = QVBoxLayout(info_group)
        self.plugin_info_text = QTextEdit()
        self.plugin_info_text.setReadOnly(True)
        self.plugin_info_text.setMinimumHeight(180)
        info_layout.addWidget(self.plugin_info_text)
        layout.addWidget(info_group)

        load_btn = QPushButton("Load Plugin")
        load_btn.setMinimumHeight(42)
        load_btn.clicked.connect(self._load_plugin)
        layout.addWidget(load_btn)
        layout.addStretch()
        return w

    def _create_site_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        layout.addWidget(self._step_title("Step 2: Select LocalWP Site"))
        layout.addWidget(self._hint(
            "Auto-detects C:\\Users\\<user>\\Local Sites\\*\\app\\public. "
            "Plugin Check runs via WP-CLI from the site root."
        ))

        auto_group = QGroupBox("LocalWP Sites")
        auto_layout = QVBoxLayout(auto_group)
        site_row = QHBoxLayout()
        self.site_combo = QComboBox()
        self.site_combo.setMinimumHeight(38)
        self.site_combo.currentIndexChanged.connect(self._on_site_changed)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_sites)
        site_row.addWidget(QLabel("Site:"))
        site_row.addWidget(self.site_combo, 1)
        site_row.addWidget(refresh_btn)
        auto_layout.addLayout(site_row)

        self.site_info_text = QTextEdit()
        self.site_info_text.setReadOnly(True)
        self.site_info_text.setMinimumHeight(140)
        auto_layout.addWidget(self.site_info_text)
        layout.addWidget(auto_group)

        manual_group = QGroupBox("Manual WordPress Root")
        manual_layout = QHBoxLayout(manual_group)
        self.site_path_input = QLineEdit()
        self.site_path_input.setPlaceholderText("Path to wp-config.php parent (app/public)")
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_site)
        manual_layout.addWidget(self.site_path_input)
        manual_layout.addWidget(browse_btn)
        layout.addWidget(manual_group)

        validate_btn = QPushButton("Validate Site && WP-CLI")
        validate_btn.setMinimumHeight(40)
        validate_btn.clicked.connect(self._validate_site)
        layout.addWidget(validate_btn)
        layout.addStretch()
        return w

    def _create_review_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        layout.addWidget(self._step_title("Step 3: Run Review"))
        layout.addWidget(self._hint(
            "Runs Plugin Check (installs/activates if needed), deterministic static rules, "
            "and a deterministic fix-priority summary."
        ))

        summary_group = QGroupBox("Configuration")
        summary_layout = QVBoxLayout(summary_group)
        self.review_summary_text = QTextEdit()
        self.review_summary_text.setReadOnly(True)
        self.review_summary_text.setMinimumHeight(100)
        summary_layout.addWidget(self.review_summary_text)
        layout.addWidget(summary_group)

        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout(progress_group)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimumHeight(22)
        progress_layout.addWidget(self.progress_bar)
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMinimumHeight(200)
        progress_layout.addWidget(self.status_text)
        layout.addWidget(progress_group)

        self.review_btn = QPushButton("Start Review")
        self.review_btn.setMinimumHeight(48)
        self.review_btn.clicked.connect(self._start_review)
        layout.addWidget(self.review_btn)
        layout.addStretch()
        return w

    def _create_results_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        layout.addWidget(self._step_title("Step 4: Results"))
        self.summary_card_values = {}
        self.summary_card_subtitles = {}
        cards_widget = QWidget()
        cards_layout = QGridLayout(cards_widget)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setHorizontalSpacing(10)
        cards_layout.setVerticalSpacing(10)

        metric_cards = [
            ("issues", "Total Issues", "#1f6feb"),
            ("critical", "Critical", "#b32d2e"),
            ("high", "High", "#cf222e"),
            ("medium", "Medium", "#9a6700"),
            ("low", "Low", "#1a7f37"),
            ("passed", "Passed", "#1a7f37"),
            ("failed", "Failed", "#cf222e"),
            ("warnings", "Warnings", "#9a6700"),
            ("not_applicable", "N/A", "#6e7781"),
            ("manual", "Manual", "#57606a"),
            ("plugin_check_errors", "Plugin Check Errors", "#b32d2e"),
            ("plugin_check_warnings", "Plugin Check Warnings", "#9a6700"),
        ]

        for idx, (key, title, accent) in enumerate(metric_cards):
            card = self._create_metric_card(key, title, accent)
            cards_layout.addWidget(card, idx // 4, idx % 4)
        for col in range(4):
            cards_layout.setColumnStretch(col, 1)
        layout.addWidget(cards_widget)

        self.results_summary = QLabel()
        self.results_summary.setWordWrap(True)
        self.results_summary.setStyleSheet(
            "background: #ffffff; padding: 10px 12px; border-radius: 6px; "
            "border: 1px solid #d8dee4; color: #57606a;"
        )
        layout.addWidget(self.results_summary)

        splitter = QSplitter(Qt.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("Category Checklist"))
        self.category_tree = QTreeWidget()
        self.category_tree.setHeaderLabels(["Category / Check", "Status"])
        self.category_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.category_tree.itemSelectionChanged.connect(self._on_category_selected)
        left_layout.addWidget(self.category_tree)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("Details && Review Summary"))
        self.analysis_detail_text = QTextEdit()
        self.analysis_detail_text.setReadOnly(True)
        self.analysis_detail_text.setMinimumHeight(120)
        right_layout.addWidget(self.analysis_detail_text)

        self.issues_table = QTableWidget()
        self.issues_table.setColumnCount(5)
        self.issues_table.setHorizontalHeaderLabels(
            ["Severity", "Category", "Title", "File", "Line"]
        )
        self.issues_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.issues_table.setAlternatingRowColors(True)
        right_layout.addWidget(self.issues_table)
        splitter.addWidget(right)
        splitter.setSizes([480, 720])
        layout.addWidget(splitter)

        export_row = QHBoxLayout()
        for label, handler in [
            ("Export HTML", self._export_html),
            ("Export JSON", self._export_json),
            ("Copy Codex Prompt", self._copy_codex_prompt),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(handler)
            btn.setMinimumHeight(38)
            export_row.addWidget(btn)
        layout.addLayout(export_row)
        return w

    def _step_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        f = QFont()
        f.setPointSize(13)
        f.setBold(True)
        lbl.setFont(f)
        return lbl

    def _hint(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #666;")
        lbl.setWordWrap(True)
        return lbl

    def _create_metric_card(self, key: str, title: str, accent: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            f"""
            QFrame {{
                background: #ffffff;
                border: 1px solid #d8dee4;
                border-left: 4px solid {accent};
                border-radius: 6px;
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
            """
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(4)

        title_label = QLabel(title.upper())
        title_label.setStyleSheet("color: #57606a; font-size: 11px; font-weight: 700;")
        card_layout.addWidget(title_label)

        value_label = QLabel("0")
        value_font = QFont()
        value_font.setPointSize(20)
        value_font.setBold(True)
        value_label.setFont(value_font)
        value_label.setStyleSheet("color: #1f2328;")
        card_layout.addWidget(value_label)

        subtitle_label = QLabel("")
        subtitle_label.setWordWrap(True)
        subtitle_label.setStyleSheet("color: #6e7781; font-size: 11px;")
        card_layout.addWidget(subtitle_label)

        self.summary_card_values[key] = value_label
        self.summary_card_subtitles[key] = subtitle_label
        return card

    def _set_metric_card(self, key: str, value, subtitle: str = ""):
        if key in self.summary_card_values:
            self.summary_card_values[key].setText(str(value))
            self.summary_card_subtitles[key].setText(subtitle)

    def _open_settings(self):
        dlg = SettingsDialog(self.settings, self)
        dlg.exec()

    def _browse_plugin_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select Plugin Folder")
        if path:
            self.plugin_path_input.setText(path)

    def _browse_plugin_zip(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Plugin ZIP", "", "ZIP Archives (*.zip)"
        )
        if path:
            self.plugin_path_input.setText(path)

    def _load_plugin(self):
        path = self.plugin_path_input.text().strip()
        if not path:
            QMessageBox.warning(self, "Error", "Select a plugin folder or ZIP file.")
            return

        if self.plugin_detector:
            self.plugin_detector.cleanup()

        detector = PluginDetector(path)
        success, metadata, error = detector.detect()
        if not success or not metadata:
            detector.cleanup()
            QMessageBox.critical(self, "Error", f"Failed to load plugin:\n{error}")
            return

        self.plugin_detector = detector
        self.plugin = metadata
        self.settings.set("last_plugin_path", path)
        self._display_plugin_info()

        site = self.localwp_validator.find_site_for_plugin(metadata.root_path)
        if site:
            idx = self.site_combo.findText(site.name)
            if idx >= 0:
                self.site_combo.setCurrentIndex(idx)
            self.site = site
            self._display_site_info()
            QMessageBox.information(
                self, "Plugin Loaded",
                f"Loaded {metadata.name} v{metadata.version}\n\n"
                f"Auto-detected LocalWP site: {site.name}",
            )
        else:
            QMessageBox.information(
                self, "Plugin Loaded",
                f"Loaded {metadata.name} v{metadata.version}\n\nSelect a LocalWP site to continue.",
            )

    def _display_plugin_info(self):
        if not self.plugin:
            return
        p = self.plugin
        requires = ", ".join(p.requires_plugins) if p.requires_plugins else "None"
        self.plugin_info_text.setText(
            f"Name: {p.name}\n"
            f"Version: {p.version}\n"
            f"Stable Tag: {p.stable_tag or '-'}\n"
            f"Text Domain: {p.text_domain or '-'}\n"
            f"Requires PHP: {p.requires_php}\n"
            f"Requires WordPress: {p.requires_wp}\n"
            f"Requires Plugins: {requires}\n"
            f"WooCommerce: {'Yes' if p.woo_compatible else 'No'}\n"
            f"Main File: {p.main_file}\n"
            f"Root Path: {p.root_path}"
        )

    def _refresh_sites(self):
        self.localwp_validator.refresh_sites()
        self.site_combo.blockSignals(True)
        self.site_combo.clear()
        for site in self.localwp_validator.get_available_sites():
            self.site_combo.addItem(site["name"], site["path"])
        self.site_combo.blockSignals(False)
        if self.site_combo.count() > 0:
            self._on_site_changed()

    def _on_site_changed(self):
        if self.site_combo.currentIndex() < 0:
            return
        path = self.site_combo.currentData()
        site = self.localwp_validator.select_site_by_path(path)
        if site:
            self.site = site
            self.settings.set("last_site_path", site.path)
            self._display_site_info()

    def _display_site_info(self):
        if not self.site:
            return
        s = self.site
        self.site_info_text.setText(
            f"Site: {s.name}\n"
            f"URL: {s.wp_url or '-'}\n"
            f"Path: {s.path}\n"
            f"WordPress: {s.wordpress_version or '-'}\n"
            f"PHP: {s.php_version or '-'}\n"
            f"Valid: {'Yes' if s.is_valid else 'Not validated'}"
        )

    def _browse_site(self):
        path = QFileDialog.getExistingDirectory(self, "Select WordPress Root (app/public)")
        if path:
            self.site_path_input.setText(path)
            site = self.localwp_validator.select_site_by_path(path)
            if site:
                self.site = site
                self._display_site_info()

    def _validate_site(self):
        path = self.site_path_input.text().strip() or (
            self.site.path if self.site else ""
        )
        if not path:
            QMessageBox.warning(self, "Error", "Select a site path first.")
            return

        site = self.localwp_validator.select_site_by_path(path)
        if not site:
            QMessageBox.critical(self, "Invalid", "Path is not a valid WordPress root.")
            return

        ok, msg = self.localwp_validator.validate_site(site, use_wp_cli=True)
        self.site = site
        self._display_site_info()

        if ok:
            QMessageBox.information(self, "Site Valid", f"{msg}\n\nWP-CLI checks completed where available.")
        else:
            QMessageBox.warning(self, "Validation Issue", msg)

    def _start_review(self):
        if not self.plugin:
            QMessageBox.warning(self, "Error", "Load a plugin first.")
            return
        if not self.site:
            QMessageBox.warning(self, "Error", "Select a LocalWP site first.")
            return

        self.review_summary_text.setText(
            f"Plugin: {self.plugin.name} v{self.plugin.version}\n"
            f"Site: {self.site.name} ({self.site.wp_url})\n"
            f"Checks: Plugin Check + deterministic static rules\n"
            f"Summary: deterministic local analysis"
        )

        self.review_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_text.clear()

        self.worker = ReviewWorker(self.plugin, self.site, self.settings)
        self.worker.progress.connect(self._on_progress)
        self.worker.progress_value.connect(self.progress_bar.setValue)
        self.worker.finished.connect(self._on_review_finished)
        self.worker.error.connect(self._on_review_error)
        self.worker.start()

    def _on_progress(self, message: str):
        self.status_text.append(message)
        self.status_text.moveCursor(QTextCursor.End)

    def _on_review_finished(self, result: FullReviewResult):
        self.full_result = result
        self.review_btn.setEnabled(True)
        self._display_results()
        self.current_page = 3
        self.stacked.setCurrentIndex(3)
        self._update_nav_buttons()

    def _on_review_error(self, error: str):
        self.status_text.append(f"ERROR: {error}")
        self.review_btn.setEnabled(True)
        QMessageBox.critical(self, "Review Error", error)

    def _display_results(self):
        if not self.full_result:
            return

        review = self.full_result.review
        checklist = self.full_result.checklist
        counts = review.issue_count_by_severity
        skipped = sum(cat.skipped for cat in checklist.all_category_results)
        not_applicable = sum(cat.not_applicable for cat in checklist.all_category_results)

        self._set_metric_card("issues", len(review.all_issues), "Plugin Check + static findings")
        self._set_metric_card("critical", counts["critical"], "Release-blocking risk")
        self._set_metric_card("high", counts["high"], "Fix before handoff")
        self._set_metric_card("medium", counts["medium"], "Needs review")
        self._set_metric_card("low", counts["low"], "Cleanup / polish")
        self._set_metric_card("passed", checklist.total_passed, f"of {checklist.total_checks} checks")
        self._set_metric_card("failed", checklist.total_failed, "Checklist topics with failures")
        self._set_metric_card("warnings", checklist.total_warnings, "Review or confirm")
        self._set_metric_card("not_applicable", not_applicable, "No matching code surface")
        self._set_metric_card("manual", skipped, "Runtime/manual verification")
        self._set_metric_card("plugin_check_errors", len(review.plugin_check.errors), "Official Plugin Check")
        self._set_metric_card("plugin_check_warnings", len(review.plugin_check.warnings), "Official Plugin Check")

        self.results_summary.setText(
            f"<b>{review.plugin.name}</b> v{review.plugin.version} reviewed with "
            f"{self.full_result.summary_engine}. "
            f"Checklist coverage: {checklist.total_passed}/{checklist.total_checks} passed; "
            f"{not_applicable} not applicable; {skipped} manual/runtime."
        )

        self.category_tree.clear()
        for cat_result in checklist.all_category_results:
            cat_item = QTreeWidgetItem([
                f"{cat_result.category_name} ({cat_result.passed}/{cat_result.total} passed)",
                "",
            ])
            cat_item.setData(0, Qt.UserRole, cat_result)
            self.category_tree.addTopLevelItem(cat_item)

            for check in cat_result.checks:
                if (
                    check.status == CheckStatus.NOT_APPLICABLE
                    and not self.settings.get("show_not_applicable", True)
                ):
                    continue
                child = QTreeWidgetItem([check.name, check.status.value.upper()])
                child.setData(0, Qt.UserRole, check)
                child.setForeground(1, QColor(STATUS_COLORS.get(check.status, "#333")))
                details = "\n".join(check.details) if check.details else check.message
                child.setToolTip(0, details)
                cat_item.addChild(child)

                # Add individual issues as sub-items under the check/topic
                for issue in check.issues:
                    loc = f"{issue.file_path or 'unknown'}{f':{issue.line_number}' if issue.line_number else ''}"
                    issue_title = f"[{issue.severity.value.upper()}] {issue.title} ({loc})"
                    issue_child = QTreeWidgetItem([issue_title, ""])
                    issue_child.setData(0, Qt.UserRole, issue)
                    
                    sev_colors = {
                        "critical": "#b32d2e",
                        "high": "#dba617",
                        "medium": "#996800",
                        "low": "#00a32a",
                        "info": "#757575",
                    }
                    color_hex = sev_colors.get(issue.severity.value, "#333")
                    issue_child.setForeground(0, QColor(color_hex))
                    issue_child.setToolTip(0, f"Description: {issue.description}\nCode: {issue.code_snippet or '-'}\nSuggestion: {issue.suggestion or '-'}")
                    child.addChild(issue_child)

            cat_item.setExpanded(cat_result.failed > 0 or cat_result.warnings > 0)

        self.issues_table.setRowCount(0)
        for issue in review.all_issues:
            row = self.issues_table.rowCount()
            self.issues_table.insertRow(row)
            self.issues_table.setItem(row, 0, QTableWidgetItem(issue.severity.value.upper()))
            self.issues_table.setItem(row, 1, QTableWidgetItem(issue.category.value))
            self.issues_table.setItem(row, 2, QTableWidgetItem(issue.title))
            self.issues_table.setItem(row, 3, QTableWidgetItem(issue.file_path or "-"))
            self.issues_table.setItem(row, 4, QTableWidgetItem(str(issue.line_number or "-")))

        self.analysis_detail_text.setText(review.analysis_summary or "No summary generated.")

    def _on_category_selected(self):
        items = self.category_tree.selectedItems()
        if not items:
            return
        item = items[0]
        data = item.data(0, Qt.UserRole)
        
        from models import CategoryResult, CategoryCheck, ReviewIssue
        
        if isinstance(data, CategoryResult):
            lines = [f"## Category: {data.category_name}\n"]
            for check in data.checks:
                lines.append(f"### {check.name} [{check.status.value.upper()}]")
                lines.append(f"Status: {check.message}\n")
                if check.issues:
                    lines.append(f"Discovered Issues ({len(check.issues)}):")
                    for issue in check.issues:
                        lines.append(f"- [{issue.severity.value.upper()}] {issue.title}")
                        lines.append(f"  File: {issue.file_path or 'unknown'}:{issue.line_number or '-'}")
                    lines.append("")
            self.analysis_detail_text.setText("\n".join(lines))
            
        elif isinstance(data, CategoryCheck):
            lines = [
                f"## Check Topic: {data.name}",
                f"Status: **{data.status.value.upper()}** ({data.message})",
                f"Severity: {data.severity}\n",
            ]
            if data.issues:
                lines.append("### Discovered Issues:")
                for idx, issue in enumerate(data.issues, 1):
                    lines.append(f"{idx}. **[{issue.severity.value.upper()}] {issue.title}**")
                    lines.append(f"   - **File:** `{issue.file_path or 'unknown'}`{f' line {issue.line_number}' if issue.line_number else ''}")
                    lines.append(f"   - **Description:** {issue.description}")
                    if issue.code_snippet:
                        lines.append(f"   - **Code:** `{issue.code_snippet.strip()}`")
                    if issue.suggestion:
                        lines.append(f"   - **Suggested Fix:** {issue.suggestion}")
                    lines.append("")
            else:
                lines.append("No issues found for this check.")
            self.analysis_detail_text.setText("\n".join(lines))
            
        elif isinstance(data, ReviewIssue):
            lines = [
                f"## Issue: {data.title}",
                f"Severity: **{data.severity.value.upper()}**",
                f"Category: {data.category.value}",
                f"File: `{data.file_path or 'unknown'}`{f' line {data.line_number}' if data.line_number else ''}\n",
                f"### Description:",
                data.description,
                "",
            ]
            if data.code_snippet:
                lines.append("### Code Snippet:")
                lines.append(f"```php\n{data.code_snippet.strip()}\n```\n")
            if data.suggestion:
                lines.append("### Suggested Fix:")
                lines.append(data.suggestion)
            self.analysis_detail_text.setText("\n".join(lines))

    def _export_html(self):
        if not self.full_result:
            QMessageBox.warning(self, "Error", "No results to export.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save HTML Report", "", "HTML (*.html)")
        if path:
            ReportGenerator(self.full_result.review, self.full_result.checklist).generate_html_report(path)
            QMessageBox.information(self, "Saved", f"Report saved to:\n{path}")

    def _export_json(self):
        if not self.full_result:
            QMessageBox.warning(self, "Error", "No results to export.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save JSON Report", "", "JSON (*.json)")
        if path:
            ReportGenerator(self.full_result.review, self.full_result.checklist).generate_json_report(path)
            QMessageBox.information(self, "Saved", f"JSON saved to:\n{path}")

    def _copy_codex_prompt(self):
        if not self.full_result:
            QMessageBox.warning(self, "Error", "No results available.")
            return
        prompt = ReportGenerator(self.full_result.review, self.full_result.checklist).generate_codex_prompt()
        QApplication.clipboard().setText(prompt)
        QMessageBox.information(self, "Copied", "Codex fix prompt copied to clipboard.")

    def _go_back(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.stacked.setCurrentIndex(self.current_page)
            self._update_nav_buttons()

    def _go_next(self):
        if self.current_page == 0 and not self.plugin:
            QMessageBox.warning(self, "Error", "Load a plugin first.")
            return
        if self.current_page == 1 and not self.site:
            QMessageBox.warning(self, "Error", "Select a site first.")
            return
        if self.current_page == 2:
            self._start_review()
            return
        if self.current_page < 3:
            self.current_page += 1
            self.stacked.setCurrentIndex(self.current_page)
            self._update_nav_buttons()

    def _update_nav_buttons(self):
        self.prev_btn.setEnabled(self.current_page > 0)
        labels = ["Next", "Next", "Start Review", "Done"]
        self.next_btn.setText(labels[self.current_page])
        self.next_btn.setEnabled(self.current_page < 3)

    def _apply_styling(self):
        self.setStyleSheet("""
            QMainWindow { background: #f6f7f9; }
            QWidget { font-size: 13px; }
            QLabel { color: #1f2328; }
            QPushButton {
                background: #1f6feb; color: white; border: 1px solid #1f6feb;
                border-radius: 5px; padding: 8px 16px; font-weight: 600;
            }
            QPushButton:hover { background: #175bc2; border-color: #175bc2; }
            QPushButton:disabled { background: #d0d7de; border-color: #d0d7de; color: #57606a; }
            QLineEdit, QTextEdit, QComboBox, QTreeWidget, QTableWidget {
                border: 1px solid #d0d7de; border-radius: 5px;
                padding: 6px; background: #ffffff; color: #1f2328;
                selection-background-color: #dbeafe;
                selection-color: #111827;
            }
            QTreeWidget::item, QTableWidget::item { padding: 4px; }
            QTreeWidget::item:selected, QTableWidget::item:selected {
                background: #dbeafe; color: #111827;
            }
            QGroupBox {
                border: 1px solid #d8dee4; border-radius: 6px;
                margin-top: 10px; padding: 14px 10px 10px 10px;
                background: #ffffff; font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin; left: 10px; padding: 0 6px;
                color: #24292f; background: #f6f7f9;
            }
            QHeaderView::section {
                background: #eef2f7; padding: 8px; border: none;
                border-right: 1px solid #d8dee4; font-weight: 600;
            }
            QProgressBar {
                border: 1px solid #d0d7de; border-radius: 5px; background: #eaeef2;
                text-align: center; color: #24292f;
            }
            QProgressBar::chunk { background: #1f6feb; border-radius: 4px; }
        """)

    def closeEvent(self, event):
        """Clean up extracted ZIP files when the application closes."""
        if self.plugin_detector:
            self.plugin_detector.cleanup()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("WP Plugin Review Assistant")
    window = WPPluginReviewAssistant()
    window.show()
    sys.exit(app.exec())
