"""Single-file organization operation."""

import os
import shutil

from datetime import datetime
from typing import Any, Optional

from ai_content_classifier.services.auto_organization.operations.helpers import (
    determine_file_type,
    resolve_name_conflict,
    sanitize_dirname,
)
from ai_content_classifier.services.auto_organization.operations.types import (
    AutoOrganizationStructure,
)
from ai_content_classifier.services.auto_organization.types import (
    AutoOrganizationDataKey,
    AutoOrganizationOperationCode,
    AutoOrganizationOperationResult,
    OrganizationConfig,
)
from ai_content_classifier.services.database.types import DatabaseOperationCode


class OrganizeSingleFileOperation:
    """Execute one organization operation for one source file."""

    def __init__(self, db_service: Any, logger: Any):
        self.db_service = db_service
        self.logger = logger

    def execute(
        self, file_path: str, config: OrganizationConfig
    ) -> AutoOrganizationOperationResult:
        try:
            target_path = self._build_target_path(file_path=file_path, config=config)
            return self._perform_file_action(
                source_path=file_path,
                target_path=target_path,
                action=config.organization_action,
            )
        except Exception as exc:
            self.logger.error(f"Error organizing file {file_path}: {exc}")
            return self._error_result(
                code=AutoOrganizationOperationCode.UNKNOWN_ERROR,
                message=f"Error organizing file: {exc}",
                source_path=file_path,
                target_path="",
                action=config.organization_action,
                error=str(exc),
            )

    def _build_target_path(self, file_path: str, config: OrganizationConfig) -> str:
        structure = config.organization_structure
        filename = os.path.basename(file_path)
        content_item = self._safe_get_content_item(file_path)

        if structure == AutoOrganizationStructure.BY_CATEGORY.value:
            category = self._extract_category(content_item)
            folder = os.path.join(config.target_directory, sanitize_dirname(category))
        elif structure == AutoOrganizationStructure.BY_YEAR.value:
            year = self._extract_year(file_path, content_item)
            folder = os.path.join(config.target_directory, str(year))
        elif structure == AutoOrganizationStructure.BY_TYPE.value:
            file_type = determine_file_type(file_path)
            folder = os.path.join(config.target_directory, file_type)
        elif structure == AutoOrganizationStructure.BY_CATEGORY_YEAR.value:
            category = self._extract_category(content_item)
            year = self._extract_year(file_path, content_item)
            folder = os.path.join(
                config.target_directory,
                sanitize_dirname(category),
                str(year),
            )
        elif structure == AutoOrganizationStructure.BY_TYPE_CATEGORY.value:
            file_type = determine_file_type(file_path)
            category = self._extract_category(content_item)
            folder = os.path.join(
                config.target_directory,
                file_type,
                sanitize_dirname(category),
            )
        elif structure == AutoOrganizationStructure.CUSTOM.value:
            # V1.8: custom stays a deterministic fallback on category.
            category = self._extract_category(content_item)
            folder = os.path.join(config.target_directory, sanitize_dirname(category))
        else:
            raise ValueError(f"Unsupported organization structure: {structure}")

        os.makedirs(folder, exist_ok=True)
        target_path = os.path.join(folder, filename)
        return resolve_name_conflict(target_path)

    def _safe_get_content_item(self, file_path: str) -> Optional[Any]:
        try:
            result = self.db_service.get_content_by_path(file_path)
            if not result.success:
                if result.code != DatabaseOperationCode.NOT_FOUND:
                    self.logger.warning(
                        "DB read failed for path '%s': code=%s message=%s",
                        file_path,
                        result.code,
                        result.message,
                    )
                return None
            return (result.data or {}).get("item")
        except Exception as exc:
            self.logger.debug(f"Could not fetch content item for {file_path}: {exc}")
            return None

    @staticmethod
    def _extract_category(content_item: Optional[Any]) -> str:
        category = getattr(content_item, "category", None) if content_item else None
        if not isinstance(category, str) or not category.strip():
            return "Uncategorized"
        return category

    @staticmethod
    def _extract_year(file_path: str, content_item: Optional[Any]) -> int:
        try:
            creation_date = (
                getattr(content_item, "creation_date", None) if content_item else None
            )

            if hasattr(creation_date, "year"):
                return creation_date.year

            if isinstance(creation_date, str) and creation_date.strip():
                try:
                    return datetime.fromisoformat(creation_date).year
                except ValueError:
                    pass

            if isinstance(content_item, dict):
                metadata_date = content_item.get("creation_date")
                if hasattr(metadata_date, "year"):
                    return metadata_date.year

            return datetime.fromtimestamp(os.path.getmtime(file_path)).year
        except (OSError, TypeError, ValueError):
            return datetime.now().year

    def _perform_file_action(
        self,
        source_path: str,
        target_path: str,
        action: str,
    ) -> AutoOrganizationOperationResult:
        try:
            content_item = self._safe_get_content_item(source_path)
            file_hash = (
                getattr(content_item, "file_hash", None) if content_item else None
            )

            if not os.path.exists(source_path):
                return self._error_result(
                    code=AutoOrganizationOperationCode.VALIDATION_ERROR,
                    message="Source file does not exist",
                    source_path=source_path,
                    target_path=target_path,
                    action=action,
                    error="Source file does not exist",
                    file_hash=file_hash,
                )

            file_size = os.path.getsize(source_path)

            if action == "copy":
                shutil.copy2(source_path, target_path)
                self.logger.debug(f"File copied: {source_path} -> {target_path}")
            elif action == "move":
                shutil.move(source_path, target_path)
                self.logger.debug(f"File moved: {source_path} -> {target_path}")
                db_result = self.db_service.update_content_path(
                    source_path=source_path,
                    target_path=target_path,
                )
                if not db_result.success:
                    mapped_code = (
                        AutoOrganizationOperationCode.CONFLICT_ERROR
                        if db_result.code == DatabaseOperationCode.INVALID_INPUT
                        else AutoOrganizationOperationCode.DATABASE_ERROR
                    )
                    message = (
                        f"Move completed but DB update failed: {db_result.message}"
                    )
                    return self._error_result(
                        code=mapped_code,
                        message=message,
                        source_path=source_path,
                        target_path=target_path,
                        action=action,
                        error=str(
                            (db_result.data or {}).get("error") or db_result.message
                        ),
                        file_hash=file_hash,
                        size_bytes=file_size,
                    )
            else:
                return self._error_result(
                    code=AutoOrganizationOperationCode.VALIDATION_ERROR,
                    message=f"Invalid organization action: {action}",
                    source_path=source_path,
                    target_path=target_path,
                    action=action,
                    error=f"Invalid organization action: {action}",
                    file_hash=file_hash,
                )

            result = self._success_result(
                message="File organized successfully",
                source_path=source_path,
                target_path=target_path,
                action=action,
                size_bytes=file_size,
                file_hash=file_hash,
            )
            self.logger.info(
                "Organization operation completed: code=%s source_path=%s target_path=%s action=%s",
                result.code.value,
                source_path,
                target_path,
                action,
            )
            return result

        except FileExistsError as exc:
            self.logger.warning(f"Conflict while organizing file: {exc}")
            return self._error_result(
                code=AutoOrganizationOperationCode.CONFLICT_ERROR,
                message=f"Destination conflict: {exc}",
                source_path=source_path,
                target_path=target_path,
                action=action,
                error=str(exc),
            )
        except (OSError, shutil.Error) as exc:
            self.logger.error(f"Filesystem error performing file action: {exc}")
            return self._error_result(
                code=AutoOrganizationOperationCode.FILESYSTEM_ERROR,
                message=f"Filesystem error: {exc}",
                source_path=source_path,
                target_path=target_path,
                action=action,
                error=str(exc),
            )
        except Exception as exc:
            self.logger.error(f"Error performing file action: {exc}")
            return self._error_result(
                code=AutoOrganizationOperationCode.UNKNOWN_ERROR,
                message=f"Unexpected organization error: {exc}",
                source_path=source_path,
                target_path=target_path,
                action=action,
                error=str(exc),
            )

    def _success_result(
        self,
        message: str,
        source_path: str,
        target_path: str,
        action: str,
        size_bytes: int = 0,
        file_hash: Optional[str] = None,
    ) -> AutoOrganizationOperationResult:
        data = {
            AutoOrganizationDataKey.SOURCE_PATH.value: source_path,
            AutoOrganizationDataKey.TARGET_PATH.value: target_path,
            AutoOrganizationDataKey.ACTION.value: action,
            AutoOrganizationDataKey.ERROR.value: None,
            AutoOrganizationDataKey.SIZE_BYTES.value: size_bytes,
        }
        if file_hash:
            data[AutoOrganizationDataKey.FILE_HASH.value] = file_hash
        return AutoOrganizationOperationResult(
            success=True,
            code=AutoOrganizationOperationCode.OK,
            message=message,
            data=data,
        )

    def _error_result(
        self,
        code: AutoOrganizationOperationCode,
        message: str,
        source_path: str,
        target_path: str,
        action: str,
        error: Optional[str] = None,
        file_hash: Optional[str] = None,
        size_bytes: int = 0,
    ) -> AutoOrganizationOperationResult:
        data = {
            AutoOrganizationDataKey.SOURCE_PATH.value: source_path,
            AutoOrganizationDataKey.TARGET_PATH.value: target_path,
            AutoOrganizationDataKey.ACTION.value: action,
            AutoOrganizationDataKey.ERROR.value: error or message,
            AutoOrganizationDataKey.SIZE_BYTES.value: size_bytes,
        }
        if file_hash:
            data[AutoOrganizationDataKey.FILE_HASH.value] = file_hash
        result = AutoOrganizationOperationResult(
            success=False,
            code=code,
            message=message,
            data=data,
        )
        self.logger.warning(
            "Organization operation failed: code=%s source_path=%s target_path=%s action=%s message=%s",
            code.value,
            source_path,
            target_path,
            action,
            message,
        )
        return result
