# views/widgets/dialogs/categorization/categorization_progress_dialog.py
"""
CategorizationProgressDialog - Dialog for automatic categorization progress.

Refactored version using the new architecture with base widgets
and reusable components.
"""

import os
import time
from typing import Any, Dict

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from ai_content_classifier.views.widgets.base.action_bar import ActionBar
from ai_content_classifier.views.widgets.base.header_section import HeaderSection
from ai_content_classifier.views.widgets.base.themed_dialog import ThemedDialog
from ai_content_classifier.views.widgets.common.progress_panel import ProgressPanel


class CategorizationProgressDialog(ThemedDialog):
    """
    Dialog for automatic categorization progress.

    Uses the new architecture with reusable widgets.
    Displays real-time progress, results, and logs.
    """

    # Signal to request process cancellation
    cancellation_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    resume_requested = pyqtSignal()

    def __init__(self, total_files: int, parent=None):
        # Progress data
        self.total_files = total_files
        self.processed_files = 0
        self.successful_classifications = 0
        self.failed_classifications = 0
        self.start_time = time.time()

        # Dialog state
        self.is_completed = False
        self.is_cancelled = False
        self.is_paused = False
        self._confidence_values = []
        self._high_confidence_count = 0

        # Initialize base dialog
        super().__init__(
            parent=parent,
            title="Categorization in Progress",
            description=f"Processing {total_files} files with AI-powered categorization.",
            modal=False,
        )

        # Specific configuration
        self.resize(800, 600)
        self._fit_to_screen()

        # Prevent closing with X (force button usage)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowMinimizeButtonHint
        )
        self.setWindowModality(Qt.WindowModality.NonModal)

        # Timer for statistics
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_statistics)
        self.update_timer.start(1000)  # Update every second

    def create_header(self) -> QFrame:
        """Create the header with real-time statistics."""
        # Main header
        header = HeaderSection(
            title="🤖 Categorization in Progress",
            description="AI-powered file categorization with real-time progress tracking.",
            parent=self,
        )

        # Statistics container
        stats_container = QWidget()
        stats_container.setObjectName("progressStatsContainer")
        stats_layout = QHBoxLayout(stats_container)
        stats_layout.setContentsMargins(12, 8, 12, 8)
        stats_layout.setSpacing(20)

        # Main statistics
        self.processed_label = self.create_stat_label(
            "📁 Processed: 0", "processedLabel"
        )
        self.success_label = self.create_stat_label("✅ Successful: 0", "successLabel")
        self.failed_label = self.create_stat_label("❌ Failed: 0", "failedLabel")
        self.speed_label = self.create_stat_label("⚡ Speed: -", "speedLabel")

        stats_layout.addWidget(self.processed_label)
        stats_layout.addWidget(self.success_label)
        stats_layout.addWidget(self.failed_label)
        stats_layout.addStretch()
        stats_layout.addWidget(self.speed_label)

        # Add to header
        header.add_to_layout(stats_container)

        return header

    def create_stat_label(self, text: str, object_name: str) -> QLabel:
        """Create a styled statistic label."""
        label = QLabel(text)
        label.setObjectName(object_name)
        label.setFont(self.create_bold_font())
        return label

    def create_content(self) -> QFrame:
        """Create the main dialog content."""
        content = QFrame()
        content.setObjectName("progressContent")

        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(20)

        # Main progress panel
        self.progress_panel = ProgressPanel(
            parent=self,
            title="Categorization Progress",
            show_details=False,
            show_log=True,
        )

        # Disable the ProgressPanel cancel button (we use our own)
        self.progress_panel.set_cancellable(False)

        layout.addWidget(self.progress_panel)

        # Tabs for details
        self.details_tabs = QTabWidget()
        self.details_tabs.setObjectName("detailsTabs")

        # Recent results tab
        results_tab = self.create_results_tab()
        self.details_tabs.addTab(results_tab, "📊 Recent Results")

        # Detailed statistics tab
        stats_tab = self.create_detailed_stats_tab()
        self.details_tabs.addTab(stats_tab, "📈 Statistics")

        layout.addWidget(self.details_tabs)

        return content

    def create_results_tab(self) -> QWidget:
        """Create the recent results tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Header
        results_header = QLabel("📊 Latest Classification Results")
        results_header.setObjectName("resultsHeader")
        results_header.setFont(self.create_bold_font(1))
        layout.addWidget(results_header)

        # Results table
        self.results_table = QTableWidget()
        self.results_table.setObjectName("resultsTable")
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels(
            ["File", "Category", "Confidence", "Time"]
        )

        # Table configuration
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.results_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.results_table.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)

        # Auto resize
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self.results_table)

        # Result info
        self.results_info = QLabel("Results will appear here as files are processed...")
        self.results_info.setObjectName("resultsInfo")
        self.results_info.setFont(self.create_italic_font())
        layout.addWidget(self.results_info)

        return widget

    def create_detailed_stats_tab(self) -> QWidget:
        """Create the detailed statistics tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(16)

        # Header
        stats_header = QLabel("📈 Detailed Statistics")
        stats_header.setObjectName("statsHeader")
        stats_header.setFont(self.create_bold_font(1))
        layout.addWidget(stats_header)

        # Metrics container
        metrics_container = QWidget()
        metrics_container.setObjectName("metricsContainer")
        metrics_layout = QVBoxLayout(metrics_container)
        metrics_layout.setSpacing(12)

        # Performance metrics
        perf_frame = QFrame()
        perf_frame.setObjectName("performanceFrame")
        perf_layout = QVBoxLayout(perf_frame)

        perf_title = QLabel("⚡ Performance Metrics")
        perf_title.setFont(self.create_bold_font())
        perf_layout.addWidget(perf_title)

        self.avg_time_label = QLabel("Average processing time: -")
        self.total_time_label = QLabel("Total elapsed time: -")
        self.eta_label = QLabel("Estimated completion: -")

        perf_layout.addWidget(self.avg_time_label)
        perf_layout.addWidget(self.total_time_label)
        perf_layout.addWidget(self.eta_label)

        metrics_layout.addWidget(perf_frame)

        # Quality metrics
        quality_frame = QFrame()
        quality_frame.setObjectName("qualityFrame")
        quality_layout = QVBoxLayout(quality_frame)

        quality_title = QLabel("🎯 Quality Metrics")
        quality_title.setFont(self.create_bold_font())
        quality_layout.addWidget(quality_title)

        self.success_rate_label = QLabel("Success rate: -")
        self.avg_confidence_label = QLabel("Average confidence: -")
        self.high_confidence_label = QLabel("High confidence (>80%): -")

        quality_layout.addWidget(self.success_rate_label)
        quality_layout.addWidget(self.avg_confidence_label)
        quality_layout.addWidget(self.high_confidence_label)

        metrics_layout.addWidget(quality_frame)

        layout.addWidget(metrics_container)
        layout.addStretch()

        return widget

    def create_footer(self) -> QFrame:
        """Create the footer with control buttons."""
        # Use ActionBar for buttons
        action_bar = ActionBar(self, alignment="right")

        # Control buttons
        action_bar.add_action("⏸️ Pause", self.toggle_pause, "pauseButton")
        action_bar.add_stretch()
        action_bar.add_action("⏹️ Stop", self.request_cancellation, "stopButton")

        # References for manipulation
        self.pause_button = action_bar.get_action_button("pauseButton")
        self.stop_button = action_bar.get_action_button("stopButton")

        # Initial state
        self.pause_button.setEnabled(True)

        return action_bar

    def toggle_pause(self):
        """Toggle between pause and resume."""
        if self.is_completed or self.is_cancelled:
            return

        self.is_paused = not self.is_paused

        if self.is_paused:
            self.pause_button.setText("▶️ Resume")
            self.add_log("⏸️ Categorization paused")
            self.pause_requested.emit()
        else:
            self.pause_button.setText("⏸️ Pause")
            self.add_log("▶️ Categorization resumed")
            self.resume_requested.emit()

    def update_progress(self, processed: int, successful: int, failed: int):
        """Update progress with new data."""
        self.processed_files = processed
        self.successful_classifications = successful
        self.failed_classifications = failed

        # Update the progress panel
        self.progress_panel.update_progress(
            processed, current_item=f"File {processed}/{self.total_files}", success=True
        )

        # Update statistics labels
        self.processed_label.setText(f"📁 Processed: {processed}/{self.total_files}")
        self.success_label.setText(f"✅ Successful: {successful}")
        self.failed_label.setText(f"❌ Failed: {failed}")

        # Update result info
        if processed > 0:
            self.results_info.setText(
                f"Showing latest results from {processed} processed files"
            )

        # Check if completed
        if processed >= self.total_files:
            self.set_completion_status(failed == 0, "")

    def update_statistics(self):
        """Update real-time statistics."""
        if self.processed_files > 0:
            elapsed = time.time() - self.start_time
            speed = self.processed_files / elapsed

            # Estimated remaining time
            if speed > 0:
                remaining = self.total_files - self.processed_files
                eta_seconds = remaining / speed

                if eta_seconds < 60:
                    eta_text = f"ETA: {int(eta_seconds)}s"
                elif eta_seconds < 3600:
                    eta_text = f"ETA: {int(eta_seconds // 60)}m{int(eta_seconds % 60)}s"
                else:
                    eta_text = f"ETA: {int(eta_seconds // 3600)}h{int((eta_seconds % 3600) // 60)}m"
            else:
                eta_text = "ETA: Calculating..."

            # Speed formatting
            if speed < 1:
                speed_text = f"{speed * 60:.1f} files/min"
            else:
                speed_text = f"{speed:.1f} files/s"

            self.speed_label.setText(f"⚡ {speed_text} • {eta_text}")

            # Detailed statistics
            self.update_detailed_stats(elapsed, speed)
        else:
            self.speed_label.setText("⚡ Speed: Starting...")

    def update_detailed_stats(self, elapsed: float, speed: float):
        """Update detailed statistics."""
        try:
            # Performance metrics
            avg_time = elapsed / self.processed_files if self.processed_files > 0 else 0
            self.avg_time_label.setText(
                f"Average processing time: {avg_time:.2f}s per file"
            )

            total_hours = int(elapsed // 3600)
            total_minutes = int((elapsed % 3600) // 60)
            total_seconds = int(elapsed % 60)
            if total_hours > 0:
                time_text = f"{total_hours}h {total_minutes}m {total_seconds}s"
            elif total_minutes > 0:
                time_text = f"{total_minutes}m {total_seconds}s"
            else:
                time_text = f"{total_seconds}s"
            self.total_time_label.setText(f"Total elapsed time: {time_text}")

            # ETA
            remaining = self.total_files - self.processed_files
            if speed > 0 and remaining > 0:
                eta_seconds = remaining / speed
                if eta_seconds < 3600:
                    eta_text = f"{int(eta_seconds // 60)}m {int(eta_seconds % 60)}s"
                else:
                    eta_text = f"{int(eta_seconds // 3600)}h {int((eta_seconds % 3600) // 60)}m"
                self.eta_label.setText(f"Estimated completion: {eta_text}")
            else:
                self.eta_label.setText("Estimated completion: Complete")

            # Quality metrics
            if self.processed_files > 0:
                success_rate = (
                    self.successful_classifications / self.processed_files
                ) * 100
                self.success_rate_label.setText(f"Success rate: {success_rate:.1f}%")
                if self._confidence_values:
                    avg_confidence = sum(self._confidence_values) / len(
                        self._confidence_values
                    )
                    self.avg_confidence_label.setText(
                        f"Average confidence: {avg_confidence:.1%}"
                    )
                else:
                    self.avg_confidence_label.setText("Average confidence: -")

                self.high_confidence_label.setText(
                    f"High confidence (>80%): {self._high_confidence_count}"
                )

        except Exception as e:
            self.logger.error(f"Error updating detailed stats: {e}")

    def add_result(
        self, file_path: str, category: str, confidence: float, processing_time: float
    ):
        """Add a result to the table with improved formatting."""
        try:
            # Keep only the last 100 results
            if self.results_table.rowCount() >= 100:
                self.results_table.removeRow(0)

            # Add new row
            row = self.results_table.rowCount()
            self.results_table.insertRow(row)

            # Create items
            filename = os.path.basename(file_path)
            filename_item = QTableWidgetItem(filename)
            filename_item.setToolTip(file_path)  # Full path in tooltip

            category_item = QTableWidgetItem(category)

            # Color hint by confidence
            confidence_item = QTableWidgetItem(f"{confidence:.1%}")
            if confidence >= 0.8:
                confidence_item.setToolTip("High confidence")
            elif confidence >= 0.6:
                confidence_item.setToolTip("Medium confidence")
            else:
                confidence_item.setToolTip("Low confidence")

            time_item = QTableWidgetItem(f"{processing_time:.1f}s")

            # Set items
            self.results_table.setItem(row, 0, filename_item)
            self.results_table.setItem(row, 1, category_item)
            self.results_table.setItem(row, 2, confidence_item)
            self.results_table.setItem(row, 3, time_item)

            self._confidence_values.append(confidence)
            if confidence >= 0.8:
                self._high_confidence_count += 1

            # Scroll to bottom
            self.results_table.scrollToBottom()

            # Log in ProgressPanel
            status = "✅" if confidence >= 0.6 else "⚠️"
            self.progress_panel.log_message(
                f"{status} {filename} → {category} ({confidence:.1%})"
            )

        except Exception as e:
            self.logger.error(f"Error adding result: {e}")

    def add_log(self, message: str):
        """Add a message to logs."""
        try:
            self.progress_panel.log_message(message)
        except Exception as e:
            self.logger.error(f"Error adding log: {e}")

    def request_cancellation(self) -> bool:
        """Request process stop with confirmation."""
        if self.is_completed:
            self.accept()
            return True

        reply = QMessageBox.question(
            self,
            "🛑 Stop Categorization",
            "Do you really want to stop categorization?\n\n"
            "• Already processed files will keep their categories\n"
            "• Progress will be lost for incomplete files\n"
            "• You can resume categorization later",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.is_cancelled = True
            self.add_log("🛑 Cancellation requested by user")
            self.cancellation_requested.emit()

            # Update the interface
            self.stop_button.setEnabled(False)
            self.stop_button.setText("🔄 Stopping...")

            # Stop progress
            self.progress_panel.cancel_progress()

            return True
        else:
            self.add_log("ℹ️ Cancellation cancelled by user")
            return False

    def set_completion_status(self, success: bool, message: str = ""):
        """Set the final categorization status."""
        self.is_completed = True

        # Complete progress
        self.progress_panel.complete_progress(success=success)

        if success:
            if self.failed_classifications > 0:
                status_msg = f"Completed with {self.failed_classifications} errors"
                self.add_log(f"⚠️ {status_msg}")
            else:
                status_msg = "Categorization completed successfully!"
                self.add_log(f"✅ {status_msg}")
        else:
            status_msg = f"Categorization failed: {message}"
            self.add_log(f"❌ {status_msg}")

        # Update buttons
        self.stop_button.setText("🔚 Close")
        self.stop_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.pause_button.setText("⏸️ Pause")
        self.is_paused = False

        # Stop statistics timer
        if hasattr(self, "update_timer"):
            self.update_timer.stop()

        # Final statistics
        total_time = time.time() - self.start_time
        self.add_log(
            f"📊 Final stats: {self.successful_classifications} successful, {self.failed_classifications} failed in {total_time:.1f}s"
        )

    def start_categorization(self):
        """Start categorization."""
        self.progress_panel.start_progress(
            max_value=self.total_files, title="Categorizing Files"
        )
        self.pause_button.setEnabled(True)
        self.pause_button.setText("⏸️ Pause")
        self.add_log("🚀 Categorization started")

    def closeEvent(self, event):
        """Handle the window close event."""
        if not self.is_completed and not self.is_cancelled:
            # Continue processing in the background without blocking the application.
            self.hide()
            self.add_log("ℹ️ Progress window hidden (categorization continues)")
            event.ignore()
        else:
            # Clean up timer
            if hasattr(self, "update_timer"):
                self.update_timer.stop()
            event.accept()  # Allow closing

    def validate_configuration(self) -> tuple[bool, str]:
        """Validation for ThemedDialog (not really needed here)."""
        return True, ""

    def get_configuration(self) -> Dict[str, Any]:
        """Return final statistics."""
        return {
            "total_files": self.total_files,
            "processed_files": self.processed_files,
            "successful_classifications": self.successful_classifications,
            "failed_classifications": self.failed_classifications,
            "elapsed_time": time.time() - self.start_time,
            "is_completed": self.is_completed,
            "is_cancelled": self.is_cancelled,
        }
