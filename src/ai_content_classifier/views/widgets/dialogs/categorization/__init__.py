# views/widgets/dialogs/categorization/__init__.py
"""
Dialogs de categorization de files.

Contains all dialogs related to automatic categorization
et manuelle des files.
"""

from .categorization_dialog import CategorizationDialog
from .categorization_progress_dialog import CategorizationProgressDialog

__all__ = ["CategorizationDialog", "CategorizationProgressDialog"]
