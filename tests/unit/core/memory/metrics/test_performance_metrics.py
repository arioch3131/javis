import unittest

from ai_content_classifier.core.memory.metrics.performance_metrics import (
    PerformanceMetrics,
)


class TestPerformanceMetrics(unittest.TestCase):
    def test_defaults(self):
        metrics = PerformanceMetrics()

        self.assertEqual(metrics.history_size, 1000)
        self.assertTrue(metrics.enable_detailed_tracking)
        self.assertEqual(metrics.cache_hits, 0)
        self.assertEqual(metrics.cache_misses, 0)
        self.assertEqual(metrics.total_files, 0)
        self.assertEqual(metrics.visible_items, 0)
        self.assertEqual(metrics.scroll_fps, 0.0)
        self.assertEqual(metrics.memory_usage_mb, 0.0)

    def test_custom_initialization(self):
        metrics = PerformanceMetrics(history_size=42, enable_detailed_tracking=False)

        self.assertEqual(metrics.history_size, 42)
        self.assertFalse(metrics.enable_detailed_tracking)
        self.assertEqual(metrics.cache_hits, 0)
        self.assertEqual(metrics.cache_misses, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
