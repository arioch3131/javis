"""
Builders and coordinators for MainWindow.

These modules split MainWindow construction into components
that are modular and maintainable.
"""

from .main import MainWindow
from .menu_builder import MenuBuilder
from .ui_builder import UIBuilder

__all__ = ["UIBuilder", "MenuBuilder", "MainWindow"]
