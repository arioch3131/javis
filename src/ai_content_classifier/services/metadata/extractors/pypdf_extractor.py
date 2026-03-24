import importlib
import os
from pathlib import Path
from typing import Any, Dict

from ai_content_classifier.services.metadata.extractors.base_extractor import (
    BaseMetadataExtractor,
)


class PyPDFExtractor(BaseMetadataExtractor):
    """Metadata extractor specifically for PDF files using pypdf."""

    def __init__(self):
        super().__init__()
        self.pypdf_available = self._check_dependency("pypdf")
        if not self.pypdf_available:
            self.logger.warning(
                "pypdf library not available. PDF metadata extraction will be limited."
            )

    def _check_dependency(self, module_name: str) -> bool:
        """
        Check if a Python module is available.

        Args:
            module_name: Name of the module to check

        Returns:
            True if the module is available, False otherwise
        """
        try:
            importlib.import_module(module_name)
            return True
        except ImportError:
            return False

    def can_handle(self, file_path: str) -> bool:
        """
        Checks if the extractor can handle the given file.

        Args:
            file_path: Path to the file

        Returns:
            True if the file is a PDF and pypdf is available, False otherwise
        """
        if not self.pypdf_available:
            return False

        ext = Path(file_path).suffix.lower()
        return (
            ext == ".pdf"
            and os.path.isfile(file_path)
            and os.access(file_path, os.R_OK)
        )

    def get_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Extracts metadata from the PDF file using pypdf.

        Args:
            file_path: Path to the PDF file

        Returns:
            Dictionary of extracted metadata
        """
        metadata = self.get_basic_metadata(file_path)

        if not self.pypdf_available:
            metadata["error"] = "pypdf library is not installed"
            return metadata

        try:
            import pypdf

            pdf_info = {}

            with open(file_path, "rb") as f:
                pdf = pypdf.PdfReader(f)

                pdf_info["page_count"] = len(pdf.pages)

                try:
                    first_page_text = pdf.pages[0].extract_text()
                    if first_page_text:
                        pdf_info["first_page_preview"] = first_page_text[:1000]
                except Exception as e:
                    self.logger.debug(f"Could not extract text from PDF: {str(e)}")

                if pdf.metadata:
                    doc_info = {}
                    for key, value in pdf.metadata.items():
                        if value and isinstance(value, (str, int, float, bool)):
                            clean_key = key.replace("/", "")
                            doc_info[clean_key] = value

                    if doc_info:
                        pdf_info["document_info"] = doc_info

                metadata["pdf_info"] = pdf_info

        except Exception as e:
            self.logger.error(f"Error extracting PDF metadata with pypdf: {str(e)}")
            metadata["error"] = f"Error extracting PDF metadata with pypdf: {str(e)}"

        return metadata
