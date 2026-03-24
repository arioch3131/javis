# views/widgets/dialogs/__init__.py
"""
Application dialogs organized by functional domain.

This structure improves maintenance and dialog discovery
by grouping them by functionality.
"""

from .categorization.categorization_dialog import CategorizationDialog
from .categorization.categorization_progress_dialog import CategorizationProgressDialog

# Import des dialogs principaux
from .organization.auto_organize_dialog import AutoOrganizeDialog
from .scan.advanced_scan_dialog import AdvancedScanDialog
from .scan.basic_scan_type_dialog import BasicScanTypeDialog
from .scan.scan_progress_dialog import ScanProgressDialog

__all__ = [
    "AutoOrganizeDialog",
    "CategorizationDialog",
    "CategorizationProgressDialog",
    "AdvancedScanDialog",
    "BasicScanTypeDialog",
    "ScanProgressDialog",
]
