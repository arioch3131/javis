
import unittest
import sys

from ai_content_classifier.core.memory.factories.factory_interface import ObjectFactory

# A concrete implementation for testing purposes
class ConcreteFactory(ObjectFactory):
    def create(self, *args, **kwargs): return "created"
    def reset(self, obj): return True
    def validate(self, obj): return True
    def get_key(self, *args, **kwargs): return "key"
    # We don't implement destroy or estimate_size to test the defaults

class IncompleteFactory(ObjectFactory):
    # Missing the 'create' method
    def reset(self, obj): return True
    def validate(self, obj): return True
    def get_key(self, *args, **kwargs): return "key"

class TestObjectFactoryInterface(unittest.TestCase):

    def test_abstract_methods_must_be_implemented(self):
        """Test that instantiating a factory without all abstract methods fails."""
        with self.assertRaises(TypeError):
            IncompleteFactory()

    def test_concrete_factory_instantiation(self):
        """Test that a correctly implemented factory can be instantiated."""
        try:
            factory = ConcreteFactory()
            self.assertIsInstance(factory, ObjectFactory)
        except TypeError:
            self.fail("ConcreteFactory should instantiate without a TypeError.")

    def test_default_destroy_method(self):
        """Test that the default destroy() method exists and does nothing."""
        factory = ConcreteFactory()
        try:
            factory.destroy("some_object")
            # No exception should be raised
        except Exception as e:
            self.fail(f"Default destroy() method raised an exception: {e}")

    def test_default_estimate_size_method(self):
        """Test the default estimate_size() method uses sys.getsizeof."""
        factory = ConcreteFactory()
        test_string = "hello world"
        
        # The default implementation should be equivalent to sys.getsizeof
        expected_size = sys.getsizeof(test_string)
        self.assertEqual(factory.estimate_size(test_string), expected_size)

if __name__ == '__main__':
    unittest.main(verbosity=2)
