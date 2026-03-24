from dataclasses import dataclass


@dataclass
class PerformanceMetrics:
    """Runtime metrics consumed by the grid performance UI."""

    total_files: int = 0
    visible_items: int = 0
    scroll_fps: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    memory_usage_mb: float = 0.0
