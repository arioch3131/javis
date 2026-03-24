"""
Factory implementation for creating and managing BytesIO buffer objects.

This module provides a BytesIOFactory class that implements the ObjectFactory
interface for pooling in-memory binary data buffers, reducing allocation overhead.
"""

from io import BytesIO
from typing import Any

from ai_content_classifier.core.memory.factories.factory_interface import ObjectFactory


class BytesIOFactory(ObjectFactory[BytesIO]):
    """
    An implementation of `ObjectFactory` for creating and managing `io.BytesIO` buffer objects.
    This factory is useful for pooling in-memory binary data buffers, reducing the overhead
    of repeatedly allocating and deallocating `BytesIO` objects.
    """

    def create(self, *args: Any, **kwargs: Any) -> BytesIO:
        """
        Creates a new `BytesIO` object, optionally pre-sized with null bytes.

        Args:
            *args: Variable positional arguments. First argument is treated
                    as initial_size if provided.
            **kwargs: Variable keyword arguments. 'initial_size' key is used if provided.

        Returns:
            BytesIO: A new `BytesIO` instance.
        """
        # Extract initial_size from args or kwargs
        initial_size = 0
        if args:
            initial_size = args[0] if isinstance(args[0], int) else 0
        elif "initial_size" in kwargs:
            initial_size = kwargs.get("initial_size", 0)

        buffer = BytesIO()
        if initial_size > 0:
            buffer.write(b"\0" * initial_size)
            buffer.seek(0)  # Reset cursor to the beginning
        return buffer

    def reset(self, obj: BytesIO) -> bool:
        """
        Resets a `BytesIO` object by moving its cursor to the beginning and truncating its content.
        This prepares the buffer for reuse without reallocating memory.

        Args:
            obj (BytesIO): The `BytesIO` object to reset.

        Returns:
            bool: True if the reset was successful, False otherwise.
        """
        try:
            obj.seek(0)
            obj.truncate(0)
            return True
        except IOError as exc:
            # Catch all exceptions to ensure graceful handling
            _ = exc  # Acknowledge the exception variable
            return False

    def validate(self, obj: BytesIO) -> bool:
        """
        Validates a `BytesIO` object to ensure it is a valid `BytesIO` instance and is not closed.

        Args:
            obj (BytesIO): The `BytesIO` object to validate.

        Returns:
            bool: True if the object is a valid and open `BytesIO` instance, False otherwise.
        """
        return isinstance(obj, BytesIO) and not obj.closed

    def get_key(self, *args: Any, **kwargs: Any) -> str:
        """
        Generates a unique key for `BytesIO` objects based on their approximate size.
        This groups buffers of similar sizes together for more efficient reuse.

        Args:
            *args: Variable positional arguments. First argument is treated
                    as initial_size if provided.
            **kwargs: Variable keyword arguments. 'initial_size' key is used if provided.

        Returns:
            str: A string key representing the size bucket of the `BytesIO` object.
        """
        # Extract initial_size from args or kwargs
        initial_size = 0
        if args:
            initial_size = args[0] if isinstance(args[0], int) else 0
        elif "initial_size" in kwargs:
            initial_size = kwargs.get("initial_size", 0)

        # Group by size chunks for reuse (e.g., round to nearest KB)
        size_bucket = (initial_size // 1024) * 1024
        return f"bytesio_{size_bucket}"

    def destroy(self, obj: BytesIO) -> None:
        """
        Properly closes a `BytesIO` object to release its underlying resources.
        This method is called when an object is permanently removed from the pool.

        Args:
            obj (BytesIO): The `BytesIO` object to destroy.
        """
        try:
            obj.close()
        except IOError as exc:
            # Catch all exceptions during close to ensure graceful handling
            _ = exc  # Acknowledge the exception variable

    def estimate_size(self, obj: BytesIO) -> int:
        """
        Estimates the current memory size of the `BytesIO` buffer in bytes.
        This is done by temporarily moving the cursor to the end to get the buffer's size.

        Args:
            obj (BytesIO): The `BytesIO` object for which to estimate the size.

        Returns:
            int: The estimated size of the buffer in bytes, or 0 if an error occurs.
        """
        try:
            current_pos = obj.tell()
            obj.seek(0, 2)  # Move to the end of the buffer
            size = obj.tell()  # Get the current position, which is the size
            obj.seek(current_pos)  # Return cursor to original position
            return size
        except IOError as exc:
            # Catch all exceptions to ensure graceful handling
            _ = exc  # Acknowledge the exception variable
            return 0
