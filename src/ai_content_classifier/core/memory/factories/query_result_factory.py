"""
Factory implementation for creating and managing query result objects.

This module provides a concrete implementation of the ObjectFactory interface
specifically designed for handling lists of dictionaries that represent
database query results.
"""

import sys
from typing import Any, Dict, List

from ai_content_classifier.core.memory.factories.factory_interface import ObjectFactory


class QueryResultFactory(ObjectFactory[List[Dict[str, Any]]]):
    """
    An implementation of `ObjectFactory` for creating and managing lists of dictionaries,
    typically representing query results from a database.
    """

    def create(self, *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
        """
        Creates a new empty list to hold query results.

        Args:
            *args: Variable length argument list
                    (unused but maintained for interface compatibility).
            **kwargs: Arbitrary keyword arguments
                    (unused but maintained for interface compatibility).

        Returns:
            List[Dict[str, Any]]: A new empty list.
        """
        return []

    def reset(self, obj: List[Dict[str, Any]]) -> bool:
        """
        Resets a list of query results by clearing its content.

        Args:
            obj (List[Dict[str, Any]]): The list to reset.

        Returns:
            bool: True if the list was successfully reset, False otherwise.
        """
        try:
            obj.clear()
            return True
        except (AttributeError, TypeError):
            # AttributeError: obj doesn't have clear method
            # TypeError: obj is not mutable
            return False

    def validate(self, obj: List[Dict[str, Any]]) -> bool:
        """
        Validates a list of query results to ensure it is a list.

        Args:
            obj (List[Dict[str, Any]]): The list to validate.

        Returns:
            bool: True if the object is a list, False otherwise.
        """
        return isinstance(obj, list)

    def get_key(self, *args: Any, **kwargs: Any) -> str:
        """
        Generates a unique key for query result objects. Since all query results
        are essentially lists of dictionaries, a single key is sufficient for pooling.

        Args:
            *args: Variable length argument list
                    (unused but maintained for interface compatibility).
            **kwargs: Arbitrary keyword arguments
                (unused but maintained for interface compatibility).

        Returns:
            str: A fixed string key "query_result_list".
        """
        return "query_result_list"

    def estimate_size(self, obj: List[Dict[str, Any]]) -> int:
        """
        Estimates the memory size of the list of query results.
        This is a rough estimate based on the number of items and a typical item size.

        Args:
            obj (List[Dict[str, Any]]): The list of query results.

        Returns:
            int: The estimated size in bytes.
        """
        # Estimate size based on list overhead + average item size
        list_overhead = sys.getsizeof([])
        if not obj:
            return list_overhead

        # Rough estimate for an average dictionary item (e.g., 100 bytes per dict)
        avg_item_size = 100
        return list_overhead + len(obj) * avg_item_size
