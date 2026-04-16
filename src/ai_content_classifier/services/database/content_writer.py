"""Write operations for content database with a unified mutation contract."""

import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from ai_content_classifier.core.logger import LoggableMixin
from ai_content_classifier.models.content_models import (
    Audio,
    ContentItem,
    Document,
    Image,
    Video,
    datetime_utcnow,
)
from ai_content_classifier.repositories.content_repository import (
    ContentRepositoryFactory,
)
from ai_content_classifier.services.database import utils
from ai_content_classifier.services.database.database_service import DatabaseService
from ai_content_classifier.services.database.types import DatabaseOperationResult
from ai_content_classifier.services.database.write_operations import (
    ClearAllContentOperation,
    ClearContentCategoryOperation,
    CreateContentItemOperation,
    DeleteContentByPathsOperation,
    SaveItemBatchOperation,
    UpdateContentCategoryOperation,
    UpdateMetadataBatchOperation,
)


class ContentWriter(LoggableMixin):
    """Handles all write database operations for content items."""

    def __init__(
        self, database_service: DatabaseService, repos: ContentRepositoryFactory
    ):
        self.__init_logger__()
        self.database_service = database_service
        self.repos = repos

        self._create_content_item_operation = CreateContentItemOperation()
        self._save_item_batch_operation = SaveItemBatchOperation()
        self._update_metadata_batch_operation = UpdateMetadataBatchOperation()
        self._update_content_category_operation = UpdateContentCategoryOperation()
        self._clear_content_category_operation = ClearContentCategoryOperation()
        self._clear_all_content_operation = ClearAllContentOperation()
        self._delete_content_by_paths_operation = DeleteContentByPathsOperation()

    def create_content_item(
        self,
        path: str,
        content_type: str,
        extract_basic_info: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
        refresh: bool = True,
        session: Optional[Session] = None,
    ) -> DatabaseOperationResult:
        return self._create_content_item_operation.execute(
            self,
            path=path,
            content_type=content_type,
            extract_basic_info=extract_basic_info,
            metadata=metadata,
            refresh=refresh,
            session=session,
        )

    def save_item_batch(
        self,
        items: List[Dict[str, Any]],
        refresh: bool = True,
        session: Optional[Session] = None,
    ) -> DatabaseOperationResult:
        return self._save_item_batch_operation.execute(
            self,
            items=items,
            refresh=refresh,
            session=session,
        )

    def update_metadata_batch(
        self,
        metadata_updates: List[Tuple[int, Dict[str, Any]]],
        refresh: bool = False,
        session: Optional[Session] = None,
    ) -> DatabaseOperationResult:
        return self._update_metadata_batch_operation.execute(
            self,
            metadata_updates=metadata_updates,
            refresh=refresh,
            session=session,
        )

    def update_content_category(
        self,
        file_path: str,
        category: str,
        confidence: float,
        extraction_method: str,
        extraction_details: str,
        session: Optional[Session] = None,
    ) -> DatabaseOperationResult:
        return self._update_content_category_operation.execute(
            self,
            file_path=file_path,
            category=category,
            confidence=confidence,
            extraction_method=extraction_method,
            extraction_details=extraction_details,
            session=session,
        )

    def clear_content_category(
        self, file_path: str, session: Optional[Session] = None
    ) -> DatabaseOperationResult:
        return self._clear_content_category_operation.execute(
            self,
            file_path=file_path,
            session=session,
        )

    def clear_all_content(
        self, session: Optional[Session] = None
    ) -> DatabaseOperationResult:
        return self._clear_all_content_operation.execute(self, session=session)

    def delete_content_by_paths(
        self, file_paths: List[str], session: Optional[Session] = None
    ) -> DatabaseOperationResult:
        return self._delete_content_by_paths_operation.execute(
            self,
            file_paths=file_paths,
            session=session,
        )

    def _validate_content_creation_params(self, path: str, content_type: str) -> None:
        if not path:
            raise ValueError("File path cannot be empty.")
        if not content_type:
            raise ValueError("Content type cannot be empty.")

    def _extract_file_info(self, path: str, extract_basic_info: bool) -> Dict[str, Any]:
        file_info = {
            "filename": os.path.basename(path),
            "directory": os.path.dirname(path),
            "file_size": None,
        }

        if extract_basic_info and os.path.exists(path):
            try:
                file_info["file_size"] = os.path.getsize(path)
            except OSError as e:
                self.logger.warning(f"Could not get file size for {path}: {e}")
        return file_info

    def _create_typed_content_item(
        self,
        path: str,
        content_type: str,
        file_info: Dict[str, Any],
        file_hash: Optional[str],
        metadata: Optional[Dict[str, Any]],
    ) -> ContentItem:
        serialized_metadata = utils.serialize_metadata_for_json(metadata)

        common_args = {
            "path": path,
            "filename": file_info["filename"],
            "directory": file_info["directory"],
            "file_size": file_info["file_size"],
            "file_hash": file_hash,
            "content_type": content_type,
            "content_metadata": serialized_metadata,
            "metadata_extracted": metadata is not None,
            "year_taken": self._resolve_year_taken(path, metadata),
        }

        type_mapping = {
            "image": Image,
            "document": Document,
            "video": Video,
            "audio": Audio,
        }

        item_class = type_mapping.get(content_type, ContentItem)
        return item_class(**common_args)

    def _is_valid_item_data(self, item_data: Dict[str, Any]) -> bool:
        return (
            isinstance(item_data, dict)
            and "path" in item_data
            and bool(item_data["path"])
            and "content_type" in item_data
        )

    def _create_content_item_from_data(
        self, item_data: Dict[str, Any]
    ) -> Optional[ContentItem]:
        try:
            path = item_data["path"]
            content_type = item_data.get("content_type", "content_item")

            filename = item_data.get("filename", os.path.basename(path))
            directory = item_data.get("directory", os.path.dirname(path))
            file_size = item_data.get("file_size")
            metadata = item_data.get("metadata")

            serialized_metadata = utils.serialize_metadata_for_json(metadata)

            common_args = {
                "path": path,
                "filename": filename,
                "directory": directory,
                "file_size": file_size,
                "file_hash": item_data.get("file_hash")
                or self._compute_hash_if_exists(path),
                "content_type": content_type,
                "content_metadata": serialized_metadata,
                "metadata_extracted": metadata is not None,
                "year_taken": item_data.get("year_taken")
                or self._resolve_year_taken(path, metadata),
            }

            if content_type == "image":
                return Image(
                    **common_args,
                    width=item_data.get("width"),
                    height=item_data.get("height"),
                    format=item_data.get("format"),
                )
            if content_type == "document":
                return Document(
                    **common_args,
                    language=item_data.get("language"),
                    page_count=item_data.get("page_count"),
                    text_content=item_data.get("text_content"),
                )
            if content_type == "video":
                return Video(
                    **common_args,
                    duration=item_data.get("duration"),
                    width=item_data.get("width"),
                    height=item_data.get("height"),
                    format=item_data.get("format"),
                )
            if content_type == "audio":
                return Audio(
                    **common_args,
                    duration=item_data.get("duration"),
                    bit_rate=item_data.get("bit_rate"),
                    sample_rate=item_data.get("sample_rate"),
                    format=item_data.get("format"),
                )
            return ContentItem(**common_args)

        except Exception as e:
            self.logger.error(f"Error creating content item from data dictionary: {e}")
            return None

    def _compute_hash_if_exists(self, file_path: str) -> Optional[str]:
        """Computes SHA-256 hash when the file is accessible."""
        if not file_path or not os.path.exists(file_path):
            return None
        try:
            return utils.compute_file_hash(file_path)
        except Exception as e:
            self.logger.debug(f"Could not compute hash for {file_path}: {e}")
            return None

    def _process_metadata_updates(
        self, session: Session, metadata_updates: List[Tuple[int, Dict[str, Any]]]
    ) -> Tuple[List[ContentItem], List[int]]:
        updated_items: List[ContentItem] = []
        failed_ids: List[int] = []

        for item_id, metadata in metadata_updates:
            item = session.query(ContentItem).filter(ContentItem.id == item_id).first()

            if not item:
                failed_ids.append(item_id)
                continue

            if item.content_metadata is None:
                item.content_metadata = {}

            serialized_metadata = utils.serialize_metadata_for_json(metadata)

            item.content_metadata.update(serialized_metadata) or {}

            flag_modified(item, "content_metadata")

            item.year_taken = self._resolve_year_taken(item.path, serialized_metadata)
            item.metadata_extracted = True
            item.date_modified = datetime_utcnow()

            updated_items.append(item)

        return updated_items, failed_ids

    def _update_existing_item(
        self,
        existing_item: ContentItem,
        path: str,
        extract_basic_info: bool,
        metadata: Optional[Dict[str, Any]],
    ) -> None:
        """Update selected fields for an existing item during re-scan."""
        if extract_basic_info and os.path.exists(path):
            try:
                existing_item.file_size = os.path.getsize(path)
            except OSError:
                pass
            try:
                existing_item.file_hash = utils.compute_file_hash(path)
            except Exception:
                pass

        if metadata is not None:
            serialized_metadata = utils.serialize_metadata_for_json(metadata)
            if existing_item.content_metadata is None:
                existing_item.content_metadata = {}
            existing_item.content_metadata.update(serialized_metadata or {})
            flag_modified(existing_item, "content_metadata")
            existing_item.metadata_extracted = True

        existing_item.year_taken = self._resolve_year_taken(
            path, metadata or existing_item.content_metadata
        )
        existing_item.date_modified = datetime_utcnow()

    def _resolve_year_taken(
        self, file_path: str, metadata: Optional[Dict[str, Any]]
    ) -> Optional[int]:
        """
        Resolve year_taken with priority:
        1) year from metadata when available
        2) filesystem mtime year fallback
        """
        year = self._extract_year_from_metadata(metadata or {})
        if year is not None:
            return year

        try:
            return int(datetime.fromtimestamp(os.path.getmtime(file_path)).year)
        except Exception:
            return None

    def _extract_year_from_metadata(self, metadata: Dict[str, Any]) -> Optional[int]:
        """Extract a valid year from metadata date/year keys."""
        if not isinstance(metadata, dict):
            return None
        for key in (
            "year",
            "year_taken",
            "creation_date",
            "date_created",
            "date",
            "created",
            "timestamp",
            "DateTimeOriginal",
            "datetime_original",
        ):
            if key not in metadata:
                continue
            year = self._extract_year_value(metadata.get(key))
            if year is not None:
                return year
        return None

    def _extract_year_value(self, raw_value: Any) -> Optional[int]:
        """Parse a year in [1900, 2100] from mixed metadata values."""
        if raw_value is None:
            return None

        if isinstance(raw_value, datetime):
            year = raw_value.year
            return year if 1900 <= year <= 2100 else None

        if isinstance(raw_value, int):
            return raw_value if 1900 <= raw_value <= 2100 else None

        text = str(raw_value).strip()
        if not text:
            return None

        match = re.search(r"(19\d{2}|20\d{2}|2100)", text)
        if not match:
            return None

        year = int(match.group(1))
        return year if 1900 <= year <= 2100 else None
