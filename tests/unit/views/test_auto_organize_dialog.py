from unittest.mock import MagicMock

from ai_content_classifier.views.widgets.dialogs.organization.auto_organize_dialog import (
    AutoOrganizeDialog,
)


def test_validate_configuration_uses_file_selector_public_state():
    dialog = AutoOrganizeDialog.__new__(AutoOrganizeDialog)
    dialog.target_selector = MagicMock()
    dialog.target_selector.is_path_valid.return_value = False
    dialog.target_selector.get_path.return_value = "/tmp/missing"
    dialog.target_selector.error_label.text.return_value = "❌ Directory does not exist"

    is_valid, error_message = dialog.validate_configuration()

    assert is_valid is False
    assert error_message == "Directory does not exist"
