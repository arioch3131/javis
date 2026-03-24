# views/widgets/dialogs/organization/auto_organize_dialog.py
"""
AutoOrganizeDialog - Dialog to automatically organize les files already scanned.

Version refactored utilisant la nouvelle architecture avec les widgets basic
et les composants reusables.
"""

import os
from typing import Any, Dict, List, Tuple

from ai_content_classifier.controllers.auto_organization_controller import (
    AutoOrganizationController,
)
from ai_content_classifier.services.theme.theme_service import ThemePalette
from PyQt6.QtCore import QSettings, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from ai_content_classifier.views.widgets.base.action_bar import ActionBar
from ai_content_classifier.views.widgets.base.header_section import HeaderSection
from ai_content_classifier.views.widgets.base.themed_dialog import ThemedDialog
from ai_content_classifier.views.widgets.common.file_selector import FileSelector
from ai_content_classifier.views.widgets.common.progress_panel import ProgressPanel


class AutoOrganizeDialog(ThemedDialog):
    """
    Dialog to configure l'organisation automatique des files existants.

    Uses la nouvelle architecture avec widgets reusables et validation integratede.
    Integrated with AutoOrganizationController for full organization management.
    """

    # Signal emitted quand l'organisation est completed successfully
    organization_completed = pyqtSignal(dict)  # Statistiques finales

    def __init__(
        self,
        file_list: List[Tuple[str, str]],
        organization_controller: AutoOrganizationController,
        parent=None,
    ):
        # Data and controller
        self.file_list = file_list  # Liste de (file_path, directory)
        self.file_count = len(file_list)
        self.organization_controller = organization_controller

        # State du dialog
        self.is_organizing = False
        self.preview_data = None

        # Initialiser le dialog basic
        super().__init__(
            parent=parent,
            title="Auto-Organize Current Files",
            description=f"Organize {self.file_count} currently displayed files into a structured folder hierarchy based on their categories, types, or creation dates.",
            modal=True,
        )

        # Specific configuration
        self.resize(800, 700)
        self._fit_to_screen()

        # ✅ CONNEXION AVEC LE CONTRÔLEUR D'ORGANISATION
        self.connect_organization_controller()

        # Saved configuration
        self.load_settings()

        # Timer pour les animations et feedback
        self.feedback_timer = QTimer()
        self.feedback_timer.setSingleShot(True)

    def connect_organization_controller(self):
        """Connect les signaux avec le controller d'organisation."""
        if not self.organization_controller:
            return

        try:
            # Signaux du controller vers le dialog
            self.organization_controller.organization_started.connect(
                self.on_organization_started
            )
            self.organization_controller.progress_updated.connect(
                self.on_progress_updated
            )
            self.organization_controller.file_organized.connect(self.on_file_organized)
            self.organization_controller.organization_completed.connect(
                self.on_organization_completed
            )
            self.organization_controller.organization_cancelled.connect(
                self.on_organization_cancelled
            )
            self.organization_controller.organization_error.connect(
                self.on_organization_error
            )
            self.organization_controller.preview_ready.connect(self.on_preview_ready)

            self.logger.debug("Organization controller signals connectd")

        except Exception as e:
            self.logger.error(f"Error connecting organization controller: {e}")

    def create_header(self) -> QFrame:
        """Create the header avec statistiques."""
        # Header principal
        header = HeaderSection(
            title="📂 Auto-Organize Current Files",
            description=f"Organize {self.file_count} currently displayed files into a structured folder hierarchy.",
            parent=self,
        )

        # Ajouter les statistiques
        stats_container = QWidget()
        stats_container.setObjectName("statsContainer")
        stats_layout = QHBoxLayout(stats_container)
        stats_layout.setContentsMargins(12, 8, 12, 8)

        # File count
        file_count_label = QLabel("📊 Files Ready")
        file_count_label.setObjectName("statLabel")
        file_count_value = QLabel(f"{self.file_count}")
        file_count_value.setObjectName("statValue")

        # Estimated time
        estimated_seconds = self.file_count * 0.1  # 0.1 second per file
        if estimated_seconds < 60:
            time_text = f"{estimated_seconds:.0f}s"
        else:
            time_text = f"{estimated_seconds / 60:.1f}m"

        time_label = QLabel("⏱️ Estimated Time")
        time_label.setObjectName("statLabel")
        time_value = QLabel(time_text)
        time_value.setObjectName("statValue")

        stats_layout.addWidget(file_count_label)
        stats_layout.addWidget(file_count_value)
        stats_layout.addStretch()
        stats_layout.addWidget(time_label)
        stats_layout.addWidget(time_value)

        # Ajouter au header
        header.add_to_layout(stats_container)

        return header

    def apply_dialog_theme(self, palette: ThemePalette):
        """Applique le theme du dialogue avec des titres de sections lisibles."""
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
        """Create le contenu principal du dialog."""
        content = QFrame()
        content.setObjectName("organizationContent")

        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(20)

        # Configuration en tabs
        self.config_tabs = QTabWidget()
        self.config_tabs.setObjectName("configurationTabs")

        # Tab Principal
        main_tab = self.create_main_tab()
        self.config_tabs.addTab(main_tab, "🏗️ Structure")

        # Tab Options
        options_tab = self.create_options_tab()
        self.config_tabs.addTab(options_tab, "⚙️ Options")

        # Tab Preview
        preview_tab = self.create_preview_tab()
        self.config_tabs.addTab(preview_tab, "👁️ Preview")

        layout.addWidget(self.config_tabs)

        # Progress panel (hidden initially)
        self.progress_panel = ProgressPanel(
            parent=self, title="Organization Progress", show_details=True, show_log=True
        )
        self.progress_panel.cancel_requested.connect(self.cancel_organization)
        self.progress_panel.hide()
        layout.addWidget(self.progress_panel)

        return content

    def create_main_tab(self) -> QWidget:
        """Create l'tab principal avec destination et structure."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(20)

        # === DESTINATION SECTION ===
        dest_group = QGroupBox("📁 Destination Directory")
        dest_layout = QVBoxLayout(dest_group)
        dest_layout.setSpacing(12)

        # Usesr FileSelector pour la destination
        self.target_selector = FileSelector(
            mode="directory",
            parent=self,
            label="Target Directory:",
            placeholder="Choose where to organize your files...",
        )

        # Smart default value
        default_target = os.path.expanduser("~/Organized_Files")
        self.target_selector.set_path(default_target)

        # Connexions
        self.target_selector.path_changed.connect(self.on_target_changed)
        self.target_selector.path_validated.connect(self.on_target_validated)

        dest_layout.addWidget(self.target_selector)

        # Info sur l'espace disque
        self.space_info_label = QLabel()
        self.space_info_label.setObjectName("spaceInfoLabel")
        dest_layout.addWidget(self.space_info_label)

        layout.addWidget(dest_group)

        # === ACTION SECTION ===
        action_group = QGroupBox("⚡ Organization Action")
        action_layout = QVBoxLayout(action_group)
        action_layout.setSpacing(12)

        # Radio buttons pour l'action
        self.action_group = QButtonGroup()

        # Copy option
        copy_container = QWidget()
        copy_layout = QHBoxLayout(copy_container)
        copy_layout.setContentsMargins(0, 0, 0, 0)

        self.copy_radio = QRadioButton("📋 Copy files")
        self.copy_radio.setChecked(True)  # Safe default
        copy_desc = QLabel("(Keep originals in current locations)")
        copy_desc.setObjectName("actionDescription")

        copy_layout.addWidget(self.copy_radio)
        copy_layout.addWidget(copy_desc)
        copy_layout.addStretch()

        # Move option
        move_container = QWidget()
        move_layout = QHBoxLayout(move_container)
        move_layout.setContentsMargins(0, 0, 0, 0)

        self.move_radio = QRadioButton("📤 Move files")
        move_desc = QLabel("(Relocate files to new organization)")
        move_desc.setObjectName("actionDescription")

        move_layout.addWidget(self.move_radio)
        move_layout.addWidget(move_desc)
        move_layout.addStretch()

        self.action_group.addButton(self.copy_radio)
        self.action_group.addButton(self.move_radio)

        action_layout.addWidget(copy_container)
        action_layout.addWidget(move_container)

        # Warning pour move
        self.move_warning = QLabel(
            "⚠️ Warning: Move action will remove files from their current locations!"
        )
        self.move_warning.setObjectName("warningLabel")
        self.move_warning.hide()
        action_layout.addWidget(self.move_warning)

        # Connexions
        self.copy_radio.toggled.connect(self.on_action_changed)
        self.move_radio.toggled.connect(self.on_action_changed)

        layout.addWidget(action_group)

        # === STRUCTURE SECTION ===
        structure_group = QGroupBox("🏗️ Organization Structure")
        structure_layout = QVBoxLayout(structure_group)
        structure_layout.setSpacing(12)

        # Combo pour structure
        structure_selection_layout = QHBoxLayout()

        structure_label = QLabel("Structure:")
        structure_label.setObjectName("fieldLabel")

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

        # Connexion
        self.structure_combo.currentTextChanged.connect(
            self.update_structure_description
        )

        structure_selection_layout.addWidget(structure_label)
        structure_selection_layout.addWidget(self.structure_combo, 1)
        structure_selection_layout.addStretch()

        structure_layout.addLayout(structure_selection_layout)

        # Description de la structure
        self.structure_description = QLabel()
        self.structure_description.setObjectName("structureDescription")
        self.structure_description.setWordWrap(True)
        structure_layout.addWidget(self.structure_description)

        layout.addWidget(structure_group)

        layout.addStretch()
        return widget

    def create_options_tab(self) -> QWidget:
        """Create l'tab des advanced options."""
        widget = QWidget()

        # Scroll area pour les options
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(20)

        # === FILE HANDLING OPTIONS ===
        file_group = QGroupBox("📁 File Handling")
        file_layout = QVBoxLayout(file_group)
        file_layout.setSpacing(10)

        self.preserve_dates_cb = QCheckBox("📅 Preserve file dates and metadata")
        self.preserve_dates_cb.setChecked(True)
        self.preserve_dates_cb.setToolTip(
            "Keep original creation and modification dates"
        )

        self.handle_duplicates_cb = QCheckBox("🔄 Auto-rename duplicate files")
        self.handle_duplicates_cb.setChecked(True)
        self.handle_duplicates_cb.setToolTip(
            "Automatically rename files with conflicting names"
        )

        self.create_log_cb = QCheckBox("📝 Create organization log file")
        self.create_log_cb.setChecked(True)
        self.create_log_cb.setToolTip("Generate a detailed log of all operations")

        file_layout.addWidget(self.preserve_dates_cb)
        file_layout.addWidget(self.handle_duplicates_cb)
        file_layout.addWidget(self.create_log_cb)

        layout.addWidget(file_group)

        # === PERFORMANCE OPTIONS ===
        perf_group = QGroupBox("⚡ Performance")
        perf_layout = QGridLayout(perf_group)
        perf_layout.setSpacing(12)

        # Batch size
        batch_label = QLabel("Batch size:")
        batch_label.setObjectName("fieldLabel")

        self.batch_size_combo = QComboBox()
        self.batch_size_combo.addItems(
            ["10 files", "25 files", "50 files", "100 files"]
        )
        self.batch_size_combo.setCurrentIndex(1)  # 25 by default
        self.batch_size_combo.setToolTip("Number of files processed in each batch")

        perf_layout.addWidget(batch_label, 0, 0)
        perf_layout.addWidget(self.batch_size_combo, 0, 1)

        # Verification
        self.verify_copies_cb = QCheckBox("Verify file integrity after copy/move")
        self.verify_copies_cb.setChecked(True)
        self.verify_copies_cb.setToolTip(
            "Compare file checksums to ensure successful operations"
        )
        perf_layout.addWidget(self.verify_copies_cb, 1, 0, 1, 2)

        layout.addWidget(perf_group)

        # === POST-ORGANIZATION OPTIONS ===
        post_group = QGroupBox("🎯 After Organization")
        post_layout = QVBoxLayout(post_group)
        post_layout.setSpacing(10)

        self.open_target_cb = QCheckBox("📁 Open target directory when complete")
        self.open_target_cb.setChecked(True)
        self.open_target_cb.setToolTip("Automatically open the organized directory")

        self.show_report_cb = QCheckBox("📊 Show detailed organization report")
        self.show_report_cb.setChecked(True)
        self.show_report_cb.setToolTip(
            "Display a summary of the organization operation"
        )

        post_layout.addWidget(self.open_target_cb)
        post_layout.addWidget(self.show_report_cb)

        layout.addWidget(post_group)

        layout.addStretch()

        scroll.setWidget(content_widget)

        # Main layout for the tab
        tab_layout = QVBoxLayout(widget)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll)

        return widget

    def create_preview_tab(self) -> QWidget:
        """Create l'tab d'preview."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Controls de l'preview
        controls_layout = QHBoxLayout()

        self.preview_btn = QPushButton("🔍 Generate Preview")
        self.preview_btn.clicked.connect(self.generate_preview)
        controls_layout.addWidget(self.preview_btn)

        controls_layout.addStretch()

        # Indicateur de statut
        self.preview_status = QLabel(
            "Click 'Generate Preview' to see organization structure"
        )
        self.preview_status.setObjectName("previewStatus")
        controls_layout.addWidget(self.preview_status)

        layout.addLayout(controls_layout)

        # Tree widget pour l'preview
        self.preview_tree = QTreeWidget()
        self.preview_tree.setHeaderLabels(["Folder Structure", "Files", "Size"])
        self.preview_tree.setAlternatingRowColors(True)
        layout.addWidget(self.preview_tree, 1)

        # Information de l'preview
        self.preview_info_label = QLabel()
        self.preview_info_label.setObjectName("previewInfoLabel")
        self.preview_info_label.setWordWrap(True)
        layout.addWidget(self.preview_info_label)

        return widget

    def create_footer(self) -> QFrame:
        """Create le pied de page avec boutons."""
        # Usesr ActionBar pour les boutons
        action_bar = ActionBar(self, alignment="right")

        # Boutons principaux
        action_bar.add_action("👁️ Preview", self.show_preview_tab, "previewButton")
        action_bar.add_stretch()
        action_bar.add_action("❌ Cancel", self.cancel_operation, "cancelButton")
        action_bar.add_action(
            "🚀 Start Organization",
            self.start_organization,
            "organizeButton",
            primary=True,
        )

        # References for manipulation
        self.organize_btn = action_bar.get_action_button("organizeButton")
        self.cancel_btn = action_bar.get_action_button("cancelButton")
        self.preview_btn_footer = action_bar.get_action_button("previewButton")

        return action_bar

    # === MÉTHODES D'ÉVÉNEMENTS ===

    def on_target_changed(self, path: str):
        """Called quand le chemin cible change."""
        self.update_space_info(path)
        self.validate_configuration()

    def on_target_validated(self, is_valid: bool, error_message: str):
        """Called quand la validation du chemin change."""
        self.validate_configuration()

    def on_action_changed(self):
        """Handle le changement d'action (copy/move)."""
        is_move = self.move_radio.isChecked()
        self.move_warning.setVisible(is_move)

        action = "move" if is_move else "copy"
        self.logger.debug(f"Organization action changed to: {action}")

    def update_structure_description(self):
        """Update la description of the selected structure."""
        structure = self.structure_combo.currentText()

        descriptions = {
            "By Category": "Files will be organized into folders based on their AI-assigned categories (e.g., Work, Personal, Archive).",
            "By Year": "Files will be organized by their creation year (e.g., 2024, 2023, 2022).",
            "By Type": "Files will be organized by file type (e.g., Documents, Images, Videos, Audio).",
            "By Category/Year": "Two-level organization: Category folders containing year subfolders.",
            "By Type/Category": "Two-level organization: File type folders containing category subfolders.",
        }

        description = descriptions.get(structure, "Custom organization structure")
        self.structure_description.setText(description)

        self.logger.debug(f"Organization structure changed to: {structure}")

    def update_space_info(self, target_dir: str):
        """Update les informations d'espace disque."""
        try:
            if not target_dir or not os.path.exists(target_dir):
                self.space_info_label.setText("📁 Directory will be created")
                return

            if hasattr(os, "statvfs"):  # Unix/Linux
                stat = os.statvfs(target_dir)
                available_bytes = stat.f_bavail * stat.f_frsize
                total_bytes = stat.f_blocks * stat.f_frsize

                available_gb = available_bytes / (1024**3)
                total_gb = total_bytes / (1024**3)
                percent_free = (available_bytes / total_bytes) * 100

                if percent_free > 50:
                    icon = "💚"
                elif percent_free > 20:
                    icon = "💛"
                else:
                    icon = "🔴"

                self.space_info_label.setText(
                    f"{icon} Available: {available_gb:.1f} GB / {total_gb:.1f} GB ({percent_free:.1f}% free)"
                )
            else:
                self.space_info_label.setText("💿 Space information not available")

        except Exception as e:
            self.space_info_label.setText("⚠️ Could not determine available space")
            self.logger.debug(f"Error getting space info: {e}")

    def show_preview_tab(self):
        """Display l'tab d'preview."""
        self.config_tabs.setCurrentIndex(2)  # Index de l'tab preview

    def generate_preview(self):
        """Generate un preview de l'organisation."""
        config_dict = self.get_configuration()

        self.preview_status.setText("Generating preview...")
        self.preview_btn.setEnabled(False)

        try:
            # Usesr le controller pour generate l'preview
            self.organization_controller.generate_preview(self.file_list, config_dict)

        except Exception as e:
            self.logger.error(f"Error generating preview: {e}")
            self.preview_status.setText(f"Preview error: {e}")
            self.preview_btn.setEnabled(True)

    def start_organization(self):
        """Lance l'organisation avec validation finale."""
        if self.is_organizing:
            return

        config_dict = self.get_configuration()

        # Validation finale
        is_valid, error_message = self.validate_configuration()
        if not is_valid:
            self.show_validation_error(error_message)
            return

        # Confirmation finale
        if not self.confirm_organization(config_dict):
            return

        try:
            # Saver les settings
            self.save_settings()

            use_integrated_operations = bool(
                self.organization_controller
                and self.organization_controller.has_integrated_operations_host()
            )

            if not use_integrated_operations:
                # Displayr le panel de progression
                self.progress_panel.show()
                self.config_tabs.hide()

                # Start la progression
                self.progress_panel.start_progress(
                    max_value=self.file_count, title="Organizing Files"
                )

            # Usesr le controller pour run l'organisation
            success = self.organization_controller.start_organization(
                self.file_list, config_dict
            )

            if success:
                self.is_organizing = True
                self.organize_btn.setEnabled(False)
                self.cancel_btn.setText("❌ Cancel Operation")
                if use_integrated_operations:
                    self.accept()
            else:
                if not use_integrated_operations:
                    self.progress_panel.hide()
                    self.config_tabs.show()
                QMessageBox.critical(
                    self,
                    "Organization Error",
                    "Failed to start organization. Check logs for details.",
                )

        except Exception as e:
            self.logger.error(f"Error starting organization: {e}")
            self.progress_panel.hide()
            self.config_tabs.show()
            QMessageBox.critical(
                self, "Organization Error", f"Failed to start organization:\n{e}"
            )

    def cancel_organization(self):
        """Cancel l'organisation in progress."""
        if self.is_organizing:
            reply = QMessageBox.question(
                self,
                "Cancel Organization",
                "Are you sure you want to cancel the ongoing organization?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.organization_controller.cancel_organization()

    def cancel_operation(self):
        """Handle l'global cancellation."""
        if self.is_organizing:
            self.cancel_organization()
        else:
            self.reject()

    # === SLOTS POUR LES ÉVÉNEMENTS DU CONTRÔLEUR ===

    def on_organization_started(self):
        """Called quand l'organisation starts."""
        self.is_organizing = True
        self.organize_btn.setEnabled(False)
        self.cancel_btn.setText("❌ Cancel Operation")

    def on_progress_updated(self, processed: int, total: int):
        """Called pour update la progression."""
        self.progress_panel.update_progress(processed, success=True)

    def on_file_organized(self, source: str, target: str, action: str):
        """Called when a file is organized."""
        filename = os.path.basename(source)
        self.progress_panel.log_message(
            f"{action.title()}: {filename} -> {os.path.basename(target)}"
        )

    def on_organization_completed(self, stats: dict):
        """Called quand l'organisation est completed."""
        self.is_organizing = False

        if self.organization_controller.has_integrated_operations_host():
            self.organization_completed.emit(stats)
            self.accept()
            return

        # Terminer la progression
        self.progress_panel.complete_progress(success=True)

        # Émettre le signal
        self.organization_completed.emit(stats)

        # Offer to close or view results
        self._show_completion_dialog(stats)

    def on_organization_cancelled(self):
        """Called when organization is cancelled."""
        self.is_organizing = False
        self.progress_panel.cancel_progress()
        self.organize_btn.setEnabled(True)
        self.cancel_btn.setText("❌ Cancel")

        # Back to configuration
        self.progress_panel.hide()
        self.config_tabs.show()

    def on_organization_error(self, error: str):
        """Called en cas d'error d'organisation."""
        self.is_organizing = False
        self.progress_panel.complete_progress(success=False)
        self.organize_btn.setEnabled(True)
        self.cancel_btn.setText("❌ Cancel")

        # Back to configuration
        self.progress_panel.hide()
        self.config_tabs.show()

        QMessageBox.critical(
            self, "Organization Error", f"Organization failed:\n{error}"
        )

    def on_preview_ready(self, preview: dict):
        """Called when preview is ready."""
        self.preview_btn.setEnabled(True)

        if "error" in preview:
            self.preview_status.setText(f"Preview error: {preview['error']}")
            return

        self.preview_data = preview
        self._update_preview_display()

        file_count = preview.get("file_count", 0)
        folder_count = len(preview.get("structure", {}))
        conflicts = len(preview.get("conflicts", []))

        self.preview_status.setText(
            f"Preview: {file_count} files in {folder_count} folders ({conflicts} conflicts)"
        )

    def _update_preview_display(self):
        """Update display de l'preview."""
        if not self.preview_data:
            return

        self.preview_tree.clear()
        structure = self.preview_data.get("structure", {})

        for folder_path, files in structure.items():
            folder_name = os.path.basename(folder_path) or folder_path
            folder_item = QTreeWidgetItem([folder_name, str(len(files)), ""])

            # Ajouter les files
            for filename in files[:10]:  # Limiter display
                file_item = QTreeWidgetItem([filename, "", ""])
                folder_item.addChild(file_item)

            if len(files) > 10:
                more_item = QTreeWidgetItem(
                    [f"... and {len(files) - 10} more files", "", ""]
                )
                more_item.setDisabled(True)
                folder_item.addChild(more_item)

            self.preview_tree.addTopLevelItem(folder_item)
            folder_item.setExpanded(True)

        # Summary information
        total_size = self.preview_data.get("total_size_mb", 0)
        conflicts = len(self.preview_data.get("conflicts", []))

        info_text = f"Total size: {total_size:.1f} MB"
        if conflicts > 0:
            info_text += f" | ⚠️ {conflicts} naming conflicts detected"

        self.preview_info_label.setText(info_text)

    def _show_completion_dialog(self, stats: dict):
        """Display un dialog de completion."""
        successful = stats.get("successful", 0)
        total = stats.get("total_files", 0)
        target_dir = stats.get("target_directory", "")

        msg = QMessageBox(self)
        msg.setWindowTitle("Organization Completed")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText(f"Successfully organized {successful}/{total} files!")

        if target_dir and self.open_target_cb.isChecked():
            msg.setInformativeText(f"Files organized in: {target_dir}")

            open_button = msg.addButton(
                "📁 Open Folder", QMessageBox.ButtonRole.ActionRole
            )
            open_button.clicked.connect(lambda: self._open_target_directory(target_dir))

        msg.exec()
        self.accept()

    def _open_target_directory(self, target_dir: str):
        """Ouvre le folder cible dans l'explorateur."""
        try:
            import platform
            import subprocess

            system = platform.system()
            if system == "Windows":
                subprocess.run(["explorer", target_dir])
            elif system == "Darwin":  # macOS
                subprocess.run(["open", target_dir])
            else:  # Linux
                subprocess.run(["xdg-open", target_dir])

        except Exception as e:
            self.logger.error(f"Error opening target directory: {e}")

    # === VALIDATION ET CONFIGURATION ===

    def validate_configuration(self) -> tuple[bool, str]:
        """Valide la configuration actuelle."""
        errors = []

        # Check the file selector
        if not self.target_selector.is_path_valid():
            selector_error = ""
            error_label = getattr(self.target_selector, "error_label", None)
            if error_label and hasattr(error_label, "text"):
                selector_error = error_label.text().strip()
            if selector_error.startswith("❌ "):
                selector_error = selector_error[2:].strip()
            if not selector_error:
                indicator = getattr(self.target_selector, "validation_indicator", None)
                if indicator and hasattr(indicator, "toolTip"):
                    selector_error = indicator.toolTip().strip()
            errors.append(selector_error or "Invalid target directory")

        # Specific validations
        target_path = self.target_selector.get_path()
        if not target_path:
            errors.append("No target directory specified")

        # Return the result
        is_valid = len(errors) == 0
        error_message = "; ".join(errors) if errors else ""

        return is_valid, error_message

    def get_configuration(self) -> Dict[str, Any]:
        """Return la configuration actuelle."""
        # Extraire la taille de batch
        batch_text = self.batch_size_combo.currentText()
        batch_size = int(batch_text.split()[0])  # "25 files" -> 25

        return {
            # Configuration basic
            "target_directory": self.target_selector.get_path(),
            "organization_structure": self.structure_combo.currentText(),
            "organization_action": "move" if self.move_radio.isChecked() else "copy",
            "file_count": self.file_count,
            # Options de file
            "preserve_dates": self.preserve_dates_cb.isChecked(),
            "handle_duplicates": self.handle_duplicates_cb.isChecked(),
            "create_log": self.create_log_cb.isChecked(),
            # Options de performance
            "batch_size": batch_size,
            "verify_copies": self.verify_copies_cb.isChecked(),
            # Options post-organisation
            "open_target": self.open_target_cb.isChecked(),
            "show_report": self.show_report_cb.isChecked(),
        }

    def set_configuration(self, config: Dict[str, Any]):
        """Set la configuration du dialog."""
        try:
            if "target_directory" in config:
                self.target_selector.set_path(config["target_directory"])

            if "organization_structure" in config:
                index = self.structure_combo.findText(config["organization_structure"])
                if index >= 0:
                    self.structure_combo.setCurrentIndex(index)

            if "organization_action" in config:
                if config["organization_action"] == "move":
                    self.move_radio.setChecked(True)
                else:
                    self.copy_radio.setChecked(True)

            # Options
            if "preserve_dates" in config:
                self.preserve_dates_cb.setChecked(config["preserve_dates"])
            if "handle_duplicates" in config:
                self.handle_duplicates_cb.setChecked(config["handle_duplicates"])
            if "create_log" in config:
                self.create_log_cb.setChecked(config["create_log"])
            if "verify_copies" in config:
                self.verify_copies_cb.setChecked(config["verify_copies"])
            if "open_target" in config:
                self.open_target_cb.setChecked(config["open_target"])
            if "show_report" in config:
                self.show_report_cb.setChecked(config["show_report"])

            # Batch size
            if "batch_size" in config:
                batch_size = config["batch_size"]
                for i in range(self.batch_size_combo.count()):
                    text = self.batch_size_combo.itemText(i)
                    if str(batch_size) in text:
                        self.batch_size_combo.setCurrentIndex(i)
                        break

        except Exception as e:
            self.logger.error(f"Error setting configuration: {e}")

    def confirm_organization(self, config_dict: Dict) -> bool:
        """Demande confirmation finale."""
        action = config_dict["organization_action"]
        target = config_dict["target_directory"]
        structure = config_dict["organization_structure"]
        count = config_dict["file_count"]

        # Estimated time calculation
        estimated_seconds = count * 0.1
        time_text = (
            f"{estimated_seconds:.0f} seconds"
            if estimated_seconds < 60
            else f"{estimated_seconds / 60:.1f} minutes"
        )

        # Message de confirmation
        message_parts = [
            f"Ready to {action} {count} files to:",
            f"📁 {target}",
            "",
            f"🏗️ Organization: {structure}",
            f"⏱️ Estimated time: {time_text}",
            "",
        ]

        if action == "move":
            message_parts.extend(
                [
                    "⚠️ WARNING: FILES WILL BE MOVED!",
                    "• Files will be removed from current locations",
                    "• This action cannot be easily undone",
                    "",
                ]
            )

        message_parts.append("Do you want to proceed?")
        message = "\n".join(message_parts)

        reply = QMessageBox.question(
            self,
            f"🚀 Confirm {action.title()} Organization",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        return reply == QMessageBox.StandardButton.Yes

    def load_settings(self):
        """Load les settings depuis QSettings."""
        settings = QSettings("Javis", "AutoOrganize")

        config = {
            "target_directory": settings.value(
                "default_target", os.path.expanduser("~/Organized_Files")
            ),
            "organization_structure": settings.value(
                "default_structure", "By Category"
            ),
            "organization_action": settings.value("default_action", "copy"),
            "preserve_dates": settings.value("preserve_dates", True, type=bool),
            "handle_duplicates": settings.value("handle_duplicates", True, type=bool),
            "create_log": settings.value("create_log", True, type=bool),
            "verify_copies": settings.value("verify_copies", True, type=bool),
            "batch_size": settings.value("batch_size", 25, type=int),
            "open_target": settings.value("open_target", True, type=bool),
            "show_report": settings.value("show_report", True, type=bool),
        }

        self.set_configuration(config)

    def save_settings(self):
        """Save les settings dans QSettings."""
        settings = QSettings("Javis", "AutoOrganize")
        config = self.get_configuration()

        for key, value in config.items():
            if key != "file_count":  # Ne pas saver le nombre de files
                settings.setValue(key.replace("organization_", "default_"), value)

        settings.sync()
        self.logger.debug("Settings saved successfully")

    def showEvent(self, event):
        """Called when the dialog is shown."""
        super().showEvent(event)

        # Initial update
        self.update_structure_description()
        self.update_space_info(self.target_selector.get_path())
        self.validate_configuration()
