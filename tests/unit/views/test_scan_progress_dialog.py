import sys
from types import SimpleNamespace

from PyQt6.QtWidgets import QApplication

from ai_content_classifier.views.widgets.dialogs.scan.scan_progress_dialog import (
    ScanProgressDialog,
)


class TestScanProgressDialog:
    @classmethod
    def setup_class(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_dialog_starts_with_collapsed_details_and_close_hidden(self):
        dialog = ScanProgressDialog()

        assert dialog.details_container.isHidden()
        assert dialog.details_toggle_button.text() == "Show details"
        assert dialog.close_button.isHidden()

    def test_update_progress_stays_indeterminate_while_total_is_unknown(self):
        dialog = ScanProgressDialog()
        dialog.start_scan("/tmp", estimated_files=0)
        progress = SimpleNamespace(
            files_found=24,
            files_processed=0,
            total_files_scanned=3942,
            current_directory="/tmp",
            current_file="/tmp/example.png",
            scan_speed=58.7,
            estimated_total_files=0,
            errors=0,
        )

        dialog.update_progress(progress)

        assert dialog.progress_bar.maximum() == 0
        assert dialog.progress_hint_label.text() == "discovering..."
        assert dialog.found_value_label.text() == "24"
        assert dialog.speed_value_label.text() == "58.7"

    def test_update_progress_switches_to_determinate_once_total_is_known(self):
        dialog = ScanProgressDialog()
        dialog.start_scan("/tmp", estimated_files=0)
        progress = SimpleNamespace(
            files_found=6305,
            files_processed=6200,
            total_files_scanned=219858,
            current_directory="/tmp",
            current_file="/tmp/example.png",
            scan_speed=76.5,
            estimated_total_files=6305,
            errors=0,
        )

        dialog.update_progress(progress)

        assert dialog.progress_bar.maximum() == 6305
        assert dialog.progress_bar.value() == 6200
        assert dialog.progress_hint_label.text() == "6 200 / 6 305 files"

    def test_scan_finish_switches_actions_from_cancel_to_close(self):
        dialog = ScanProgressDialog()
        dialog.start_scan("/tmp", estimated_files=10)

        assert not dialog.cancel_button.isHidden()
        assert dialog.close_button.isHidden()

        dialog.on_scan_finished(success=True, final_stats={"files_found": 10})

        assert dialog.cancel_button.isHidden()
        assert not dialog.close_button.isHidden()
        assert dialog.title_label.text() == "Scan completed"

    def test_details_toggle_expands_technical_information(self):
        dialog = ScanProgressDialog()

        dialog.details_toggle_button.click()

        assert dialog.details_visible is True
        assert not dialog.details_container.isHidden()
        assert dialog.details_toggle_button.text() == "Hide details"
