"""
Factory implementation for creating and managing NumpyArray buffer objects.

This module provides a NumpyArrayFactory class that implements the ObjectFactory
interface for pooling in-memory binary data buffers, reducing allocation overhead.
"""

import numpy as np

from ai_content_classifier.core.memory.factories.factory_interface import ObjectFactory


class NumpyArrayFactory(ObjectFactory[np.ndarray]):
    """
    An implementation of `ObjectFactory` for creating and managing NumPy array objects.
    This factory is particularly useful for applications that frequently allocate and
    deallocate numerical arrays of specific shapes and data types, such as machine learning
    or scientific computing.
    """

    def create(self, *args, **kwargs) -> np.ndarray:
        """
        Creates a new NumPy array initialized with zeros.

        Args:
            shape (tuple): The dimensions of the array (e.g., (10, 20) for a 2D array).
                          Should be passed as first positional argument or 'shape' keyword.
            dtype (str): The data type of the array elements (e.g., 'float32', 'int64').
                         Defaults to 'float32'. Can be passed as second positional argument
                         or 'dtype' keyword.

        Returns:
            np.ndarray: A new NumPy array instance.
        """
        # Extract shape and dtype from args/kwargs
        if args:
            shape = args[0]
            dtype = args[1] if len(args) > 1 else kwargs.get("dtype", "float32")
        else:
            shape = kwargs.get("shape")
            dtype = kwargs.get("dtype", "float32")

        if shape is None:
            raise ValueError("Shape must be provided")

        return np.zeros(shape, dtype=dtype)

    def reset(self, obj: np.ndarray) -> bool:
        """
        Resets the NumPy array by filling all its elements with zeros.
        This prepares the array for reuse without reallocating memory.

        Args:
            obj (np.ndarray): The NumPy array to reset.

        Returns:
            bool: True if the array was successfully reset, False otherwise.
        """
        try:
            obj.fill(0)
            return True
        except (AttributeError, ValueError, TypeError):
            # Log the exception if necessary
            # More specific exceptions that could occur during fill operation
            return False

    def validate(self, obj: np.ndarray) -> bool:
        """
        Validates a NumPy array to ensure it is a valid `np.ndarray` instance,
        is not a view of another array, and is writeable.

        Args:
            obj (np.ndarray): The NumPy array to validate.

        Returns:
            bool: True if the array is valid and ready for reuse, False otherwise.
        """
        try:  # pylint: disable=duplicate-code
            return (
                isinstance(obj, np.ndarray)
                and obj.base is None  # Ensure it's not a view of another array
                and obj.flags["WRITEABLE"]  # Ensure it's writeable
            )
        except (AttributeError, KeyError, TypeError):
            # More specific exceptions for attribute access and flag checking
            return False

    def get_key(self, *args, **kwargs) -> str:
        """
        Generates a unique key for NumPy arrays based on their shape and data type.
        This ensures that arrays with identical structures are grouped together for pooling.

        Args:
            shape (tuple): The shape of the array. Can be passed as first positional
                          argument or 'shape' keyword.
            dtype (str): The data type of the array. Can be passed as second positional
                        argument or 'dtype' keyword.

        Returns:
            str: A string key representing the array's shape and data type.
        """
        # Extract shape and dtype from args/kwargs
        if args:
            shape = args[0]
            dtype = args[1] if len(args) > 1 else kwargs.get("dtype", "float32")
        else:
            shape = kwargs.get("shape")
            dtype = kwargs.get("dtype", "float32")

        if shape is None:
            raise ValueError("Shape must be provided")

        return f"numpy_{shape}_{dtype}"

    def estimate_size(self, obj: np.ndarray) -> int:
        """
        Returns the exact memory size of the NumPy array in bytes.
        NumPy arrays provide `nbytes` attribute for precise memory usage.

        Args:
            obj (np.ndarray): The NumPy array for which to estimate the size.

        Returns:
            int: The exact size of the array in bytes.
        """
        return obj.nbytes
