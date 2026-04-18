"""Built-in filtering plugins."""

from ai_content_classifier.services.filtering.plugins.category_filter import (
    CategoryFilterPlugin,
)
from ai_content_classifier.services.filtering.plugins.extension_filter import (
    ExtensionFilterPlugin,
)
from ai_content_classifier.services.filtering.plugins.file_type_filter import (
    FileTypeFilterPlugin,
)
from ai_content_classifier.services.filtering.plugins.year_filter import (
    YearFilterPlugin,
)

__all__ = [
    "CategoryFilterPlugin",
    "ExtensionFilterPlugin",
    "FileTypeFilterPlugin",
    "YearFilterPlugin",
]
