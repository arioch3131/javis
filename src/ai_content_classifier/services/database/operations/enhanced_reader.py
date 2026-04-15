# operations/enhanced_reader.py
"""
Compatibility shim for the merged reader implementation.
"""

from ai_content_classifier.services.database.content_reader import ContentReader


class EnhancedContentReader(ContentReader):
    """
    Transitional compatibility alias.
    The read logic now lives in ``ContentReader`` with explicit API methods.
    """

    def __init__(self, database_service, query_optimizer, metrics):
        super().__init__(
            database_service=database_service,
            query_optimizer=query_optimizer,
            metrics=metrics,
        )
