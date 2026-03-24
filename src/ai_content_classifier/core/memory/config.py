"""
Memory pool configuration module.

This module provides configuration classes and presets for managing memory pools.
It includes predefined configurations optimized for different use cases such as
high throughput, low memory, image processing, database connections, and more.
"""

from dataclasses import dataclass
from enum import Enum


class MemoryPreset(Enum):
    """
    Defines predefined configuration presets for the memory pool.
    Each preset is optimized for a specific use case, providing a quick way to
    configure the pool for common scenarios.

    Attributes:
        HIGH_THROUGHPUT (str): Optimized for fast object acquisition and high reuse rates,
                                typically at the cost of higher memory usage.
        LOW_MEMORY (str): Optimized for strict memory constraints, prioritizing minimal
                          memory footprint over raw performance.
        IMAGE_PROCESSING (str): Tailored for large image objects, balancing memory
                                consumption with processing efficiency.
        DATABASE_CONNECTIONS (str): Configured for managing database connections or similar
                                    long-lived, resource-intensive objects,
                                    emphasizing stability and reuse.
        BATCH_PROCESSING (str): Suited for batch jobs or long-running tasks where objects
                                might be held for extended periods, with less frequent cleanup.
        DEVELOPMENT (str): A verbose preset for development and debugging, with extensive
                           logging and strict corruption detection.
        CUSTOM (str): Represents a user-defined or manually configured pool, not adhering
                      to any specific predefined preset.
    """

    HIGH_THROUGHPUT = "high_throughput"
    LOW_MEMORY = "low_memory"
    IMAGE_PROCESSING = "image_processing"
    DATABASE_CONNECTIONS = "database_connections"
    BATCH_PROCESSING = "batch_processing"
    DEVELOPMENT = "development"
    CUSTOM = "custom"


@dataclass
class MemoryConfig:  # pylint: disable=too-many-instance-attributes
    """
    Represents the configuration for a memory pool. This dataclass holds various
    parameters that control the behavior, performance, and resource usage of the
    `GenericMemoryPool`.

    Attributes:
        max_size (int): The maximum number of objects that can be held in the pool
                        for a specific key. This limits the memory footprint for each
                        type of pooled object.
        ttl_seconds (float): Time-to-live in seconds for pooled objects. Objects older
                             than this will be considered expired and removed during cleanup.
        cleanup_interval (float): The interval (in seconds) at which background cleanup
                                  tasks are executed.
        enable_logging (bool): If True, enables detailed logging for pool operations.
        enable_background_cleanup (bool): If True, a background thread will periodically
                                          clean up the pool.
        max_validation_attempts (int): The maximum number of times an object will be
                                       re-validated if it initially fails validation
                                       before being marked as corrupted.
        corrupted_object_threshold (int): The number of corrupted objects for a given key
                                          that triggers an alert or warning, indicating
                                          potential issues with the factory.

        # Performance metrics configuration
        enable_performance_metrics (bool): If True, enables the collection of detailed
                                           performance metrics.
        track_acquisition_times (bool): If True, records individual acquisition times for
                                        more granular analysis.
        track_lock_contention (bool): If True, tracks time spent waiting for pool locks
                                      to identify contention issues.
        performance_history_size (int): The number of historical performance records to keep.

        # Configuration for different usage patterns (hints for auto-tuning)
        expected_concurrency (int): An estimate of the maximum number of concurrent threads
                                    or processes that will acquire objects from the pool.
                                    Used for optimization hints.
        object_creation_cost (str): A qualitative estimate of how expensive it is to create
                                    a new object ('low', 'medium', 'high'). Influences
                                    pool sizing strategies.
        memory_pressure (str): A qualitative estimate of memory availability in the
                               environment ('low', 'normal', 'high'). Influences memory
                               management strategies.
    """

    max_size: int = 20
    ttl_seconds: float = 300.0
    cleanup_interval: float = 60.0
    enable_logging: bool = False
    enable_background_cleanup: bool = True
    max_validation_attempts: int = 3
    corrupted_object_threshold: int = 5  # Max number of corrupted objects before alert

    # New performance metrics
    enable_performance_metrics: bool = True
    track_acquisition_times: bool = True
    track_lock_contention: bool = True
    performance_history_size: int = 1000

    # Configuration for different usage patterns
    expected_concurrency: int = 10  # Expected number of threads
    object_creation_cost: str = "medium"  # low, medium, high
    memory_pressure: str = "normal"  # low, normal, high

    def __post_init__(self):
        """
        Performs validation on the configuration parameters after initialization.
        Ensures that values are within acceptable ranges and types.

        Raises:
            ValueError: If any configuration parameter has an invalid value.
        """
        if self.max_size <= 0:
            raise ValueError("max_size must be positive")
        if self.ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        if self.cleanup_interval <= 0:
            raise ValueError("cleanup_interval must be positive")
        if self.expected_concurrency <= 0:
            raise ValueError("expected_concurrency must be positive")
        if self.object_creation_cost not in ["low", "medium", "high"]:
            raise ValueError("object_creation_cost must be 'low', 'medium', or 'high'")
        if self.memory_pressure not in ["low", "normal", "high"]:
            raise ValueError("memory_pressure must be 'low', 'normal', or 'high'")


class MemoryConfigFactory:
    """
    A factory class responsible for creating `PoolConfig` instances, particularly
    for predefined presets and for auto-tuning configurations based on observed
    metrics.
    """

    # Configuration presets mapping
    _PRESET_CONFIGS = {
        MemoryPreset.HIGH_THROUGHPUT: {
            "max_size": 100,
            "ttl_seconds": 1800.0,
            "cleanup_interval": 120.0,
            "enable_logging": False,
            "enable_background_cleanup": True,
            "max_validation_attempts": 2,
            "corrupted_object_threshold": 20,
            "expected_concurrency": 50,
            "object_creation_cost": "medium",
            "memory_pressure": "normal",
            "enable_performance_metrics": True,
            "track_acquisition_times": True,
            "track_lock_contention": True,
            "performance_history_size": 2000,
        },
        MemoryPreset.LOW_MEMORY: {
            "max_size": 5,
            "ttl_seconds": 60.0,
            "cleanup_interval": 15.0,
            "enable_logging": False,
            "enable_background_cleanup": True,
            "max_validation_attempts": 1,
            "corrupted_object_threshold": 2,
            "expected_concurrency": 5,
            "object_creation_cost": "low",
            "memory_pressure": "high",
            "enable_performance_metrics": False,
            "track_acquisition_times": False,
            "track_lock_contention": False,
            "performance_history_size": 100,
        },
        MemoryPreset.IMAGE_PROCESSING: {
            "max_size": 30,
            "ttl_seconds": 600.0,
            "cleanup_interval": 90.0,
            "enable_logging": True,
            "enable_background_cleanup": True,
            "max_validation_attempts": 3,
            "corrupted_object_threshold": 3,
            "expected_concurrency": 15,
            "object_creation_cost": "high",
            "memory_pressure": "high",
            "enable_performance_metrics": True,
            "track_acquisition_times": True,
            "track_lock_contention": True,
            "performance_history_size": 500,
        },
        MemoryPreset.DATABASE_CONNECTIONS: {
            "max_size": 20,
            "ttl_seconds": 3600.0,
            "cleanup_interval": 300.0,
            "enable_logging": True,
            "enable_background_cleanup": True,
            "max_validation_attempts": 3,
            "corrupted_object_threshold": 3,
            "expected_concurrency": 25,
            "object_creation_cost": "high",
            "memory_pressure": "low",
            "enable_performance_metrics": True,
            "track_acquisition_times": True,
            "track_lock_contention": True,
            "performance_history_size": 1000,
        },
        MemoryPreset.BATCH_PROCESSING: {
            "max_size": 50,
            "ttl_seconds": 7200.0,
            "cleanup_interval": 600.0,
            "enable_logging": True,
            "enable_background_cleanup": False,
            "max_validation_attempts": 1,
            "corrupted_object_threshold": 10,
            "expected_concurrency": 10,
            "object_creation_cost": "medium",
            "memory_pressure": "normal",
            "enable_performance_metrics": True,
            "track_acquisition_times": False,
            "track_lock_contention": False,
            "performance_history_size": 200,
        },
        MemoryPreset.DEVELOPMENT: {
            "max_size": 10,
            "ttl_seconds": 30.0,
            "cleanup_interval": 10.0,
            "enable_logging": True,
            "enable_background_cleanup": True,
            "max_validation_attempts": 3,
            "corrupted_object_threshold": 1,
            "expected_concurrency": 3,
            "object_creation_cost": "low",
            "memory_pressure": "low",
            "enable_performance_metrics": True,
            "track_acquisition_times": True,
            "track_lock_contention": True,
            "performance_history_size": 100,
        },
    }

    @staticmethod
    def create_preset(preset: MemoryPreset) -> MemoryConfig:
        """
        Creates a `MemoryConfig` instance tailored for a specific use case defined
        by a `MemoryPreset`. Each preset provides a set of optimized default values
        for memory management parameters.

        Args:
            preset (MemoryPreset): The desired configuration preset.

        Returns:
            MemoryConfig: A `MemoryConfig` instance configured according to the specified preset.
        """
        config_params = MemoryConfigFactory._PRESET_CONFIGS.get(preset)

        if config_params is not None:
            return MemoryConfig(**config_params)

        # CUSTOM or default case
        return MemoryConfig()
