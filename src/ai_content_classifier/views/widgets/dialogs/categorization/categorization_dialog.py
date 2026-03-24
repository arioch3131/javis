# views/widgets/dialogs/categorization/categorization_dialog.py
"""
CategorizationDialog - Dialog to configure and run automatic categorization.

Refactored version using the new architecture with base widgets
and reusable components.
"""

from typing import Any, Dict, List

from ai_content_classifier.controllers.llm_controller import LLMController
from ai_content_classifier.services.theme.theme_service import ThemePalette
from PyQt6.QtCore import QSettings, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QLabel,
    QMessageBox,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QToolTip,
    QVBoxLayout,
    QWidget,
)
from ai_content_classifier.views.widgets.base.action_bar import ActionBar
from ai_content_classifier.views.widgets.base.header_section import HeaderSection
from ai_content_classifier.views.widgets.base.themed_dialog import ThemedDialog
from ai_content_classifier.views.widgets.common.category_editor import CategoryEditor


class CategorizationDialog(ThemedDialog):
    """
    Dialog to configure automatic file categorization.

    Uses the new architecture with reusable widgets and built-in validation.
    Lets users configure categories, processing options, and LLM models.
    """

    # Signal emitted when the user launches categorization
    categorization_requested = pyqtSignal(dict)  # Full configuration

    def __init__(
        self,
        file_count: int,
        file_types: Dict[str, int],
        llm_controller: LLMController,
        available_categories: List[str],
        parent=None,
    ):
        # Input data
        self.file_count = file_count
        self.file_types = file_types
        self.llm_controller = llm_controller
        self.available_categories = available_categories

        # Initialize base dialog
        super().__init__(
            parent=parent,
            title="Automatic File Categorization",
            description=f"Configure and launch AI-powered categorization for {file_count} files using advanced machine learning models.",
            modal=True,
        )

        # Specific configuration
        self.resize(800, 700)
        self._fit_to_screen()

        # Timer for improved tooltips
        self.tooltip_timer = QTimer()
        self.tooltip_timer.setSingleShot(True)

        # Flag to prevent duplicate signal connections
        self._signals_connectd = False

        # Load saved settings
        self.load_settings()

    def connect_category_signals(self):
        """Connect CategoryEditor signals after full UI creation."""
        if self._signals_connectd:
            return

        try:
            # RE-ENABLE CategoryEditor signals
            if hasattr(self, "category_editor"):
                self.category_editor.blockSignals(False)

            # CategoryEditor signal connections
            self.category_editor.categories_changed.connect(self.on_categories_changed)
            self._signals_connectd = True
            self.logger.debug("Category editor signals connectd and unblocked")
        except Exception as e:
            self.logger.error(f"Error connecting category signals: {e}")

    def create_header(self) -> QFrame:
        """Create the header with file statistics."""
        # Main header
        header = HeaderSection(
            title="🤖 Automatic File Categorization",
            description=f"Configure and launch AI-powered categorization for {self.file_count} files.",
            parent=self,
        )

        # Add file statistics
        stats_container = QWidget()
        stats_container.setObjectName("fileStatsContainer")
        stats_layout = QGridLayout(stats_container)
        stats_layout.setSpacing(16)
        stats_layout.setContentsMargins(12, 8, 12, 8)

        # Total files
        total_label = QLabel("📁 Total Files")
        total_label.setObjectName("statLabel")
        total_count = QLabel(f"{self.file_count}")
        total_count.setObjectName("statCount")
        stats_layout.addWidget(total_label, 0, 0)
        stats_layout.addWidget(total_count, 0, 1)

        # Per-file-type details
        col = 2
        for file_type, count in self.file_types.items():
            if count > 0:
                # Icon by file type
                if "Image" in file_type:
                    emoji = "🖼️"
                elif "Document" in file_type:
                    emoji = "📄"
                else:
                    emoji = "📁"

                type_label = QLabel(f"{emoji} {file_type}")
                type_label.setObjectName("statLabel")
                type_count = QLabel(f"{count}")
                type_count.setObjectName("statCount")

                stats_layout.addWidget(type_label, 0, col)
                stats_layout.addWidget(type_count, 0, col + 1)
                col += 2

        # Center stats
        stats_layout.setColumnStretch(col, 1)

        # Add to header
        header.add_to_layout(stats_container)

        return header

    def apply_dialog_theme(self, palette: ThemePalette):
        """Apply the dialog theme with readable section headings."""
        super().apply_dialog_theme(palette)
        self.setStyleSheet(
            self.styleSheet()
            + f"""
                QTabWidget#configurationTabs::pane {{
                    border: none;
                    background: transparent;
                }}
                QGroupBox {{
                    margin-top: 16px;
                    padding-top: 14px;
                    font-weight: 600;
                    border: 1px solid {palette.outline};
                    border-radius: 8px;
                    background-color: {palette.surface};
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    left: 12px;
                    padding: 0 6px;
                    color: {palette.on_surface};
                    background-color: {palette.background};
                }}
            """
        )

    def create_content(self) -> QFrame:
        """Create the main dialog content."""
        content = QFrame()
        content.setObjectName("categorizationContent")

        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(20)

        # Tab-based configuration
        self.config_tabs = QTabWidget()
        self.config_tabs.setObjectName("configurationTabs")

        # Categories tab
        categories_tab = self.create_categories_tab()
        self.config_tabs.addTab(categories_tab, "🏷️ Categories")

        # Options tab
        options_tab = self.create_options_tab()
        self.config_tabs.addTab(options_tab, "⚙️ Options")

        # Models tab
        models_tab = self.create_models_tab()
        self.config_tabs.addTab(models_tab, "🧠 AI Models")

        layout.addWidget(self.config_tabs)

        return content

    def create_categories_tab(self) -> QWidget:
        """Create the category management tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Instructions
        instructions_container = QWidget()
        instructions_container.setObjectName("instructionsContainer")
        instructions_layout = QVBoxLayout(instructions_container)
        instructions_layout.setContentsMargins(12, 12, 12, 12)

        instructions_title = QLabel("📝 Category Configuration")
        instructions_title.setObjectName("instructionsTitle")
        instructions_title.setFont(self.create_bold_font(1))
        instructions_layout.addWidget(instructions_title)

        instructions_text = QLabel(
            "Define the categories for file classification. The AI will automatically "
            "choose the most appropriate category for each file based on its content. "
            "Add at least 2 categories to enable categorization."
        )
        instructions_text.setObjectName("instructionsText")
        instructions_text.setWordWrap(True)
        instructions_layout.addWidget(instructions_text)

        layout.addWidget(instructions_container)

        # Reusable category editor
        self.category_editor = CategoryEditor(
            parent=self, title="Categorization Categories"
        )

        # BLOCK SIGNALS during initialization
        self.category_editor.blockSignals(True)

        # Specific configuration
        self.category_editor.set_allow_empty(False)
        self.category_editor.set_max_categories(20)

        # Specialized predefined categories
        specialized_categories = {
            "Work Documents",
            "Personal Files",
            "Photos & Images",
            "Archive",
            "Projects",
            "Reference Materials",
            "Temporary",
            "Financial",
            "Legal",
            "Educational",
            "Entertainment",
        }
        self.category_editor.set_predefined_categories(specialized_categories)

        layout.addWidget(self.category_editor, 1)

        # Load available categories (signals are still blocked)
        if self.available_categories:
            self.category_editor.set_categories(self.available_categories)
        else:
            # Default categories
            default_categories = ["Work", "Personal", "Archive"]
            self.category_editor.set_categories(default_categories)

        # Keep signals blocked; they will be enabled in showEvent()

        return widget

    def create_options_tab(self) -> QWidget:
        """Create the processing options tab."""
        widget = QWidget()

        # Scroll area for options
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(20)

        # === FILE TYPES ===
        file_types_group = QGroupBox("📁 File Types to Process")
        file_types_layout = QVBoxLayout(file_types_group)
        file_types_layout.setSpacing(8)

        self.process_images_cb = QCheckBox("🖼️ Process Images")
        self.process_images_cb.setChecked(True)
        self.process_images_cb.setToolTip(
            "Categorize image files (JPG, PNG, GIF, etc.)"
        )

        self.process_documents_cb = QCheckBox("📄 Process Documents")
        self.process_documents_cb.setChecked(True)
        self.process_documents_cb.setToolTip(
            "Categorize document files (PDF, DOC, TXT, etc.)"
        )

        file_types_layout.addWidget(self.process_images_cb)
        file_types_layout.addWidget(self.process_documents_cb)

        layout.addWidget(file_types_group)

        # === PROCESSING OPTIONS ===
        processing_group = QGroupBox("⚙️ Processing Configuration")
        processing_layout = QGridLayout(processing_group)
        processing_layout.setSpacing(12)

        # Batch size
        batch_label = QLabel("Files per batch:")
        batch_label.setObjectName("optionLabel")

        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(1, 50)
        self.batch_size_spin.setValue(10)
        self.batch_size_spin.setToolTip("Number of files processed simultaneously")

        processing_layout.addWidget(batch_label, 0, 0)
        processing_layout.addWidget(self.batch_size_spin, 0, 1)

        # Confidence threshold
        confidence_label = QLabel("Confidence threshold:")
        confidence_label.setObjectName("optionLabel")

        self.confidence_spin = QSpinBox()
        self.confidence_spin.setRange(1, 100)
        self.confidence_spin.setValue(30)
        self.confidence_spin.setSuffix("%")
        self.confidence_spin.setToolTip(
            "Classifications below this threshold will be marked as uncertain"
        )

        processing_layout.addWidget(confidence_label, 1, 0)
        processing_layout.addWidget(self.confidence_spin, 1, 1)

        layout.addWidget(processing_group)

        # === POST-PROCESSING OPTIONS ===
        post_group = QGroupBox("💾 After Categorization")
        post_layout = QVBoxLayout(post_group)
        post_layout.setSpacing(8)

        self.save_results_cb = QCheckBox("💾 Save results to database")
        self.save_results_cb.setChecked(True)
        self.save_results_cb.setToolTip(
            "Store categorization results in the application database"
        )

        self.show_report_cb = QCheckBox("📊 Show detailed report")
        self.show_report_cb.setChecked(True)
        self.show_report_cb.setToolTip("Display a summary report after categorization")

        self.export_csv_cb = QCheckBox("📄 Export results to CSV")
        self.export_csv_cb.setChecked(False)
        self.export_csv_cb.setToolTip("Create a CSV file with categorization results")

        self.only_uncategorized_cb = QCheckBox("❓ Categorize only unclassified files")
        self.only_uncategorized_cb.setChecked(False)
        self.only_uncategorized_cb.setToolTip("Skip files that already have a category")

        post_layout.addWidget(self.save_results_cb)
        post_layout.addWidget(self.show_report_cb)
        post_layout.addWidget(self.export_csv_cb)
        post_layout.addWidget(self.only_uncategorized_cb)

        layout.addWidget(post_group)

        layout.addStretch()

        scroll.setWidget(content_widget)

        # Main layout for the tab
        tab_layout = QVBoxLayout(widget)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll)

        return widget

    def create_models_tab(self) -> QWidget:
        """Create the AI model configuration tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(20)

        # Instructions
        info_container = QWidget()
        info_container.setObjectName("modelInfoContainer")
        info_layout = QVBoxLayout(info_container)
        info_layout.setContentsMargins(12, 12, 12, 12)

        info_title = QLabel("🧠 AI Model Configuration")
        info_title.setFont(self.create_bold_font(1))
        info_layout.addWidget(info_title)

        info_text = QLabel(
            "Select which AI models to use for different file types. "
            "Different models may provide varying accuracy and speed. "
            "'Auto' mode will choose the best available model automatically."
        )
        info_text.setWordWrap(True)
        info_layout.addWidget(info_text)

        layout.addWidget(info_container)

        # Model configuration
        models_group = QGroupBox("🤖 Model Selection")
        models_layout = QGridLayout(models_group)
        models_layout.setSpacing(12)

        # Model for images
        image_model_label = QLabel("Image Analysis Model:")
        image_model_label.setObjectName("optionLabel")

        self.image_model_combo = QComboBox()
        self.image_model_combo.setObjectName("imageModelCombo")

        # Model for documents
        doc_model_label = QLabel("Document Analysis Model:")
        doc_model_label.setObjectName("optionLabel")

        self.document_model_combo = QComboBox()
        self.document_model_combo.setObjectName("documentModelCombo")

        models_layout.addWidget(image_model_label, 0, 0)
        models_layout.addWidget(self.image_model_combo, 0, 1)
        models_layout.addWidget(doc_model_label, 1, 0)
        models_layout.addWidget(self.document_model_combo, 1, 1)

        # Create the status label before loading models
        self.model_status_label = QLabel("Loading models...")
        self.model_status_label.setObjectName("modelStatusLabel")
        models_layout.addWidget(self.model_status_label, 2, 0, 1, 2)

        layout.addWidget(models_group)

        # Advanced options
        advanced_group = QGroupBox("🔧 Advanced Options")
        advanced_layout = QVBoxLayout(advanced_group)
        advanced_layout.setSpacing(8)

        self.enable_fallback_cb = QCheckBox("🔄 Enable model fallback")
        self.enable_fallback_cb.setChecked(True)
        self.enable_fallback_cb.setToolTip(
            "Automatically try alternative models if primary model fails"
        )

        self.cache_results_cb = QCheckBox("💾 Cache model results")
        self.cache_results_cb.setChecked(True)
        self.cache_results_cb.setToolTip(
            "Store model results to avoid reprocessing identical content"
        )

        advanced_layout.addWidget(self.enable_fallback_cb)
        advanced_layout.addWidget(self.cache_results_cb)

        layout.addWidget(advanced_group)

        # Load available models (after creating the label)
        self.load_available_models()

        layout.addStretch()

        return widget

    def create_footer(self) -> QFrame:
        """Create the footer with action buttons."""
        # Use ActionBar for buttons
        action_bar = ActionBar(self, alignment="right")

        # Main action buttons
        action_bar.add_action(
            "👁️ Preview (5 files)", self.preview_categorization, "previewButton"
        )
        action_bar.add_stretch()
        action_bar.add_action("❌ Cancel", self.reject, "cancelButton")
        action_bar.add_action(
            "🚀 Start Categorization",
            self.start_categorization,
            "startButton",
            primary=True,
        )

        # References for later updates
        self.start_button = action_bar.get_action_button("startButton")
        self.preview_button = action_bar.get_action_button("previewButton")

        # Initial state (if categories are already loaded)
        if hasattr(self, "category_editor"):
            self.update_button_states()

        return action_bar

    def load_available_models(self):
        """Load available AI models with robust error handling."""
        try:
            # Ensure widgets exist before using them
            if not hasattr(self, "model_status_label"):
                self.logger.warning(
                    "model_status_label not created yet, skipping model loading"
                )
                return

            if not hasattr(self, "image_model_combo") or not hasattr(
                self, "document_model_combo"
            ):
                self.logger.warning(
                    "Model combo boxes not created yet, skipping model loading"
                )
                return

            # Set status to loading state
            self.model_status_label.setText("🔄 Loading available models...")

            # Load models through the controller
            available_models = self.llm_controller.get_available_models()

            if available_models:
                models_to_display = ["Auto (recommended)"] + available_models

                # Add items to combo boxes
                self.image_model_combo.addItems(models_to_display)
                self.document_model_combo.addItems(models_to_display)

                # Success status
                self.model_status_label.setText(
                    f"✅ {len(available_models)} models available"
                )
                self.model_status_label.setStyleSheet(
                    "color: green; font-weight: bold;"
                )

                self.logger.info(
                    f"Loaded {len(available_models)} LLM models successfully: {available_models}"
                )
            else:
                # No model available
                fallback_items = ["Auto (recommended)", "No models available"]
                self.image_model_combo.addItems(fallback_items)
                self.document_model_combo.addItems(fallback_items)

                self.model_status_label.setText("⚠️ No models available")
                self.model_status_label.setStyleSheet(
                    "color: orange; font-weight: bold;"
                )

                self.logger.warning("No LLM models available")

        except Exception as e:
            self.logger.error(f"Could not load LLM models: {e}")

            # Robust error handling with widget guards
            error_items = ["Auto (recommended)", "Error - see logs"]

            try:
                # Check widget existence before mutating them
                if hasattr(self, "image_model_combo"):
                    self.image_model_combo.clear()  # Clear first
                    self.image_model_combo.addItems(error_items)
                    self.image_model_combo.setEnabled(False)

                if hasattr(self, "document_model_combo"):
                    self.document_model_combo.clear()  # Clear first
                    self.document_model_combo.addItems(error_items)
                    self.document_model_combo.setEnabled(False)

                if hasattr(self, "model_status_label"):
                    self.model_status_label.setText(
                        "❌ Error loading models - check logs"
                    )
                    self.model_status_label.setStyleSheet(
                        "color: red; font-weight: bold;"
                    )

            except Exception as nested_error:
                self.logger.error(f"Error in error handling for models: {nested_error}")
                # If error handling itself fails, avoid cascading crashes

    def on_categories_changed(self, categories: List[str]):
        """Called when categories change."""
        try:
            self.logger.debug(f"Categories changed: {len(categories)} categories")
            self.update_button_states()
        except Exception as e:
            self.logger.error(f"Error in on_categories_changed: {e}")
            # Do not re-raise to avoid cascading crashes

    def update_button_states(self):
        """Update button states based on current configuration."""
        # Strong guard: verify required attributes exist
        try:
            start_button = getattr(self, "start_button", None)
            preview_button = getattr(self, "preview_button", None)
            category_editor = getattr(self, "category_editor", None)

            # Exit early if a critical element is missing
            if not start_button or not preview_button or not category_editor:
                self.logger.debug(
                    "Buttons or category editor not ready yet, skipping update"
                )
                return

            categories = self.category_editor.get_categories()
            category_count = len(categories)

            # Enable buttons based on number of categories
            buttons_enabled = category_count >= 2
            self.start_button.setEnabled(buttons_enabled)
            self.preview_button.setEnabled(buttons_enabled)

            # Informative tooltips
            if category_count == 0:
                tooltip = (
                    "❌ No categories defined. Add at least 2 categories to start."
                )
            elif category_count == 1:
                tooltip = (
                    "⚠️ Only 1 category defined. Add at least 1 more category to start."
                )
            else:
                estimated_time = self.file_count * 2  # 2 seconds per file
                time_text = (
                    f"{estimated_time // 60}m{estimated_time % 60}s"
                    if estimated_time >= 60
                    else f"{estimated_time}s"
                )
                tooltip = (
                    f"✅ Ready to categorize {self.file_count} files into {category_count} categories\n"
                    f"Estimated time: ~{time_text}"
                )

            self.start_button.setToolTip(tooltip)
            self.preview_button.setToolTip(
                f"Test categorization on 5 random files\n{tooltip}"
            )

            self.logger.debug(
                f"Button states updated: {category_count} categories, enabled={buttons_enabled}"
            )

        except Exception as e:
            self.logger.error(f"Error updating button states: {e}")
            # On error, fail safely instead of crashing

    def validate_configuration(self) -> tuple[bool, str]:
        """Validate current configuration."""
        errors = []

        # Check categories
        categories = self.category_editor.get_categories()
        if len(categories) < 2:
            errors.append("At least 2 categories are required for categorization")

        # Check file types
        if (
            not self.process_images_cb.isChecked()
            and not self.process_documents_cb.isChecked()
        ):
            errors.append("At least one file type must be selected for processing")

        # Check models
        if (
            not self.image_model_combo.isEnabled()
            and not self.document_model_combo.isEnabled()
        ):
            errors.append("No AI models available - check your configuration")

        is_valid = len(errors) == 0
        error_message = "; ".join(errors) if errors else ""

        return is_valid, error_message

    def get_configuration(self) -> Dict[str, Any]:
        """Return the full categorization configuration."""
        categories = self.category_editor.get_categories()

        config = {
            # Categories
            "categories": categories,
            "category_count": len(categories),
            # File types
            "process_images": self.process_images_cb.isChecked(),
            "process_documents": self.process_documents_cb.isChecked(),
            # Processing options
            "batch_size": self.batch_size_spin.value(),
            "confidence_threshold": self.confidence_spin.value() / 100.0,
            # AI models
            "image_model": self.image_model_combo.currentText(),
            "document_model": self.document_model_combo.currentText(),
            "enable_fallback": self.enable_fallback_cb.isChecked(),
            "cache_results": self.cache_results_cb.isChecked(),
            # Post-processing options
            "save_results": self.save_results_cb.isChecked(),
            "show_report": self.show_report_cb.isChecked(),
            "export_csv": self.export_csv_cb.isChecked(),
            "only_uncategorized": self.only_uncategorized_cb.isChecked(),
            # Metadata
            "total_files": self.file_count,
            "file_types": self.file_types,
        }

        return config

    def set_configuration(self, config: Dict[str, Any]):
        """Set dialog configuration."""
        try:
            # Categories
            if "categories" in config:
                self.category_editor.set_categories(config["categories"])

            # File types
            if "process_images" in config:
                self.process_images_cb.setChecked(config["process_images"])
            if "process_documents" in config:
                self.process_documents_cb.setChecked(config["process_documents"])

            # Processing options
            if "batch_size" in config:
                self.batch_size_spin.setValue(config["batch_size"])
            if "confidence_threshold" in config:
                self.confidence_spin.setValue(int(config["confidence_threshold"] * 100))

            # Models
            if "image_model" in config:
                index = self.image_model_combo.findText(config["image_model"])
                if index >= 0:
                    self.image_model_combo.setCurrentIndex(index)

            if "document_model" in config:
                index = self.document_model_combo.findText(config["document_model"])
                if index >= 0:
                    self.document_model_combo.setCurrentIndex(index)

            # Advanced options
            if "enable_fallback" in config:
                self.enable_fallback_cb.setChecked(config["enable_fallback"])
            if "cache_results" in config:
                self.cache_results_cb.setChecked(config["cache_results"])

            # Post-processing
            if "save_results" in config:
                self.save_results_cb.setChecked(config["save_results"])
            if "show_report" in config:
                self.show_report_cb.setChecked(config["show_report"])
            if "export_csv" in config:
                self.export_csv_cb.setChecked(config["export_csv"])
            if "only_uncategorized" in config:
                self.only_uncategorized_cb.setChecked(config["only_uncategorized"])

        except Exception as e:
            self.logger.error(f"Error setting configuration: {e}")

    def preview_categorization(self):
        """Run a preview on a small subset of files."""
        is_valid, error_message = self.validate_configuration()
        if not is_valid:
            self.show_validation_error(error_message)
            return

        config = self.get_configuration()
        config["preview_mode"] = True
        config["preview_count"] = 5

        self.logger.info(
            f"Preview categorization requested with {config['category_count']} categories"
        )
        self.categorization_requested.emit(config)

    def start_categorization(self):
        """Run full categorization."""
        is_valid, error_message = self.validate_configuration()
        if not is_valid:
            self.show_validation_error(error_message)
            return

        config = self.get_configuration()

        if config.get("save_results", True) and not config.get(
            "only_uncategorized", False
        ):
            reply = QMessageBox.question(
                self,
                "Overwrite existing categories?",
                "This will re-categorize files that already have a category and overwrite their current categorization.\n\n"
                "Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        # Confirmation for large batches
        if self.file_count > 100:
            estimated_time = self.file_count * 2
            time_text = (
                f"{estimated_time // 60}m{estimated_time % 60}s"
                if estimated_time >= 60
                else f"{estimated_time}s"
            )

            reply = QMessageBox.question(
                self,
                "🚀 Confirm Categorization",
                f"About to categorize {self.file_count} files into {config['category_count']} categories.\n\n"
                f"Estimated time: ~{time_text}\n"
                f"Batch size: {config['batch_size']} files\n"
                f"Confidence threshold: {config['confidence_threshold']:.0%}\n\n"
                f"Continue with categorization?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

        # Save settings
        self.save_settings()

        config["preview_mode"] = False

        self.logger.info(
            f"Full categorization requested: {self.file_count} files, {config['category_count']} categories"
        )
        self.categorization_requested.emit(config)
        self.accept()

    def show_tooltip(self, widget, message):
        """Show a temporary tooltip as feedback."""
        QToolTip.showText(
            widget.mapToGlobal(widget.rect().center()),
            message,
            widget,
            widget.rect(),
            3000,
        )

    def load_settings(self):
        """Load settings from QSettings."""
        try:
            settings = QSettings("Javis", "Categorization")

            config = {
                "process_images": settings.value("process_images", True, type=bool),
                "process_documents": settings.value(
                    "process_documents", True, type=bool
                ),
                "batch_size": settings.value("batch_size", 10, type=int),
                "confidence_threshold": settings.value(
                    "confidence_threshold", 0.3, type=float
                ),
                "image_model": settings.value("image_model", "Auto (recommended)"),
                "document_model": settings.value(
                    "document_model", "Auto (recommended)"
                ),
                "enable_fallback": settings.value("enable_fallback", True, type=bool),
                "cache_results": settings.value("cache_results", True, type=bool),
                "save_results": settings.value("save_results", True, type=bool),
                "show_report": settings.value("show_report", True, type=bool),
                "export_csv": settings.value("export_csv", False, type=bool),
                "only_uncategorized": settings.value(
                    "only_uncategorized", False, type=bool
                ),
            }

            # Apply configuration only when widgets exist and initialization is complete
            if (
                hasattr(self, "process_images_cb")
                and hasattr(self, "_signals_connected")
                and self._signals_connected
            ):
                self.set_configuration(config)
                self.logger.debug("Settings loaded and applied")
            else:
                # Store config for deferred application
                self._pending_config = config
                self.logger.debug("Settings loaded, will apply later")

        except Exception as e:
            self.logger.error(f"Error loading settings: {e}")

    def save_settings(self):
        """Save settings to QSettings."""
        settings = QSettings("Javis", "Categorization")
        config = self.get_configuration()

        # Save configurable options
        settings_to_save = [
            "process_images",
            "process_documents",
            "batch_size",
            "confidence_threshold",
            "image_model",
            "document_model",
            "enable_fallback",
            "cache_results",
            "save_results",
            "show_report",
            "export_csv",
            "only_uncategorized",
        ]

        for key in settings_to_save:
            if key in config:
                settings.setValue(key, config[key])

        # Save categories
        categories = self.category_editor.get_categories()
        settings.setValue("last_categories", categories)

        settings.sync()
        self.logger.debug("Categorization settings saved successfully")

    def showEvent(self, event):
        """Called when the dialog is shown."""
        super().showEvent(event)

        try:
            # Connect signals after full UI creation
            self.connect_category_signals()

            # Apply deferred configuration if present
            if hasattr(self, "_pending_config"):
                self.set_configuration(self._pending_config)
                delattr(self, "_pending_config")
                self.logger.debug("Applied pending configuration")

            # Load settings if not already loaded
            if not hasattr(self, "_pending_config"):
                self.load_settings()

            # Initial button state update
            self.update_button_states()

            self.logger.debug("Dialog show event completed successfully")

        except Exception as e:
            self.logger.error(f"Error in showEvent: {e}")
            # Continue even if an error occurs to avoid blocking display
