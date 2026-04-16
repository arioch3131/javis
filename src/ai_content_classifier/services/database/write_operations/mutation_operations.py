"""Write operation classes for content database mutations."""

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from ai_content_classifier.models.content_models import ContentItem, datetime_utcnow
from ai_content_classifier.services.database.types import (
    DatabaseOperationCode,
    DatabaseOperationDataKey,
    DatabaseOperationResult,
)


class CreateContentItemOperation:
    def execute(
        self,
        writer: Any,
        path: str,
        content_type: str,
        extract_basic_info: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
        refresh: bool = True,
        session: Optional[Session] = None,
    ) -> DatabaseOperationResult:
        try:
            writer._validate_content_creation_params(path, content_type)
        except ValueError as exc:
            return DatabaseOperationResult(
                success=False,
                code=DatabaseOperationCode.INVALID_INPUT,
                message=str(exc),
                data={
                    DatabaseOperationDataKey.ERROR.value: str(exc),
                    "path": path,
                    "content_type": content_type,
                },
            )

        external_session = session is not None
        session = session or writer.database_service.Session()

        try:
            existing_item = (
                session.query(ContentItem).filter(ContentItem.path == path).first()
            )
            if isinstance(existing_item, ContentItem):
                writer._update_existing_item(
                    existing_item=existing_item,
                    path=path,
                    extract_basic_info=extract_basic_info,
                    metadata=metadata,
                )
                if external_session:
                    session.flush()
                else:
                    session.commit()

                if refresh:
                    session.refresh(existing_item)

                return DatabaseOperationResult(
                    success=True,
                    code=DatabaseOperationCode.OK,
                    message="Content item updated.",
                    data={"item": existing_item, "created": False},
                )

            file_info = writer._extract_file_info(path, extract_basic_info)

            item = writer._create_typed_content_item(
                path=path,
                content_type=content_type,
                file_info=file_info,
                file_hash=writer._compute_hash_if_exists(path)
                if extract_basic_info
                else None,
                metadata=metadata,
            )
            session.add(item)

            if external_session:
                session.flush()
            else:
                session.commit()

            if refresh:
                session.refresh(item)

            writer.logger.debug(f"Created content item: {path} (type: {content_type}).")
            return DatabaseOperationResult(
                success=True,
                code=DatabaseOperationCode.OK,
                message="Content item created.",
                data={"item": item, "created": True},
            )

        except SQLAlchemyError as exc:
            if not external_session:
                session.rollback()
            writer.logger.error(f"Error creating content item for {path}: {exc}")
            return DatabaseOperationResult(
                success=False,
                code=DatabaseOperationCode.DB_ERROR,
                message="Database error while creating content item.",
                data={
                    DatabaseOperationDataKey.ERROR.value: str(exc),
                    "path": path,
                },
            )
        except Exception as exc:
            if not external_session:
                session.rollback()
            writer.logger.error(
                f"Unexpected error creating content item for {path}: {exc}",
                exc_info=True,
            )
            return DatabaseOperationResult(
                success=False,
                code=DatabaseOperationCode.UNKNOWN_ERROR,
                message="Unexpected error while creating content item.",
                data={
                    DatabaseOperationDataKey.ERROR.value: str(exc),
                    "path": path,
                },
            )
        finally:
            if not external_session:
                session.close()


class SaveItemBatchOperation:
    def execute(
        self,
        writer: Any,
        items: List[Dict[str, Any]],
        refresh: bool = True,
        session: Optional[Session] = None,
    ) -> DatabaseOperationResult:
        if not items:
            return DatabaseOperationResult(
                success=True,
                code=DatabaseOperationCode.OK,
                message="No items to save.",
                data={
                    "items": [],
                    "saved_count": 0,
                    DatabaseOperationDataKey.IGNORED_COUNT.value: 0,
                    DatabaseOperationDataKey.FAILED_PATHS.value: [],
                    DatabaseOperationDataKey.NORMALIZED_PATHS.value: [],
                },
            )

        external_session = session is not None
        session = session or writer.database_service.Session()

        try:
            content_items: List[ContentItem] = []
            failed_paths: List[str] = []
            ignored_count = 0
            normalized_paths = [
                str(item.get("path") or "")
                for item in items
                if isinstance(item, dict) and item.get("path")
            ]

            for item_data in items:
                if not writer._is_valid_item_data(item_data):
                    writer.logger.warning(
                        f"Skipping invalid item data in batch: {item_data}"
                    )
                    ignored_count += 1
                    continue

                item_path = str(item_data["path"])
                existing_item = (
                    session.query(ContentItem)
                    .filter(ContentItem.path == item_data["path"])
                    .first()
                )
                if isinstance(existing_item, ContentItem):
                    writer._update_existing_item(
                        existing_item=existing_item,
                        path=item_data["path"],
                        extract_basic_info=True,
                        metadata=item_data.get("metadata"),
                    )
                    content_items.append(existing_item)
                    continue

                item = writer._create_content_item_from_data(item_data)
                if item is None:
                    failed_paths.append(item_path)
                    continue
                session.add(item)
                content_items.append(item)

            if external_session:
                session.flush()
            else:
                session.commit()

            if refresh:
                for item in content_items:
                    session.refresh(item)

            saved_count = len(content_items)
            has_failures = bool(failed_paths or ignored_count)
            if saved_count == 0 and has_failures:
                code = DatabaseOperationCode.INVALID_INPUT
                success = False
                message = "No valid items were saved."
            elif has_failures:
                code = DatabaseOperationCode.PARTIAL_SUCCESS
                success = True
                message = "Batch saved partially."
            else:
                code = DatabaseOperationCode.OK
                success = True
                message = "Batch saved successfully."

            return DatabaseOperationResult(
                success=success,
                code=code,
                message=message,
                data={
                    "items": content_items,
                    "saved_count": saved_count,
                    DatabaseOperationDataKey.IGNORED_COUNT.value: ignored_count,
                    DatabaseOperationDataKey.FAILED_PATHS.value: failed_paths,
                    DatabaseOperationDataKey.NORMALIZED_PATHS.value: normalized_paths,
                },
            )

        except SQLAlchemyError as exc:
            if not external_session:
                session.rollback()
            writer.logger.error(f"Error saving batch of content items: {exc}")
            return DatabaseOperationResult(
                success=False,
                code=DatabaseOperationCode.DB_ERROR,
                message="Database error while saving content batch.",
                data={DatabaseOperationDataKey.ERROR.value: str(exc)},
            )
        except Exception as exc:
            if not external_session:
                session.rollback()
            writer.logger.error(
                f"Unexpected error saving batch of content items: {exc}",
                exc_info=True,
            )
            return DatabaseOperationResult(
                success=False,
                code=DatabaseOperationCode.UNKNOWN_ERROR,
                message="Unexpected error while saving content batch.",
                data={DatabaseOperationDataKey.ERROR.value: str(exc)},
            )
        finally:
            if not external_session:
                session.close()


class UpdateMetadataBatchOperation:
    def execute(
        self,
        writer: Any,
        metadata_updates: List[Tuple[int, Dict[str, Any]]],
        refresh: bool = False,
        session: Optional[Session] = None,
    ) -> DatabaseOperationResult:
        if not metadata_updates:
            return DatabaseOperationResult(
                success=True,
                code=DatabaseOperationCode.OK,
                message="No metadata updates provided.",
                data={
                    "updated_count": 0,
                    DatabaseOperationDataKey.IGNORED_COUNT.value: 0,
                    DatabaseOperationDataKey.FAILED_IDS.value: [],
                },
            )

        external_session = session is not None
        session = session or writer.database_service.Session()

        try:
            updated_items, failed_ids = writer._process_metadata_updates(
                session=session,
                metadata_updates=metadata_updates,
            )

            if external_session:
                session.flush()
            else:
                session.commit()

            if refresh:
                for item in updated_items:
                    session.refresh(item)

            updated_count = len(updated_items)
            ignored_count = len(metadata_updates) - updated_count

            if updated_count == 0 and failed_ids:
                code = DatabaseOperationCode.NOT_FOUND
                success = False
                message = "No target items found for metadata update."
            elif failed_ids:
                code = DatabaseOperationCode.PARTIAL_SUCCESS
                success = True
                message = "Metadata batch updated partially."
            else:
                code = DatabaseOperationCode.OK
                success = True
                message = "Metadata batch updated successfully."

            return DatabaseOperationResult(
                success=success,
                code=code,
                message=message,
                data={
                    "updated_count": updated_count,
                    "items": updated_items,
                    DatabaseOperationDataKey.IGNORED_COUNT.value: ignored_count,
                    DatabaseOperationDataKey.FAILED_IDS.value: failed_ids,
                },
            )

        except SQLAlchemyError as exc:
            if not external_session:
                session.rollback()
            writer.logger.error(f"Error updating metadata batch: {exc}")
            return DatabaseOperationResult(
                success=False,
                code=DatabaseOperationCode.DB_ERROR,
                message="Database error while updating metadata batch.",
                data={DatabaseOperationDataKey.ERROR.value: str(exc)},
            )
        except Exception as exc:
            if not external_session:
                session.rollback()
            writer.logger.error(
                f"Unexpected error updating metadata batch: {exc}",
                exc_info=True,
            )
            return DatabaseOperationResult(
                success=False,
                code=DatabaseOperationCode.UNKNOWN_ERROR,
                message="Unexpected error while updating metadata batch.",
                data={DatabaseOperationDataKey.ERROR.value: str(exc)},
            )
        finally:
            if not external_session:
                session.close()


class UpdateContentCategoryOperation:
    def execute(
        self,
        writer: Any,
        file_path: str,
        category: str,
        confidence: float,
        extraction_method: str,
        extraction_details: str,
        session: Optional[Session] = None,
    ) -> DatabaseOperationResult:
        normalized_path = str(file_path or "").strip()
        if not normalized_path:
            return DatabaseOperationResult(
                success=False,
                code=DatabaseOperationCode.INVALID_INPUT,
                message="File path cannot be empty.",
                data={DatabaseOperationDataKey.ERROR.value: "empty_path"},
            )

        external_session = session is not None
        session = session or writer.database_service.Session()

        try:
            item = (
                session.query(ContentItem)
                .filter(ContentItem.path == normalized_path)
                .first()
            )

            if not item:
                return DatabaseOperationResult(
                    success=False,
                    code=DatabaseOperationCode.NOT_FOUND,
                    message=f"Content item not found for path: {normalized_path}.",
                    data={
                        DatabaseOperationDataKey.FAILED_PATHS.value: [normalized_path]
                    },
                )

            item.category = category
            item.classification_confidence = confidence

            if item.content_metadata is None:
                item.content_metadata = {}

            item.content_metadata["classification"] = {
                "category": category,
                "confidence": confidence,
                "extraction_method": extraction_method,
                "extraction_details": extraction_details,
                "timestamp": datetime_utcnow().isoformat(),
            }

            flag_modified(item, "content_metadata")
            item.date_modified = datetime_utcnow()

            if external_session:
                session.flush()
            else:
                session.commit()

            return DatabaseOperationResult(
                success=True,
                code=DatabaseOperationCode.OK,
                message="Content category updated.",
                data={"item": item, "path": normalized_path},
            )

        except SQLAlchemyError as exc:
            if not external_session:
                session.rollback()
            writer.logger.error(f"Error updating category for {normalized_path}: {exc}")
            return DatabaseOperationResult(
                success=False,
                code=DatabaseOperationCode.DB_ERROR,
                message="Database error while updating content category.",
                data={DatabaseOperationDataKey.ERROR.value: str(exc)},
            )
        except Exception as exc:
            if not external_session:
                session.rollback()
            writer.logger.error(
                f"Unexpected error updating category for {normalized_path}: {exc}",
                exc_info=True,
            )
            return DatabaseOperationResult(
                success=False,
                code=DatabaseOperationCode.UNKNOWN_ERROR,
                message="Unexpected error while updating content category.",
                data={DatabaseOperationDataKey.ERROR.value: str(exc)},
            )
        finally:
            if not external_session:
                session.close()


class ClearContentCategoryOperation:
    def execute(
        self,
        writer: Any,
        file_path: str,
        session: Optional[Session] = None,
    ) -> DatabaseOperationResult:
        normalized_path = str(file_path or "").strip()
        if not normalized_path:
            return DatabaseOperationResult(
                success=False,
                code=DatabaseOperationCode.INVALID_INPUT,
                message="File path cannot be empty.",
                data={DatabaseOperationDataKey.ERROR.value: "empty_path"},
            )

        external_session = session is not None
        session = session or writer.database_service.Session()

        try:
            item = (
                session.query(ContentItem)
                .filter(ContentItem.path == normalized_path)
                .first()
            )

            if not item:
                return DatabaseOperationResult(
                    success=False,
                    code=DatabaseOperationCode.NOT_FOUND,
                    message=f"Content item not found for path: {normalized_path}.",
                    data={
                        DatabaseOperationDataKey.FAILED_PATHS.value: [normalized_path]
                    },
                )

            item.category = None
            item.classification_confidence = None

            if item.content_metadata is None:
                item.content_metadata = {}
            if isinstance(item.content_metadata, dict):
                item.content_metadata.pop("classification", None)
                flag_modified(item, "content_metadata")

            item.date_modified = datetime_utcnow()

            if external_session:
                session.flush()
            else:
                session.commit()

            return DatabaseOperationResult(
                success=True,
                code=DatabaseOperationCode.OK,
                message="Content category cleared.",
                data={"item": item, "path": normalized_path},
            )

        except SQLAlchemyError as exc:
            if not external_session:
                session.rollback()
            writer.logger.error(f"Error clearing category for {normalized_path}: {exc}")
            return DatabaseOperationResult(
                success=False,
                code=DatabaseOperationCode.DB_ERROR,
                message="Database error while clearing content category.",
                data={DatabaseOperationDataKey.ERROR.value: str(exc)},
            )
        except Exception as exc:
            if not external_session:
                session.rollback()
            writer.logger.error(
                f"Unexpected error clearing category for {normalized_path}: {exc}",
                exc_info=True,
            )
            return DatabaseOperationResult(
                success=False,
                code=DatabaseOperationCode.UNKNOWN_ERROR,
                message="Unexpected error while clearing content category.",
                data={DatabaseOperationDataKey.ERROR.value: str(exc)},
            )
        finally:
            if not external_session:
                session.close()


class ClearAllContentOperation:
    def execute(
        self,
        writer: Any,
        session: Optional[Session] = None,
    ) -> DatabaseOperationResult:
        external_session = session is not None
        session = session or writer.database_service.Session()

        try:
            num_deleted = int(
                session.query(ContentItem).delete(synchronize_session="fetch") or 0
            )
            if external_session:
                session.flush()
            else:
                session.commit()

            return DatabaseOperationResult(
                success=True,
                code=DatabaseOperationCode.OK,
                message="All content items were deleted.",
                data={DatabaseOperationDataKey.DELETED_COUNT.value: num_deleted},
            )
        except SQLAlchemyError as exc:
            if not external_session:
                session.rollback()
            writer.logger.error(f"Error clearing all content items: {exc}")
            return DatabaseOperationResult(
                success=False,
                code=DatabaseOperationCode.DB_ERROR,
                message="Database error while clearing all content items.",
                data={DatabaseOperationDataKey.ERROR.value: str(exc)},
            )
        except Exception as exc:
            if not external_session:
                session.rollback()
            writer.logger.error(
                f"Unexpected error clearing all content items: {exc}",
                exc_info=True,
            )
            return DatabaseOperationResult(
                success=False,
                code=DatabaseOperationCode.UNKNOWN_ERROR,
                message="Unexpected error while clearing all content items.",
                data={DatabaseOperationDataKey.ERROR.value: str(exc)},
            )
        finally:
            if not external_session:
                session.close()


class DeleteContentByPathsOperation:
    def execute(
        self,
        writer: Any,
        file_paths: List[str],
        session: Optional[Session] = None,
    ) -> DatabaseOperationResult:
        normalized_paths = [
            str(path) for path in dict.fromkeys(file_paths or []) if path
        ]
        if not normalized_paths:
            return DatabaseOperationResult(
                success=True,
                code=DatabaseOperationCode.OK,
                message="No file paths provided for deletion.",
                data={
                    DatabaseOperationDataKey.DELETED_COUNT.value: 0,
                    DatabaseOperationDataKey.IGNORED_COUNT.value: 0,
                    DatabaseOperationDataKey.FAILED_PATHS.value: [],
                    DatabaseOperationDataKey.NORMALIZED_PATHS.value: [],
                },
            )

        external_session = session is not None
        session = session or writer.database_service.Session()

        try:
            num_deleted = int(
                session.query(ContentItem)
                .filter(ContentItem.path.in_(normalized_paths))
                .delete(synchronize_session="fetch")
                or 0
            )
            if external_session:
                session.flush()
            else:
                session.commit()

            ignored_count = max(len(normalized_paths) - num_deleted, 0)
            failed_paths: List[str] = []
            code = DatabaseOperationCode.OK
            success = True
            message = "Content items deleted by path."

            if ignored_count > 0:
                code = DatabaseOperationCode.PARTIAL_SUCCESS
                message = "Some paths were not found during deletion."

            return DatabaseOperationResult(
                success=success,
                code=code,
                message=message,
                data={
                    DatabaseOperationDataKey.DELETED_COUNT.value: num_deleted,
                    DatabaseOperationDataKey.IGNORED_COUNT.value: ignored_count,
                    DatabaseOperationDataKey.FAILED_PATHS.value: failed_paths,
                    DatabaseOperationDataKey.NORMALIZED_PATHS.value: normalized_paths,
                },
            )
        except SQLAlchemyError as exc:
            if not external_session:
                session.rollback()
            writer.logger.error(f"Error deleting content items by path: {exc}")
            return DatabaseOperationResult(
                success=False,
                code=DatabaseOperationCode.DB_ERROR,
                message="Database error while deleting content items by path.",
                data={
                    DatabaseOperationDataKey.ERROR.value: str(exc),
                    DatabaseOperationDataKey.NORMALIZED_PATHS.value: normalized_paths,
                },
            )
        except Exception as exc:
            if not external_session:
                session.rollback()
            writer.logger.error(
                f"Unexpected error deleting content items by path: {exc}",
                exc_info=True,
            )
            return DatabaseOperationResult(
                success=False,
                code=DatabaseOperationCode.UNKNOWN_ERROR,
                message="Unexpected error while deleting content items by path.",
                data={
                    DatabaseOperationDataKey.ERROR.value: str(exc),
                    DatabaseOperationDataKey.NORMALIZED_PATHS.value: normalized_paths,
                },
            )
        finally:
            if not external_session:
                session.close()
