# views/widgets/common/progress_panel.py
"""
ProgressPanel - Progress panel reusable.

Widget to display long-running operation progress with
detailed information et cancel option.
"""

import time
from typing import Any, Callable, Dict, List

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)
from ai_content_classifier.services.theme.theme_service import ThemePalette
from ai_content_classifier.services.theme.theme_service import get_theme_service
from ai_content_classifier.views.widgets.base.themed_widget import ThemedWidget
from ai_content_classifier.views.widgets.common.operation_state import (
    OperationViewState,
)


class ProgressPanel(ThemedWidget):
    """
    Progress panel with advanced features.

    Features :
    - Barre de progression avec pourcentage
    - Detailed information (processed files, errors, etc.)
    - Real-time operation log
    - Bouton d'annulation
    - Statistiques de performance
    - Animations fluides
    - States visuels distincts
    """

    # Signaux
    cancel_requested = pyqtSignal()  # Cancel requested
    progress_completed = pyqtSignal(dict)  # Progression completed avec stats
    state_changed = pyqtSignal(str)  # State changed
    action_requested = pyqtSignal(str)  # Action requested

    def __init__(
        self,
        parent=None,
        title: str = "Progress",
        show_details: bool = True,
        show_log: bool = False,
    ):
        super().__init__(parent, "progressPanel")

        # Configuration
        self.title = title
        self.show_details = show_details
        self.show_log = show_log

        # State de progression
        self.current_progress = 0
        self.max_progress = 100
        self.is_running = False
        self.is_indeterminate = False
        self.is_cancellable = True
        self.start_time = None
        self.end_time = None

        # Statistiques
        self.stats = {
            "items_processed": 0,
            "items_total": 0,
            "items_successful": 0,
            "items_failed": 0,
            "items_skipped": 0,
            "errors": [],
            "current_item": "",
            "elapsed_time": 0,
            "estimated_remaining": 0,
            "processing_rate": 0,  # items per second
        }

        # Log des messages
        self.log_messages = []
        self.max_log_messages = 1000
        self.details_expanded = False
        self._current_operation_state: OperationViewState | None = None
        self._action_callbacks: dict[str, Callable[[], None]] = {}
        self.show_progress_bar = True

        self.setup_ui()
        self.reset_progress()

    def setup_ui(self):
        """Configure l'interface du panel."""
        metrics = get_theme_service().get_theme_definition().metrics
        layout = self.get_main_layout()
        layout.setSpacing(metrics.spacing_sm)

        # Header with title and controls
        self.header_container = self.create_header()
        layout.addWidget(self.header_container)

        # Barre de progression principale
        self.progress_container = self.create_progress_bar()
        layout.addWidget(self.progress_container)

        self.summary_container = self.create_summary_section()
        layout.addWidget(self.summary_container)

        # Detailed information (optional)
        if self.show_details:
            self.details_container = self.create_details_section()
            layout.addWidget(self.details_container)

        # Operations log (optional)
        if self.show_log:
            self.log_container = self.create_log_section()
            layout.addWidget(self.log_container, 1)

        # Actions (annulation, etc.)
        self.actions_container = self.create_actions_section()
        layout.addWidget(self.actions_container)
        self.set_details_expanded(False)

    def create_header(self) -> QFrame:
        """Create the header du panel."""
        theme = get_theme_service().get_theme_definition()
        metrics = theme.metrics
        typography = theme.typography
        header = QFrame()
        header.setObjectName("progressHeader")

        layout = QHBoxLayout(header)
        layout.setContentsMargins(
            metrics.spacing_md,
            metrics.spacing_sm,
            metrics.spacing_md,
            metrics.spacing_sm,
        )
        layout.setSpacing(metrics.spacing_sm)

        # Titre avec state
        self.title_label = QLabel(f"⏳ {self.title}")
        self.title_label.setObjectName("progressTitle")
        self.title_label.setFont(self.create_bold_font(2))
        layout.addWidget(self.title_label)

        layout.addStretch()

        # Indicateur d'state
        self.state_indicator = QLabel("●")
        self.state_indicator.setObjectName("stateIndicator")
        self.state_indicator.setFont(
            QFont(typography.font_family, typography.font_size_xl - 6)
        )
        layout.addWidget(self.state_indicator)

        return header

    def create_progress_bar(self) -> QFrame:
        """Create la barre de progression principale."""
        metrics = get_theme_service().get_theme_definition().metrics
        container = QFrame()
        container.setObjectName("progressContainer")

        layout = QVBoxLayout(container)
        layout.setContentsMargins(
            metrics.spacing_md,
            metrics.spacing_sm,
            metrics.spacing_md,
            metrics.spacing_sm,
        )
        layout.setSpacing(metrics.spacing_xs)

        # Barre de progression
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("mainProgressBar")
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        # Information basic
        info_layout = QHBoxLayout()

        # Current item
        self.current_item_label = QLabel("Ready")
        self.current_item_label.setObjectName("currentItemLabel")
        self.current_item_label.setFont(self.create_italic_font())
        info_layout.addWidget(self.current_item_label, 1)

        # Estimated time
        self.time_label = QLabel("--:--")
        self.time_label.setObjectName("timeLabel")
        self.time_label.setFont(self.create_bold_font())
        info_layout.addWidget(self.time_label)

        layout.addLayout(info_layout)

        return container

    def create_summary_section(self) -> QFrame:
        """Creates compact summary row with a details toggle."""
        metrics = get_theme_service().get_theme_definition().metrics
        container = QFrame()
        container.setObjectName("summaryContainer")

        layout = QHBoxLayout(container)
        layout.setContentsMargins(
            metrics.spacing_md,
            metrics.spacing_xs,
            metrics.spacing_md,
            metrics.spacing_xs,
        )
        layout.setSpacing(metrics.spacing_sm)

        self.summary_label = QLabel("Ready")
        self.summary_label.setObjectName("summaryLabel")
        layout.addWidget(self.summary_label, 1)

        self.details_toggle_button = QPushButton("Show details")
        self.details_toggle_button.setObjectName("detailsToggleButton")
        self.details_toggle_button.setCheckable(True)
        self.details_toggle_button.clicked.connect(
            lambda checked: self.set_details_expanded(checked)
        )
        layout.addWidget(self.details_toggle_button)

        return container

    def create_details_section(self) -> QFrame:
        """Create the details section."""
        metrics = get_theme_service().get_theme_definition().metrics
        container = QFrame()
        container.setObjectName("detailsContainer")

        layout = QVBoxLayout(container)
        layout.setContentsMargins(
            metrics.spacing_md,
            metrics.spacing_sm,
            metrics.spacing_md,
            metrics.spacing_sm,
        )
        layout.setSpacing(metrics.spacing_sm)

        # Titre de section
        details_title = QLabel("📊 Details")
        details_title.setFont(self.create_bold_font(1))
        layout.addWidget(details_title)

        # Grille de statistiques
        stats_layout = QHBoxLayout()

        # Column 1: Items
        items_container = QFrame()
        items_container.setObjectName("statsContainer")
        items_layout = QVBoxLayout(items_container)
        items_layout.setContentsMargins(
            metrics.spacing_sm,
            metrics.spacing_xs,
            metrics.spacing_sm,
            metrics.spacing_xs,
        )

        self.processed_label = QLabel("Processed: 0/0")
        self.processed_label.setObjectName("statsLabel")
        items_layout.addWidget(self.processed_label)

        self.successful_label = QLabel("✅ Success: 0")
        self.successful_label.setObjectName("successLabel")
        items_layout.addWidget(self.successful_label)

        self.failed_label = QLabel("❌ Failed: 0")
        self.failed_label.setObjectName("failedLabel")
        items_layout.addWidget(self.failed_label)

        stats_layout.addWidget(items_container, 1)

        # Colonne 2 : Performance
        perf_container = QFrame()
        perf_container.setObjectName("statsContainer")
        perf_layout = QVBoxLayout(perf_container)
        perf_layout.setContentsMargins(
            metrics.spacing_sm,
            metrics.spacing_xs,
            metrics.spacing_sm,
            metrics.spacing_xs,
        )

        self.rate_label = QLabel("Rate: 0 items/s")
        self.rate_label.setObjectName("statsLabel")
        perf_layout.addWidget(self.rate_label)

        self.elapsed_label = QLabel("Elapsed: 00:00")
        self.elapsed_label.setObjectName("statsLabel")
        perf_layout.addWidget(self.elapsed_label)

        self.remaining_label = QLabel("Remaining: --:--")
        self.remaining_label.setObjectName("statsLabel")
        perf_layout.addWidget(self.remaining_label)

        stats_layout.addWidget(perf_container, 1)

        layout.addLayout(stats_layout)

        return container

    def create_log_section(self) -> QFrame:
        """Create la section de log."""
        theme = get_theme_service().get_theme_definition()
        metrics = theme.metrics
        typography = theme.typography
        container = QFrame()
        container.setObjectName("logContainer")

        layout = QVBoxLayout(container)
        layout.setContentsMargins(
            metrics.spacing_md,
            metrics.spacing_sm,
            metrics.spacing_md,
            metrics.spacing_sm,
        )
        layout.setSpacing(metrics.spacing_xs)

        # Title with controls
        header_layout = QHBoxLayout()

        log_title = QLabel("📝 Activity Log")
        log_title.setFont(self.create_bold_font(1))
        header_layout.addWidget(log_title)

        header_layout.addStretch()

        # Bouton clear log
        self.clear_log_button = QPushButton("🗑️")
        self.clear_log_button.setObjectName("clearLogButton")
        self.clear_log_button.setFixedSize(
            metrics.control_height - 12, metrics.control_height - 12
        )
        self.clear_log_button.setToolTip("Clear log")
        self.clear_log_button.clicked.connect(self.clear_log)
        header_layout.addWidget(self.clear_log_button)

        layout.addLayout(header_layout)

        # Zone de log
        self.log_text = QTextEdit()
        self.log_text.setObjectName("logText")
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(120)
        self.log_text.setFont(
            QFont(typography.font_family_monospace, typography.font_size_xs - 2)
        )
        layout.addWidget(self.log_text)

        return container

    def create_actions_section(self) -> QFrame:
        """Create la section des actions."""
        metrics = get_theme_service().get_theme_definition().metrics
        container = QFrame()
        container.setObjectName("actionsContainer")

        layout = QHBoxLayout(container)
        layout.setContentsMargins(
            metrics.spacing_sm,
            metrics.spacing_xs,
            metrics.spacing_sm,
            metrics.spacing_xs,
        )
        layout.setSpacing(metrics.spacing_sm)

        layout.addStretch()

        # Bouton d'annulation
        self.cancel_button = QPushButton("❌ Cancel")
        self.cancel_button.setObjectName("cancelButton")
        self.cancel_button.clicked.connect(self._on_cancel_clicked)
        self.cancel_button.setEnabled(False)
        layout.addWidget(self.cancel_button)

        self.secondary_button = QPushButton("Close")
        self.secondary_button.setObjectName("secondaryOperationButton")
        self.secondary_button.clicked.connect(lambda: self._emit_action("close"))
        self.secondary_button.hide()
        layout.addWidget(self.secondary_button)

        return container

    def apply_default_theme(self, palette: ThemePalette):
        """Apply theme to panel."""
        try:
            theme = get_theme_service().get_theme_definition(palette.name)
            metrics = theme.metrics
            typography = theme.typography
            on_secondary = getattr(
                palette, "on_secondary", getattr(palette, "on_surface", "#1e293b")
            )

            style = f"""
                QFrame#progressHeader {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 {palette.surface},
                        stop:1 {palette.surface_variant}
                    );
                    border: 1px solid {palette.outline};
                    border-radius: {metrics.radius_md - 2}px;
                }}

                QLabel#progressTitle {{
                    color: {palette.primary};
                    font-family: "{typography.font_family}";
                    font-weight: {typography.font_weight_bold};
                }}

                QLabel#stateIndicator {{
                    color: {palette.secondary};
                }}

                QFrame#progressContainer {{
                    background-color: {palette.surface};
                    border: 1px solid {palette.outline};
                    border-radius: {metrics.radius_md - 2}px;
                }}

                QProgressBar#mainProgressBar {{
                    border: {metrics.focus_width}px solid {palette.outline};
                    border-radius: {metrics.radius_md - 2}px;
                    background-color: {palette.surface_variant};
                    text-align: center;
                    font-family: "{typography.font_family}";
                    font-weight: {typography.font_weight_bold};
                    min-height: {metrics.control_height - 16}px;
                }}

                QProgressBar#mainProgressBar::chunk {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 {palette.primary},
                        stop:1 {palette.primary_light}
                    );
                    border-radius: {metrics.radius_sm}px;
                    margin: {max(1, metrics.spacing_xs - 2)}px;
                }}

                QLabel#currentItemLabel {{
                    color: {palette.on_surface_variant};
                    font-family: "{typography.font_family}";
                    font-size: {typography.font_size_sm}px;
                }}

                QLabel#summaryLabel {{
                    color: {palette.on_surface};
                    font-family: "{typography.font_family}";
                    font-size: {typography.font_size_sm}px;
                    font-weight: {typography.font_weight_medium};
                }}

                QLabel#timeLabel {{
                    color: {palette.primary};
                    font-family: "{typography.font_family}";
                    font-weight: {typography.font_weight_bold};
                }}

                QFrame#summaryContainer, QFrame#detailsContainer, QFrame#logContainer {{
                    background-color: {palette.surface_variant};
                    border: 1px solid {palette.outline};
                    border-radius: {metrics.radius_md - 2}px;
                }}

                QFrame#statsContainer {{
                    background-color: {palette.surface};
                    border: 1px solid {palette.outline_variant};
                    border-radius: {metrics.radius_sm}px;
                }}

                QLabel#statsLabel {{
                    color: {palette.on_surface};
                    padding: {max(1, metrics.spacing_xs - 2)}px;
                    font-family: "{typography.font_family}";
                    font-size: {typography.font_size_sm}px;
                }}

                QLabel#successLabel {{
                    color: {palette.success if hasattr(palette, "success") else palette.primary};
                    padding: {max(1, metrics.spacing_xs - 2)}px;
                    font-family: "{typography.font_family}";
                    font-size: {typography.font_size_sm}px;
                }}

                QLabel#failedLabel {{
                    color: {palette.error};
                    padding: {max(1, metrics.spacing_xs - 2)}px;
                    font-family: "{typography.font_family}";
                    font-size: {typography.font_size_sm}px;
                }}

                QTextEdit#logText {{
                    background-color: {palette.surface};
                    border: 1px solid {palette.outline_variant};
                    border-radius: {metrics.radius_sm - 2}px;
                    color: {palette.on_surface};
                    font-family: "{typography.font_family_monospace}";
                    font-size: {typography.font_size_xs - 2}px;
                }}

                QFrame#actionsContainer {{
                    background-color: {palette.surface_variant};
                    border-top: 1px solid {palette.outline};
                    border-radius: 0 0 {metrics.radius_md - 2}px {metrics.radius_md - 2}px;
                }}

                QPushButton#cancelButton {{
                    background-color: {palette.error};
                    color: white;
                    border: none;
                    border-radius: {metrics.radius_sm}px;
                    padding: {metrics.spacing_sm}px {metrics.spacing_lg}px;
                    min-height: {metrics.control_height}px;
                    font-family: "{typography.font_family}";
                    font-weight: {typography.font_weight_bold};
                }}

                QPushButton#cancelButton:hover:enabled {{
                    background-color: {palette.error_dark if hasattr(palette, "error_dark") else palette.error};
                }}

                QPushButton#cancelButton:disabled {{
                    background-color: {palette.disabled};
                    color: {palette.disabled_text};
                }}

                QPushButton#detailsToggleButton,
                QPushButton#secondaryOperationButton {{
                    background-color: transparent;
                    color: {palette.on_surface_variant};
                    border: 1px solid {palette.outline};
                    border-radius: {metrics.radius_sm}px;
                    padding: {max(2, metrics.spacing_xs - 1)}px {metrics.spacing_sm}px;
                    min-height: {metrics.control_height - 10}px;
                }}

                QPushButton#clearLogButton {{
                    background-color: {palette.secondary};
                    color: {on_secondary};
                    border: none;
                    border-radius: {metrics.radius_sm - 2}px;
                }}
            """
            self.setStyleSheet(style)

        except Exception as e:
            self.logger.error(f"Error applying progress panel theme: {e}")

    # === GESTION DE L'ÉTAT ===

    def start_progress(self, max_value: int = 100, title: str = None):
        """Start une new progress."""
        if title:
            self.title = title
            self.title_label.setText(f"⏳ {title}")

        normalized_max = int(max_value) if max_value is not None else 0
        self.is_indeterminate = normalized_max <= 0
        self.max_progress = max(1, normalized_max) if not self.is_indeterminate else 0
        self.current_progress = 0
        self.is_running = True
        self.start_time = time.time()
        self.end_time = None

        # Reset statistiques
        self.stats = {
            "items_processed": 0,
            "items_total": self.max_progress if not self.is_indeterminate else 0,
            "items_successful": 0,
            "items_failed": 0,
            "items_skipped": 0,
            "errors": [],
            "current_item": "",
            "elapsed_time": 0,
            "estimated_remaining": 0,
            "processing_rate": 0,
        }

        # Interface
        if self.is_indeterminate:
            # Qt busy mode when total is unknown.
            self.progress_bar.setRange(0, 0)
            self.progress_bar.setTextVisible(False)
        else:
            self.progress_bar.setRange(0, self.max_progress)
            self.progress_bar.setValue(0)
            self.progress_bar.setTextVisible(True)
        self.cancel_button.setEnabled(self.is_cancellable)

        # State visuel
        self._set_visual_state("running")

        # Timer for updates
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_time_info)
        self.update_timer.start(1000)  # Update every second

        self.log_message("🚀 Progress started")
        self.summary_label.setText(f"{self.title} in progress")
        self.set_details_expanded(False)
        self.state_changed.emit("started")

    def update_progress(
        self,
        value: int,
        current_item: str = "",
        success: bool = True,
        error_message: str = "",
    ):
        """Update la progression."""
        if not self.is_running:
            return

        if self._current_operation_state is not None:
            # Integrated Operations mode is driven through apply_operation_state().
            return

        previous_processed = int(self.stats.get("items_processed", 0))
        value_int = max(0, int(value))
        if self.is_indeterminate:
            self.current_progress = value_int
        else:
            self.current_progress = min(value_int, self.max_progress)
            self.progress_bar.setValue(self.current_progress)

        # Statistiques
        self.stats["items_processed"] = value_int
        self.stats["current_item"] = current_item

        # Count outcomes only when processing actually advanced or when explicit error is reported.
        delta_processed = max(0, value_int - previous_processed)
        if delta_processed > 0 or error_message:
            if success:
                self.stats["items_successful"] += max(1, delta_processed)
            else:
                self.stats["items_failed"] += max(1, delta_processed)
                if error_message:
                    self.stats["errors"].append(
                        {
                            "item": current_item,
                            "message": error_message,
                            "time": time.time(),
                        }
                    )

        # Calcul du taux de traitement
        if self.start_time:
            elapsed = time.time() - self.start_time
            if elapsed > 0:
                self.stats["processing_rate"] = value / elapsed

                # Estimation du temps restant
                remaining_items = self.max_progress - value_int
                if self.stats["processing_rate"] > 0 and not self.is_indeterminate:
                    self.stats["estimated_remaining"] = (
                        remaining_items / self.stats["processing_rate"]
                    )

        # Interface update
        self._update_display()

        # Log
        if current_item:
            status = "✅" if success else "❌"
            self.log_message(f"{status} {current_item}")
            if not success and error_message:
                self.log_message(f"   Error: {error_message}", "error")

        # Check if complete
        if (not self.is_indeterminate) and value_int >= self.max_progress:
            self.complete_progress()

    def complete_progress(self, success: bool = True):
        """Termine la progression."""
        if not self.is_running:
            return

        self.is_running = False
        self.end_time = time.time()
        self.cancel_button.setEnabled(False)

        if hasattr(self, "update_timer"):
            self.update_timer.stop()

        # Calculs finaux
        if self.start_time:
            self.stats["elapsed_time"] = self.end_time - self.start_time

        # State visuel
        if success:
            self._set_visual_state("completed")
            self.title_label.setText(f"✅ {self.title} - Completed")
            self.log_message("🎉 Progress completed successfully")
        else:
            self._set_visual_state("failed")
            self.title_label.setText(f"❌ {self.title} - Failed")
            self.log_message("💥 Progress failed")

        # Final update
        self._update_display()

        # Signal
        self.progress_completed.emit(self.stats.copy())
        self.state_changed.emit("completed" if success else "failed")

    def cancel_progress(self):
        """Cancel la progression."""
        if not self.is_running:
            return

        self.is_running = False
        self.end_time = time.time()
        self.cancel_button.setEnabled(False)

        if hasattr(self, "update_timer"):
            self.update_timer.stop()

        # State visuel
        self._set_visual_state("cancelled")
        self.title_label.setText(f"⏹️ {self.title} - Cancelled")

        self.log_message("⏹️ Progress cancelled by user")
        self.state_changed.emit("cancelled")

    def reset_progress(self):
        """Reset la progression."""
        self.is_running = False
        self.current_progress = 0
        self.start_time = None
        self.end_time = None

        # Interface
        self.progress_bar.setValue(0)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(True)
        self.cancel_button.setEnabled(False)
        self.current_item_label.setText("Ready")
        self.is_indeterminate = False
        self.summary_label.setText("Ready")
        self.secondary_button.hide()
        self._current_operation_state = None

        # State visuel
        self._set_visual_state("ready")

        if hasattr(self, "update_timer"):
            self.update_timer.stop()

        self.state_changed.emit("ready")

    def _set_visual_state(self, state: str):
        """Set l'state visuel du panel."""
        state_colors = {
            "ready": "gray",
            "running": "#4CAF50",  # Vert
            "completed": "#2196F3",  # Bleu
            "failed": "#F44336",  # Rouge
            "cancelled": "#FF9800",  # Orange
        }

        color = state_colors.get(state, "gray")
        self.state_indicator.setStyleSheet(f"color: {color};")

        # Animation du point pour l'state running
        if state == "running":
            self._start_pulse_animation()
        else:
            self._stop_pulse_animation()

    def _start_pulse_animation(self):
        """Start l'pulsing animation."""
        if not hasattr(self, "pulse_animation"):
            self.pulse_animation = QPropertyAnimation(self.state_indicator, b"opacity")
            self.pulse_animation.setDuration(1000)
            self.pulse_animation.setStartValue(1.0)
            self.pulse_animation.setEndValue(0.3)
            self.pulse_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
            self.pulse_animation.setLoopCount(-1)  # Infini

        self.pulse_animation.start()

    def _stop_pulse_animation(self):
        """Stop l'pulsing animation."""
        if hasattr(self, "pulse_animation"):
            self.pulse_animation.stop()

    def _update_display(self):
        """Update display des informations."""
        # Current item
        if self.stats["current_item"]:
            # Tronquer si trop long
            item = self.stats["current_item"]
            if len(item) > 50:
                item = item[:47] + "..."
            self.current_item_label.setText(item)

        # details (si enabled)
        if self.show_details:
            total_text = (
                str(self.stats["items_total"])
                if int(self.stats.get("items_total", 0)) > 0
                else "?"
            )
            self.processed_label.setText(
                f"Processed: {self.stats['items_processed']}/{total_text}"
            )
            self.successful_label.setText(
                f"✅ Success: {self.stats['items_successful']}"
            )
            self.failed_label.setText(f"❌ Failed: {self.stats['items_failed']}")

            # Performance
            rate = self.stats["processing_rate"]
            self.rate_label.setText(f"Rate: {self._format_rate(rate, 'items')}")

        if self.is_running:
            rate = self.stats["processing_rate"]
            self.summary_label.setText(
                f"{self.stats['items_processed']} processed at {self._format_rate(rate, 'items')}"
            )

    def _update_time_info(self):
        """Update les informations de temps."""
        if not self.start_time:
            return

        # Elapsed time
        elapsed = time.time() - self.start_time
        self.stats["elapsed_time"] = elapsed
        elapsed_str = self._format_time(elapsed)

        # Estimated remaining time
        remaining = (
            0 if self.is_indeterminate else self.stats.get("estimated_remaining", 0)
        )
        if self.is_indeterminate:
            remaining_str = "scanning..."
        else:
            remaining_str = self._format_time(remaining) if remaining > 0 else "--:--"

        # Interface update
        self.time_label.setText(f"{elapsed_str} / {remaining_str}")

        if self.show_details:
            self.elapsed_label.setText(f"Elapsed: {elapsed_str}")
            self.remaining_label.setText(f"Remaining: {remaining_str}")

    def _format_time(self, seconds: float) -> str:
        """Formate un temps en secondes en format MM:SS."""
        if seconds < 0:
            return "--:--"

        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"

    @staticmethod
    def _format_rate(rate: float, unit: str) -> str:
        if rate <= 0:
            return f"0.0 {unit}/s"
        if rate < 1:
            return f"{rate * 60:.1f} {unit}/min"
        return f"{rate:.1f} {unit}/s"

    def _on_cancel_clicked(self):
        """Called when cancel button is clicked."""
        if (
            self._current_operation_state
            and self._current_operation_state.primary_action
        ):
            self._emit_action(self._current_operation_state.primary_action)
            return
        self.cancel_requested.emit()
        self.cancel_progress()

    def _emit_action(self, action: str):
        self.action_requested.emit(action)
        callback = self._action_callbacks.get(action)
        if callback:
            callback()

    # === LOG ===

    def log_message(self, message: str, level: str = "info"):
        """Ajoute un message au log."""
        timestamp = time.strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"

        # Add to list
        self.log_messages.append(
            {"timestamp": timestamp, "message": message, "level": level}
        )

        # Limiter le nombre de messages
        if len(self.log_messages) > self.max_log_messages:
            self.log_messages.pop(0)

        # Displayr dans l'interface if enabled
        if self.show_log and hasattr(self, "log_text"):
            # Couleur selon le niveau
            color = {
                "error": "red",
                "warning": "orange",
                "info": "black",
                "success": "green",
            }.get(level, "black")

            self.log_text.append(
                f'<span style="color: {color};">{formatted_message}</span>'
            )

            # Auto-scroll vers le bas
            cursor = self.log_text.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.log_text.setTextCursor(cursor)

    def clear_log(self):
        """Vide le log."""
        self.log_messages.clear()
        if hasattr(self, "log_text"):
            self.log_text.clear()

    # === API PUBLIQUE ===

    def set_cancellable(self, cancellable: bool):
        """Set si la progression can be canceled."""
        self.is_cancellable = cancellable
        if hasattr(self, "cancel_button"):
            self.cancel_button.setVisible(cancellable)

    def set_show_details(self, show: bool):
        """Enable/disable details display."""
        self.show_details = show
        if hasattr(self, "details_container"):
            self.details_container.setVisible(show and self.details_expanded)

    def set_show_log(self, show: bool):
        """Enable/disable display du log."""
        self.show_log = show
        if hasattr(self, "log_container"):
            self.log_container.setVisible(show and self.details_expanded)

    def set_show_progress_bar(self, show: bool):
        """Shows or hides the inline progress bar area."""
        self.show_progress_bar = show
        if hasattr(self, "progress_container"):
            self.progress_container.setVisible(show)

    def set_details_expanded(self, expanded: bool):
        """Shows or hides detailed operation information."""
        self.details_expanded = expanded
        if hasattr(self, "details_toggle_button"):
            self.details_toggle_button.setChecked(expanded)
            self.details_toggle_button.setText(
                "Hide details" if expanded else "Show details"
            )
        if hasattr(self, "details_container"):
            self.details_container.setVisible(self.show_details and expanded)
        if hasattr(self, "log_container"):
            self.log_container.setVisible(self.show_log and expanded)

    def set_operation_action_handlers(
        self, handlers: dict[str, Callable[[], None]] | None
    ):
        self._action_callbacks = handlers or {}

    def apply_operation_state(self, state: OperationViewState):
        """Applies a unified operation state to the panel."""
        self._current_operation_state = state
        self.title = state.title
        self.title_label.setText(f"⏳ {state.title}")
        self.summary_label.setText(state.summary)
        self.current_item_label.setText(
            state.current_item or "Waiting for first item..."
        )

        self.is_running = state.state in {
            "discovering",
            "running",
            "paused",
            "cancelling",
        }
        self.is_indeterminate = not state.is_determinate or state.progress_total <= 0
        if self.is_indeterminate:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, max(1, state.progress_total))
            self.progress_bar.setValue(
                min(state.progress_current, state.progress_total)
            )

        self._apply_operation_stats(state)
        self._apply_operation_details(state)
        self._apply_operation_log(state)
        self._apply_operation_actions(state)
        self._apply_operation_visual_state(state.state)

    def _apply_operation_stats(self, state: OperationViewState):
        stats = state.stats[:3]
        targets = [self.processed_label, self.successful_label, self.failed_label]
        defaults = ["Processed: --", "Success: --", "Failed: --"]
        for target, default, stat in zip(
            targets, defaults, stats + [None] * (3 - len(stats))
        ):
            if stat is None:
                target.setText(default)
            else:
                suffix = f" {stat.hint}" if stat.hint else ""
                target.setText(f"{stat.label}: {stat.value}{suffix}")

    def _apply_operation_details(self, state: OperationViewState):
        details = {detail.label.lower(): detail.value for detail in state.details}
        if "processed" in details:
            self.processed_label.setText(f"Processed: {details.get('processed', '--')}")
        else:
            self.processed_label.setText(f"Scanned: {details.get('scanned', '--')}")
        self.rate_label.setText(f"Rate: {details.get('rate', '--')}")
        self.elapsed_label.setText(f"Elapsed: {details.get('elapsed', '--:--')}")
        self.remaining_label.setText(f"Remaining: {details.get('remaining', '--:--')}")
        if "directory" in details:
            self.current_item_label.setToolTip(details["directory"])

    def _apply_operation_log(self, state: OperationViewState):
        if self.show_log and hasattr(self, "log_text"):
            self.log_text.clear()
            for entry in state.log_entries[-50:]:
                self.log_text.append(entry)

    def _apply_operation_actions(self, state: OperationViewState):
        if state.primary_action == "cancel":
            self.cancel_button.setText(state.primary_action_label or "Cancel")
            self.cancel_button.setEnabled(True)
            self.cancel_button.show()
        elif state.primary_action == "pause":
            self.cancel_button.setText(state.primary_action_label or "Pause")
            self.cancel_button.setEnabled(True)
            self.cancel_button.show()
        else:
            self.cancel_button.hide()
            self.cancel_button.setEnabled(False)

        if state.secondary_action:
            self.secondary_button.setText(
                state.secondary_action_label or state.secondary_action.title()
            )
            self.secondary_button.show()
            self.secondary_button.setEnabled(True)
        else:
            self.secondary_button.hide()

    def _apply_operation_visual_state(self, state: str):
        visual_state = {
            "idle": "ready",
            "discovering": "running",
            "running": "running",
            "paused": "cancelled",
            "cancelling": "cancelled",
            "completed": "completed",
            "failed": "failed",
        }.get(state, "ready")
        self._set_visual_state(visual_state)

    def get_stats(self) -> Dict[str, Any]:
        """Return les statistiques actuelles."""
        return self.stats.copy()

    def get_log_messages(self) -> List[Dict[str, Any]]:
        """Return les messages de log."""
        return self.log_messages.copy()

    def is_progress_running(self) -> bool:
        """Check si une progression est in progress."""
        return self.is_running

    def is_indeterminate_mode(self) -> bool:
        """Return True si la progression est en mode indeterminate."""
        return self.is_indeterminate

    def set_total_items(self, total_items: int) -> None:
        """Switch en mode determinate avec un total connu."""
        total = max(0, int(total_items))
        if total <= 0:
            return

        self.max_progress = total
        self.stats["items_total"] = total
        self.is_indeterminate = False
        self.progress_bar.setRange(0, total)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setValue(min(self.current_progress, total))
        self._update_display()

    def set_outcome_counters(self, successful: int, failed: int) -> None:
        """allows syncing les counters de succeededte/failure from external source."""
        self.stats["items_successful"] = max(0, int(successful))
        self.stats["items_failed"] = max(0, int(failed))
        self._update_display()

    def get_progress_percentage(self) -> float:
        """Return le pourcentage de progression."""
        if self.max_progress == 0:
            return 0
        return (self.current_progress / self.max_progress) * 100
