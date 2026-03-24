import sys

from PyQt6.QtWidgets import QApplication

from ai_content_classifier.views.widgets.common.operation_state import (
    OperationDetail,
    OperationStat,
    OperationViewState,
)
from ai_content_classifier.views.widgets.common.progress_panel import ProgressPanel


class TestProgressPanelOperationState:
    @classmethod
    def setup_class(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_apply_operation_state_keeps_details_collapsed_by_default(self):
        panel = ProgressPanel(show_details=True, show_log=True)
        state = OperationViewState(
            operation_id="scan",
            kind="scan",
            title="Scanning...",
            state="discovering",
            summary="3 942 files scanned",
            current_item="/tmp/example.png",
            stats=[
                OperationStat("Found", "24", "files"),
                OperationStat("Success", "0", "processed"),
                OperationStat("Speed", "58.7", "files / sec"),
            ],
            details=[
                OperationDetail("Scanned", "3942"),
                OperationDetail("Directory", "/tmp"),
                OperationDetail("Rate", "58.7 items/s"),
                OperationDetail("Elapsed", "00:01"),
                OperationDetail("Remaining", "waiting for file discovery"),
            ],
            log_entries=["[00:08:13] Scan started"],
            primary_action="cancel",
        )

        panel.apply_operation_state(state)

        assert panel.summary_label.text() == "3 942 files scanned"
        assert panel.details_container.isHidden()
        assert panel.cancel_button.text() == "Cancel"
        assert not panel.cancel_button.isHidden()

        panel.set_details_expanded(True)
        assert panel.processed_label.text() == "Scanned: 3942"
        assert panel.rate_label.text() == "Rate: 58.7 items/s"

    def test_inline_progress_bar_can_be_hidden_for_integrated_operations(self):
        panel = ProgressPanel(show_details=True, show_log=False)

        panel.set_show_progress_bar(False)

        assert panel.progress_container.isHidden()
