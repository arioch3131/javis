import sys
from unittest.mock import MagicMock

import ai_content_classifier.views.widgets.dialogs.categorization.categorization_dialog as dialog_module
from PyQt6.QtWidgets import QApplication

from ai_content_classifier.views.widgets.dialogs.categorization.categorization_dialog import (
    CategorizationDialog,
)


class TestCategorizationDialog:
    @classmethod
    def setup_class(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_start_categorization_prompts_only_when_rewriting_existing_categories(
        self, monkeypatch
    ):
        dialog = CategorizationDialog.__new__(CategorizationDialog)
        dialog.file_count = 10
        dialog.logger = MagicMock()
        dialog.save_settings = MagicMock()
        dialog.accept = MagicMock()
        dialog.categorization_requested = MagicMock()
        dialog.validate_configuration = MagicMock(return_value=(True, ""))
        dialog.get_configuration = MagicMock(
            return_value={
                "category_count": 3,
                "batch_size": 10,
                "confidence_threshold": 0.3,
                "save_results": True,
                "only_uncategorized": False,
            }
        )

        question_mock = MagicMock(
            return_value=dialog_module.QMessageBox.StandardButton.No
        )
        monkeypatch.setattr(dialog_module.QMessageBox, "question", question_mock)

        dialog.start_categorization()

        question_mock.assert_called_once()
        dialog.categorization_requested.emit.assert_not_called()

    def test_start_categorization_skips_overwrite_prompt_for_only_unclassified(
        self, monkeypatch
    ):
        dialog = CategorizationDialog.__new__(CategorizationDialog)
        dialog.file_count = 10
        dialog.logger = MagicMock()
        dialog.save_settings = MagicMock()
        dialog.accept = MagicMock()
        dialog.categorization_requested = MagicMock()
        dialog.validate_configuration = MagicMock(return_value=(True, ""))
        dialog.get_configuration = MagicMock(
            return_value={
                "category_count": 3,
                "batch_size": 10,
                "confidence_threshold": 0.3,
                "save_results": True,
                "only_uncategorized": True,
            }
        )

        question_mock = MagicMock()
        monkeypatch.setattr(dialog_module.QMessageBox, "question", question_mock)

        dialog.start_categorization()

        question_mock.assert_not_called()
        dialog.categorization_requested.emit.assert_called_once()
