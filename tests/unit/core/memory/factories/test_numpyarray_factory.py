import unittest
import numpy as np
from unittest.mock import Mock, PropertyMock

from ai_content_classifier.core.memory.factories.numpyarray_factory import (
    NumpyArrayFactory,
)


class TestNumpyArrayFactory(unittest.TestCase):
    def setUp(self):
        self.factory = NumpyArrayFactory()

    def test_create(self):
        """Test creating a numpy array."""
        shape = (10, 20)
        dtype = "uint8"
        array = self.factory.create(shape=shape, dtype=dtype)

        self.assertIsInstance(array, np.ndarray)
        self.assertEqual(array.shape, shape)
        self.assertEqual(array.dtype, np.dtype(dtype))
        self.assertTrue(np.all(array == 0))  # Should be initialized to zeros

    def test_create_with_positional_args(self):
        """Test creating an array with positional shape/dtype arguments."""
        array = self.factory.create((2, 3), "int16")
        self.assertEqual(array.shape, (2, 3))
        self.assertEqual(array.dtype, np.dtype("int16"))

    def test_create_without_shape_raises(self):
        """Test create() raises when shape is not provided."""
        with self.assertRaises(ValueError):
            self.factory.create()

    def test_validate(self):
        """Test the validation of a numpy array."""
        array = self.factory.create(shape=(5, 5))
        self.assertTrue(self.factory.validate(array))

        # Test with a non-writeable array
        array.flags.writeable = False
        self.assertFalse(self.factory.validate(array))
        array.flags.writeable = True  # Reset for other tests

        # Test with a view of an array
        view = array[1:3, 1:3]
        self.assertFalse(self.factory.validate(view))

    def test_reset(self):
        """Test that the array is correctly reset to all zeros."""
        array = self.factory.create(shape=(3, 3))
        array.fill(42)  # Fill with a non-zero value
        self.assertFalse(np.all(array == 0))

        self.assertTrue(self.factory.reset(array))
        self.assertTrue(np.all(array == 0))

    def test_get_key(self):
        """Test the key generation logic."""
        shape1 = (10, 10)
        dtype1 = "float32"
        key1 = self.factory.get_key(shape=shape1, dtype=dtype1)
        self.assertEqual(key1, "numpy_(10, 10)_float32")

        shape2 = (20, 30)
        dtype2 = "int64"
        key2 = self.factory.get_key(shape=shape2, dtype=dtype2)
        self.assertEqual(key2, "numpy_(20, 30)_int64")

    def test_get_key_with_positional_args(self):
        """Test key generation with positional args."""
        key = self.factory.get_key((4, 5), "uint8")
        self.assertEqual(key, "numpy_(4, 5)_uint8")

    def test_get_key_without_shape_raises(self):
        """Test get_key() raises when shape is not provided."""
        with self.assertRaises(ValueError):
            self.factory.get_key()

    def test_estimate_size(self):
        """Test the size estimation of the array."""
        shape = (10, 10)
        dtype = "float64"  # 8 bytes
        array = self.factory.create(shape=shape, dtype=dtype)

        expected_size = 10 * 10 * 8
        self.assertEqual(self.factory.estimate_size(array), expected_size)
        self.assertEqual(array.nbytes, expected_size)

    def test_reset_exception(self):
        """Test that reset() handles exceptions gracefully."""
        mock_array = unittest.mock.Mock()
        mock_array.fill.side_effect = AttributeError("Fill failed")
        self.assertFalse(self.factory.reset(mock_array))

    def test_validate_exception(self):
        """Test that validate() handles exceptions gracefully."""
        mock_array = Mock(spec=np.ndarray)  # Mock a numpy array
        type(mock_array).base = PropertyMock(
            side_effect=AttributeError("Base access failed")
        )
        self.assertFalse(self.factory.validate(mock_array))


if __name__ == "__main__":
    unittest.main(verbosity=2)
