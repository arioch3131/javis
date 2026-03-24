# views/widgets/dialogs/scan/advanced_scan_dialog.py
"""
AdvancedScanDialog - Dialog to configure and run advanced scans.

Refactored version using the new architecture with base widgets
and reusable components. Integrates the LLM logic from categorization_dialog
and the organization logic from auto_organize_dialog.
"""

import os
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

from ai_content_classifier.controllers.auto_organization_controller import (
    AutoOrganizationController,
)
from ai_content_classifier.controllers.llm_controller import LLMController
from ai_content_classifier.models.config_models import ConfigKey
from ai_content_classifier.services.theme.theme_service import ThemePalette
from PyQt6.QtCore import QSettings, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from ai_content_classifier.views.widgets.base.action_bar import ActionBar
from ai_content_classifier.views.widgets.base.header_section import HeaderSection
from ai_content_classifier.views.widgets.base.themed_dialog import ThemedDialog
from ai_content_classifier.views.widgets.common.category_editor import CategoryEditor
from ai_content_classifier.views.widgets.common.file_selector import FileSelector
from ai_content_classifier.views.widgets.common.progress_panel import ProgressPanel

if TYPE_CHECKING:
    from ai_content_classifier.views.managers.settings_manager import SettingsManager


class FavoriteButton(QPushButton):
    """Button for a favorite folder with icon and path."""

    favorite_selected = pyqtSignal(str)  # Selected path

    def __init__(self, name: str, path: str, parent=None):
        super().__init__(parent)

        self.path = path
        self.name = name

        # Button configuration
        self.setText(f"📁 {name}")
        self.setToolTip(f"Quick select: {path}")
        self.setObjectName("favoriteButton")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Connection
        self.clicked.connect(lambda: self.favorite_selected.emit(self.path))


class AdvancedScanDialog(ThemedDialog):
    """
    Advanced dialog to configure and run file scans.

    Refactored version using the new architecture with:
    - ThemedDialog comme base
    - Reusable widgets for file selection
    - LLM integration inspired by categorization_dialog
    - Organization logic inspired by auto_organize_dialog
    """

    # Signals
    scan_requested = pyqtSignal(dict)  # Full scan configuration

    def __init__(
        self,
        llm_controller: LLMController,
        organization_controller: AutoOrganizationController,
        settings_manager: Optional["SettingsManager"] = None,
        parent=None,
    ):
        # Controllers
        self.llm_controller = llm_controller
        self.organization_controller = organization_controller
        self.settings_manager = settings_manager

        # Internal state
        self.selected_directory = ""
        self.favorites = []
        self.recent_scans = []

        # Initialize base dialog
        super().__init__(
            parent=parent,
            title="Advanced Directory Scanner",
            description="Configure scanning options, AI processing, and file organization in one comprehensive interface.",
            modal=True,
        )

        # Specific configuration
        self.resize(900, 700)
        self._fit_to_screen()
        self.setAcceptDrops(True)  # Drag & Drop support

        # Feedback timer
        self.feedback_timer = QTimer()
        self.feedback_timer.setSingleShot(True)

        # Load settings and persisted data
        self.load_settings()

        # Finalize initialization after all widgets are created
        self.finalize_initialization()

    def create_header(self) -> QFrame:
        """Create the header with title and statistics."""
        # Main header
        header = HeaderSection(
            title="Advanced Directory Scanner",
            description="Configure scanning options, AI processing, and file organization in one comprehensive interface.",
            icon="🔍",
            parent=self,
        )

        return header

    def apply_dialog_theme(self, palette: ThemePalette):
        """Apply the dialog theme with readable section titles."""
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
        content.setObjectName("scanContent")

        layout = QHBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(0)

        # Tabbed configuration
        self.config_tabs = QTabWidget()
        self.config_tabs.setObjectName("configurationTabs")

        # Source tab
        source_tab = self.create_source_tab()
        self.config_tabs.addTab(source_tab, "📁 Source")

        # Processing tab
        processing_tab = self.create_processing_tab()
        self.config_tabs.addTab(processing_tab, "⚙️ Processing")

        # AI & classification tab
        ai_tab = self.create_ai_tab()
        self.config_tabs.addTab(ai_tab, "🤖 AI")

        # Organization tab
        organization_tab = self.create_organization_tab()
        self.config_tabs.addTab(organization_tab, "📂 Organization")

        layout.addWidget(self.config_tabs, 1)

        # Progress panel (hidden initially)
        self.progress_panel = ProgressPanel(
            parent=self, title="Scan Progress", show_details=True, show_log=True
        )
        self.progress_panel.cancel_requested.connect(self.cancel_scan)
        self.progress_panel.hide()

        # Main layout with progress
        main_layout = QVBoxLayout()
        main_layout.addWidget(content, 1)
        main_layout.addWidget(self.progress_panel)

        main_container = QFrame()
        main_container.setLayout(main_layout)

        return main_container

    def create_sidebar(self) -> QWidget:
        """Create the sidebar with favorites and history."""
        sidebar = QFrame()
        sidebar.setObjectName("sidebarFrame")
        sidebar.setMaximumWidth(250)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 12, 0)
        layout.setSpacing(16)

        # === SECTION FAVORIS ===
        favorites_group = QGroupBox("⭐ Quick Access")
        favorites_group.setObjectName("favoritesGroup")
        favorites_layout = QVBoxLayout(favorites_group)
        favorites_layout.setSpacing(8)

        # Scroll area for favorites
        favorites_scroll = QScrollArea()
        favorites_scroll.setObjectName("favoritesScroll")
        favorites_scroll.setWidgetResizable(True)
        favorites_scroll.setMaximumHeight(180)
        favorites_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.favorites_container = QWidget()
        self.favorites_container.setObjectName("favoritesContainer")
        self.favorites_layout = QVBoxLayout(self.favorites_container)
        self.favorites_layout.setContentsMargins(6, 6, 6, 6)
        self.favorites_layout.addStretch()

        favorites_scroll.setWidget(self.favorites_container)
        favorites_layout.addWidget(favorites_scroll)

        # "Add Current" button
        add_fav_btn = QPushButton("➕ Add Current")
        add_fav_btn.setObjectName("addFavoriteButton")
        add_fav_btn.setToolTip("Add current directory to favorites")
        add_fav_btn.clicked.connect(self.add_current_to_favorites)
        favorites_layout.addWidget(add_fav_btn)

        layout.addWidget(favorites_group)

        # === HISTORY SECTION ===
        history_group = QGroupBox("🕒 Recent Scans")
        history_group.setObjectName("historyGroup")
        history_layout = QVBoxLayout(history_group)
        history_layout.setSpacing(8)

        self.history_list = QListWidget()
        self.history_list.setObjectName("historyList")
        self.history_list.setMaximumHeight(120)
        self.history_list.itemDoubleClicked.connect(self.load_from_history)
        history_layout.addWidget(self.history_list)

        # Bouton clear history
        clear_history_btn = QPushButton("🗑️ Clear")
        clear_history_btn.setObjectName("clearHistoryButton")
        clear_history_btn.clicked.connect(self.clear_history)
        history_layout.addWidget(clear_history_btn)

        layout.addWidget(history_group)
        layout.addStretch()

        # Populate initial data
        self.populate_favorites()
        self.populate_history()

        return sidebar

    def create_source_tab(self) -> QWidget:
        """Create the source selection tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(20)

        # === SÉLECTION DE DOSSIER ===
        dir_group = QGroupBox("📁 Directory Selection")
        dir_group.setObjectName("directoryGroup")
        dir_layout = QVBoxLayout(dir_group)
        dir_layout.setSpacing(12)

        # Use FileSelector for selection
        self.directory_selector = FileSelector(
            mode="directory",
            parent=self,
            label="Target Directory:",
            placeholder="Select or drag & drop a directory to scan...",
        )

        # Connexions
        self.directory_selector.path_changed.connect(self.on_directory_changed)
        self.directory_selector.path_validated.connect(self.on_directory_validated)

        dir_layout.addWidget(self.directory_selector)

        # Information about the selected folder
        self.dir_info_label = QLabel("No directory selected")
        self.dir_info_label.setObjectName("directoryInfoLabel")
        self.dir_info_label.setWordWrap(True)
        dir_layout.addWidget(self.dir_info_label)

        layout.addWidget(dir_group)

        # === TYPES DE FICHIERS ===
        types_group = QGroupBox("📋 File Types")
        types_group.setObjectName("fileTypesGroup")
        types_layout = QVBoxLayout(types_group)
        types_layout.setSpacing(16)

        # Checkboxes pour types principaux
        types_checkboxes_layout = QGridLayout()
        types_checkboxes_layout.setSpacing(12)

        self.scan_documents_cb = QCheckBox("📄 Documents")
        self.scan_documents_cb.setObjectName("documentsCheckbox")
        self.scan_documents_cb.setChecked(True)
        self.scan_documents_cb.setToolTip("PDF, DOC, TXT, etc.")

        self.scan_images_cb = QCheckBox("🖼️ Images")
        self.scan_images_cb.setObjectName("imagesCheckbox")
        self.scan_images_cb.setChecked(True)
        self.scan_images_cb.setToolTip("JPG, PNG, GIF, etc.")

        self.scan_videos_cb = QCheckBox("🎥 Videos")
        self.scan_videos_cb.setObjectName("videosCheckbox")
        self.scan_videos_cb.setToolTip("MP4, AVI, MOV, etc.")

        self.scan_audio_cb = QCheckBox("🎵 Audio")
        self.scan_audio_cb.setObjectName("audioCheckbox")
        self.scan_audio_cb.setToolTip("MP3, WAV, FLAC, etc.")

        self.scan_others_cb = QCheckBox("📁 Other Files")
        self.scan_others_cb.setObjectName("othersCheckbox")
        self.scan_others_cb.setToolTip("All other file types")

        types_checkboxes_layout.addWidget(self.scan_documents_cb, 0, 0)
        types_checkboxes_layout.addWidget(self.scan_images_cb, 0, 1)
        types_checkboxes_layout.addWidget(self.scan_videos_cb, 1, 0)
        types_checkboxes_layout.addWidget(self.scan_audio_cb, 1, 1)
        types_checkboxes_layout.addWidget(self.scan_others_cb, 2, 0, 1, 2)

        types_layout.addLayout(types_checkboxes_layout)

        # Custom extensions
        custom_ext_layout = QHBoxLayout()
        custom_ext_layout.setSpacing(12)

        custom_label = QLabel("Custom Extensions:")
        custom_label.setObjectName("fieldLabel")
        custom_ext_layout.addWidget(custom_label)

        self.custom_extensions_input = QLineEdit()
        self.custom_extensions_input.setObjectName("customExtensionsInput")
        self.custom_extensions_input.setPlaceholderText("e.g., .xyz, .custom, .special")
        custom_ext_layout.addWidget(self.custom_extensions_input)

        types_layout.addLayout(custom_ext_layout)
        layout.addWidget(types_group)

        # === FILTRES ===
        filters_group = QGroupBox("🔍 Filters")
        filters_group.setObjectName("filtersGroup")
        filters_layout = QGridLayout(filters_group)
        filters_layout.setSpacing(12)

        # Taille minimum
        min_size_label = QLabel("Min Size:")
        min_size_label.setObjectName("fieldLabel")
        filters_layout.addWidget(min_size_label, 0, 0)

        self.min_size_spin = QSpinBox()
        self.min_size_spin.setObjectName("minSizeSpinBox")
        self.min_size_spin.setRange(0, 10_000_000)
        self.min_size_spin.setSuffix(" KB")
        filters_layout.addWidget(self.min_size_spin, 0, 1)

        # Taille maximum
        max_size_label = QLabel("Max Size:")
        max_size_label.setObjectName("fieldLabel")
        filters_layout.addWidget(max_size_label, 0, 2)

        self.max_size_spin = QSpinBox()
        self.max_size_spin.setObjectName("maxSizeSpinBox")
        self.max_size_spin.setRange(0, 10_000_000)
        self.max_size_spin.setValue(1_024_000)  # 1GB default in KB
        self.max_size_spin.setSuffix(" KB")
        filters_layout.addWidget(self.max_size_spin, 0, 3)

        # Additional options
        self.skip_hidden_cb = QCheckBox("Skip hidden files and folders")
        self.skip_hidden_cb.setObjectName("skipHiddenCheckbox")
        self.skip_hidden_cb.setChecked(True)
        filters_layout.addWidget(self.skip_hidden_cb, 1, 0, 1, 4)

        layout.addWidget(filters_group)
        layout.addStretch()

        return widget

    def create_processing_tab(self) -> QWidget:
        """Create the processing options tab."""
        widget = QWidget()

        # Scroll area pour les options
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(20)

        # === EXTRACTION DE MÉTADONNÉES ===
        metadata_group = QGroupBox("📊 Metadata")
        metadata_group.setObjectName("metadataGroup")
        metadata_layout = QVBoxLayout(metadata_group)
        metadata_layout.setSpacing(12)

        self.extract_metadata_cb = QCheckBox(
            "Extract file metadata (EXIF, document properties, etc.)"
        )
        self.extract_metadata_cb.setObjectName("extractMetadataCheckbox")
        self.extract_metadata_cb.setChecked(True)
        metadata_layout.addWidget(self.extract_metadata_cb)

        # Advanced metadata options
        metadata_options_layout = QHBoxLayout()
        metadata_options_layout.setSpacing(20)

        self.deep_metadata_cb = QCheckBox("Deep analysis (slower but more complete)")
        self.deep_metadata_cb.setObjectName("deepMetadataCheckbox")

        self.cache_metadata_cb = QCheckBox("Cache results for faster future scans")
        self.cache_metadata_cb.setObjectName("cacheMetadataCheckbox")
        self.cache_metadata_cb.setChecked(True)

        metadata_options_layout.addWidget(self.deep_metadata_cb)
        metadata_options_layout.addWidget(self.cache_metadata_cb)
        metadata_options_layout.addStretch()

        metadata_layout.addLayout(metadata_options_layout)
        layout.addWidget(metadata_group)

        # === GÉNÉRATION DE THUMBNAILS ===
        thumbs_group = QGroupBox("🖼️ Thumbnails")
        thumbs_group.setObjectName("thumbnailsGroup")
        thumbs_layout = QVBoxLayout(thumbs_group)
        thumbs_layout.setSpacing(12)

        self.generate_thumbnails_cb = QCheckBox("Generate thumbnails for images")
        self.generate_thumbnails_cb.setObjectName("generateThumbnailsCheckbox")
        self.generate_thumbnails_cb.setChecked(True)
        thumbs_layout.addWidget(self.generate_thumbnails_cb)

        # Options thumbnails
        thumbs_options_layout = QGridLayout()
        thumbs_options_layout.setSpacing(12)

        size_label = QLabel("Size:")
        size_label.setObjectName("fieldLabel")
        thumbs_options_layout.addWidget(size_label, 0, 0)

        self.thumbnail_size_combo = QComboBox()
        self.thumbnail_size_combo.setObjectName("thumbnailSizeCombo")
        self.thumbnail_size_combo.addItems(["128x128", "256x256", "512x512"])
        self.thumbnail_size_combo.setCurrentText("256x256")
        thumbs_options_layout.addWidget(self.thumbnail_size_combo, 0, 1)

        quality_label = QLabel("Quality:")
        quality_label.setObjectName("fieldLabel")
        thumbs_options_layout.addWidget(quality_label, 0, 2)

        self.thumbnail_quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.thumbnail_quality_slider.setObjectName("thumbnailQualitySlider")
        self.thumbnail_quality_slider.setRange(50, 100)
        self.thumbnail_quality_slider.setValue(85)
        self.thumbnail_quality_slider.setToolTip(
            "Higher = better quality, larger files"
        )
        thumbs_options_layout.addWidget(self.thumbnail_quality_slider, 0, 3)

        self.quality_value_label = QLabel("85%")
        self.quality_value_label.setObjectName("qualityValueLabel")
        self.thumbnail_quality_slider.valueChanged.connect(
            lambda v: self.quality_value_label.setText(f"{v}%")
        )
        thumbs_options_layout.addWidget(self.quality_value_label, 0, 4)

        thumbs_layout.addLayout(thumbs_options_layout)
        layout.addWidget(thumbs_group)

        # === PERFORMANCE ===
        perf_group = QGroupBox("⚡ Performance")
        perf_group.setObjectName("performanceGroup")
        perf_layout = QGridLayout(perf_group)
        perf_layout.setSpacing(12)

        # Nombre de threads
        threads_label = QLabel("Worker Threads:")
        threads_label.setObjectName("fieldLabel")
        perf_layout.addWidget(threads_label, 0, 0)

        self.threads_spin = QSpinBox()
        self.threads_spin.setObjectName("threadsSpinBox")
        self.threads_spin.setRange(1, 16)
        self.threads_spin.setValue(4)
        self.threads_spin.setToolTip(
            "More threads = faster processing, higher CPU usage"
        )
        perf_layout.addWidget(self.threads_spin, 0, 1)

        # Batch size
        batch_label = QLabel("Batch Size:")
        batch_label.setObjectName("fieldLabel")
        perf_layout.addWidget(batch_label, 0, 2)

        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setObjectName("batchSizeSpinBox")
        self.batch_size_spin.setRange(10, 1000)
        self.batch_size_spin.setValue(100)
        self.batch_size_spin.setToolTip("Files processed per batch")
        perf_layout.addWidget(self.batch_size_spin, 0, 3)

        # Pause between batches
        self.pause_between_batches_cb = QCheckBox(
            "Pause between batches (reduce system load)"
        )
        self.pause_between_batches_cb.setObjectName("pauseBatchesCheckbox")
        perf_layout.addWidget(self.pause_between_batches_cb, 1, 0, 1, 4)

        layout.addWidget(perf_group)
        layout.addStretch()

        scroll.setWidget(content_widget)

        # Main layout for the tab
        tab_layout = QVBoxLayout(widget)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll)

        return widget

    def create_ai_tab(self) -> QWidget:
        """Create the AI and categorization tab (inspired by categorization_dialog)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(20)

        # === ACTIVATION DE L'IA ===
        ai_enable_group = QGroupBox("🤖 AI Processing")
        ai_enable_group.setObjectName("aiEnableGroup")
        ai_enable_layout = QVBoxLayout(ai_enable_group)
        ai_enable_layout.setSpacing(12)

        self.auto_categorize_cb = QCheckBox(
            "Enable automatic AI categorization during scan"
        )
        self.auto_categorize_cb.setObjectName("autoCategorizeCheckbox")
        self.auto_categorize_cb.toggled.connect(self.on_ai_toggled)
        ai_enable_layout.addWidget(self.auto_categorize_cb)

        ai_info = QLabel(
            "AI categorization will analyze file content and assign appropriate categories "
            "automatically during the scan process."
        )
        ai_info.setObjectName("aiInfoLabel")
        ai_info.setWordWrap(True)
        ai_enable_layout.addWidget(ai_info)

        layout.addWidget(ai_enable_group)

        # === CATÉGORIES ===
        categories_group = QGroupBox("🏷️ Categories")
        categories_group.setObjectName("categoriesGroup")
        categories_layout = QVBoxLayout(categories_group)
        categories_layout.setSpacing(12)

        # Instructions
        categories_info = QLabel(
            "Define categories for automatic classification. Files will be assigned "
            "to the most appropriate category based on their content."
        )
        categories_info.setWordWrap(True)
        categories_layout.addWidget(categories_info)

        # Reusable category editor (inspired by categorization_dialog)
        self.category_editor = CategoryEditor(parent=self, title="Scan Categories")

        # Scan-specific configuration
        self.category_editor.set_allow_empty(True)  # Can be empty if AI is disabled
        self.category_editor.set_max_categories(15)

        # Predefined categories for scan
        scan_categories = {
            "Work Documents",
            "Personal Files",
            "Photos",
            "Videos",
            "Archive",
            "Projects",
            "Reference",
            "Temporary",
            "Financial",
            "Educational",
        }
        self.category_editor.set_predefined_categories(scan_categories)

        # Default categories for scan
        default_scan_categories = ["Work", "Personal", "Archive", "Media"]
        self.category_editor.set_categories(default_scan_categories)

        categories_layout.addWidget(self.category_editor)
        layout.addWidget(categories_group)

        # === MODÈLES IA ===
        models_group = QGroupBox("🧠 Models")
        models_group.setObjectName("modelsGroup")
        models_layout = QGridLayout(models_group)
        models_layout.setSpacing(12)

        # Model for documents
        doc_model_label = QLabel("Document Model:")
        doc_model_label.setObjectName("fieldLabel")
        models_layout.addWidget(doc_model_label, 0, 0)

        self.document_model_combo = QComboBox()
        self.document_model_combo.setObjectName("documentModelCombo")
        models_layout.addWidget(self.document_model_combo, 0, 1)

        # Model for images
        image_model_label = QLabel("Image Model:")
        image_model_label.setObjectName("fieldLabel")
        models_layout.addWidget(image_model_label, 1, 0)

        self.image_model_combo = QComboBox()
        self.image_model_combo.setObjectName("imageModelCombo")
        models_layout.addWidget(self.image_model_combo, 1, 1)

        # Seuil de confiance
        confidence_label = QLabel("Confidence Threshold:")
        confidence_label.setObjectName("fieldLabel")
        models_layout.addWidget(confidence_label, 2, 0)

        confidence_container = QWidget()
        confidence_layout = QHBoxLayout(confidence_container)
        confidence_layout.setContentsMargins(0, 0, 0, 0)

        self.confidence_slider = QSlider(Qt.Orientation.Horizontal)
        self.confidence_slider.setObjectName("confidenceSlider")
        self.confidence_slider.setRange(10, 100)
        self.confidence_slider.setValue(30)  # Comme categorization_dialog
        confidence_layout.addWidget(self.confidence_slider)

        self.confidence_label = QLabel("30%")
        self.confidence_label.setObjectName("confidenceValueLabel")
        self.confidence_slider.valueChanged.connect(
            lambda v: self.confidence_label.setText(f"{v}%")
        )
        confidence_layout.addWidget(self.confidence_label)

        models_layout.addWidget(confidence_container, 2, 1)

        # Model status
        self.model_status_label = QLabel("Loading models...")
        self.model_status_label.setObjectName("modelStatusLabel")
        models_layout.addWidget(self.model_status_label, 3, 0, 1, 2)

        layout.addWidget(models_group)

        # Load available models
        self.load_available_models()

        layout.addStretch()
        return widget

    def create_organization_tab(self) -> QWidget:
        """Create the organization tab (inspired by auto_organize_dialog)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(20)

        # === ACTIVATION DE L'ORGANISATION ===
        org_enable_group = QGroupBox("📂 Auto-Organization")
        org_enable_group.setObjectName("orgEnableGroup")
        org_enable_layout = QVBoxLayout(org_enable_group)
        org_enable_layout.setSpacing(12)

        self.auto_organize_cb = QCheckBox(
            "Enable automatic file organization after scan"
        )
        self.auto_organize_cb.setObjectName("autoOrganizeCheckbox")
        self.auto_organize_cb.toggled.connect(self.on_organization_toggled)
        org_enable_layout.addWidget(self.auto_organize_cb)

        org_info = QLabel(
            "Files will be automatically organized into a structured folder hierarchy "
            "based on their categories and types after scanning."
        )
        org_info.setObjectName("orgInfoLabel")
        org_info.setWordWrap(True)
        org_enable_layout.addWidget(org_info)

        layout.addWidget(org_enable_group)

        # === DESTINATION ===
        dest_group = QGroupBox("📁 Destination")
        dest_group.setObjectName("destinationGroup")
        dest_layout = QVBoxLayout(dest_group)
        dest_layout.setSpacing(12)

        # Utiliser FileSelector pour la destination (comme auto_organize_dialog)
        self.target_selector = FileSelector(
            mode="directory",
            parent=self,
            label="Target Directory:",
            placeholder="Choose where to organize your files...",
        )

        # Default value
        default_target = os.path.expanduser("~/Organized_Files")
        self.target_selector.set_path(default_target)

        dest_layout.addWidget(self.target_selector)
        layout.addWidget(dest_group)

        # === ACTION ET STRUCTURE ===
        config_group = QGroupBox("⚙️ Configuration")
        config_group.setObjectName("configGroup")
        config_layout = QGridLayout(config_group)
        config_layout.setSpacing(12)

        # Action sur les files (comme auto_organize_dialog)
        action_label = QLabel("Action:")
        action_label.setObjectName("fieldLabel")
        config_layout.addWidget(action_label, 0, 0)

        action_container = QWidget()
        action_layout = QHBoxLayout(action_container)
        action_layout.setContentsMargins(0, 0, 0, 0)

        self.action_group = QButtonGroup()

        self.copy_radio = QRadioButton("📋 Copy files")
        self.copy_radio.setObjectName("copyRadio")
        self.copy_radio.setChecked(True)  # Safe default
        self.copy_radio.setToolTip("Keep originals in current locations")

        self.move_radio = QRadioButton("📤 Move files")
        self.move_radio.setObjectName("moveRadio")
        self.move_radio.setToolTip("Relocate files to new organization")

        self.action_group.addButton(self.copy_radio)
        self.action_group.addButton(self.move_radio)

        action_layout.addWidget(self.copy_radio)
        action_layout.addWidget(self.move_radio)
        action_layout.addStretch()

        config_layout.addWidget(action_container, 0, 1)

        # Structure d'organisation
        structure_label = QLabel("Structure:")
        structure_label.setObjectName("fieldLabel")
        config_layout.addWidget(structure_label, 1, 0)

        self.structure_combo = QComboBox()
        self.structure_combo.setObjectName("structureCombo")

        # Use structures supported by the controller
        if self.organization_controller:
            supported_structures = (
                self.organization_controller.get_supported_structures()
            )
            self.structure_combo.addItems(supported_structures)
        else:
            # Fallback
            self.structure_combo.addItems(
                [
                    "By Category",
                    "By Year",
                    "By Type",
                    "By Category/Year",
                    "By Type/Category",
                ]
            )

        config_layout.addWidget(self.structure_combo, 1, 1)

        layout.addWidget(config_group)

        # === PREVIEW DE LA STRUCTURE ===
        preview_group = QGroupBox("👁️ Preview")
        preview_group.setObjectName("previewGroup")
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setSpacing(8)

        self.structure_preview = QTextEdit()
        self.structure_preview.setObjectName("structurePreview")
        self.structure_preview.setMaximumHeight(100)
        self.structure_preview.setReadOnly(True)
        self.structure_preview.setPlainText(
            "/target/Work/Documents/\n"
            "/target/Personal/Photos/\n"
            "/target/Archive/Old_Files/"
        )
        preview_layout.addWidget(self.structure_preview)

        layout.addWidget(preview_group)

        # Connexions pour la preview
        self.structure_combo.currentTextChanged.connect(self.update_structure_preview)
        self.target_selector.path_changed.connect(self.update_structure_preview)

        layout.addStretch()
        return widget

    def create_footer(self) -> QFrame:
        """Create the footer with action buttons."""
        # Utiliser ActionBar pour les boutons
        action_bar = ActionBar(self, alignment="right")

        # Boutons principaux
        action_bar.add_stretch()
        action_bar.add_action("❌ Cancel", self.cancel_operation, "cancelButton")
        action_bar.add_action(
            "🚀 Start Pipeline",
            self.start_pipeline,
            "startPipelineButton",
            primary=True,
        )

        # References for manipulation
        self.start_pipeline_btn = action_bar.get_action_button("startPipelineButton")
        self.cancel_btn = action_bar.get_action_button("cancelButton")

        return action_bar

    def finalize_initialization(self):
        """Finalize initialization after all widgets are created."""
        try:
            self._apply_application_settings()

            # These methods can now be called safely
            if hasattr(self, "auto_categorize_cb"):
                self.on_ai_toggled(self.auto_categorize_cb.isChecked())

            if hasattr(self, "auto_organize_cb"):
                self.on_organization_toggled(self.auto_organize_cb.isChecked())

            # Validation initiale
            self.validate_configuration()

            # Update preview
            if hasattr(self, "structure_preview"):
                self.update_structure_preview()

            self.logger.info(
                "Advanced scan dialog initialization completed successfully"
            )

        except Exception as e:
            self.logger.error(f"Error in finalize_initialization: {e}")

    # === MÉTHODES D'ÉVÉNEMENTS ===

    def on_directory_changed(self, path: str):
        """Called when the selected folder changes."""
        self.selected_directory = path
        self.update_directory_info(path)
        self.validate_configuration()

    def on_directory_validated(self, is_valid: bool, error_message: str):
        """Called when folder validation changes."""
        self.validate_configuration()

    def on_ai_toggled(self, enabled: bool):
        """Called when AI is enabled/disabled."""
        try:
            # Update category validation
            if hasattr(self, "category_editor") and self.category_editor:
                if enabled:
                    self.category_editor.set_allow_empty(False)
                else:
                    self.category_editor.set_allow_empty(True)

            # Validate only when everything is initialized
            if hasattr(self, "directory_selector"):
                self.validate_configuration()

        except Exception as e:
            self.logger.error(f"Error in on_ai_toggled: {e}")

    def on_organization_toggled(self, enabled: bool):
        """Called when organization is enabled/disabled."""
        try:
            # Les controles restent configurables meme si l'option n'est pas encore active.
            # Le toggle ne change que l'intention d'appliquer l'organisation au scan.

            # Validate only when everything is initialized
            if hasattr(self, "directory_selector"):
                self.validate_configuration()

        except Exception as e:
            self.logger.error(f"Error in on_organization_toggled: {e}")

    def load_available_models(self):
        """Load available AI models (inspired by categorization_dialog)."""
        try:
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

            # Mettre le statut en "loadment"
            self.model_status_label.setText("🔄 Loading available models...")

            # Load models through the controller
            available_models = self.llm_controller.get_available_models()

            if available_models:
                models_to_display = ["Auto (recommended)"] + available_models

                # Ajouter aux combo boxes
                self.image_model_combo.clear()
                self.document_model_combo.clear()
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
                    f"Loaded {len(available_models)} LLM models successfully"
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

            # Robust error handling
            error_items = ["Auto (recommended)", "Error - see logs"]

            try:
                if hasattr(self, "image_model_combo"):
                    self.image_model_combo.clear()
                    self.image_model_combo.addItems(error_items)
                    self.image_model_combo.setEnabled(False)

                if hasattr(self, "document_model_combo"):
                    self.document_model_combo.clear()
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

    def _apply_application_settings(self):
        """Apply persisted application settings to relevant scan tabs."""
        try:
            config_service = getattr(
                getattr(self.llm_controller, "llm_service", None),
                "config_service",
                None,
            )
            if config_service is None:
                return

            categories = (
                self.settings_manager.get_unified_categories()
                if self.settings_manager is not None
                else config_service.get(ConfigKey.CATEGORIES)
            )
            if (
                isinstance(categories, list)
                and categories
                and hasattr(self, "category_editor")
            ):
                self.category_editor.set_categories(categories)

            confidence_threshold = config_service.get(ConfigKey.CONFIDENCE_THRESHOLD)
            if isinstance(confidence_threshold, (int, float)) and hasattr(
                self, "confidence_slider"
            ):
                self.confidence_slider.setValue(int(float(confidence_threshold) * 100))

            image_model = config_service.get(ConfigKey.IMAGE_MODEL)
            document_model = config_service.get(ConfigKey.DOCUMENT_MODEL)
            if hasattr(self, "image_model_combo"):
                self._select_combo_value(self.image_model_combo, image_model)
            if hasattr(self, "document_model_combo"):
                self._select_combo_value(self.document_model_combo, document_model)

        except Exception as e:
            self.logger.error(f"Error applying application settings: {e}")

    @staticmethod
    def _select_combo_value(combo: QComboBox, value: str | None) -> None:
        """Select a combo value if it exists in the list."""
        if not value:
            return
        index = combo.findText(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def update_directory_info(self, directory: str):
        """Update information for the selected folder."""
        try:
            if directory and os.path.exists(directory):
                try:
                    # Compter les files et calculer la taille
                    files = [
                        f
                        for f in os.listdir(directory)
                        if os.path.isfile(os.path.join(directory, f))
                    ]
                    file_count = len(files)

                    total_size = 0
                    for f in files:
                        try:
                            total_size += os.path.getsize(os.path.join(directory, f))
                        except (OSError, PermissionError):
                            continue

                    size_mb = total_size / (1024 * 1024)

                    # Estimation du temps de scan
                    estimated_seconds = file_count * 0.05  # 50ms par file
                    if estimated_seconds < 60:
                        time_text = f"{estimated_seconds:.0f}s"
                    else:
                        time_text = f"{estimated_seconds / 60:.1f}m"

                    self.dir_info_label.setText(
                        f"📊 {file_count} files, ~{size_mb:.1f} MB | "
                        f"⏱️ Estimated scan time: {time_text}"
                    )
                    self.dir_info_label.setStyleSheet(
                        "color: green; font-weight: bold;"
                    )

                except (OSError, PermissionError) as e:
                    self.dir_info_label.setText("⚠️ Directory not accessible")
                    self.dir_info_label.setStyleSheet(
                        "color: orange; font-weight: bold;"
                    )
                    self.logger.warning(f"Cannot access directory {directory}: {e}")
            else:
                self.dir_info_label.setText("No directory selected")
                self.dir_info_label.setStyleSheet("color: gray; font-style: italic;")

        except Exception as e:
            self.logger.error(f"Error updating directory info: {e}")

    def update_structure_preview(self):
        """Update the preview of the organization structure."""
        try:
            if not hasattr(self, "structure_preview"):
                return

            structure = self.structure_combo.currentText()
            target = self.target_selector.get_path() or "/target"

            preview_lines = []

            if structure == "By Category":
                categories = self.category_editor.get_categories()
                if categories:
                    for cat in categories[:3]:  # Montrer 3 exemples
                        preview_lines.append(f"{target}/{cat}/")
                else:
                    preview_lines = [
                        f"{target}/Work/",
                        f"{target}/Personal/",
                        f"{target}/Archive/",
                    ]
            elif structure == "By Year":
                preview_lines = [
                    f"{target}/2024/",
                    f"{target}/2023/",
                    f"{target}/2022/",
                ]
            elif structure == "By Type":
                preview_lines = [
                    f"{target}/Documents/",
                    f"{target}/Images/",
                    f"{target}/Videos/",
                ]
            elif structure == "By Category/Year":
                categories = self.category_editor.get_categories()
                cat = categories[0] if categories else "Work"
                preview_lines = [f"{target}/{cat}/2024/", f"{target}/{cat}/2023/"]
            elif structure == "By Type/Category":
                categories = self.category_editor.get_categories()
                cat = categories[0] if categories else "Work"
                preview_lines = [
                    f"{target}/Documents/{cat}/",
                    f"{target}/Images/{cat}/",
                ]
            else:
                preview_lines = [f"{target}/Custom_Structure/"]

            self.structure_preview.setPlainText("\n".join(preview_lines))

        except Exception as e:
            self.logger.error(f"Error updating structure preview: {e}")

    def add_current_to_favorites(self):
        """Ajoute le folder actuel aux favoris."""
        try:
            current_dir = self.directory_selector.get_path()
            if not current_dir:
                QMessageBox.warning(
                    self, "No Directory", "Please select a directory first."
                )
                return

            # Ask for a name for the favorite
            from PyQt6.QtWidgets import QInputDialog

            name, ok = QInputDialog.getText(
                self,
                "Add Favorite",
                "Enter a name for this favorite:",
                text=os.path.basename(current_dir) or "Favorite",
            )

            if ok and name:
                self.favorites.append({"name": name, "path": current_dir})
                self.save_settings()
                self.populate_favorites()
                self.logger.info(f"Added favorite: {name} -> {current_dir}")

        except Exception as e:
            self.logger.error(f"Error adding favorite: {e}")

    def populate_favorites(self):
        """Remplit la liste des favoris."""
        try:
            # Vider le layout existant
            while self.favorites_layout.count() > 1:  # Garder le stretch
                child = self.favorites_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

            # Ajouter les favoris
            for fav in self.favorites:
                btn = FavoriteButton(fav["name"], fav["path"])
                btn.favorite_selected.connect(self.directory_selector.set_path)
                self.favorites_layout.insertWidget(
                    self.favorites_layout.count() - 1, btn
                )

            self.logger.debug(f"Populated {len(self.favorites)} favorites")

        except Exception as e:
            self.logger.error(f"Error populating favorites: {e}")

    def populate_history(self):
        """Remplit l'historique."""
        try:
            self.history_list.clear()
            for scan in self.recent_scans:
                date_str = scan.get("date", "Unknown")
                path = scan.get("path", "Unknown")
                item_text = f"{date_str} - {os.path.basename(path)}"

                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, scan)
                item.setToolTip(f"Double-click to load: {path}")
                self.history_list.addItem(item)

            self.logger.debug(f"Populated {len(self.recent_scans)} history items")

        except Exception as e:
            self.logger.error(f"Error populating history: {e}")

    def load_from_history(self, item):
        """Load une configuration depuis l'historique."""
        try:
            scan_data = item.data(Qt.ItemDataRole.UserRole)
            if scan_data and "config" in scan_data:
                config = scan_data["config"]
                self.set_configuration(config)
                self.logger.info(
                    f"Loaded configuration from history: {scan_data.get('path', 'Unknown')}"
                )

        except Exception as e:
            self.logger.error(f"Error loading from history: {e}")

    def clear_history(self):
        """Vide l'historique."""
        try:
            reply = QMessageBox.question(
                self,
                "Clear History",
                "Are you sure you want to clear all scan history?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.recent_scans.clear()
                self.save_settings()
                self.populate_history()
                self.logger.info("Scan history cleared")

        except Exception as e:
            self.logger.error(f"Error clearing history: {e}")

    # === VALIDATION ET CONFIGURATION ===

    def validate_configuration(self) -> tuple[bool, str]:
        """Valide la configuration actuelle."""
        errors = []

        try:
            # Ensure widgets exist before using them
            if hasattr(self, "directory_selector") and self.directory_selector:
                if not self.directory_selector.is_path_valid():
                    errors.append("Invalid directory selection")
            else:
                errors.append("Directory selector not initialized")

            # Check file types (only if checkboxes exist)
            if all(
                hasattr(self, attr)
                for attr in [
                    "scan_documents_cb",
                    "scan_images_cb",
                    "scan_videos_cb",
                    "scan_audio_cb",
                    "scan_others_cb",
                ]
            ):
                types_selected = any(
                    [
                        self.scan_documents_cb.isChecked(),
                        self.scan_images_cb.isChecked(),
                        self.scan_videos_cb.isChecked(),
                        self.scan_audio_cb.isChecked(),
                        self.scan_others_cb.isChecked(),
                    ]
                )

                if not types_selected:
                    errors.append("No file types selected")

            # Check AI configuration (only if widgets exist)
            if hasattr(self, "auto_categorize_cb") and hasattr(self, "category_editor"):
                if self.auto_categorize_cb.isChecked():
                    categories = self.category_editor.get_categories()
                    if len(categories) < 2:
                        errors.append(
                            "At least 2 categories required for AI categorization"
                        )

            # Check organization (only if widgets exist)
            if hasattr(self, "auto_organize_cb") and hasattr(self, "target_selector"):
                if self.auto_organize_cb.isChecked():
                    if not self.target_selector.is_path_valid():
                        errors.append("Invalid organization target directory")

            # Enable/disable buttons (only if they exist)
            has_errors = len(errors) > 0

            for btn_attr in ["basic_scan_btn", "ai_scan_btn", "full_scan_btn"]:
                if hasattr(self, btn_attr):
                    btn = getattr(self, btn_attr)
                    if btn:
                        btn.setEnabled(not has_errors)

            # Return the result
            is_valid = len(errors) == 0
            error_message = "; ".join(errors) if errors else ""

            return is_valid, error_message

        except Exception as e:
            self.logger.error(f"Error in validate_configuration: {e}")
            return False, f"Validation error: {str(e)}"

    def get_configuration(self) -> Dict[str, Any]:
        """Return full scan configuration."""
        try:
            # Categories (if AI is enabled)
            categories = []
            if (
                hasattr(self, "auto_categorize_cb")
                and self.auto_categorize_cb.isChecked()
            ):
                if hasattr(self, "category_editor"):
                    categories = self.category_editor.get_categories()

            config = {
                # Source
                "directory": (
                    self.directory_selector.get_path()
                    if hasattr(self, "directory_selector")
                    else ""
                ),
                "file_types": {
                    "documents": (
                        self.scan_documents_cb.isChecked()
                        if hasattr(self, "scan_documents_cb")
                        else True
                    ),
                    "images": (
                        self.scan_images_cb.isChecked()
                        if hasattr(self, "scan_images_cb")
                        else True
                    ),
                    "videos": (
                        self.scan_videos_cb.isChecked()
                        if hasattr(self, "scan_videos_cb")
                        else False
                    ),
                    "audio": (
                        self.scan_audio_cb.isChecked()
                        if hasattr(self, "scan_audio_cb")
                        else False
                    ),
                    "others": (
                        self.scan_others_cb.isChecked()
                        if hasattr(self, "scan_others_cb")
                        else False
                    ),
                },
                "custom_extensions": (
                    [
                        ext.strip()
                        for ext in self.custom_extensions_input.text().split(",")
                        if ext.strip()
                    ]
                    if hasattr(self, "custom_extensions_input")
                    else []
                ),
                "min_size_kb": (
                    self.min_size_spin.value() if hasattr(self, "min_size_spin") else 0
                ),
                "max_size_kb": (
                    self.max_size_spin.value()
                    if hasattr(self, "max_size_spin")
                    else 1_024_000
                ),
                "skip_hidden": (
                    self.skip_hidden_cb.isChecked()
                    if hasattr(self, "skip_hidden_cb")
                    else True
                ),
                # Processing
                "extract_metadata": (
                    self.extract_metadata_cb.isChecked()
                    if hasattr(self, "extract_metadata_cb")
                    else True
                ),
                "deep_metadata": (
                    self.deep_metadata_cb.isChecked()
                    if hasattr(self, "deep_metadata_cb")
                    else False
                ),
                "cache_metadata": (
                    self.cache_metadata_cb.isChecked()
                    if hasattr(self, "cache_metadata_cb")
                    else True
                ),
                "generate_thumbnails": (
                    self.generate_thumbnails_cb.isChecked()
                    if hasattr(self, "generate_thumbnails_cb")
                    else True
                ),
                "thumbnail_size": (
                    self.thumbnail_size_combo.currentText()
                    if hasattr(self, "thumbnail_size_combo")
                    else "256x256"
                ),
                "thumbnail_quality": (
                    self.thumbnail_quality_slider.value()
                    if hasattr(self, "thumbnail_quality_slider")
                    else 85
                ),
                "worker_threads": (
                    self.threads_spin.value() if hasattr(self, "threads_spin") else 4
                ),
                "batch_size": (
                    self.batch_size_spin.value()
                    if hasattr(self, "batch_size_spin")
                    else 100
                ),
                "pause_batches": (
                    self.pause_between_batches_cb.isChecked()
                    if hasattr(self, "pause_between_batches_cb")
                    else False
                ),
                # AI
                "auto_categorize": (
                    self.auto_categorize_cb.isChecked()
                    if hasattr(self, "auto_categorize_cb")
                    else False
                ),
                "categories": categories,
                "document_model": (
                    self.document_model_combo.currentText()
                    if hasattr(self, "document_model_combo")
                    else "Auto (recommended)"
                ),
                "image_model": (
                    self.image_model_combo.currentText()
                    if hasattr(self, "image_model_combo")
                    else "Auto (recommended)"
                ),
                "confidence_threshold": (
                    self.confidence_slider.value() / 100.0
                    if hasattr(self, "confidence_slider")
                    else 0.3
                ),
                # Organization
                "auto_organize": (
                    self.auto_organize_cb.isChecked()
                    if hasattr(self, "auto_organize_cb")
                    else False
                ),
                "target_directory": (
                    self.target_selector.get_path()
                    if hasattr(self, "target_selector")
                    else ""
                ),
                "organization_action": (
                    "move"
                    if (hasattr(self, "move_radio") and self.move_radio.isChecked())
                    else "copy"
                ),
                "organization_structure": (
                    self.structure_combo.currentText()
                    if hasattr(self, "structure_combo")
                    else "By Category"
                ),
                # Meta
                "timestamp": datetime.now().isoformat(),
                "config_version": "3.0_refactored",
            }

            return config

        except Exception as e:
            self.logger.error(f"Error generating scan configuration: {e}")
            return {}

    def set_configuration(self, config: Dict[str, Any]):
        """Set the dialog configuration."""
        try:
            # Source
            if "directory" in config and hasattr(self, "directory_selector"):
                self.directory_selector.set_path(config["directory"])

            # Types de files
            file_types = config.get("file_types", {})
            if hasattr(self, "scan_documents_cb"):
                self.scan_documents_cb.setChecked(file_types.get("documents", True))
            if hasattr(self, "scan_images_cb"):
                self.scan_images_cb.setChecked(file_types.get("images", True))
            if hasattr(self, "scan_videos_cb"):
                self.scan_videos_cb.setChecked(file_types.get("videos", False))
            if hasattr(self, "scan_audio_cb"):
                self.scan_audio_cb.setChecked(file_types.get("audio", False))
            if hasattr(self, "scan_others_cb"):
                self.scan_others_cb.setChecked(file_types.get("others", False))

            # Custom extensions
            if "custom_extensions" in config and hasattr(
                self, "custom_extensions_input"
            ):
                extensions_text = ", ".join(config["custom_extensions"])
                self.custom_extensions_input.setText(extensions_text)

            # Filtres
            if hasattr(self, "min_size_spin"):
                if "min_size_kb" in config:
                    self.min_size_spin.setValue(config["min_size_kb"])
                elif "min_size_mb" in config:
                    self.min_size_spin.setValue(int(config["min_size_mb"] * 1024))
            if hasattr(self, "max_size_spin"):
                if "max_size_kb" in config:
                    self.max_size_spin.setValue(config["max_size_kb"])
                elif "max_size_mb" in config:
                    self.max_size_spin.setValue(int(config["max_size_mb"] * 1024))
            if "skip_hidden" in config and hasattr(self, "skip_hidden_cb"):
                self.skip_hidden_cb.setChecked(config["skip_hidden"])

            # Processing
            if "extract_metadata" in config and hasattr(self, "extract_metadata_cb"):
                self.extract_metadata_cb.setChecked(config["extract_metadata"])
            if "deep_metadata" in config and hasattr(self, "deep_metadata_cb"):
                self.deep_metadata_cb.setChecked(config["deep_metadata"])
            if "cache_metadata" in config and hasattr(self, "cache_metadata_cb"):
                self.cache_metadata_cb.setChecked(config["cache_metadata"])
            if "generate_thumbnails" in config and hasattr(
                self, "generate_thumbnails_cb"
            ):
                self.generate_thumbnails_cb.setChecked(config["generate_thumbnails"])
            if "thumbnail_size" in config and hasattr(self, "thumbnail_size_combo"):
                index = self.thumbnail_size_combo.findText(config["thumbnail_size"])
                if index >= 0:
                    self.thumbnail_size_combo.setCurrentIndex(index)
            if "thumbnail_quality" in config and hasattr(
                self, "thumbnail_quality_slider"
            ):
                self.thumbnail_quality_slider.setValue(config["thumbnail_quality"])
            if "worker_threads" in config and hasattr(self, "threads_spin"):
                self.threads_spin.setValue(config["worker_threads"])
            if "batch_size" in config and hasattr(self, "batch_size_spin"):
                self.batch_size_spin.setValue(config["batch_size"])
            if "pause_batches" in config and hasattr(self, "pause_between_batches_cb"):
                self.pause_between_batches_cb.setChecked(config["pause_batches"])

            # AI
            if "auto_categorize" in config and hasattr(self, "auto_categorize_cb"):
                self.auto_categorize_cb.setChecked(config["auto_categorize"])
            if "categories" in config and hasattr(self, "category_editor"):
                self.category_editor.set_categories(config["categories"])
            if "confidence_threshold" in config and hasattr(self, "confidence_slider"):
                value = int(config["confidence_threshold"] * 100)
                self.confidence_slider.setValue(value)

            # Organization
            if "auto_organize" in config and hasattr(self, "auto_organize_cb"):
                self.auto_organize_cb.setChecked(config["auto_organize"])
            if "target_directory" in config and hasattr(self, "target_selector"):
                self.target_selector.set_path(config["target_directory"])
            if "organization_action" in config:
                if hasattr(self, "move_radio") and hasattr(self, "copy_radio"):
                    if config["organization_action"] == "move":
                        self.move_radio.setChecked(True)
                    else:
                        self.copy_radio.setChecked(True)
            if "organization_structure" in config and hasattr(self, "structure_combo"):
                index = self.structure_combo.findText(config["organization_structure"])
                if index >= 0:
                    self.structure_combo.setCurrentIndex(index)

        except Exception as e:
            self.logger.error(f"Error setting configuration: {e}")

    def start_pipeline(self):
        """Launch the configured sequential scan pipeline."""
        try:
            config = self.get_configuration()
            config["scan_type"] = "pipeline"
            config["ai_processing"] = bool(
                config.get("auto_categorize", False)
                or config.get("auto_organize", False)
            )

            # Validation finale
            is_valid, error_message = self.validate_configuration()
            if not is_valid:
                self.show_validation_error(error_message)
                return

            # Confirmation pour organisation
            if not self._confirm_pipeline_start(config):
                return

            self.save_to_history(config)
            self.scan_requested.emit(config)
            self.accept()

            self.logger.info(f"Pipeline scan started for {config['directory']}")

        except Exception as e:
            self.logger.error(f"Error starting pipeline scan: {e}")

    def _confirm_pipeline_start(self, config: Dict[str, Any]) -> bool:
        """Request final confirmation for destructive/important pipeline steps."""
        if not config.get("auto_organize", False):
            return True

        action = config["organization_action"]
        reply = QMessageBox.question(
            self,
            f"Confirm {action.title()} Organization",
            f"Files will be {action}ed to: {config['target_directory']}\n\n"
            f"Structure: {config['organization_structure']}\n"
            f"Continue with configured scan pipeline?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        return reply == QMessageBox.StandardButton.Yes

    def cancel_operation(self):
        """Cancel the operation."""
        self.reject()

    def cancel_scan(self):
        """Cancel an ongoing scan (if implemented)."""
        # This method can be connectd to a scan controller
        self.logger.info("Scan cancellation requested")

    def save_to_history(self, config: Dict):
        """Save dans l'historique."""
        try:
            history_entry = {
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "path": config["directory"],
                "config": config,
            }

            # Add to the beginning of the list, limit to 10
            self.recent_scans.insert(0, history_entry)
            self.recent_scans = self.recent_scans[:10]

            self.save_settings()
            self.logger.debug(f"Saved scan to history: {config['directory']}")

        except Exception as e:
            self.logger.error(f"Error saving to history: {e}")

    def load_settings(self):
        """Load settings from QSettings."""
        try:
            settings = QSettings("Javis", "AdvancedScan")

            # Favoris
            favorites_data = settings.value("favorites", [])
            if isinstance(favorites_data, list):
                self.favorites = favorites_data

            # Historique
            history_data = settings.value("recent_scans", [])
            if isinstance(history_data, list):
                self.recent_scans = history_data

            self.logger.debug(
                f"Loaded settings: {len(self.favorites)} favorites, {len(self.recent_scans)} history items"
            )

        except Exception as e:
            self.logger.error(f"Error loading settings: {e}")

    def save_settings(self):
        """Save settings to QSettings."""
        try:
            settings = QSettings("Javis", "AdvancedScan")
            settings.setValue("favorites", self.favorites)
            settings.setValue("recent_scans", self.recent_scans)
            settings.sync()

            self.logger.debug("Settings saved successfully")

        except Exception as e:
            self.logger.error(f"Error saving settings: {e}")

    # === DRAG & DROP SUPPORT ===

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag-and-drop enter event."""
        try:
            if event.mimeData().hasUrls():
                event.acceptProposedAction()
                self.logger.debug("Drag enter event accepted")
        except Exception as e:
            self.logger.error(f"Error in drag enter event: {e}")

    def dropEvent(self, event: QDropEvent):
        """Handle file/folder drop event."""
        try:
            urls = event.mimeData().urls()
            if urls:
                path = urls[0].toLocalFile()
                if os.path.isdir(path):
                    if hasattr(self, "directory_selector"):
                        self.directory_selector.set_path(path)
                        event.acceptProposedAction()
                        self.logger.info(f"Directory dropped: {path}")
                else:
                    self.logger.warning(f"Dropped item is not a directory: {path}")
        except Exception as e:
            self.logger.error(f"Error in drop event: {e}")

    def showEvent(self, event):
        """Called when the dialog is shown."""
        super().showEvent(event)

        try:
            # Initial update
            self.validate_configuration()

            if hasattr(self, "structure_preview"):
                self.update_structure_preview()

        except Exception as e:
            self.logger.error(f"Error in showEvent: {e}")
