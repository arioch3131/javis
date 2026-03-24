# ai_content_classifier/views/widgets/settings_view.py
"""
Dynamically generated settings dialog for the application.
"""

from ai_content_classifier.controllers.llm_controller import LLMController
from ai_content_classifier.models.config_models import ConfigKey
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QWidget,
)
from ai_content_classifier.services.config_service import ConfigService
from ai_content_classifier.services.i18n.i18n_service import get_i18n_service, tr
from ai_content_classifier.views.widgets.base.action_bar import ActionBar
from ai_content_classifier.views.widgets.base.themed_dialog import ThemedDialog


class SettingsView(ThemedDialog):
    """
    A dynamically generated dialog for configuring all application settings.
    """

    test_llm_connection_requested = pyqtSignal(str, QObject)

    def __init__(
        self, config_service: ConfigService, llm_controller: LLMController, parent=None
    ):
        self.config_service = config_service
        self.llm_controller = llm_controller
        self.input_widgets = {}  # Initialize input_widgets here
        self._language_combo = None
        self._language_codes: list[str] = []
        super().__init__(
            parent=parent,
            title=tr("settings.title", "Application Settings"),
            description=tr(
                "settings.description", "Configure all application preferences."
            ),
            modal=True,
        )
        self.setMinimumWidth(700)
        self._create_tabs_and_widgets()  # Call this from init to populate tabs immediately

    def create_footer(self):
        """
        Override ThemedDialog default footer.
        SettingsView provides its own Save/Cancel action bar at the bottom.
        """
        return None

    def _create_tabs_and_widgets(self):
        self.tab_widget = QTabWidget()
        self.main_layout.addWidget(self.tab_widget)

        all_settings = self.config_service.get_all_settings()

        for category_name, settings_in_category in all_settings.items():
            category_widget = QWidget()
            form_layout = QFormLayout(category_widget)

            for setting_label, setting_data in settings_in_category.items():
                key = setting_data["key"]
                definition = setting_data["definition"]
                current_value = setting_data["value"]

                # Exposed in dedicated "Language" tab for visibility.
                if key == ConfigKey.LANGUAGE:
                    continue

                widget = None
                if key in [ConfigKey.IMAGE_MODEL, ConfigKey.DOCUMENT_MODEL]:
                    widget = QComboBox()
                    # Models will be populated dynamically after connection test
                    widget.addItem(
                        str(current_value)
                    )  # Add current value as a placeholder
                    widget.setCurrentText(str(current_value))
                elif definition.options:
                    widget = QComboBox()
                    for option in definition.options:
                        widget.addItem(str(option))
                    widget.setCurrentText(str(current_value))
                elif definition.type is bool:
                    widget = QCheckBox()
                    widget.setChecked(current_value)
                elif definition.type is int:
                    widget = QSpinBox()
                    widget.setRange(-999999, 999999)  # Arbitrary large range
                    widget.setValue(current_value)
                elif definition.type is float:
                    widget = QDoubleSpinBox()
                    widget.setRange(-999999.0, 999999.0)
                    widget.setValue(current_value)
                elif definition.type is list:
                    widget = QTextEdit()
                    widget.setPlaceholderText(
                        tr("settings.comma_separated_values", "Comma-separated values")
                    )
                    widget.setText(", ".join(map(str, current_value)))
                    widget.setFixedHeight(50)  # Make it smaller for single line
                else:  # Default to QLineEdit for str and other types
                    widget = QLineEdit()
                    widget.setText(str(current_value))

                if widget:
                    form_layout.addRow(f"{definition.label}:", widget)
                    self.input_widgets[key] = widget

            # Add specific buttons or elements per category
            if category_name == "API":
                test_llm_button = QPushButton(
                    tr("settings.test_llm_connection", "Test LLM Connection")
                )
                test_llm_button.clicked.connect(
                    self._on_test_llm_connection_button_clicked
                )
                form_layout.addRow(test_llm_button)
                self.test_llm_button = test_llm_button

                self.connection_status_label = QLabel(
                    tr(
                        "settings.connection.not_tested",
                        "Connection status: not tested",
                    )
                )
                form_layout.addRow(self.connection_status_label)

            tab_label = tr(f"settings.categories.{category_name}", category_name)
            self.tab_widget.addTab(category_widget, tab_label)

        self._add_language_tab()

        # Add action bar with Save and Cancel buttons
        action_bar = ActionBar()
        self.main_layout.addWidget(action_bar)

        save_button = action_bar.add_action(
            tr("settings.buttons.save", "Save"), self.accept, primary=True
        )
        cancel_button = action_bar.add_action(
            tr("settings.buttons.cancel", "Cancel"), self.reject
        )

        save_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        self.accepted.connect(self.save_settings)

        # Connect LLMController signals
        self.llm_controller.modelsRetrieved.connect(self._on_models_retrieved)
        self.llm_controller.connectionStatusChanged.connect(
            self._on_connection_status_changed
        )

    def _get_widget_for_key(self, config_key):
        """
        Returns an input widget for a configuration key, tolerant to enum identity
        differences caused by mixed import paths.
        """
        widget = self.input_widgets.get(config_key)
        if widget:
            return widget

        key_value = getattr(config_key, "value", str(config_key))
        for stored_key, stored_widget in self.input_widgets.items():
            stored_value = getattr(stored_key, "value", str(stored_key))
            if stored_value == key_value:
                return stored_widget
        return None

    def _on_test_llm_connection_button_clicked(self):
        api_url_widget = self._get_widget_for_key(ConfigKey.API_URL)
        if api_url_widget:
            api_url = api_url_widget.text()
            if not api_url.strip():
                QMessageBox.warning(
                    self,
                    tr("settings.api.missing_title", "Missing API URL"),
                    tr(
                        "settings.api.missing_message",
                        "Please provide an API URL before testing the connection.",
                    ),
                )
                return

            if hasattr(self, "test_llm_button"):
                self.test_llm_button.setEnabled(False)
            if hasattr(self, "connection_status_label"):
                self.connection_status_label.setText(
                    tr("settings.connection.testing", "Connection status: testing...")
                )

            self.llm_controller.test_connection(api_url)
        else:
            QMessageBox.warning(
                self,
                tr("settings.configuration_error_title", "Configuration error"),
                tr(
                    "settings.configuration_error_api_missing",
                    "API URL field not found in settings dialog.",
                ),
            )

    def _on_models_retrieved(self, models: list):
        self.logger.info(f"Models retrieved: {models}")
        image_model_widget = self._get_widget_for_key(ConfigKey.IMAGE_MODEL)
        document_model_widget = self._get_widget_for_key(ConfigKey.DOCUMENT_MODEL)

        if isinstance(image_model_widget, QComboBox):
            image_model_widget.clear()
            image_model_widget.addItems(models)
            current_image_model = self.config_service.get(ConfigKey.IMAGE_MODEL)
            if current_image_model in models:
                image_model_widget.setCurrentText(current_image_model)
            else:
                image_model_widget.setCurrentIndex(
                    0
                )  # Select first model if current not found

        if isinstance(document_model_widget, QComboBox):
            document_model_widget.clear()
            document_model_widget.addItems(models)
            current_document_model = self.config_service.get(ConfigKey.DOCUMENT_MODEL)
            if current_document_model in models:
                document_model_widget.setCurrentText(current_document_model)
            else:
                document_model_widget.setCurrentIndex(
                    0
                )  # Select first model if current not found

    def _on_connection_status_changed(self, success: bool, message: str):
        if hasattr(self, "test_llm_button"):
            self.test_llm_button.setEnabled(True)

        if success:
            self.logger.info(f"LLM Connection successful: {message}")
            if hasattr(self, "connection_status_label"):
                self.connection_status_label.setText(
                    tr("settings.connection.success", "Connection status: success")
                )
            QMessageBox.information(
                self,
                tr("settings.llm_connection_title", "LLM Connection"),
                tr("settings.connection_success_message", "Connection successful.")
                + f"\n\n{message}",
            )
        else:
            self.logger.error(f"LLM Connection failed: {message}")
            if hasattr(self, "connection_status_label"):
                self.connection_status_label.setText(
                    tr("settings.connection.failed", "Connection status: failed")
                )
            QMessageBox.warning(
                self,
                tr("settings.llm_connection_title", "LLM Connection"),
                tr("settings.connection_failed_message", "Connection failed.")
                + f"\n\n{message}",
            )

    def save_settings(self):
        previous_language = self.config_service.get(ConfigKey.LANGUAGE)
        for key, widget in self.input_widgets.items():
            value = None
            if isinstance(widget, QLineEdit):
                value = widget.text()
            elif isinstance(widget, QSpinBox):
                value = widget.value()
            elif isinstance(widget, QDoubleSpinBox):
                value = widget.value()
            elif isinstance(widget, QComboBox):
                value = widget.currentText()
            elif isinstance(widget, QTextEdit):
                value = [
                    item.strip()
                    for item in widget.toPlainText().split(",")
                    if item.strip()
                ]
            elif isinstance(widget, QCheckBox):
                value = widget.isChecked()

            if value is not None:
                self.config_service.set(key, value)

        if self._language_combo is not None:
            idx = self._language_combo.currentIndex()
            if 0 <= idx < len(self._language_codes):
                selected_language = self._language_codes[idx]
                self.config_service.set(ConfigKey.LANGUAGE, selected_language)
                if selected_language != previous_language:
                    get_i18n_service().set_language(selected_language)
                    self._refresh_runtime_language_ui()
                    QMessageBox.information(
                        self,
                        tr("settings.language.changed_title", "Language updated"),
                        tr(
                            "settings.language.changed_message",
                            "Language preference saved. Main menus were refreshed. Some dialogs may need to be reopened.",
                        ),
                    )

    def _add_language_tab(self):
        """Adds a dedicated language tab for better discoverability."""
        language_widget = QWidget()
        layout = QFormLayout(language_widget)

        language_combo = QComboBox()
        language_options = [
            ("en", tr("settings.language.english", "English")),
            ("fr", tr("settings.language.french", "Francais")),
        ]
        for code, label in language_options:
            language_combo.addItem(label)
            self._language_codes.append(code)

        current_language = self.config_service.get(ConfigKey.LANGUAGE)
        try:
            current_index = self._language_codes.index(current_language)
        except ValueError:
            current_index = 0
        language_combo.setCurrentIndex(current_index)

        layout.addRow(tr("settings.language.label", "Language:"), language_combo)
        layout.addRow(
            QLabel(
                tr(
                    "settings.language.help",
                    "Tip: language is saved in settings and will be reused at startup.",
                )
            )
        )

        self._language_combo = language_combo
        self.tab_widget.addTab(language_widget, tr("settings.language.tab", "Language"))

    def _refresh_runtime_language_ui(self) -> None:
        """
        Refresh main UI labels that are safe to recreate at runtime.
        """
        try:
            parent_window = self.parent()
            if not parent_window:
                return

            # Refresh menu and toolbars with current i18n language.
            if hasattr(parent_window, "menu_builder"):
                parent_window.menu_builder.create_menus_and_toolbars()
                if hasattr(parent_window, "connect_menu_handlers"):
                    parent_window.connect_menu_handlers()
        except Exception as exc:
            self.logger.warning(f"Runtime i18n refresh failed: {exc}")
