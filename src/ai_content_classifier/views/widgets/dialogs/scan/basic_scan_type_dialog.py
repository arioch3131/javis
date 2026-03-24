from typing import Dict

from PyQt6.QtWidgets import (
    QDialogButtonBox,
    QCheckBox,
    QFrame,
    QLabel,
    QVBoxLayout,
)
from ai_content_classifier.views.widgets.base.themed_dialog import ThemedDialog


class BasicScanTypeDialog(ThemedDialog):
    """Simple dialog to choose which file groups to include in a basic scan."""

    def __init__(self, parent=None):
        super().__init__(
            parent=parent,
            title="Choose File Types",
            description=None,
            modal=True,
        )
        self.resize(420, 210)

    def create_header(self) -> QFrame | None:
        """This dialog is intentionally compact and does not use the generic header."""
        return None

    def create_content(self) -> QFrame:
        content = QFrame()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        info_label = QLabel("Select at least one file type to scan.")
        info_label.setWordWrap(True)
        info_label.setObjectName("scanTypeInfoLabel")
        layout.addWidget(info_label)

        self.scan_images_cb = QCheckBox("Images")
        self.scan_images_cb.setChecked(True)
        layout.addWidget(self.scan_images_cb)

        self.scan_documents_cb = QCheckBox("Documents")
        self.scan_documents_cb.setChecked(True)
        layout.addWidget(self.scan_documents_cb)

        layout.addStretch()
        return content

    def create_footer(self) -> QFrame:
        footer = QFrame(self)
        layout = QVBoxLayout(footer)
        layout.setContentsMargins(18, 0, 18, 18)

        button_box = QDialogButtonBox(self)
        cancel_button = button_box.addButton(
            "Cancel", QDialogButtonBox.ButtonRole.RejectRole
        )
        start_button = button_box.addButton(
            "Start scan", QDialogButtonBox.ButtonRole.AcceptRole
        )
        start_button.setObjectName("okButton")
        cancel_button.setObjectName("cancelButton")
        button_box.rejected.connect(self.reject)
        button_box.accepted.connect(self.accept_with_validation)
        layout.addWidget(button_box)
        return footer

    def validate_configuration(self) -> tuple[bool, str]:
        if not (self.scan_images_cb.isChecked() or self.scan_documents_cb.isChecked()):
            return False, "Select at least one file type."
        return True, ""

    def get_file_types(self) -> Dict[str, bool]:
        return {
            "documents": self.scan_documents_cb.isChecked(),
            "images": self.scan_images_cb.isChecked(),
            "videos": False,
            "audio": False,
            "others": False,
        }
