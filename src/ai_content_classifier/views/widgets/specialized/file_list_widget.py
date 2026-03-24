# ai_content_classifier/views/widgets/file_list_widget.py
import os

from PyQt6.QtCore import QSortFilterProxyModel, Qt
from PyQt6.QtGui import QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import QHeaderView, QTreeView


class FileListWidget(QTreeView):
    """
    Widget to display the list of files and directories.
    Uses QTreeView with QStandardItemModel for a custom view.
    """

    # Constants for type detection (as in content_database_service.py)
    IMAGE_EXTENSIONS = {
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".bmp",
        ".tiff",
        ".webp",
        ".ico",
        ".heic",
        ".heif",
        ".jp2",
        ".j2k",
        ".avif",
    }
    DOCUMENT_EXTENSIONS = {
        ".pdf",
        ".doc",
        ".docx",
        ".txt",
        ".md",
        ".rtf",
        ".odt",
        ".csv",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
    }

    def __init__(self, parent=None):
        super().__init__(parent)

        # Model with 4 columns: Name, Type, Category, Directory
        self.model = QStandardItemModel(0, 4)
        self.model.setHeaderData(0, Qt.Orientation.Horizontal, "File Name")
        self.model.setHeaderData(1, Qt.Orientation.Horizontal, "Type")
        self.model.setHeaderData(2, Qt.Orientation.Horizontal, "Category")
        self.model.setHeaderData(3, Qt.Orientation.Horizontal, "Directory")

        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.model)
        self.setModel(self.proxy_model)

        # Display configuration to take 100% width
        self.setAnimated(False)
        self.setIndentation(20)
        self.setSortingEnabled(True)

        # Column configuration to take full available width
        header = self.header()

        # Define proportions for each column
        # Name: 40%, Type: 15%, Category: 20%, Directory: 25%
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        # Define minimum widths to prevent columns from becoming too small
        header.setMinimumSectionSize(80)

        # Allow manual resizing if necessary
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # File Name
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Type
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # Category
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)  # Directory

        # Ensure the last section stretches to fill the space
        header.setStretchLastSection(True)

    def _detect_content_type(self, file_path: str) -> str:
        """
        Detects the content type based on the file extension.

        Args:
            file_path: File path

        Returns:
            Content type as a string
        """
        ext = os.path.splitext(file_path)[1].lower()

        if ext in self.IMAGE_EXTENSIONS:
            return "🖼️ Image"
        elif ext in self.DOCUMENT_EXTENSIONS:
            return "📄 Document"
        else:
            return "📁 File"

    def set_file_data(self, file_data: list[tuple[str, str]]):
        """
        Populates the model with file data.
        Args:
            file_data: List of tuples (full_file_path, directory_path).
        """
        self.model.setRowCount(0)  # Clear existing data
        self.model.blockSignals(True)  # Block signals during population
        print(f"DEBUG: set_file_data received {len(file_data)} files.")

        for full_path, directory_path, category, content_type in file_data:
            # Extract just the file name instead of the full path
            filename = os.path.basename(full_path)

            # Detect content type
            content_type = self._detect_content_type(full_path)

            # Create items for each column
            file_name_item = QStandardItem(filename)
            # Store the full path in data to retrieve it later
            file_name_item.setData(full_path, Qt.ItemDataRole.UserRole)

            type_item = QStandardItem(content_type)
            category_item = QStandardItem(category)
            directory_item = QStandardItem(directory_path)

            # Make Type and Category columns non-editable by default
            type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            # Allow category editing for future functionality
            # category_item can remain editable

            self.model.appendRow(
                [file_name_item, type_item, category_item, directory_item]
            )

        self.model.blockSignals(False)  # Unblock signals
        print(f"DEBUG: Model now has {self.model.rowCount()} rows.")
        self.model.layoutChanged.emit()  # Emit layout changed signal to refresh view
        self.update()  # Force repaint

    def set_name_filters(self, name_filters: list[str]):
        """
        Applies file name filters to the model.
        Note: This implementation is simplified for QStandardItemModel.
        It filters on the file path column.
        """
        if name_filters:
            filter_regex = "|".join([f"\\.{ext.lstrip('.')}$" for ext in name_filters])
            self.proxy_model.setFilterRegularExpression(filter_regex)
            self.proxy_model.setFilterKeyColumn(0)  # Filter by file name column
            self.proxy_model.setFilterCaseSensitivity(
                Qt.CaseSensitivity.CaseInsensitive
            )
        else:
            self.proxy_model.setFilterRegularExpression("")  # Clear filter

    def get_selected_file_path(self, index):
        """
        Returns the full path of the selected file.
        """
        # Map the proxy model index to the source model index
        source_index = self.proxy_model.mapToSource(index)
        # Get the item from the first column (file name)
        item = self.model.item(source_index.row(), 0)

        if item:
            # Get the full path stored in UserRole
            full_path = item.data(Qt.ItemDataRole.UserRole)
            return full_path
        return None

    def get_selected_file_info(self, index):
        """
        Returns all information of the selected file.

        Returns:
            dict: Dictionary with 'path', 'name', 'type', 'category', 'directory'
        """
        source_index = self.proxy_model.mapToSource(index)

        if source_index.isValid():
            name_item = self.model.item(source_index.row(), 0)
            type_item = self.model.item(source_index.row(), 1)
            category_item = self.model.item(source_index.row(), 2)
            directory_item = self.model.item(source_index.row(), 3)

            if name_item:
                return {
                    "path": name_item.data(Qt.ItemDataRole.UserRole),
                    "name": name_item.text(),
                    "type": type_item.text() if type_item else "",
                    "category": (
                        category_item.text() if category_item else "Uncategorized"
                    ),
                    "directory": directory_item.text() if directory_item else "",
                }

        return None

    def update_file_category(self, index, new_category: str):
        """
        Updates the category of a file.

        Args:
            index: File index in the view
            new_category: New category
        """
        source_index = self.proxy_model.mapToSource(index)

        if source_index.isValid():
            category_item = self.model.item(source_index.row(), 2)
            if category_item:
                category_item.setText(new_category)
                print(
                    f"DEBUG: Updated category to '{new_category}' for file at row {source_index.row()}"
                )

    def filter_by_type(self, file_type: str):
        """
        Filters files by type.

        Args:
            file_type: File type to display ('Image', 'Document', 'Video', 'Audio', 'All')
        """
        if file_type == "All":
            self.proxy_model.setFilterRegularExpression("")
        else:
            # Filter by Type column (column 1)
            self.proxy_model.setFilterKeyColumn(1)
            self.proxy_model.setFilterRegularExpression(file_type)
            self.proxy_model.setFilterCaseSensitivity(
                Qt.CaseSensitivity.CaseInsensitive
            )

    def filter_by_category(self, category: str):
        """
        Filters files by category.

        Args:
            category: Category to display
        """
        if category == "All":
            self.proxy_model.setFilterRegularExpression("")
        else:
            # Filter by Category column (column 2)
            self.proxy_model.setFilterKeyColumn(2)
            self.proxy_model.setFilterRegularExpression(category)
            self.proxy_model.setFilterCaseSensitivity(
                Qt.CaseSensitivity.CaseInsensitive
            )

    def get_statistics(self):
        """
        Returns statistics on displayed files.

        Returns:
            dict: Statistics by type and category
        """
        stats = {"total": self.model.rowCount(), "by_type": {}, "by_category": {}}

        for row in range(self.model.rowCount()):
            type_item = self.model.item(row, 1)
            category_item = self.model.item(row, 2)

            if type_item:
                type_text = type_item.text()
                stats["by_type"][type_text] = stats["by_type"].get(type_text, 0) + 1

            if category_item:
                category_text = category_item.text()
                stats["by_category"][category_text] = (
                    stats["by_category"].get(category_text, 0) + 1
                )

        return stats
