"""
Base widgets with integrated theme support.

Ces widgets servent de fondation pour tous les composants
custom application widgets.
"""

from .action_bar import ActionBar
from .header_section import HeaderSection
from .themed_dialog import ThemedDialog
from .themed_widget import ThemedWidget

__all__ = ["ThemedWidget", "ThemedDialog", "HeaderSection", "ActionBar"]
