import unittest

from ai_content_classifier.core.memory.config import MemoryConfig, MemoryPreset, MemoryConfigFactory

class TestMemoryConfig(unittest.TestCase):

    def test_default_values(self):
        """Test that MemoryConfig has sane default values."""
        config = MemoryConfig()
        self.assertGreater(config.max_size, 0)
        self.assertGreater(config.ttl_seconds, 0)
        self.assertGreater(config.cleanup_interval, 0)
        self.assertTrue(config.enable_performance_metrics)

    def test_parameter_validation(self):
        """Test that invalid parameters raise a ValueError."""
        with self.assertRaises(ValueError):
            MemoryConfig(max_size=0)
        with self.assertRaises(ValueError):
            MemoryConfig(ttl_seconds=-10)
        with self.assertRaises(ValueError):
            MemoryConfig(cleanup_interval=0)
        with self.assertRaises(ValueError):
            MemoryConfig(expected_concurrency=0)
        with self.assertRaises(ValueError):
            MemoryConfig(object_creation_cost="invalid_cost")
        with self.assertRaises(ValueError):
            MemoryConfig(memory_pressure="invalid_pressure")

class TestMemoryConfigFactory(unittest.TestCase):

    def test_create_all_presets(self):
        """Test that the factory can create a config for every defined preset."""
        default_config = MemoryConfig() # Get default config once
        for preset in MemoryPreset:
            with self.subTest(preset=preset.name):
                config = MemoryConfigFactory.create_preset(preset)
                self.assertIsInstance(config, MemoryConfig)

                if preset == MemoryPreset.CUSTOM:
                    self.assertEqual(config.max_size, default_config.max_size)
                    self.assertEqual(config.ttl_seconds, default_config.ttl_seconds)
                    # Add more assertions for other default values if necessary
                elif preset == MemoryPreset.DATABASE_CONNECTIONS:
                    # DATABASE_CONNECTIONS specifically has max_size=20, which is the default
                    self.assertEqual(config.max_size, 20)
                    # Add other specific assertions for DATABASE_CONNECTIONS if needed
                else:
                    # For other presets, ensure they are not the default config
                    self.assertNotEqual(config.max_size, default_config.max_size)

    def test_high_throughput_preset_values(self):
        """Test the specific values of the HIGH_THROUGHPUT preset."""
        config = MemoryConfigFactory.create_preset(MemoryPreset.HIGH_THROUGHPUT)
        self.assertGreaterEqual(config.max_size, 50)
        self.assertGreaterEqual(config.ttl_seconds, 1000)
        self.assertFalse(config.enable_logging)

    def test_low_memory_preset_values(self):
        """Test the specific values of the LOW_MEMORY preset."""
        config = MemoryConfigFactory.create_preset(MemoryPreset.LOW_MEMORY)
        self.assertLessEqual(config.max_size, 10)
        self.assertLessEqual(config.ttl_seconds, 120)
        self.assertFalse(config.enable_performance_metrics)

    def test_development_preset_values(self):
        """Test the specific values of the DEVELOPMENT preset."""
        config = MemoryConfigFactory.create_preset(MemoryPreset.DEVELOPMENT)
        self.assertTrue(config.enable_logging)
        self.assertLessEqual(config.ttl_seconds, 60)
        self.assertEqual(config.corrupted_object_threshold, 1)

if __name__ == '__main__':
    unittest.main(verbosity=2)
