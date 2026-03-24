"""
A factory implementation for creating and managing PIL Image objects with pooling support.

This module provides the PILImageFactory class that implements the ObjectFactory
interface for PIL (Pillow) Image objects, enabling efficient memory management
through object pooling.
"""

from PIL import Image

from ai_content_classifier.core.memory.factories.factory_interface import ObjectFactory


class PILImageFactory(ObjectFactory[Image.Image]):
    """
    An implementation of `ObjectFactory` for creating and managing PIL (Pillow) Image objects.
    This factory is designed to pool image objects, which can be memory-intensive, thereby
    reducing the overhead of frequent image creation and destruction.
    """

    def __init__(self, enable_reset: bool = True):
        """
        Initializes the PILImageFactory.

        Args:
            enable_reset (bool): If True, the `reset` method will clear the image content.
                                 If False, the `reset` method will do nothing, which might
                                 be useful if the image content is always overwritten
                                 after acquisition. Defaults to True.
        """
        self.enable_reset = enable_reset

    def create(self, *args, **kwargs) -> Image.Image:
        """
        Creates a new PIL Image object with specified dimensions and mode.

        Args:
            *args: Variable length argument list. Expected:
                   - width (int): The width of the image in pixels.
                   - height (int): The height of the image in pixels.
                   - mode (str, optional): The image mode (e.g., "RGB", "RGBA", "L").
                     Defaults to "RGB".
            **kwargs: Arbitrary keyword arguments for additional parameters.

        Returns:
            Image.Image: A new PIL Image instance.
        """
        if len(args) >= 2:
            width, height = args[0], args[1]
            mode = args[2] if len(args) > 2 else kwargs.get("mode", "RGB")
        else:
            width = kwargs.get("width")
            height = kwargs.get("height")
            mode = kwargs.get("mode", "RGB")

        if width is None or height is None:
            raise ValueError("Width and height must be specified")

        return Image.new(mode, (width, height))

    def reset(self, obj: Image.Image) -> bool:
        """
        Resets the image content by filling it with a default color (black or transparent).
        This prepares the image for reuse.

        Args:
            obj (Image.Image): The PIL Image object to reset.

        Returns:
            bool: True if the reset was successful or if `enable_reset` is False,
                  False otherwise.
        """
        if not self.enable_reset:
            return True

        try:
            # Fill the image based on its mode
            if obj.mode == "RGB":
                obj.paste((0, 0, 0), [0, 0, obj.width, obj.height])  # Black
            elif obj.mode == "RGBA":
                obj.paste(
                    (0, 0, 0, 0), [0, 0, obj.width, obj.height]
                )  # Transparent black
            elif obj.mode == "L":
                obj.paste(0, [0, 0, obj.width, obj.height])  # Black (grayscale)
            return True
        except (AttributeError, ValueError, TypeError):
            # Log the exception if necessary
            return False

    def validate(self, obj: Image.Image) -> bool:  # pylint: disable=duplicate-code
        """
        Validates a PIL Image object to ensure it is a valid image instance, has positive
        dimensions, and is not closed.

        Args:
            obj (Image.Image): The PIL Image object to validate.

        Returns:
            bool: True if the image is valid and open, False otherwise.
        """
        try:  # pylint: disable=duplicate-code
            return (
                obj is not None
                and hasattr(obj, "width")
                and hasattr(obj, "height")
                and obj.width > 0
                and obj.height > 0
                and not getattr(
                    obj, "_closed", False
                )  # Check if the image is explicitly closed
            )
        except (AttributeError, TypeError):
            return False

    def get_key(self, *args, **kwargs) -> str:
        """
        Generates a unique key for PIL Image objects based on their dimensions and mode.
        This ensures that images with identical characteristics are grouped together
        for pooling.

        Args:
            *args: Variable length argument list. Expected:
                   - width (int): The width of the image.
                   - height (int): The height of the image.
                   - mode (str, optional): The mode of the image.
            **kwargs: Arbitrary keyword arguments for additional parameters.

        Returns:
            str: A string key representing the image's dimensions and mode.
        """
        if len(args) >= 2:
            width, height = args[0], args[1]
            mode = args[2] if len(args) > 2 else kwargs.get("mode", "RGB")
        else:
            width = kwargs.get("width")
            height = kwargs.get("height")
            mode = kwargs.get("mode", "RGB")

        if width is None or height is None:
            raise ValueError("Width and height must be specified")

        return f"{width}x{height}_{mode}"

    def destroy(self, obj: Image.Image) -> None:
        """
        Properly closes a PIL Image object to release its underlying resources.
        This method is called when an object is permanently removed from the pool.

        Args:
            obj (Image.Image): The PIL Image object to destroy.
        """
        try:
            obj.close()
        except (AttributeError, OSError):
            # Catch specific exceptions during close to prevent crashes
            pass

    def estimate_size(self, obj: Image.Image) -> int:
        """
        Estimates the memory size of the PIL Image object in bytes.
        This is an approximation based on image dimensions and mode.

        Args:
            obj (Image.Image): The PIL Image object for which to estimate the size.

        Returns:
            int: The estimated size of the image in bytes.
        """
        # Approximation: width * height * bytes_per_pixel
        # This mapping provides a rough estimate for common modes.
        bytes_per_pixel = {
            "1": 1
            / 8,  # 1-bit pixels, black and white, stored with 1 byte per 8 pixels
            "L": 1,  # 8-bit pixels, grayscale
            "P": 1,  # 8-bit pixels, mapped to any other mode using a color palette
            "RGB": 3,  # 3x8-bit pixels, true color
            "RGBA": 4,  # 4x8-bit pixels, true color with transparency mask
            "CMYK": 4,  # 4x8-bit pixels, color separation
            "YCbCr": 3,  # 3x8-bit pixels, color video format
            "LAB": 3,  # 3x8-bit pixels, L*a*b color space
            "HSV": 3,  # 3x8-bit pixels, Hue, Saturation, Value color space
            "I": 4,  # 32-bit signed integer pixels
            "F": 4,  # 32-bit floating point pixels
        }.get(obj.mode, 4)  # Default to 4 bytes per pixel if mode is unknown

        return int(obj.width * obj.height * bytes_per_pixel)
