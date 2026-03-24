"""Compact scan progress dialog with collapsible technical details."""

from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
)

from ai_content_classifier.services.theme.theme_service import get_theme_service
from ai_content_classifier.views.widgets.base.action_bar import ActionBar
from ai_content_classifier.views.widgets.base.themed_dialog import ThemedDialog


class ScanProgressDialog(ThemedDialog):
    """Dialog displaying scan progress in a compact, product-oriented layout."""

    cancel_requested = pyqtSignal()

    def __init__(self, parent=None):
        self.start_time = time.time()
        self.is_scanning = False
        self.details_visible = False
        self.scan_stats = {
            "files_found": 0,
            "files_processed": 0,
            "total_files_scanned": 0,
            "current_directory": "",
            "current_file": "",
            "scan_speed": 0.0,
            "estimated_total": 0,
            "errors": 0,
        }

        super().__init__(
            parent=parent,
            title="Scanning...",
            description=None,
            modal=True,
        )

        self.resize(560, 520)
        self.setup_timer()
        self.set_scanning_state(False)
        self.close_button.setVisible(False)
        self._update_overview_display()
        self._update_detail_fields()

    def setup_timer(self):
        self.elapsed_timer = QTimer()
        self.elapsed_timer.timeout.connect(self.update_elapsed_time)
        self.elapsed_timer.start(1000)

    def create_header(self) -> QFrame:
        theme = get_theme_service().get_theme_definition()
        metrics = theme.metrics

        container = QFrame(self)
        container.setObjectName("scanHeader")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(
            metrics.spacing_md,
            metrics.spacing_md,
            metrics.spacing_md,
            metrics.spacing_sm,
        )
        layout.setSpacing(metrics.spacing_sm)

        self.status_dot = QLabel("●", container)
        self.status_dot.setObjectName("scanStatusDot")
        layout.addWidget(self.status_dot)

        self.title_label = QLabel("Scanning...", container)
        self.title_label.setObjectName("scanTitleLabel")
        layout.addWidget(self.title_label)

        layout.addStretch(1)

        self.elapsed_time_label = QLabel("00:00", container)
        self.elapsed_time_label.setObjectName("elapsedTimeLabel")
        layout.addWidget(self.elapsed_time_label)

        return container

    def create_content(self) -> QFrame:
        theme = get_theme_service().get_theme_definition()
        metrics = theme.metrics

        content = QFrame(self)
        content.setObjectName("scanContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(
            metrics.spacing_md,
            metrics.spacing_md,
            metrics.spacing_md,
            metrics.spacing_md,
        )
        layout.setSpacing(metrics.spacing_md)

        self.progress_summary_label = QLabel("0 files scanned", content)
        self.progress_summary_label.setObjectName("scanProgressSummary")
        layout.addWidget(self.progress_summary_label)

        self.progress_bar = QProgressBar(content)
        self.progress_bar.setObjectName("scanProgressBar")
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        self.progress_hint_label = QLabel("discovering...", content)
        self.progress_hint_label.setObjectName("scanProgressHint")
        layout.addWidget(self.progress_hint_label)

        stats_grid = QGridLayout()
        stats_grid.setHorizontalSpacing(metrics.spacing_sm)
        stats_grid.setVerticalSpacing(metrics.spacing_sm)
        self.found_card, self.found_value_label = self._create_stat_card(
            "Found", "0", "files"
        )
        self.success_card, self.success_value_label = self._create_stat_card(
            "Success", "0", "processed"
        )
        self.speed_card, self.speed_value_label = self._create_stat_card(
            "Speed", "--", "files / sec"
        )
        self.speed_unit_label = self.speed_card.findChild(QLabel, "scanStatSubtitle")
        stats_grid.addWidget(self.found_card, 0, 0)
        stats_grid.addWidget(self.success_card, 0, 1)
        stats_grid.addWidget(self.speed_card, 0, 2)
        layout.addLayout(stats_grid)

        current_file_title = QLabel("Current file", content)
        current_file_title.setObjectName("scanSectionLabel")
        layout.addWidget(current_file_title)

        self.current_file_label = QLabel("Waiting for first file...", content)
        self.current_file_label.setObjectName("currentFileLabel")
        self.current_file_label.setWordWrap(True)
        layout.addWidget(self.current_file_label)

        self.details_toggle_button = QToolButton(content)
        self.details_toggle_button.setObjectName("detailsToggleButton")
        self.details_toggle_button.setText("Show details")
        self.details_toggle_button.setCheckable(True)
        self.details_toggle_button.toggled.connect(self._toggle_details)
        layout.addWidget(self.details_toggle_button)

        self.details_container = QFrame(content)
        self.details_container.setObjectName("scanDetailsContainer")
        details_layout = QVBoxLayout(self.details_container)
        details_layout.setContentsMargins(
            metrics.spacing_md,
            metrics.spacing_md,
            metrics.spacing_md,
            metrics.spacing_md,
        )
        details_layout.setSpacing(metrics.spacing_sm)

        self.directory_detail_label = QLabel("Directory: --", self.details_container)
        self.rate_detail_label = QLabel("Rate: 0.0 items/s", self.details_container)
        self.elapsed_detail_label = QLabel("Elapsed: 00:00", self.details_container)
        self.remaining_detail_label = QLabel(
            "Remaining: waiting for file discovery",
            self.details_container,
        )
        self.extensions_detail_label = QLabel("Extensions: --", self.details_container)

        for widget in (
            self.directory_detail_label,
            self.rate_detail_label,
            self.elapsed_detail_label,
            self.remaining_detail_label,
            self.extensions_detail_label,
        ):
            widget.setObjectName("scanDetailLabel")
            widget.setWordWrap(True)
            details_layout.addWidget(widget)

        self.log_text = QTextEdit(self.details_container)
        self.log_text.setObjectName("scanLogText")
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(140)
        details_layout.addWidget(self.log_text)

        self.details_container.hide()
        layout.addWidget(self.details_container)
        layout.addStretch(1)

        return content

    def _create_stat_card(
        self, title: str, value: str, subtitle: str
    ) -> tuple[QFrame, QLabel]:
        card = QFrame(self)
        card.setObjectName("scanStatCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(2)

        title_label = QLabel(title, card)
        title_label.setObjectName("scanStatTitle")
        layout.addWidget(title_label)

        value_label = QLabel(value, card)
        value_label.setObjectName("scanStatValue")
        layout.addWidget(value_label)

        subtitle_label = QLabel(subtitle, card)
        subtitle_label.setObjectName("scanStatSubtitle")
        layout.addWidget(subtitle_label)

        return card, value_label

    def create_footer(self) -> QFrame:
        action_bar = ActionBar(self, alignment="right")
        action_bar.add_action("Cancel", self.on_cancel_clicked, "cancelButton")
        action_bar.add_action("Close", self.accept, "closeButton")

        self.cancel_button = action_bar.get_action_button("cancelButton")
        self.close_button = action_bar.get_action_button("closeButton")
        self.cancel_button.setEnabled(False)
        self.close_button.setEnabled(False)
        return action_bar

    def apply_dialog_theme(self, palette):
        try:
            theme = get_theme_service().get_theme_definition(palette.name)
            metrics = theme.metrics
            typography = theme.typography

            self.setStyleSheet(
                f"""
                ScanProgressDialog {{
                    background-color: {palette.background};
                    color: {palette.on_background};
                }}
                QFrame#scanHeader,
                QFrame#scanContent,
                QFrame#scanDetailsContainer,
                QFrame#scanStatCard,
                QFrame#actionContainer {{
                    background-color: {palette.surface};
                    border: 1px solid {palette.outline};
                    border-radius: {metrics.radius_md}px;
                }}
                QLabel#scanStatusDot {{
                    color: {palette.primary};
                    font-size: {typography.font_size_lg}px;
                }}
                QLabel#scanTitleLabel {{
                    color: {palette.on_surface};
                    font-family: "{typography.font_family}";
                    font-size: {typography.font_size_lg}px;
                    font-weight: {typography.font_weight_bold};
                }}
                QLabel#elapsedTimeLabel,
                QLabel#scanProgressHint,
                QLabel#scanStatTitle,
                QLabel#scanStatSubtitle,
                QLabel#scanSectionLabel,
                QLabel#scanDetailLabel {{
                    color: {palette.on_surface_variant};
                    font-family: "{typography.font_family}";
                    font-size: {typography.font_size_sm}px;
                }}
                QLabel#scanProgressSummary,
                QLabel#scanStatValue,
                QLabel#currentFileLabel {{
                    color: {palette.on_surface};
                    font-family: "{typography.font_family}";
                }}
                QLabel#scanProgressSummary,
                QLabel#scanStatValue {{
                    font-weight: {typography.font_weight_bold};
                }}
                QLabel#scanProgressSummary {{
                    font-size: {typography.font_size_lg}px;
                }}
                QLabel#scanStatValue {{
                    font-size: {typography.font_size_xl}px;
                }}
                QLabel#currentFileLabel {{
                    border: 1px solid {palette.outline};
                    border-radius: {metrics.radius_sm}px;
                    background-color: {palette.surface_variant};
                    padding: {metrics.spacing_sm}px;
                    min-height: {metrics.control_height}px;
                }}
                QToolButton#detailsToggleButton {{
                    background-color: transparent;
                    color: {palette.on_surface_variant};
                    border: none;
                    padding: 0;
                    text-align: left;
                    font-family: "{typography.font_family}";
                    font-size: {typography.font_size_sm}px;
                    font-weight: {typography.font_weight_medium};
                }}
                QToolButton#detailsToggleButton:hover {{
                    color: {palette.on_surface};
                }}
                QProgressBar#scanProgressBar {{
                    border: none;
                    border-radius: {metrics.radius_sm}px;
                    background-color: {palette.surface_variant};
                    min-height: {max(8, metrics.spacing_sm)}px;
                }}
                QProgressBar#scanProgressBar::chunk {{
                    background-color: {palette.primary};
                    border-radius: {metrics.radius_sm}px;
                }}
                QTextEdit#scanLogText {{
                    background-color: {palette.background};
                    color: {palette.on_surface};
                    border: 1px solid {palette.outline_variant};
                    border-radius: {metrics.radius_sm}px;
                    font-family: "{typography.font_family_monospace}";
                    font-size: {typography.font_size_xs}px;
                }}
                QPushButton#cancelButtonButton,
                QPushButton#closeButtonButton {{
                    min-height: {metrics.control_height}px;
                    min-width: 92px;
                }}
                """
            )
        except Exception as e:
            self.logger.error(f"Error applying scan dialog theme: {e}")

    def start_scan(self, directory: str, estimated_files: int = 0):
        self.start_time = time.time()
        self.is_scanning = True
        self.scan_stats = {
            "files_found": 0,
            "files_processed": 0,
            "total_files_scanned": 0,
            "current_directory": directory,
            "current_file": "",
            "scan_speed": 0.0,
            "estimated_total": estimated_files,
            "errors": 0,
        }

        self.setWindowTitle("Scanning...")
        self.title_label.setText("Scanning...")
        self.log_text.clear()
        self.current_file_label.setText("Waiting for first file...")
        self.progress_bar.setRange(0, 0 if estimated_files <= 0 else estimated_files)
        self.progress_bar.setValue(0)
        self._update_overview_display()
        self._update_detail_fields()
        self.set_scanning_state(True)

        if not self.elapsed_timer.isActive():
            self.elapsed_timer.start(1000)

        self.add_log_message("Scan started")
        self.logger.info(f"Scan started for directory: {directory}")

    def update_progress(self, progress_data):
        if not self.is_scanning:
            return

        try:
            if hasattr(progress_data, "__dict__"):
                self.scan_stats.update(
                    {
                        "files_found": getattr(progress_data, "files_found", 0),
                        "files_processed": getattr(progress_data, "files_processed", 0),
                        "total_files_scanned": getattr(
                            progress_data, "total_files_scanned", 0
                        ),
                        "current_directory": getattr(
                            progress_data, "current_directory", ""
                        ),
                        "current_file": getattr(progress_data, "current_file", ""),
                        "scan_speed": getattr(progress_data, "scan_speed", 0.0),
                        "estimated_total": getattr(
                            progress_data, "estimated_total_files", 0
                        ),
                        "errors": getattr(progress_data, "errors", 0),
                    }
                )
            elif isinstance(progress_data, dict):
                self.scan_stats.update(progress_data)

            self._update_overview_display()
            self._update_detail_fields()
            self._update_current_file_display()
        except Exception as e:
            self.logger.error(f"Error updating scan progress: {e}")

    def _update_overview_display(self):
        found = max(0, int(self.scan_stats.get("files_found", 0)))
        processed = max(0, int(self.scan_stats.get("files_processed", 0)))
        total_scanned = max(0, int(self.scan_stats.get("total_files_scanned", 0)))
        estimated_total = max(0, int(self.scan_stats.get("estimated_total", 0)))
        errors = max(0, int(self.scan_stats.get("errors", 0)))
        successful = max(0, processed - errors)
        speed = float(self.scan_stats.get("scan_speed", 0.0))

        self.progress_summary_label.setText(
            f"{total_scanned:,} files scanned".replace(",", " ")
        )

        if estimated_total > 0:
            self.progress_bar.setRange(0, estimated_total)
            self.progress_bar.setValue(min(processed, estimated_total))
            percentage = (
                int((processed / estimated_total) * 100) if estimated_total else 0
            )
            self.progress_hint_label.setText(
                f"{processed:,} / {estimated_total:,} files".replace(",", " ")
            )
            self.progress_hint_label.setToolTip(f"{percentage}% complete")
        else:
            self.progress_bar.setRange(0, 0)
            self.progress_hint_label.setText("discovering...")
            self.progress_hint_label.setToolTip("Waiting for file discovery")

        self.found_value_label.setText(str(found))
        self.success_value_label.setText(str(successful))
        if speed > 0:
            speed_value, speed_unit = self._format_rate_components(speed, "files")
            self.speed_value_label.setText(speed_value)
            if self.speed_unit_label is not None:
                self.speed_unit_label.setText(speed_unit)
        else:
            self.speed_value_label.setText("--")
            if self.speed_unit_label is not None:
                self.speed_unit_label.setText("files / sec")

    def _update_detail_fields(self):
        directory = self.scan_stats.get("current_directory", "")
        speed = float(self.scan_stats.get("scan_speed", 0.0))
        estimated_total = max(0, int(self.scan_stats.get("estimated_total", 0)))
        processed = max(0, int(self.scan_stats.get("files_processed", 0)))
        elapsed = max(0.0, time.time() - self.start_time)

        self.directory_detail_label.setText(
            f"Directory: {self._truncate_path(directory, max_length=72) or '--'}"
        )
        self.rate_detail_label.setText(
            f"Rate: {self._format_rate(speed, 'items')}"
            if speed > 0
            else "Rate: 0.0 items/s"
        )
        self.elapsed_detail_label.setText(f"Elapsed: {self._format_elapsed(elapsed)}")

        if estimated_total > 0 and speed > 0 and processed <= estimated_total:
            remaining_seconds = max(0.0, (estimated_total - processed) / speed)
            self.remaining_detail_label.setText(
                f"Remaining: {self._format_elapsed(remaining_seconds)}"
            )
        else:
            self.remaining_detail_label.setText("Remaining: waiting for file discovery")

        extensions = self._format_extension_summary()
        self.extensions_detail_label.setText(f"Extensions: {extensions}")

    def _format_extension_summary(self) -> str:
        current_file = str(self.scan_stats.get("current_file") or "")
        if current_file:
            _, extension = os.path.splitext(current_file)
            if extension:
                return extension.lower()
        return "--"

    def _update_current_file_display(self):
        current_file = self.scan_stats.get("current_file", "")
        current_dir = self.scan_stats.get("current_directory", "")

        if current_file:
            filename = os.path.basename(current_file)
            try:
                rel_path = (
                    os.path.relpath(current_file, current_dir)
                    if current_dir
                    else filename
                )
            except ValueError:
                rel_path = current_file
            self.current_file_label.setText(
                self._truncate_path(rel_path, max_length=92)
            )
        else:
            self.current_file_label.setText("Waiting for first file...")

    def update_elapsed_time(self):
        if not self.is_scanning:
            return

        elapsed = max(0.0, time.time() - self.start_time)
        time_text = self._format_elapsed(elapsed)
        self.elapsed_time_label.setText(time_text)
        self.elapsed_detail_label.setText(f"Elapsed: {time_text}")

    def add_log_message(self, message: str):
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")

    def on_scan_finished(
        self, success: bool = True, final_stats: Optional[Dict[str, Any]] = None
    ):
        self.is_scanning = False
        self.elapsed_timer.stop()

        if final_stats:
            self.scan_stats.update(final_stats)

        self._update_overview_display()
        self._update_detail_fields()

        if success:
            self.setWindowTitle("Scan completed")
            self.title_label.setText("Scan completed")
            self.current_file_label.setText("Scan completed successfully.")
            self.add_log_message("Scan completed successfully")
        else:
            self.setWindowTitle("Scan stopped")
            self.title_label.setText("Scan stopped")
            self.current_file_label.setText("Scan was cancelled or failed.")
            self.add_log_message("Scan cancelled or failed")

        self.set_scanning_state(False)
        self.logger.info(
            f"Scan finished: success={success}, elapsed={time.time() - self.start_time:.1f}s"
        )

    def on_cancel_clicked(self):
        if not self.is_scanning:
            return

        self.cancel_button.setEnabled(False)
        self.cancel_button.setText("Cancelling...")
        self.add_log_message("Cancellation requested")
        self.cancel_requested.emit()

    def set_scanning_state(self, scanning: bool):
        self.is_scanning = scanning
        if scanning:
            self.status_dot.setStyleSheet("color: #3b82f6;")
            self.cancel_button.setEnabled(True)
            self.cancel_button.setVisible(True)
            self.cancel_button.setText("Cancel")
            self.close_button.setEnabled(False)
            self.close_button.setVisible(False)
        else:
            self.status_dot.setStyleSheet("color: #22c55e;")
            self.cancel_button.setEnabled(False)
            self.cancel_button.setVisible(False)
            self.cancel_button.setText("Cancel")
            self.close_button.setEnabled(True)
            self.close_button.setVisible(True)

    def _toggle_details(self, visible: bool):
        self.details_visible = visible
        self.details_container.setVisible(visible)
        self.details_toggle_button.setText(
            "Hide details" if visible else "Show details"
        )

    def _truncate_path(self, path: str, max_length: int = 50) -> str:
        if not path or len(path) <= max_length:
            return path
        start_length = max_length // 3
        end_length = max_length - start_length - 3
        return f"{path[:start_length]}...{path[-end_length:]}"

    def _format_elapsed(self, elapsed_seconds: float) -> str:
        total_seconds = int(max(0, elapsed_seconds))
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    @staticmethod
    def _format_rate(rate: float, unit: str) -> str:
        if rate <= 0:
            return f"0.0 {unit}/s"
        if rate < 1:
            return f"{rate * 60:.1f} {unit}/min"
        return f"{rate:.1f} {unit}/s"

    @staticmethod
    def _format_rate_components(rate: float, unit: str) -> tuple[str, str]:
        if rate <= 0:
            return "--", f"{unit} / sec"
        if rate < 1:
            return f"{rate * 60:.1f}", f"{unit} / min"
        return f"{rate:.1f}", f"{unit} / sec"

    def closeEvent(self, event):
        if self.is_scanning and self.cancel_button.isVisible():
            event.ignore()
            self.on_cancel_clicked()
            return

        if hasattr(self, "elapsed_timer"):
            self.elapsed_timer.stop()
        event.accept()

    def reject(self):
        if self.is_scanning:
            self.on_cancel_clicked()
            return
        super().reject()

    def update_progress_legacy(self, progress):
        self.update_progress(progress)

    def get_scan_statistics(self) -> Dict[str, Any]:
        stats = self.scan_stats.copy()
        if self.start_time:
            stats["elapsed_time"] = time.time() - self.start_time
        return stats

    def is_scan_active(self) -> bool:
        return self.is_scanning

    def set_estimated_files(self, count: int):
        self.scan_stats["estimated_total"] = count
        self._update_overview_display()
        self._update_detail_fields()
