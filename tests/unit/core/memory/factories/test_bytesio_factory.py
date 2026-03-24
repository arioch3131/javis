
import unittest
from io import BytesIO

from ai_content_classifier.core.memory.factories.bytesio_factory import BytesIOFactory

class TestBytesIOFactory(unittest.TestCase):

    def setUp(self):
        self.factory = BytesIOFactory()

    def test_create(self):
        """Test creating a BytesIO object."""
        buffer = self.factory.create()
        self.assertIsInstance(buffer, BytesIO)
        self.assertTrue(buffer.writable())
        self.assertTrue(buffer.readable())
        self.assertTrue(buffer.seekable())

    def test_create_with_initial_size(self):
        """Test creating a BytesIO object with a pre-allocated size."""
        size = 1024
        buffer = self.factory.create(initial_size=size)
        self.assertEqual(buffer.getvalue(), b'\0' * size)
        self.assertEqual(buffer.tell(), 0)

    def test_validate(self):
        """Test the validation of a BytesIO object."""
        buffer = self.factory.create()
        self.assertTrue(self.factory.validate(buffer))
        
        buffer.close()
        self.assertFalse(self.factory.validate(buffer))

    def test_reset(self):
        """Test that the buffer is correctly reset."""
        buffer = self.factory.create()
        buffer.write(b"some test data")
        self.assertGreater(buffer.tell(), 0)

        self.assertTrue(self.factory.reset(buffer))
        self.assertEqual(buffer.tell(), 0)
        self.assertEqual(buffer.getvalue(), b'')

    def test_get_key(self):
        """Test the key generation logic."""
        self.assertEqual(self.factory.get_key(initial_size=0), "bytesio_0")
        self.assertEqual(self.factory.get_key(initial_size=500), "bytesio_0")
        self.assertEqual(self.factory.get_key(initial_size=1024), "bytesio_1024")
        self.assertEqual(self.factory.get_key(initial_size=1500), "bytesio_1024")

    def test_destroy(self):
        """Test that the destroy method closes the buffer."""
        buffer = self.factory.create()
        self.assertFalse(buffer.closed)
        self.factory.destroy(buffer)
        self.assertTrue(buffer.closed)

    def test_estimate_size(self):
        """Test the size estimation of the buffer."""
        buffer = self.factory.create()
        buffer.write(b"12345")
        self.assertEqual(self.factory.estimate_size(buffer), 5)
        
        buffer.write(b"67890")
        self.assertEqual(self.factory.estimate_size(buffer), 10)

        # Check that it returns to original position
        buffer.seek(3)
        self.assertEqual(self.factory.estimate_size(buffer), 10)
        self.assertEqual(buffer.tell(), 3)

    def test_reset_exception(self):
        """Test that reset() handles exceptions gracefully."""
        mock_buffer = unittest.mock.Mock()
        mock_buffer.seek.side_effect = IOError("Seek failed")
        self.assertFalse(self.factory.reset(mock_buffer))

    def test_destroy_exception(self):
        """Test that destroy() handles exceptions gracefully."""
        mock_buffer = unittest.mock.Mock()
        mock_buffer.close.side_effect = IOError("Close failed")
        try:
            self.factory.destroy(mock_buffer)
        except Exception as e:
            self.fail(f"destroy() should not raise exceptions, but raised {e}")

    def test_estimate_size_exception(self):
        """Test that estimate_size() handles exceptions gracefully."""
        mock_buffer = unittest.mock.Mock()
        mock_buffer.tell.side_effect = IOError("Tell failed")
        self.assertEqual(self.factory.estimate_size(mock_buffer), 0)

if __name__ == '__main__':
    unittest.main(verbosity=2)
