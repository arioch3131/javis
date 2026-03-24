from collections import OrderedDict
import math
import os
from typing import Callable, Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from ai_content_classifier.core.memory.factories import QPixmapFactory
from ai_content_classifier.services.file.file_type_service import (
    is_document_file,
    is_image_file,
)
from ai_content_classifier.services.performance.metrics import PerformanceMetrics
from ai_content_classifier.services.shared.cache_runtime import get_cache_runtime
from ai_content_classifier.services.theme.theme_service import (
    ThemePalette,
    get_theme_service,
)
from ai_content_classifier.views.widgets.common.file_hover_preview import (
    FileHoverPreview,
)
from ai_content_classifier.views.widgets.grid.thumbnail_item import (
    OptimizedThumbnailItem,
)
from ai_content_classifier.views.workers.thumbnail_batch_worker import (
    BatchThumbnailWorker,
)


class SmartPoolPixmapCache:
    """LRU thumbnail cache backed by a SmartPool-managed QPixmap adapter."""

    def __init__(
        self,
        *,
        target_size: int,
        max_memory_mb: int = 100,
        max_pool_size: int = 128,
        max_size_per_key: int = 12,
    ) -> None:
        self._runtime = get_cache_runtime()
        self._factory = QPixmapFactory()
        self._adapter_name = f"thumbnail_grid_qpixmap_{id(self)}"
        self._entries: OrderedDict[str, tuple[QPixmap, int, bool]] = OrderedDict()
        self._target_size = target_size
        self._max_memory_bytes = max_memory_mb * 1024 * 1024
        self._max_pool_size = max_pool_size
        self._max_size_per_key = max_size_per_key
        self.current_memory = 0
        self.hits = 0
        self.misses = 0
        self._register_adapter()

    def _register_adapter(self) -> None:
        self._runtime.register_smartpool_adapter(
            name=self._adapter_name,
            factory_function=self._factory.create,
            factory_validate_function=self._factory.validate,
            factory_args=(self._target_size, self._target_size),
            initial_size=1,
            min_size=0,
            max_size=self._max_pool_size,
            max_size_per_key=self._max_size_per_key,
            max_age_seconds=120,
            cleanup_interval=30,
            enable_background_cleanup=True,
            enable_performance_metrics=True,
            enable_auto_tuning=False,
            auto_wrap_objects=False,
            extra_config={
                "reset_func": self._factory.reset,
                "destroy_func": self._factory.destroy,
            },
        )

    def _get_adapter(self):
        manager = self._runtime.manager
        if manager is None:
            return None
        return manager.get_adapter(self._adapter_name)

    def _release_pooled_pixmap(self, pixmap: QPixmap, from_pool: bool) -> None:
        if not from_pool:
            return
        adapter = self._get_adapter()
        if adapter is not None:
            adapter.put(pixmap)

    def _estimate_size(self, pixmap: QPixmap) -> int:
        try:
            return self._factory.estimate_size(pixmap)
        except Exception:
            return 200_000

    def _evict_if_needed(self) -> None:
        while self.current_memory > self._max_memory_bytes and self._entries:
            _, (pixmap, size_bytes, from_pool) = self._entries.popitem(last=False)
            self.current_memory -= size_bytes
            self._release_pooled_pixmap(pixmap, from_pool)

    def _acquire_pixmap(self) -> tuple[QPixmap, bool]:
        adapter = self._get_adapter()
        if adapter is not None:
            pooled = adapter.get(self._target_size, self._target_size)
            if isinstance(pooled, QPixmap) and not pooled.isNull():
                return pooled, True

        fallback = QPixmap(self._target_size, self._target_size)
        fallback.fill(QColor(0, 0, 0, 0))
        return fallback, False

    def _render_thumbnail(self, target: QPixmap, source: QPixmap) -> None:
        target.fill(QColor(0, 0, 0, 0))

        painter = QPainter(target)
        try:
            src_width = source.width()
            src_height = source.height()
            if src_width <= 0 or src_height <= 0:
                return

            if src_width > src_height:
                crop_size = src_height
                crop_x = (src_width - crop_size) // 2
                source_rect = source.copy(crop_x, 0, crop_size, crop_size)
            else:
                crop_size = src_width
                crop_y = (src_height - crop_size) // 2
                source_rect = source.copy(0, crop_y, crop_size, crop_size)

            painter.drawPixmap(
                0,
                0,
                self._target_size,
                self._target_size,
                source_rect,
            )
        finally:
            painter.end()

    def get(self, key: str) -> Optional[QPixmap]:
        cached = self._entries.get(key)
        if cached is None:
            self.misses += 1
            return None

        self._entries.move_to_end(key)
        self.hits += 1
        return cached[0]

    def get_or_load(self, key: str, thumbnail_path: str) -> Optional[QPixmap]:
        cached = self.get(key)
        if cached is not None:
            return cached

        source = QPixmap(thumbnail_path)
        if source.isNull():
            return None

        target, from_pool = self._acquire_pixmap()
        self._render_thumbnail(target, source)

        size_bytes = self._estimate_size(target)
        self._entries[key] = (target, size_bytes, from_pool)
        self.current_memory += size_bytes
        self._entries.move_to_end(key)
        self._evict_if_needed()
        return target

    def clear(self) -> None:
        for pixmap, _, from_pool in self._entries.values():
            self._release_pooled_pixmap(pixmap, from_pool)
        self._entries.clear()
        self.current_memory = 0
        self.hits = 0
        self.misses = 0

    def reset_target_size(self, target_size: int) -> None:
        if target_size == self._target_size:
            return

        self.clear()
        manager = self._runtime.manager
        if manager is not None:
            manager.remove_adapter(self._adapter_name)

        self._target_size = target_size
        self._register_adapter()

    def get_hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0


class UltraOptimizedThumbnailGrid(QWidget):
    """
    Ultra-optimized grid for hundreds of gigabytes of data.
    Combines virtualization, moving window, and intelligent caching.
    VERSION CORRIGÉE pour le filtrage.
    """

    file_selected = pyqtSignal(str)
    file_activated = pyqtSignal(str)
    performance_updated = pyqtSignal(object)  # PerformanceMetrics

    def __init__(self, parent=None):
        super().__init__(parent)

        # Performance configuration
        self.visible_buffer = 20  # Off-screen items maintained
        self.thumbnail_size = 150
        self.max_concurrent_generation = 3

        # Data and cache - CORRECTION : pas de filtrage interne
        self.all_file_data: List[Tuple[str, str, str, str]] = []  # Data as received
        self.thumbnail_cache = SmartPoolPixmapCache(
            target_size=self.thumbnail_size,
            max_memory_mb=100,
        )

        # Recyclable widget pool
        self.widget_pool: List["OptimizedThumbnailItem"] = []
        self.active_widgets: Dict[int, "OptimizedThumbnailItem"] = {}

        # Workers and timers
        self.thumbnail_generator_func: Optional[Callable] = None
        self.generation_queue: List[str] = []
        self.generation_workers: List[QThread] = []

        # Performance metrics
        self.metrics = PerformanceMetrics()
        self.last_scroll_time = 0
        self.scroll_count = 0
        self.debug_metrics_visible = False

        # Timers for optimization
        self.scroll_timer = QTimer()
        self.scroll_timer.setSingleShot(True)
        self.scroll_timer.timeout.connect(self.update_visible_items)
        self.hover_preview_timer = QTimer()
        self.hover_preview_timer.setSingleShot(True)
        self.hover_preview_timer.timeout.connect(self._show_pending_hover_preview)
        self._pending_hover_data: Optional[dict] = None
        self._pending_hover_pos = None

        self.metrics_timer = QTimer()
        self.metrics_timer.timeout.connect(self.update_metrics)
        self.metrics_timer.start(1000)  # Every second

        self.setup_ui()
        self.hover_preview = FileHoverPreview()

    def setup_ui(self):
        """Configures the optimized interface."""
        metrics = get_theme_service().get_theme_definition().metrics
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(metrics.spacing_sm)

        # Performance bar
        self.create_performance_bar()

        # Ultra-optimized scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("thumbnailGridScrollArea")
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        # Content widget
        self.content_widget = QWidget()
        self.content_widget.setObjectName("thumbnailGridContent")
        self.scroll_area.setWidget(self.content_widget)

        # Scroll optimization
        self.scroll_area.verticalScrollBar().valueChanged.connect(
            self.on_optimized_scroll
        )

        self.main_layout.addWidget(self.scroll_area)
        self._setup_theme()

    def resizeEvent(self, event):
        """Handles widget resizing to recalculate layout."""
        super().resizeEvent(event)
        self.calculate_optimized_layout()
        self.update_visible_items()

    def create_performance_bar(self):
        """Creates the performance information bar."""
        theme = get_theme_service().get_theme_definition()
        metrics = theme.metrics
        perf_layout = QHBoxLayout()
        perf_layout.setContentsMargins(0, 0, 0, 0)
        perf_layout.setSpacing(metrics.spacing_sm)

        # Real-time metrics
        self.files_label = QLabel("Files: 0")
        self.files_label.setObjectName("gridMetricLabel")
        self.cache_label = QLabel("Cache: 0% hit")
        self.cache_label.setObjectName("gridMetricLabel")
        self.memory_label = QLabel("RAM: 0 MB")
        self.memory_label.setObjectName("gridMetricLabel")
        self.fps_label = QLabel("Scroll: 0 FPS")
        self.fps_label.setObjectName("gridMetricLabel")

        # Performance controls
        size_label = QLabel("Size:")
        size_label.setObjectName("gridControlLabel")
        perf_layout.addWidget(size_label)
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setObjectName("gridSizeSlider")
        self.size_slider.setRange(50, 300)  # Wider range for zoom
        self.size_slider.setValue(150)
        self.size_slider.setMaximumWidth(metrics.thumbnail_slider_width_compact)
        self.size_slider.valueChanged.connect(self.set_thumbnail_size)

        # Store default size for reset
        self.default_thumbnail_size = 150
        perf_layout.addWidget(self.size_slider)

        buffer_label = QLabel("Buffer:")
        buffer_label.setObjectName("gridControlLabel")
        perf_layout.addWidget(buffer_label)
        self.buffer_spin = QSpinBox()
        self.buffer_spin.setObjectName("gridBufferSpin")
        self.buffer_spin.setRange(5, 50)
        self.buffer_spin.setValue(20)
        self.buffer_spin.valueChanged.connect(self.set_visible_buffer)
        perf_layout.addWidget(self.buffer_spin)

        perf_layout.addStretch()

        # Metrics
        perf_layout.addWidget(self.files_label)
        perf_layout.addWidget(self.cache_label)
        perf_layout.addWidget(self.memory_label)
        perf_layout.addWidget(self.fps_label)

        # Cleanup button
        self.cleanup_btn = QPushButton("🧹 Clean Up")
        self.cleanup_btn.setObjectName("gridCleanupButton")
        self.cleanup_btn.clicked.connect(self.force_cleanup)
        perf_layout.addWidget(self.cleanup_btn)

        self.perf_widget = QWidget()
        self.perf_widget.setObjectName("gridPerfWidget")
        self.perf_widget.setLayout(perf_layout)
        self.perf_widget.setMaximumHeight(metrics.button_height)
        self.perf_widget.setVisible(self.debug_metrics_visible)
        self.main_layout.addWidget(self.perf_widget)

    def _setup_theme(self):
        theme_service = get_theme_service()
        theme_service.palette_updated.connect(self.apply_theme)
        self.apply_theme(theme_service.get_current_palette())

    def apply_theme(self, palette: ThemePalette):
        theme = get_theme_service().get_theme_definition(palette.name)
        metrics = theme.metrics
        typography = theme.typography
        self.setStyleSheet(
            f"""
            QWidget#gridPerfWidget {{
                background-color: {palette.surface_variant};
                border: 1px solid {palette.outline};
                border-radius: {metrics.radius_md}px;
            }}
            QLabel#gridMetricLabel,
            QLabel#gridControlLabel {{
                color: {palette.on_surface_variant};
                font-family: "{typography.font_family}";
                font-size: {typography.font_size_sm}px;
                font-weight: {typography.font_weight_semibold};
            }}
            QSpinBox#gridBufferSpin {{
                background-color: {palette.surface};
                color: {palette.on_surface};
                border: 1px solid {palette.outline};
                border-radius: {metrics.radius_sm}px;
                min-height: {metrics.control_height - 6}px;
                padding: 0 {metrics.spacing_sm}px;
            }}
            QPushButton#gridCleanupButton {{
                background-color: {palette.surface};
                color: {palette.on_surface};
                border: 1px solid {palette.outline};
                border-radius: {metrics.radius_sm}px;
                min-height: {metrics.control_height - 4}px;
                padding: 0 {metrics.spacing_md}px;
                font-family: "{typography.font_family}";
                font-weight: {typography.font_weight_semibold};
            }}
            QPushButton#gridCleanupButton:hover {{
                background-color: {palette.hover};
            }}
            QSlider#gridSizeSlider::groove:horizontal {{
                height: {metrics.spacing_sm - 2}px;
                background: {palette.outline};
                border-radius: {max(3, metrics.radius_sm // 2)}px;
            }}
            QSlider#gridSizeSlider::handle:horizontal {{
                width: {metrics.spacing_lg}px;
                margin: -{metrics.spacing_sm - 2}px 0;
                border-radius: {metrics.radius_sm + 2}px;
                background: {palette.primary};
            }}
            QScrollArea#thumbnailGridScrollArea {{
                background-color: {palette.surface};
                border: 1px solid {palette.outline};
                border-radius: {metrics.radius_md}px;
            }}
            QWidget#thumbnailGridContent {{
                background-color: transparent;
            }}
            """
        )

    def set_debug_metrics_visible(self, visible: bool):
        """Shows or hides developer-oriented performance metrics."""
        self.debug_metrics_visible = visible
        if hasattr(self, "perf_widget") and self.perf_widget:
            self.perf_widget.setVisible(visible)

    def set_file_data(self, file_data: List[Tuple[str, str, str, str]]):
        """
        Loads a large volume of data in an optimized way.
        FIX: Data already arrives filtered, no internal filtering needed.
        """

        # CRITICAL FIX: Clear all existing widgets when new data arrives
        self.clear_all_widgets()

        # Store all data (metadata only) - DÉJÀ FILTRÉES
        self.all_file_data = file_data

        # Update metrics
        self.metrics.total_files = len(file_data)

        # Calculate layout
        self.calculate_optimized_layout()

        # Launch initial update
        self.update_visible_items()

    def calculate_optimized_layout(self):
        """Calculates layout with mathematical optimizations."""
        if not self.all_file_data:
            self.content_widget.resize(0, 0)
            return

        # Calculate optimal dimensions
        viewport_width = self.scroll_area.viewport().width()
        item_width = self.thumbnail_size + 10

        # Use math for calculations (numpy not needed for this)
        self.columns = max(1, viewport_width // item_width)
        self.rows = math.ceil(len(self.all_file_data) / self.columns)

        # Total dimensions
        total_width = self.columns * item_width
        total_height = self.rows * (self.thumbnail_size + 40)

        self.content_widget.resize(total_width, total_height)

    def get_visible_range_optimized(self) -> Tuple[int, int]:
        """Calculates the visible range with optimizations."""
        if not self.all_file_data:
            return (0, 0)

        # Viewport position
        scroll_y = self.scroll_area.verticalScrollBar().value()
        viewport_height = self.scroll_area.viewport().height()

        # Vectorized calculations
        item_height = self.thumbnail_size + 40
        first_row = max(0, (scroll_y // item_height) - 1)
        last_row = min(self.rows, ((scroll_y + viewport_height) // item_height) + 2)

        # Index with buffer
        start_index = max(0, first_row * self.columns - self.visible_buffer)
        end_index = min(
            len(self.all_file_data), last_row * self.columns + self.visible_buffer
        )

        return (start_index, end_index)

    def update_visible_items(self):
        """Updates visible items with ultra-high performance optimizations."""
        start_index, end_index = self.get_visible_range_optimized()

        if start_index >= end_index:
            self.clear_all_widgets()
            return

        # Current and needed indices
        current_indices = set(self.active_widgets.keys())
        needed_indices = set(range(start_index, end_index))

        # Optimized widget recycling
        for index in current_indices - needed_indices:
            self.recycle_widget(index)

        # Batch thumbnail generation
        thumbnail_batch = []

        # Update/create needed widgets
        for list_index in range(start_index, end_index):
            if list_index >= len(self.all_file_data):
                continue

            # Get data - CORRECTION: utilise directement all_file_data
            file_path, directory, category, content_type = self.all_file_data[
                list_index
            ]

            # Widget management
            if list_index not in self.active_widgets:
                widget = self.get_widget_from_pool()
                self.active_widgets[list_index] = widget
                widget.configure_for_file(file_path, directory, content_type, category)

            widget = self.active_widgets[list_index]

            # Optimized positioning
            row = list_index // self.columns
            col = list_index % self.columns
            x = col * (self.thumbnail_size + 10)
            y = row * (self.thumbnail_size + 40)
            widget.setGeometry(x, y, self.thumbnail_size + 10, self.thumbnail_size + 40)

            # Thumbnail cache management - FIX: uses imported functions
            if is_document_file(file_path):
                widget.set_document_placeholder(os.path.basename(file_path))
            else:
                cached_thumbnail = self.thumbnail_cache.get(file_path)
                if cached_thumbnail:
                    widget.set_thumbnail(cached_thumbnail)
                else:
                    if is_image_file(file_path):
                        thumbnail_batch.append(file_path)

        # Start batch generation
        if thumbnail_batch and self.thumbnail_generator_func:
            self.start_batch_thumbnail_generation(thumbnail_batch)

        # Update metrics
        self.metrics.visible_items = len(self.active_widgets)

    def start_batch_thumbnail_generation(self, file_paths: List[str]):
        """Starts optimized batch thumbnail generation."""
        # Limit concurrency
        if len(self.generation_workers) >= self.max_concurrent_generation:
            return

        # Divide into chunks to avoid overload
        chunk_size = 10
        for i in range(0, len(file_paths), chunk_size):
            chunk = file_paths[i : i + chunk_size]

            worker = BatchThumbnailWorker(chunk, self.thumbnail_generator_func)
            worker.thumbnail_ready.connect(self.on_thumbnail_ready_optimized)
            worker.finished.connect(lambda w=worker: self.cleanup_worker(w))

            self.generation_workers.append(worker)
            worker.start()

    @pyqtSlot(str, str)
    def on_thumbnail_ready_optimized(self, file_path: str, thumbnail_path: str):
        """Load and cache pixmaps on the UI thread."""
        pixmap = self.thumbnail_cache.get_or_load(file_path, thumbnail_path)
        if pixmap is None:
            return

        # Update widget if visible
        for widget in self.active_widgets.values():
            if widget.file_path == file_path:
                widget.set_thumbnail(pixmap)
                break

    def on_optimized_scroll(self):
        """Optimized scroll management with debouncing."""
        import time

        current_time = time.time()

        # Calculate scroll FPS
        if self.last_scroll_time > 0:
            time_diff = current_time - self.last_scroll_time
            if time_diff > 0:
                fps = 1.0 / time_diff
                self.metrics.scroll_fps = (
                    fps * 0.1 + self.metrics.scroll_fps * 0.9
                )  # Smoothing

        self.last_scroll_time = current_time
        self.scroll_count += 1

        # Debouncing to avoid too many updates
        self.scroll_timer.start(16)  # ~60 FPS max

    def update_metrics(self):
        """Updates performance metrics."""
        # Cache metrics
        self.metrics.cache_hits = self.thumbnail_cache.hits
        self.metrics.cache_misses = self.thumbnail_cache.misses

        # Memory usage
        self.metrics.memory_usage_mb = self.thumbnail_cache.current_memory / (
            1024 * 1024
        )

        # Update UI
        hit_rate = self.thumbnail_cache.get_hit_rate()
        self.cache_label.setText(f"Cache: {hit_rate:.1%} hit")
        self.memory_label.setText(f"RAM: {self.metrics.memory_usage_mb:.1f} MB")
        self.files_label.setText(f"Files: {self.metrics.total_files:,}")
        self.fps_label.setText(f"Scroll: {self.metrics.scroll_fps:.0f} FPS")

        # Emit for external monitoring
        self.performance_updated.emit(self.metrics)

    def get_widget_from_pool(self) -> "OptimizedThumbnailItem":
        """Retrieves a widget from the pool with optimizations."""
        if self.widget_pool:
            return self.widget_pool.pop()

        # Create a new optimized widget
        widget = OptimizedThumbnailItem()
        widget.clicked.connect(self.on_thumbnail_clicked)
        widget.activated.connect(self.on_thumbnail_activated)
        widget.hover_started.connect(self.on_thumbnail_hover_started)
        widget.hover_ended.connect(self.on_thumbnail_hover_ended)
        widget.set_thumbnail_size(self.thumbnail_size)
        widget.setParent(self.content_widget)
        return widget

    def recycle_widget(self, index: int):
        """Recycles a widget in an optimized way."""
        if index in self.active_widgets:
            widget = self.active_widgets.pop(index)
            widget.clear_file()
            widget.hide()
            self.widget_pool.append(widget)

    def clear_all_widgets(self):
        """Clears all active widgets."""
        for index in list(self.active_widgets.keys()):
            self.recycle_widget(index)

    def force_cleanup(self):
        """Forces a complete cleanup."""
        # Stop all workers
        for worker in self.generation_workers:
            if worker.isRunning():
                worker.terminate()
        self.generation_workers.clear()

        # Clean up caches
        self.thumbnail_cache.clear()
        self.clear_all_widgets()

        # Force garbage collection
        import gc

        gc.collect()

    def set_thumbnail_size(self, size: int):
        """Changes thumbnail size."""
        self.thumbnail_size = max(50, min(300, size))  # Clamp size between 50 and 300
        self.size_slider.setValue(self.thumbnail_size)  # Update slider position
        self.thumbnail_cache.reset_target_size(self.thumbnail_size)
        for widget in self.active_widgets.values():
            widget.set_thumbnail_size(self.thumbnail_size)
        self.calculate_optimized_layout()
        self.update_visible_items()

    def zoom_in(self):
        """Increases thumbnail size."""
        self.set_thumbnail_size(self.thumbnail_size + 20)

    def zoom_out(self):
        """Decreases thumbnail size."""
        self.set_thumbnail_size(self.thumbnail_size - 20)

    def zoom_reset(self):
        """Resets thumbnail size to default."""
        self.set_thumbnail_size(self.default_thumbnail_size)

    def set_visible_buffer(self, buffer_size: int):
        """Changes visible buffer size."""
        self.visible_buffer = buffer_size
        self.update_visible_items()

    def cleanup_worker(self, worker):
        """Cleans up a finished worker."""
        if worker in self.generation_workers:
            self.generation_workers.remove(worker)
        worker.deleteLater()

    def get_memory_usage(self) -> float:
        """Returns memory usage in MB."""
        return self.thumbnail_cache.current_memory / (1024 * 1024)

    def on_thumbnail_clicked(self, file_path: str):
        """Handles optimized click."""
        self.hover_preview.hide()
        self.file_selected.emit(file_path)

    def on_thumbnail_activated(self, file_path: str):
        """Opens full file details for the activated thumbnail."""
        self.hover_preview.hide()
        self.file_activated.emit(file_path)

    def on_thumbnail_hover_started(self, preview_data: dict, global_pos):
        self._pending_hover_data = preview_data
        self._pending_hover_pos = global_pos
        self.hover_preview_timer.start(220)

    def on_thumbnail_hover_ended(self):
        self.hover_preview_timer.stop()
        self.hover_preview.hide()

    def _show_pending_hover_preview(self):
        if not self._pending_hover_data or self._pending_hover_pos is None:
            return
        self.hover_preview.show_for_file(
            self._pending_hover_data,
            self._pending_hover_pos,
        )
