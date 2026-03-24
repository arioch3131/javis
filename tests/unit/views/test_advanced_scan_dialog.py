from unittest.mock import MagicMock

from ai_content_classifier.models.config_models import ConfigKey
from ai_content_classifier.views.widgets.dialogs.scan.advanced_scan_dialog import (
    AdvancedScanDialog,
)


def test_apply_application_settings_uses_global_categories_models_and_threshold():
    dialog = AdvancedScanDialog.__new__(AdvancedScanDialog)
    dialog.logger = MagicMock()
    dialog.settings_manager = MagicMock()
    dialog.settings_manager.get_unified_categories.return_value = ["Space", "Work"]
    dialog.category_editor = MagicMock()
    dialog.confidence_slider = MagicMock()
    dialog.image_model_combo = MagicMock()
    dialog.image_model_combo.findText.return_value = 2
    dialog.document_model_combo = MagicMock()
    dialog.document_model_combo.findText.return_value = 1
    dialog.llm_controller = MagicMock()
    dialog.llm_controller.llm_service.config_service.get.side_effect = lambda key: {
        ConfigKey.CONFIDENCE_THRESHOLD: 0.7,
        ConfigKey.IMAGE_MODEL: "vision-model",
        ConfigKey.DOCUMENT_MODEL: "doc-model",
    }[key]

    dialog._apply_application_settings()

    dialog.category_editor.set_categories.assert_called_once_with(["Space", "Work"])
    dialog.confidence_slider.setValue.assert_called_once_with(70)
    dialog.image_model_combo.setCurrentIndex.assert_called_once_with(2)
    dialog.document_model_combo.setCurrentIndex.assert_called_once_with(1)


def test_on_organization_toggled_keeps_configuration_widgets_editable():
    dialog = AdvancedScanDialog.__new__(AdvancedScanDialog)
    dialog.logger = MagicMock()
    dialog.directory_selector = MagicMock()
    dialog.target_selector = MagicMock()
    dialog.copy_radio = MagicMock()
    dialog.move_radio = MagicMock()
    dialog.structure_combo = MagicMock()
    dialog.structure_preview = MagicMock()
    dialog.validate_configuration = MagicMock()

    dialog.on_organization_toggled(False)

    dialog.target_selector.setEnabled.assert_not_called()
    dialog.copy_radio.setEnabled.assert_not_called()
    dialog.move_radio.setEnabled.assert_not_called()
    dialog.structure_combo.setEnabled.assert_not_called()
    dialog.structure_preview.setEnabled.assert_not_called()
    dialog.validate_configuration.assert_called_once_with()


def test_start_pipeline_emits_single_config_with_pipeline_flags():
    dialog = AdvancedScanDialog.__new__(AdvancedScanDialog)
    dialog.logger = MagicMock()
    dialog.get_configuration = MagicMock(
        return_value={
            "directory": "/tmp/source",
            "auto_categorize": True,
            "auto_organize": True,
            "organization_action": "copy",
            "organization_structure": "By Category",
            "target_directory": "/tmp/organized",
        }
    )
    dialog.validate_configuration = MagicMock(return_value=(True, ""))
    dialog._confirm_pipeline_start = MagicMock(return_value=True)
    dialog.save_to_history = MagicMock()
    dialog.scan_requested = MagicMock()
    dialog.accept = MagicMock()

    dialog.start_pipeline()

    emitted_config = dialog.scan_requested.emit.call_args.args[0]
    assert emitted_config["scan_type"] == "pipeline"
    assert emitted_config["ai_processing"] is True
    dialog.save_to_history.assert_called_once_with(emitted_config)
    dialog.accept.assert_called_once_with()
