"""Module defining the interface for object factories used by the memory pool.

This module provides the `ObjectFactory` abstract base class, which defines the
contract for creating, resetting, validating, and destroying objects managed by
the `GenericMemoryPool`. It also includes the `ObjectState` Enum to represent
the lifecycle state of pooled objects.
"""

import sys
from abc import ABC, abstractmethod
from enum import Enum
from typing import Generic, TypeVar

T = TypeVar("T")


class ObjectState(Enum):
    """Represents the current state of an object within the memory pool.

    Attributes:
        VALID (str): The object is valid and ready for reuse.
        CORRUPTED (str): The object is corrupted and should not be reused.
        EXPIRED (str): The object has exceeded its time-to-live and is no longer valid.
        IN_USE (str): The object is currently acquired from the pool and in use.
    """

    VALID = "valid"
    CORRUPTED = "corrupted"
    EXPIRED = "expired"
    IN_USE = "in_use"


class ObjectFactory(ABC, Generic[T]):
    """
    Abstract base class defining the interface for object factories used by the `GenericMemoryPool`.
    A factory is responsible for creating, resetting, validating, and destroying objects that
    the pool manages. This allows the pool to be generic and work with any type of object.

    Type parameter:
        T: The type of objects that this factory will create and manage.
    """

    @abstractmethod
    def create(self, *args, **kwargs) -> T:
        """
        Creates a new instance of the object.

        Args:
            *args: Positional arguments to pass to the object's constructor.
            **kwargs: Keyword arguments to pass to the object's constructor.

        Returns:
            T: A newly created object instance.
        """
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def reset(self, obj: T) -> bool:
        """
        Resets an object to its initial state before it is returned to the pool.
        This method should clean up any transient state or data from the object's
        previous use, making it ready for reuse.

        Args:
            obj (T): The object instance to reset.

        Returns:
            bool: True if the object was successfully reset, False otherwise.
                  If False is returned, the object will be destroyed and not
                  returned to the pool.
        """
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def validate(self, obj: T) -> bool:
        """
        Validates an object to ensure it is still in a usable state.
        This method is called before an object is acquired from the pool or
        returned to it. It should perform checks to ensure the object is not
        corrupted, disconnectd, or otherwise invalid.

        Args:
            obj (T): The object instance to validate.

        Returns:
            bool: True if the object is valid and can be reused, False otherwise.
                  If False is returned, the object will be destroyed.
        """
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def get_key(self, *args, **kwargs) -> str:
        """
        Generates a unique string key for an object based on the parameters
        used to create it. This key is used by the pool to group similar objects
        together, allowing for efficient reuse. For example, a factory for
        database connections might generate keys based on connection strings.

        Args:
            *args: Positional arguments that would be passed to the `create` method.
            **kwargs: Keyword arguments that would be passed to the `create` method.

        Returns:
            str: A unique string key representing the type or configuration of
             the object.
        """
        raise NotImplementedError  # pragma: no cover

    def destroy(self, obj: T) -> None:
        """
        Cleans up an object's resources before it is permanently removed from the pool
        and destroyed.
        This method should release any external resources held by the object
        (e.g., close file handles,
        database connections, network sockets).
        This method is optional to implement; if an object does not hold external resources,
        the default implementation (which does nothing) is sufficient.

        Args:
            obj (T): The object instance to destroy.
        """

    def estimate_size(self, obj: T) -> int:
        """
        Estimates the memory size of the object in bytes.
        This method is used by the pool for memory management and reporting.
        Subclasses should override this method to provide a more accurate estimation
        if `sys.getsizeof()` is not sufficient.

        Args:
            obj (T): The object instance for which to estimate the size.

        Returns:
            int: The estimated size of the object in bytes.
        """
        return sys.getsizeof(obj)
