# presenters/status_presenter.py
"""
Status Presenter - Presents application status and log messages.

Responsibilities:
- Displaying log messages in the console
- Updating the status bar
- Managing progress indicators
- Displaying application statistics
"""

import time

from ai_content_classifier.core.logger import get_logger
from PyQt6.QtCore import QObject, pyqtSignal
from ai_content_classifier.views.main_window import MainWindow


class StatusPresenter(QObject):
    """
    Presenter for application status.

    This presenter manages everything related to displaying status,
    logs, and progress information.
    """

    # Signals emitted by the presenter
    message_logged = pyqtSignal(str, str)  # (message, level)
    status_updated = pyqtSignal(str)  # Status message
    progress_updated = pyqtSignal(int, int, int)  # (current, total, percentage)

    def __init__(self, main_window: MainWindow, parent=None):
        super().__init__(parent)
        self.logger = get_logger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

        self.main_window = main_window

        # Status state
        self.is_busy = False

        # Statistics
        self.stats = {
            "total_files": 0,
            "filtered_files": 0,
            "available_models": 0,
            "connection_status": "Disconnected",
            "last_scan_time": None,
            "scan_in_progress": False,
            "organization_in_progress": False,
        }

        self.logger.debug("Status Presenter initialized")

    def log_message(self, message: str, level: str = "INFO"):
        """
        Displays a message in the log console.

        Args:
            message: Message to display
            level: Message level (INFO, WARNING, ERROR, DEBUG)
        """
        try:
            # Timestamp the message
            timestamp = time.strftime("%H:%M:%S")
            formatted_message = f"[{timestamp}] {message}"

            # Display in the interface's log console
            if hasattr(self.main_window, "log_console_widget"):
                self.main_window.log_console_widget.log_message(
                    formatted_message, level
                )

            # Log in the logging system
            log_method = getattr(self.logger, level.lower(), self.logger.info)
            log_method(message)

            # Emit the signal
            self.message_logged.emit(formatted_message, level)

        except Exception as e:
            # Fallback in case of error
            self.logger.error(f"Error logging message: {e}")

    def update_status(self, status_message: str, is_busy: bool = False):
        """
        Updates the main status message.

        Args:
            status_message: New status message
            is_busy: Indicates if the application is busy
        """
        try:
            self.is_busy = is_busy

            # Update status bar if it exists
            if hasattr(self.main_window, "statusBar"):
                self.main_window.statusBar().showMessage(status_message)

            if hasattr(self.main_window, "set_main_status_chip"):
                self.main_window.set_main_status_chip(status_message, is_busy=is_busy)

            if hasattr(self.main_window, "set_progress_status_chip"):
                self.main_window.set_progress_status_chip(
                    status_message, is_busy=is_busy
                )

            # Emit the signal
            self.status_updated.emit(status_message)

            self.logger.debug(f"Status updated: {status_message} (busy: {is_busy})")

        except Exception as e:
            self.logger.error(f"Error updating status: {e}")

    def update_file_count(self, total_files: int):
        """
        Updates the total file count.

        Args:
            total_files: Total number of files
        """
        self.stats["total_files"] = total_files
        self._update_stats_display()
        self.logger.debug(f"File count updated: {total_files}")

    def update_filtered_count(self, filtered_files: int):
        """
        Updates the filtered file count.

        Args:
            filtered_files: Number of files after filtering
        """
        self.stats["filtered_files"] = filtered_files
        self._update_stats_display()
        self.logger.debug(f"Filtered file count: {filtered_files}")

    def update_model_count(self, model_count: int):
        """
        Updates the number of available models.

        Args:
            model_count: Number of available models
        """
        self.stats["available_models"] = model_count
        self._update_stats_display()
        self.logger.debug(f"Model count updated: {model_count}")

    def update_connection_status(
        self, status: str, is_connected: bool = False, **kwargs
    ):
        """
        Updates the connection status.

        Args:
            status: Connection status message
            is_connected: Indicates whether the connection is active
        """
        if "is_connectd" in kwargs:
            is_connected = bool(kwargs["is_connectd"])
        self.stats["connection_status"] = status

        # Update visual connection indicator if it exists
        if hasattr(self.main_window, "set_connection_status"):
            self.main_window.set_connection_status(is_connected, status)

        self._update_stats_display()
        self.logger.debug(f"Connection status updated: {status}")

    def show_scan_progress(self, show: bool):
        """
        Shows or hides the scan progress indicator.

        Args:
            show: True to show, False to hide
        """
        self.stats["scan_in_progress"] = show

        if show:
            self.update_status("Scanning...", is_busy=True)
            self.stats["last_scan_time"] = time.time()
        else:
            self.update_status("Ready", is_busy=False)

        # Update interface if it has a progress indicator
        if hasattr(self.main_window, "show_progress_indicator"):
            self.main_window.show_progress_indicator(show)

    def update_scan_progress(self, current: int, total: int, percentage: float):
        """
        Updates scan progress.

        Args:
            current: Number of items processed
            total: Total number of items
            percentage: Progress percentage
        """
        try:
            # Update status message
            self.update_status(
                f"Metadata processed: {current}/{total} files ({percentage:.1f}%)",
                is_busy=True,
            )

            # Emit progress signal
            self.progress_updated.emit(current, total, int(percentage))

            # Update interface if it has a progress bar
            if hasattr(self.main_window, "update_progress_bar"):
                self.main_window.update_progress_bar(int(percentage))

        except Exception as e:
            self.logger.error(f"Error updating progress: {e}")

    def show_organization_progress(self, show: bool):
        """
        Shows or hides the organization progress indicator.

        Args:
            show: True to show, False to hide
        """
        self.stats["organization_in_progress"] = show

        if show:
            self.update_status("Organizing files...", is_busy=True)
        else:
            self.update_status("Ready", is_busy=False)
            if hasattr(self.main_window, "update_progress_bar"):
                self.main_window.update_progress_bar(0)

        if hasattr(self.main_window, "show_progress_indicator"):
            self.main_window.show_progress_indicator(show)

    def update_organization_progress(self, current: int, total: int, percentage: float):
        """
        Updates organization progress.

        Args:
            current: Number of items processed
            total: Total number of items
            percentage: Progress percentage
        """
        try:
            self.update_status(
                f"Organization: {current}/{total} files ({percentage:.1f}%)",
                is_busy=True,
            )
            self.progress_updated.emit(current, total, int(percentage))

            if hasattr(self.main_window, "update_progress_bar"):
                self.main_window.update_progress_bar(int(percentage))

        except Exception as e:
            self.logger.error(f"Error updating organization progress: {e}")

    def update_llm_status(self, llm_type: str, is_ready: bool, message: str):
        """
        Updates the status of a specific LLM.

        Args:
            llm_type: LLM type (document, image)
            is_ready: Indicates if LLM is ready
            message: Status message
        """
        try:
            self.logger.debug(f"LLM status {llm_type}: {is_ready} - {message}")

            # Update interface if it has LLM indicators
            if llm_type == "document":
                if hasattr(self.main_window, "set_doc_llm_status"):
                    self.main_window.set_doc_llm_status(message, is_ready)
            elif llm_type == "image":
                if hasattr(self.main_window, "set_img_llm_status"):
                    self.main_window.set_img_llm_status(message, is_ready)

            # Log status
            level = "INFO" if is_ready else "WARNING"
            self.log_message(f"LLM {llm_type}: {message}", level)

        except Exception as e:
            self.logger.error(f"Error updating LLM status {llm_type}: {e}")

    def _update_stats_display(self):
        """
        Updates the statistics display.
        """
        try:
            # Build statistics message
            stats_message = f"Files: {self.stats['total_files']}"

            if self.stats["filtered_files"] != self.stats["total_files"]:
                stats_message += f" (displayed: {self.stats['filtered_files']})"

            if self.stats["available_models"] > 0:
                stats_message += f" | Models: {self.stats['available_models']}"

            # Update status bar with stats
            if hasattr(self.main_window, "statusBar"):
                status_bar = self.main_window.statusBar()

                # Create or update a permanent label for stats
                if not hasattr(self, "_stats_label"):
                    from PyQt6.QtWidgets import QLabel

                    self._stats_label = QLabel()
                    status_bar.addPermanentWidget(self._stats_label)

                self._stats_label.setText(stats_message)

        except Exception as e:
            self.logger.error(f"Error updating stats: {e}")
