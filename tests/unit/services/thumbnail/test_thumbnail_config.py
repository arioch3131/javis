import pytest

from ai_content_classifier.core.memory.config import MemoryPreset
from ai_content_classifier.services.thumbnail.config import ThumbnailConfig


def test_default_values():
    """Tests that the default values are set correctly."""
    config = ThumbnailConfig()
    assert config.thumbnail_size == (128, 128)
    assert config.enable_caching is True
    assert config.max_cache_size == 200
    assert config.resampling_method == "LANCZOS"
    assert config.memory_preset == MemoryPreset.HIGH_THROUGHPUT


def test_copy_method():
    """Tests the copy method."""
    config1 = ThumbnailConfig()
    config2 = config1.copy(thumbnail_size=(256, 256), max_workers=8)

    assert config2 is not config1
    assert config2.thumbnail_size == (256, 256)
    assert config2.max_workers == 8
    assert config2.max_cache_size == config1.max_cache_size


@pytest.mark.parametrize(
    "invalid_params, error_message",
    [
        ({"thumbnail_size": (0, 128)}, "thumbnail_size dimensions must be positive"),
        ({"thumbnail_size": (128, -10)}, "thumbnail_size dimensions must be positive"),
        ({"thumbnail_size": (8000, 128)}, "thumbnail_size dimensions too large"),
        ({"thumbnail_size": [128, 128]}, "thumbnail_size must be a tuple"),
        ({"max_pool_size": 0}, "max_pool_size must be positive"),
        ({"max_cache_size": -1}, "max_cache_size must be positive"),
        ({"max_workers": 0}, "max_workers must be positive"),
        ({"quality_levels": (0.1, 1.1)}, "quality_levels must be between 0.0 and 1.0"),
        ({"quality_levels": (0.1, 0.5)}, "quality_levels must end with 1.0"),
        ({"large_image_threshold": 0}, "large_image_threshold must be positive"),
        ({"svg_size_threshold_low": 0}, "SVG thresholds must be positive"),
        ({"svg_size_threshold_high": -1}, "SVG thresholds must be positive"),
        (
            {"svg_size_threshold_low": 100, "svg_size_threshold_high": 50},
            "svg_size_threshold_low must be <= svg_size_threshold_high",
        ),
        ({"resampling_method": "INVALID"}, "resampling_method must be one of"),
        ({"max_retries": -1}, "max_retries must be non-negative"),
        ({"retry_delay": -0.1}, "retry_delay must be non-negative"),
    ],
)
def test_invalid_config_validation(invalid_params, error_message):
    """Tests that invalid configurations raise ValueErrors."""
    with pytest.raises(ValueError, match=error_message):
        ThumbnailConfig(**invalid_params)


def test_valid_config_does_not_raise():
    """Tests that a valid configuration does not raise an error."""
    try:
        ThumbnailConfig(
            thumbnail_size=(512, 512),
            max_workers=4,
            quality_levels=(0.2, 0.5, 1.0),
            resampling_method="BICUBIC",
        )
    except ValueError:
        pytest.fail("Valid ThumbnailConfig raised ValueError unexpectedly.")
