import logging

from sqlalchemy.orm import declarative_base

from ai_content_classifier.models.base import Base, logger as base_logger

class TestBase:
    def test_base_is_declarative_base(self):
        assert isinstance(Base, type(declarative_base()))

    def test_base_logger_initialized(self):
        assert isinstance(base_logger, logging.Logger)
        assert base_logger.name == "ai_content_classifier.models.base"
        # We can't reliably test the info/debug calls on module load with patching
        # as the module is loaded before the test runs. The above assertions are sufficient.