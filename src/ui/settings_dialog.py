"""Settings dialog for WP Plugin Review Assistant."""
import logging

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from core.settings_manager import SettingsManager


logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """Application settings for review execution."""

    def __init__(self, settings_manager: SettingsManager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.setWindowTitle("Review Settings")
        self.setMinimumWidth(520)
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        scan_group = QGroupBox("Review Pipeline")
        scan_layout = QVBoxLayout(scan_group)

        self.plugin_check_box = QCheckBox("Run WordPress Plugin Check")
        self.plugin_check_box.setToolTip(
            "Uses WP-CLI and the official Plugin Check plugin as the baseline validator."
        )
        scan_layout.addWidget(self.plugin_check_box)

        self.static_analysis_box = QCheckBox("Run deterministic static rules")
        self.static_analysis_box.setToolTip(
            "Runs local deterministic checks for prefixing, loading order, security boundaries, "
            "defensive coding, WooCommerce, release hygiene, and performance risks."
        )
        scan_layout.addWidget(self.static_analysis_box)

        self.show_na_box = QCheckBox("Show not-applicable checks")
        self.show_na_box.setToolTip(
            "Keep absent surfaces visible in the checklist, such as REST checks for plugins "
            "that do not register REST routes."
        )
        scan_layout.addWidget(self.show_na_box)

        note = QLabel(
            "Reports are generated locally from Plugin Check output and deterministic static analysis."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #646970;")
        scan_layout.addWidget(note)

        layout.addWidget(scan_group)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save)
        save_btn.setDefault(True)

        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def _load_settings(self):
        settings = self.settings_manager.settings
        self.plugin_check_box.setChecked(bool(settings.get("run_plugin_check", True)))
        self.static_analysis_box.setChecked(bool(settings.get("run_static_analysis", True)))
        self.show_na_box.setChecked(bool(settings.get("show_not_applicable", True)))

    def _save(self):
        self.settings_manager.set("run_plugin_check", self.plugin_check_box.isChecked())
        self.settings_manager.set("run_static_analysis", self.static_analysis_box.isChecked())
        self.settings_manager.set("show_not_applicable", self.show_na_box.isChecked())
        self.accept()
