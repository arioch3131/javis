# ai_content_classifier/views/widgets/adaptive_preview_widget.py
# ruff: noqa: E402
import os
import sys
from typing import Any, Callable, Dict, Optional


def _restore_pyqt6_if_mocked() -> None:
    pyqt6_module = sys.modules.get("PyQt6")
    if pyqt6_module is None:
        return
    module_origin = getattr(pyqt6_module.__class__, "__module__", "")
    if module_origin.startswith("unittest.mock"):
        for module_name in (
            "PyQt6",
            "PyQt6.QtCore",
            "PyQt6.QtGui",
            "PyQt6.QtWidgets",
            "PyQt6.QtSvg",
        ):
            sys.modules.pop(module_name, None)


_restore_pyqt6_if_mocked()

from ai_content_classifier.core.logger import get_logger
from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QDesktopServices, QFont, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import QUrl
from ai_content_classifier.services.preprocessing.text_extraction_service import (
    TextExtractionService,
)
from ai_content_classifier.services.theme.theme_service import (
    ThemePalette,
    get_theme_service,
)


class AdaptiveImageLabel(QLabel):
    """
    Image label that automatically adapts to available size
    while maintaining proportions.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        from PyQt6.QtCore import Qt as QtCoreQt

        self.original_pixmap: Optional[QPixmap] = None
        self.setAlignment(QtCoreQt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(160, 160)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.metadata_generator_func: Optional[Callable] = None
        self._placeholder_fill = "#f0f0f0"
        self._placeholder_text = "#888"

        # Timer to avoid too many resizes
        self.resize_timer = QTimer()
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.update_scaled_pixmap)

    def set_pixmap(self, pixmap: QPixmap):
        """Sets the image to display."""
        self.original_pixmap = pixmap
        self.update_scaled_pixmap()

    def update_scaled_pixmap(self):
        """Updates the resized image."""
        from PyQt6.QtCore import Qt as QtCoreQt

        if not self.original_pixmap or self.original_pixmap.isNull():
            return

        # Calculate available size with margins
        available_size = self.size()
        margin = 20
        target_size = QSize(
            available_size.width() - margin, available_size.height() - margin
        )

        # Resize while maintaining proportions
        scaled_pixmap = self.original_pixmap.scaled(
            target_size,
            QtCoreQt.AspectRatioMode.KeepAspectRatio,
            QtCoreQt.TransformationMode.SmoothTransformation,
        )

        super().setPixmap(scaled_pixmap)

    def clear_image(self):
        """Clears the image."""
        self.original_pixmap = None
        self.clear()

    def resizeEvent(self, event):
        """Handles widget resizing."""
        super().resizeEvent(event)
        # Delay to avoid too many recalculations
        self.resize_timer.start(100)

    def set_placeholder(self, text: str = "No image"):
        """Displays a placeholder."""
        from PyQt6.QtCore import Qt as QtCoreQt

        # Create a placeholder pixmap
        placeholder_size = QSize(400, 300)
        placeholder = QPixmap(placeholder_size)
        placeholder.fill(QColor(self._placeholder_fill))

        # Draw text
        painter = QPainter(placeholder)
        painter.setPen(QColor(self._placeholder_text))
        font = QFont()
        font.setPointSize(16)
        painter.setFont(font)
        painter.drawText(placeholder.rect(), QtCoreQt.AlignmentFlag.AlignCenter, text)
        painter.end()

        self.set_pixmap(placeholder)

    def apply_theme(self, palette: ThemePalette):
        theme = get_theme_service().get_theme_definition(palette.name)
        metrics = theme.metrics
        self._placeholder_fill = palette.surface_variant
        self._placeholder_text = palette.on_surface_variant
        self.setStyleSheet(
            f"""
            AdaptiveImageLabel {{
                border: 1px solid {palette.outline};
                background-color: {palette.surface};
                border-radius: {metrics.radius_lg + 2}px;
            }}
            """
        )


class MetadataDisplayWidget(QWidget):
    """
    Widget to display metadata in an organized and readable way.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        """Configures the user interface."""
        from PyQt6.QtCore import Qt as QtCoreQt

        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(6)

        # Groups for different metadata types
        self.file_info_group = self.create_group("File Information")
        self.image_info_group = self.create_group("Image Properties")
        self.document_info_group = self.create_group("Document Properties")
        self.exif_group = self.create_group("EXIF Data")
        self.classification_group = self.create_group("AI Classification")

        # Scroll area for all content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(
            QtCoreQt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        scroll_area.setVerticalScrollBarPolicy(
            QtCoreQt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        # Container widget
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.addWidget(self.file_info_group)
        container_layout.addWidget(self.image_info_group)
        container_layout.addWidget(self.document_info_group)
        container_layout.addWidget(self.exif_group)
        container_layout.addWidget(self.classification_group)
        container_layout.addStretch()

        scroll_area.setWidget(container)
        self.layout.addWidget(scroll_area)

    def create_group(self, title: str) -> QGroupBox:
        """Creates a group with a title."""
        group = QGroupBox(title)

        # Vertical layout for content
        layout = QVBoxLayout(group)
        content_label = QLabel()
        content_label.setWordWrap(True)
        content_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        content_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        layout.addWidget(content_label)

        return group

    def get_content_label(self, group: QGroupBox) -> QLabel:
        """Retrieves the content label of a group."""
        return group.layout().itemAt(0).widget()

    def _set_group_content(
        self,
        group: QGroupBox,
        lines: list[str],
        empty_text: str = "",
        hide_if_empty: bool = True,
    ):
        """Sets text and visibility for one metadata group."""
        content_label = self.get_content_label(group)
        has_content = bool(lines)
        if has_content:
            content_label.setText("\n".join(lines))
            group.show()
            return

        if hide_if_empty:
            group.hide()
        else:
            content_label.setText(empty_text)
            group.show()

    def set_file_info(self, metadata: Dict[str, Any]):
        """Updates file information."""
        file_info = []

        # Basic information
        # File name is already shown in the preview header.
        if "size_formatted" in metadata:
            file_info.append(f"Size: {metadata['size_formatted']}")
        if "last_modified" in metadata:
            file_info.append(f"Modified: {metadata['last_modified']}")
        if "extension" in metadata:
            file_info.append(f"Extension: {metadata['extension']}")
        if "file_path" in metadata:
            file_info.append(f"Path: {metadata['file_path']}")

        self._set_group_content(
            self.file_info_group,
            file_info,
            empty_text="No information available",
            hide_if_empty=False,
        )

    def set_image_info(self, metadata: Dict[str, Any]):
        """Updates image information."""
        image_info = []

        if "dimensions" in metadata:
            image_info.append(f"Dimensions: {metadata['dimensions']}")
        if "format" in metadata:
            image_info.append(f"Format: {metadata['format']}")
        if "mode" in metadata:
            image_info.append(f"Color mode: {metadata['mode']}")
        if "aspect_ratio" in metadata:
            image_info.append(f"Aspect ratio: {metadata['aspect_ratio']:.2f}")

        self._set_group_content(self.image_info_group, image_info, hide_if_empty=True)

    def set_document_info(self, metadata: "Dict[str, Any]"):
        """Updates document information."""
        doc_info_list = []

        # Try to get PDF specific info
        pdf_info = metadata.get("pdf_info", {})
        if pdf_info:
            if "page_count" in pdf_info:
                doc_info_list.append(f"Pages: {pdf_info['page_count']}")
            if "first_page_preview" in pdf_info:
                doc_info_list.append(
                    f"First Page Preview: {pdf_info['first_page_preview'][:200]}..."
                )  # Limit preview length

            document_metadata = pdf_info.get("document_info", {})
            if document_metadata:
                doc_info_list.append("\n--- Document Metadata ---")
                for key, value in document_metadata.items():
                    doc_info_list.append(f"{key}: {value}")

        # Fallback to general document info if no PDF info or other document types
        if not pdf_info:
            if "page_count" in metadata:
                doc_info_list.append(f"Pages: {metadata['page_count']}")
            if "language" in metadata:
                doc_info_list.append(f"Language: {metadata['language']}")
            if "format" in metadata:
                doc_info_list.append(f"Format: {metadata['format']}")

        self._set_group_content(
            self.document_info_group, doc_info_list, hide_if_empty=True
        )

    def set_exif_info(self, metadata: Dict[str, Any]):
        """Updates EXIF information."""
        exif_info = []

        # Extract important EXIF data
        exif_data = metadata.get("exif", {})
        if exif_data:
            if "DateTimeOriginal" in exif_data:
                exif_info.append(f"Date taken: {exif_data['DateTimeOriginal']}")
            if "Software" in exif_data:
                exif_info.append(f"Software: {exif_data['Software']}")
            if "ImageWidth" in exif_data and "ImageLength" in exif_data:
                exif_info.append(
                    f"Original size: {exif_data['ImageWidth']}x{exif_data['ImageLength']}"
                )

        # GPS data
        gps_data = metadata.get("gps", {})
        if gps_data:
            exif_info.append("GPS data available")

        self._set_group_content(self.exif_group, exif_info, hide_if_empty=True)

    def set_classification_info(self, classification: Dict[str, Any]):
        """Updates classification information."""
        class_info = []

        if classification.get("category"):
            class_info.append(f"Category: {classification['category']}")
        confidence = classification.get("confidence")
        if isinstance(confidence, (int, float)):
            class_info.append(f"Confidence: {confidence:.0%}")
        if classification.get("tags"):
            tags = classification["tags"]
            if isinstance(tags, list) and tags:
                class_info.append(f"Tags: {', '.join(str(tag) for tag in tags)}")

        self._set_group_content(
            self.classification_group, class_info, hide_if_empty=True
        )

    def clear_all(self):
        """Clears all information."""
        for group in [
            self.file_info_group,
            self.image_info_group,
            self.document_info_group,
            self.exif_group,
            self.classification_group,
        ]:
            content_label = self.get_content_label(group)
            content_label.clear()
        # Keep only base file info visible by default.
        self.file_info_group.show()
        self.image_info_group.hide()
        self.document_info_group.hide()
        self.exif_group.hide()
        self.classification_group.hide()

    def apply_theme(self, palette: ThemePalette):
        theme = get_theme_service().get_theme_definition(palette.name)
        metrics = theme.metrics
        typography = theme.typography
        self.setStyleSheet(
            f"""
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            QGroupBox {{
                font-family: "{typography.font_family}";
                font-weight: {typography.font_weight_bold};
                border: 1px solid {palette.outline};
                border-radius: {metrics.radius_lg}px;
                margin-top: 0.75em;
                padding-top: {metrics.spacing_sm + 2}px;
                background-color: {palette.surface};
                color: {palette.on_surface};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: {metrics.spacing_md}px;
                padding: 0 {metrics.spacing_sm - 2}px 0 {metrics.spacing_sm - 2}px;
                color: {palette.on_surface};
            }}
            QLabel {{
                color: {palette.on_surface};
                font-family: "{typography.font_family}";
                font-size: {typography.font_size_sm}px;
            }}
            """
        )


class AdaptivePreviewWidget(QWidget):
    """
    Adaptive preview widget that adjusts to window size.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )
        self.current_file_path: Optional[str] = None
        self._text_extraction_service: Optional[TextExtractionService] = None
        self.display_mode = "embedded"
        self.setup_ui()
        self._setup_theme()

    def setup_ui(self):
        """Configures the user interface."""
        from PyQt6.QtCore import Qt as QtCoreQt

        theme = get_theme_service().get_theme_definition()
        metrics = theme.metrics
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(
            metrics.spacing_sm - 3,
            metrics.spacing_sm - 3,
            metrics.spacing_sm - 3,
            metrics.spacing_sm - 3,
        )
        self.main_layout.setSpacing(metrics.spacing_sm)

        self.header_widget = self.create_header()
        self.header_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
        self.main_layout.addWidget(self.header_widget)

        # Main horizontal splitter: preview left, metadata right
        self.main_splitter = QSplitter(QtCoreQt.Orientation.Horizontal)

        # Image section (left)
        self.image_section = self.create_image_section()
        self.main_splitter.addWidget(self.image_section)

        # Metadata section (right)
        self.metadata_widget = MetadataDisplayWidget()
        self.main_splitter.addWidget(self.metadata_widget)

        # Default proportions: larger visual preview, compact details panel
        self.main_splitter.setSizes([500, 460])
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setStretchFactor(0, 2)
        self.main_splitter.setStretchFactor(1, 3)

        self.main_layout.addWidget(self.main_splitter)
        # Start with metadata hidden until a file is selected.
        self.metadata_widget.hide()

    def create_header(self) -> QWidget:
        """Creates the preview header with file title and quick actions."""
        theme = get_theme_service().get_theme_definition()
        metrics = theme.metrics
        header = QWidget(self)
        header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(max(4, metrics.spacing_xs))

        top_row = QWidget(header)
        top_row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        top_row_layout = QHBoxLayout(top_row)
        top_row_layout.setContentsMargins(0, 0, 0, 0)
        top_row_layout.setSpacing(metrics.spacing_sm)
        top_row_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title_container = QWidget(header)
        title_container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
        title_layout = QVBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(2)

        self.title_label = QLabel("No file selected")
        self.title_label.setWordWrap(True)
        self.title_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
        title_layout.addWidget(self.title_label)

        self.path_label = QLabel("Select a file to view its details")
        self.path_label.setWordWrap(True)
        self.path_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
        title_layout.addWidget(self.path_label)

        top_row_layout.addWidget(title_container, 1)

        self.copy_path_button = QPushButton("Copy Path", header)
        self.copy_path_button.setObjectName("previewCopyPathButton")
        self.copy_path_button.setEnabled(False)
        self.copy_path_button.clicked.connect(self.copy_current_path)
        self.copy_path_button.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        top_row_layout.addWidget(self.copy_path_button)

        self.open_folder_button = QPushButton("Open Folder", header)
        self.open_folder_button.setObjectName("previewCopyPathButton")
        self.open_folder_button.setEnabled(False)
        self.open_folder_button.clicked.connect(self.open_current_folder)
        self.open_folder_button.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        top_row_layout.addWidget(self.open_folder_button)

        header_layout.addWidget(top_row)

        self.summary_container = QWidget(header)
        self.summary_container.setObjectName("previewSummary")
        self.summary_container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
        summary_layout = QHBoxLayout(self.summary_container)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(metrics.spacing_sm)

        self.size_summary_label = QLabel("No selection", self.summary_container)
        self.size_summary_label.setObjectName("previewSummaryChip")
        self.size_summary_label.setFixedHeight(42)
        summary_layout.addWidget(self.size_summary_label)

        self.type_summary_label = QLabel("", self.summary_container)
        self.type_summary_label.setObjectName("previewSummaryChip")
        self.type_summary_label.setFixedHeight(42)
        summary_layout.addWidget(self.type_summary_label)

        self.meta_summary_label = QLabel("", self.summary_container)
        self.meta_summary_label.setObjectName("previewSummaryChip")
        self.meta_summary_label.setFixedHeight(42)
        summary_layout.addWidget(self.meta_summary_label)

        summary_layout.addStretch()
        header_layout.addWidget(self.summary_container)
        self.summary_container.hide()

        return header

    def create_image_section(self) -> QWidget:
        """Creates the image display section."""
        theme = get_theme_service().get_theme_definition()
        metrics = theme.metrics
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(
            metrics.spacing_sm,
            metrics.spacing_sm,
            metrics.spacing_sm,
            metrics.spacing_sm,
        )
        layout.setSpacing(metrics.spacing_sm)

        # Adaptive image
        self.image_label = AdaptiveImageLabel()
        layout.addWidget(self.image_label)

        return section

    def _setup_theme(self):
        theme_service = get_theme_service()
        theme_service.palette_updated.connect(self.apply_theme)
        self.apply_theme(theme_service.get_current_palette())

    def apply_theme(self, palette: ThemePalette):
        theme = get_theme_service().get_theme_definition(palette.name)
        metrics = theme.metrics
        typography = theme.typography
        self.setStyleSheet(
            f"""
            AdaptivePreviewWidget {{
                background: transparent;
            }}
            QLabel {{
                color: {palette.on_surface};
                font-family: "{typography.font_family}";
            }}
            QWidget#previewSummary {{
                background-color: transparent;
            }}
            QLabel#previewSummaryChip {{
                background-color: {palette.surface_variant};
                color: {palette.on_surface_variant};
                border: 1px solid {palette.outline};
                border-radius: {metrics.radius_pill}px;
                padding: {max(2, metrics.spacing_xs - 1)}px {metrics.spacing_sm}px;
                font-family: "{typography.font_family}";
                font-size: {typography.font_size_xs}px;
                font-weight: {typography.font_weight_medium};
            }}
            QPushButton#previewCopyPathButton {{
                background-color: {palette.surface};
                color: {palette.on_surface};
                border: 1px solid {palette.outline};
                border-radius: {metrics.radius_md}px;
                padding: {metrics.spacing_sm}px {metrics.spacing_md}px;
                min-height: {metrics.control_height}px;
                font-family: "{typography.font_family}";
                font-weight: {typography.font_weight_semibold};
            }}
            QPushButton#previewCopyPathButton:disabled {{
                background-color: {palette.disabled};
                color: {palette.disabled_text};
                border: 1px solid {palette.outline};
            }}
            """
        )
        self.title_label.setStyleSheet(
            f'font-family: "{typography.font_family}"; '
            f"font-size: {typography.font_size_lg + 2}px; "
            f"font-weight: {typography.font_weight_bold}; "
            f"color: {palette.on_surface};"
        )
        self.path_label.setStyleSheet(
            f'font-family: "{typography.font_family}"; '
            f"color: {palette.on_surface_variant}; "
            f"font-size: {typography.font_size_sm}px;"
        )
        self.image_label.apply_theme(palette)
        self.metadata_widget.apply_theme(palette)
        self.metadata_widget.setMinimumWidth(
            340 if self.display_mode == "dialog" else 300
        )

    def set_metadata_generator(self, generator_func):
        """Sets the generation function."""
        self.metadata_generator_func = generator_func

    def set_file_details(self, file_data: Dict[str, Any]):
        """
        Updates displayed details with file data.

        Args:
            file_data: Dictionary containing file information
        """
        self.logger.debug(f"set_file_details - Received file_data: {file_data}")
        # Update metadata and content_type first
        metadata = file_data.get("metadata", {})
        content_type = file_data.get("content_type")

        # Update title
        if "file_path" in file_data:
            filename = os.path.basename(file_data["file_path"])
            self.title_label.setText(filename)
            self.current_file_path = file_data["file_path"]
            self.path_label.setText(file_data["file_path"])
            self.copy_path_button.setEnabled(True)
            self.open_folder_button.setEnabled(True)
            self._update_summary(file_data, metadata, content_type)

        # Clear all previous details
        self.metadata_widget.clear_all()
        self.metadata_widget.show()
        self._refresh_splitter_sizes()

        # Clear any existing text from the image label
        self.image_label.setText("")

        # Update image
        thumbnail_path = file_data.get("thumbnail_path")
        if thumbnail_path and os.path.exists(thumbnail_path):
            pixmap = QPixmap(thumbnail_path)
            if not pixmap.isNull():
                self.image_label.set_pixmap(pixmap)
            else:
                self.image_label.set_placeholder("Image not readable")
        else:
            # No thumbnail, try to display image directly if it's an image
            if self.current_file_path and self.is_image_file(self.current_file_path):
                try:
                    direct_pixmap = QPixmap(self.current_file_path)
                    if not direct_pixmap.isNull():
                        self.image_label.set_pixmap(direct_pixmap)
                    else:
                        self.image_label.set_placeholder("Preview not available")
                except Exception:
                    self.image_label.set_placeholder("Preview not available")
            else:
                # If no thumbnail, check if it's a document
                if self.current_file_path and self.is_document_file(
                    self.current_file_path
                ):
                    preview_text = self._build_document_preview_text(
                        self.current_file_path, metadata
                    )
                    if preview_text:
                        self.image_label.set_placeholder(f"Preview:\n{preview_text}")
                    else:
                        self.image_label.set_placeholder("Preview not available")
                else:
                    self.image_label.set_placeholder("Preview not available")

        if metadata:
            metadata_with_path = dict(metadata)
            metadata_with_path["file_path"] = self.current_file_path
            self.metadata_widget.set_file_info(metadata_with_path)

            if content_type == "image":
                self.logger.debug("set_file_details - Content type is image.")
                self.metadata_widget.image_info_group.show()
                self.metadata_widget.exif_group.show()
                self.metadata_widget.document_info_group.hide()
                self.metadata_widget.set_image_info(metadata)
                self.metadata_widget.set_exif_info(metadata)
            elif content_type == "document":
                self.logger.debug("set_file_details - Content type is document.")
                self.metadata_widget.document_info_group.show()
                self.metadata_widget.image_info_group.hide()
                self.metadata_widget.exif_group.hide()
                self.metadata_widget.set_document_info(metadata)
                self.logger.debug(
                    f"set_file_details - Document info set with: {metadata}"
                )
            else:
                self.logger.debug(
                    "set_file_details - Content type is unknown or not image/document."
                )
                # Hide both if type is unknown or not image/document
                self.metadata_widget.image_info_group.hide()
                self.metadata_widget.document_info_group.hide()
                self.metadata_widget.exif_group.hide()
        else:
            self.logger.debug("set_file_details - No metadata received.")
            # Basic metadata if not available
            if self.current_file_path:
                basic_metadata = self.metadata_generator_func(self.current_file_path)
                basic_metadata["file_path"] = self.current_file_path
                self.metadata_widget.set_file_info(basic_metadata)
                # Hide all type-specific groups if no metadata
                self.metadata_widget.image_info_group.hide()
                self.metadata_widget.document_info_group.hide()
                self.metadata_widget.exif_group.hide()

        # Classification
        classification = file_data.get("classification", {})
        self.metadata_widget.set_classification_info(classification)

    def clear_details(self):
        """Resets the display."""
        self.title_label.setText("No file selected")
        self.path_label.setText("Select a file to view its details")
        self.copy_path_button.setEnabled(False)
        self.open_folder_button.setEnabled(False)
        self.size_summary_label.setText("No selection")
        self.type_summary_label.clear()
        self.meta_summary_label.clear()
        self.summary_container.hide()
        self.image_label.clear_image()
        self.image_label.set_placeholder("No selection")
        self.metadata_widget.clear_all()
        self.metadata_widget.hide()
        self.current_file_path = None

    def _update_summary(
        self,
        file_data: Dict[str, Any],
        metadata: Dict[str, Any],
        content_type: Optional[str],
    ) -> None:
        info = dict(metadata)
        if "size_formatted" not in info and self.current_file_path:
            info.update(self.get_basic_file_info(self.current_file_path))

        self.size_summary_label.setText(info.get("size_formatted", "Unknown size"))

        extension = (
            info.get("extension") or os.path.splitext(file_data.get("file_path", ""))[1]
        )
        type_text = content_type.title() if isinstance(content_type, str) else "File"
        if extension:
            type_text = f"{type_text} {extension}"
        self.type_summary_label.setText(type_text.strip())

        meta_text = ""
        if metadata.get("dimensions"):
            meta_text = str(metadata["dimensions"])
        elif metadata.get("page_count"):
            meta_text = f"{metadata['page_count']} pages"
        elif metadata.get("last_modified"):
            meta_text = str(metadata["last_modified"])
        self.meta_summary_label.setText(meta_text)
        self.meta_summary_label.setVisible(bool(meta_text))
        self.summary_container.show()

    def copy_current_path(self):
        if self.current_file_path:
            QApplication.clipboard().setText(self.current_file_path)

    def open_current_folder(self):
        if self.current_file_path:
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(os.path.dirname(self.current_file_path))
            )

    def set_display_mode(self, mode: str) -> None:
        self.display_mode = mode
        if mode == "dialog":
            self.main_layout.setContentsMargins(0, 0, 0, 0)
            self.main_layout.setSpacing(6)
            self.title_label.setWordWrap(False)
            self.copy_path_button.setMinimumHeight(40)
            self.open_folder_button.setMinimumHeight(40)
        else:
            self.title_label.setWordWrap(True)
        self._refresh_splitter_sizes()

    def is_image_file(self, file_path: str) -> bool:
        """Checks if the file is an image."""
        image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"}
        ext = os.path.splitext(file_path)[1].lower()
        return ext in image_extensions

    def is_document_file(self, file_path: str) -> bool:
        """Checks if the file is a document."""
        document_extensions = {
            ".pdf",
            ".doc",
            ".docx",
            ".txt",
            ".md",
            ".odt",
            ".rtf",
            ".epub",
        }
        ext = os.path.splitext(file_path)[1].lower()
        return ext in document_extensions

    def _build_document_preview_text(
        self, file_path: str, metadata: Dict[str, Any]
    ) -> str:
        """
        Build a short preview text for document-like files.
        """
        try:
            candidates = [
                metadata.get("pdf_info", {}).get("first_page_preview", ""),
                metadata.get("docx_info", {}).get("text_preview", ""),
                metadata.get("text_preview", ""),
                metadata.get("text_content", ""),
            ]
            for value in candidates:
                if isinstance(value, str) and value.strip():
                    return self._compact_preview_text(value)

            # Fallback extraction for txt/md/doc-like files.
            if self._text_extraction_service is None:
                self._text_extraction_service = TextExtractionService()

            extraction = self._text_extraction_service.extract_text_for_llm(
                file_path, max_length=1200
            )
            if extraction.success and extraction.text.strip():
                return self._compact_preview_text(extraction.text)
        except Exception as exc:
            self.logger.debug(
                f"Document preview extraction failed for {file_path}: {exc}"
            )

        return ""

    @staticmethod
    def _compact_preview_text(
        text: str, max_lines: int = 6, max_chars: int = 480
    ) -> str:
        """Compact long text into a readable preview snippet."""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return ""
        preview = "\n".join(lines[:max_lines])
        if len(preview) > max_chars:
            return preview[: max_chars - 3] + "..."
        if len(lines) > max_lines:
            return preview + "\n..."
        return preview

    def get_basic_file_info(self, file_path: str) -> Dict[str, Any]:
        """Retrieves basic file information."""
        try:
            stat = os.stat(file_path)
            size_mb = stat.st_size / (1024 * 1024)

            return {
                "filename": os.path.basename(file_path),
                "size_formatted": (
                    f"{size_mb:.2f} MB"
                    if size_mb >= 1
                    else f"{stat.st_size / 1024:.1f} KB"
                ),
                "extension": os.path.splitext(file_path)[1],
                "last_modified": f"{stat.st_mtime:.0f}",
            }
        except Exception:
            return {"filename": os.path.basename(file_path)}

    def resizeEvent(self, event):
        """Handles widget resizing."""
        super().resizeEvent(event)
        self._refresh_splitter_sizes()

    def _refresh_splitter_sizes(self) -> None:
        total_width = max(320, self.width())
        if not self.metadata_widget.isVisible():
            self.main_splitter.setSizes([max(240, total_width), 0])
            return

        if self.display_mode == "dialog":
            image_width = max(420, int(total_width * 0.62))
            meta_width = max(360, total_width - image_width)
        else:
            image_width = max(260, int(total_width * 0.36))
            meta_width = max(320, total_width - image_width)

        self.main_splitter.setSizes([image_width, meta_width])
