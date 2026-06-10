"""Settings dialog for WP Plugin Review Assistant."""
import logging
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QComboBox, QLineEdit, QSpinBox, QCheckBox,
    QPushButton, QLabel, QGroupBox, QMessageBox,
)
from PySide6.QtCore import Qt

from core.settings_manager import SettingsManager
from core.ai_analyzer import AIAnalyzer


logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """Application settings including free local AI options."""

    def __init__(self, settings_manager: SettingsManager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.setWindowTitle("Settings")
        self.setMinimumWidth(480)
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        ai_group = QGroupBox("AI Provider (Free Local Only)")
        form = QFormLayout(ai_group)

        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["Ollama", "LM Studio", "Disabled"])
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        form.addRow("Provider:", self.provider_combo)

        self.api_url_input = QLineEdit()
        form.addRow("API URL:", self.api_url_input)

        self.model_input = QLineEdit()
        form.addRow("Model Name:", self.model_input)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 300)
        self.timeout_spin.setSuffix(" sec")
        form.addRow("AI Timeout:", self.timeout_spin)

        self.context_spin = QSpinBox()
        self.context_spin.setRange(1024, 32768)
        self.context_spin.setSingleStep(1024)
        form.addRow("Max Context:", self.context_spin)

        self.reasoning_check = QCheckBox("Enable AI reasoning summary in reports")
        form.addRow("", self.reasoning_check)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #666; font-size: 12px;")
        form.addRow("Status:", self.status_label)

        layout.addWidget(ai_group)

        btn_layout = QHBoxLayout()
        test_btn = QPushButton("Test Connection")
        test_btn.clicked.connect(self._test_connection)
        btn_layout.addWidget(test_btn)
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
        s = self.settings_manager.settings
        idx = self.provider_combo.findText(s.get("ai_provider", "Ollama"))
        if idx >= 0:
            self.provider_combo.setCurrentIndex(idx)
        self.api_url_input.setText(s.get("api_url", "http://localhost:11434"))
        self.model_input.setText(s.get("model_name", "llama3"))
        self.timeout_spin.setValue(int(s.get("ai_timeout", 30)))
        self.context_spin.setValue(int(s.get("max_context_size", 4096)))
        self.reasoning_check.setChecked(bool(s.get("enable_reasoning", True)))
        self._on_provider_changed(self.provider_combo.currentText())

    def _on_provider_changed(self, provider: str):
        enabled = provider != "Disabled"
        self.api_url_input.setEnabled(enabled)
        self.model_input.setEnabled(enabled)
        self.timeout_spin.setEnabled(enabled)
        self.context_spin.setEnabled(enabled)
        self.reasoning_check.setEnabled(enabled)

        if provider == "Ollama":
            if not self.api_url_input.text() or "1234" in self.api_url_input.text():
                self.api_url_input.setText("http://localhost:11434")
            if not self.model_input.text():
                self.model_input.setText("llama3.2")
        elif provider == "LM Studio":
            if not self.api_url_input.text() or "11434" in self.api_url_input.text():
                self.api_url_input.setText("http://localhost:1234")
            if not self.model_input.text():
                self.model_input.setText("local-model")

        if provider == "Disabled":
            self.status_label.setText("AI disabled - rule-based analysis only")
        else:
            self.status_label.setText(f"Configure {provider} local server")

    def _test_connection(self):
        temp_settings = self._current_settings()
        analyzer = AIAnalyzer(temp_settings)
        if analyzer.is_available():
            models = analyzer.get_installed_models()
            model_list = ", ".join(models[:5]) if models else "connected (no models listed)"
            QMessageBox.information(
                self, "Connection OK",
                f"{temp_settings['ai_provider']} is available.\nModels: {model_list}",
            )
        else:
            QMessageBox.warning(
                self, "Connection Failed",
                f"Could not connect to {temp_settings['ai_provider']} at {temp_settings['api_url']}.\n"
                "The app will still work using rule-based analysis.",
            )

    def _current_settings(self) -> dict:
        return {
            "ai_provider": self.provider_combo.currentText(),
            "api_url": self.api_url_input.text().strip(),
            "model_name": self.model_input.text().strip(),
            "ai_timeout": self.timeout_spin.value(),
            "max_context_size": self.context_spin.value(),
            "enable_reasoning": self.reasoning_check.isChecked(),
        }

    def _save(self):
        for key, value in self._current_settings().items():
            self.settings_manager.set(key, value)
        self.accept()
