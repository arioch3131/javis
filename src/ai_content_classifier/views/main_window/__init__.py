"""
Builders et coordinateurs pour MainWindow.

These modules split MainWindow construction into components
modulaires et maintenables.
"""

from .main import MainWindow
from .menu_builder import MenuBuilder
from .ui_builder import UIBuilder

__all__ = ["UIBuilder", "MenuBuilder", "MainWindow"]
