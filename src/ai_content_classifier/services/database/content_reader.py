"""Read operations for content database."""

import datetime
import hashlib
import json
import os
import re
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Query, Session, joinedload, load_only

from ai_content_classifier.core.logger import LoggableMixin
from ai_content_classifier.models.content_models import ContentItem
from ai_content_classifier.repositories.content_repository import ContentFilter
from ai_content_classifier.services.database.database_service import DatabaseService
from ai_content_classifier.services.database.read_operations import (
    CountAllItemsOperation,
    FindDuplicatesOperation,
    FindItemsOperation,
    GetContentByPathOperation,
    GetItemsPendingMetadataOperation,
    GetStatisticsOperation,
    GetUncategorizedItemsOperation,
    GetUniqueCategoriesOperation,
    GetUniqueExtensionsOperation,
    GetUniqueYearsOperation,
)
from ai_content_classifier.services.database.types import (
    DatabaseOperationCode,
    DatabaseOperationDataKey,
    DatabaseOperationResult,
)


class ContentReader(LoggableMixin):
    """Handles all read-only database operations for content items."""

    def __init__(
        self,
        database_service: DatabaseService,
        query_optimizer: Optional[Any] = None,
        metrics: Optional[Any] = None,
    ):
        self.__init_logger__()
        self.database_service = database_service
        self.query_optimizer = query_optimizer
        self.metrics = metrics

        self._find_items_operation = FindItemsOperation()
        self._count_all_items_operation = CountAllItemsOperation()
        self._get_items_pending_metadata_operation = GetItemsPendingMetadataOperation()
        self._find_duplicates_operation = FindDuplicatesOperation()
        self._get_statistics_operation = GetStatisticsOperation()
        self._get_content_by_path_operation = GetContentByPathOperation()
        self._get_uncategorized_items_operation = GetUncategorizedItemsOperation()
        self._get_unique_categories_operation = GetUniqueCategoriesOperation()
        self._get_unique_years_operation = GetUniqueYearsOperation()
        self._get_unique_extensions_operation = GetUniqueExtensionsOperation()

    def find_items(
        self,
        content_filter: Optional[ContentFilter] = None,
        sort_by: Optional[str] = None,
        sort_desc: bool = False,
        limit: Optional[int] = None,
        offset: int = 0,
        eager_load: bool = False,
        custom_filter: Optional[List[Any]] = None,
        session: Optional[Session] = None,
    ) -> DatabaseOperationResult:
        try:
            items = self._find_items_operation.execute(
                self,
                content_filter=content_filter,
                sort_by=sort_by,
                sort_desc=sort_desc,
                limit=limit,
                offset=offset,
                eager_load=eager_load,
                custom_filter=custom_filter,
                session=session,
            )
            return self._success_result(
                message=f"{len(items)} item(s) found.",
                data={"items": items},
            )
        except Exception as exc:
            return self._error_result("Error finding items.", exc)

    def _find_items_uncached(
        self,
        content_filter: Optional[ContentFilter] = None,
        sort_by: Optional[str] = None,
        sort_desc: bool = False,
        limit: Optional[int] = None,
        offset: int = 0,
        eager_load: bool = False,
        custom_filter: Optional[List[Any]] = None,
        session: Optional[Session] = None,
    ) -> List[ContentItem]:
        external_session = session is not None
        session = session or self.database_service.Session()

        try:
            query = self._build_find_query(
                session=session,
                content_filter=content_filter,
                custom_filter=custom_filter,
                eager_load=eager_load,
            )
            self.logger.debug(
                f"DEBUG: find_items - Query built with filter criteria: {content_filter.criteria if content_filter else 'None'}"
            )

            if sort_by:
                query = self._apply_sorting(query, sort_by, sort_desc)

            if limit is not None:
                query = query.limit(limit).offset(offset)

            results = list(query.all())
            self.logger.debug(f"Found {len(results)} items matching criteria.")
            if results:
                self.logger.debug("Filtered files paths:")
                for item in results:
                    self.logger.debug(f"  - {item.path}")

            if len(results) == 0 and not content_filter and not custom_filter:
                total_count = session.query(func.count(ContentItem.id)).scalar()
                self.logger.warning(
                    f"find_items returned 0 results, but database contains {total_count} total items."
                )
                simple_results = session.query(ContentItem).limit(5).all()
                self.logger.info(
                    f"Simple query returned {len(simple_results)} items for debugging."
                )

            return results

        except SQLAlchemyError as e:
            self.logger.error(f"Error finding items: {e}")
            raise
        finally:
            if not external_session:
                session.close()

    def count_all_items(
        self, session: Optional[Session] = None
    ) -> DatabaseOperationResult:
        try:
            count = self._count_all_items_operation.execute(self, session=session)
            return self._success_result(
                message=f"Total items: {count}.",
                data={"count": count},
            )
        except Exception as exc:
            return self._error_result(
                "Error counting items.", exc, default_data={"count": 0}
            )

    def _count_all_items_uncached(self, session: Optional[Session] = None) -> int:
        external_session = session is not None
        session = session or self.database_service.Session()

        try:
            count = session.query(func.count(ContentItem.id)).scalar()
            self.logger.debug(f"Total items in database: {count}.")
            return count
        except Exception as e:
            self.logger.error(f"Error counting items in database: {e}")
            return 0
        finally:
            if not external_session:
                session.close()

    def get_items_pending_metadata(
        self,
        content_type: Optional[str] = None,
        limit: Optional[int] = None,
        eager_load: bool = False,
        session: Optional[Session] = None,
    ) -> DatabaseOperationResult:
        try:
            items = self._get_items_pending_metadata_operation.execute(
                self,
                content_type=content_type,
                limit=limit,
                eager_load=eager_load,
                session=session,
            )
            return self._success_result(
                message=f"{len(items)} item(s) pending metadata extraction.",
                data={"items": items},
            )
        except Exception as exc:
            return self._error_result("Error retrieving pending metadata items.", exc)

    def find_duplicates(
        self, session: Optional[Session] = None
    ) -> DatabaseOperationResult:
        try:
            duplicates = self._find_duplicates_operation.execute(self, session=session)
            return self._success_result(
                message=f"{len(duplicates)} duplicate group(s) found.",
                data={"duplicates": duplicates},
            )
        except Exception as exc:
            return self._error_result("Error finding duplicate items.", exc)

    def get_statistics(
        self, session: Optional[Session] = None
    ) -> DatabaseOperationResult:
        try:
            statistics = self._get_statistics_operation.execute(self, session=session)
            return self._success_result(
                message="Statistics generated.",
                data={"statistics": statistics},
            )
        except Exception as exc:
            return self._error_result("Error generating statistics.", exc)

    def get_content_by_path(
        self, file_path: str, session: Optional[Session] = None
    ) -> DatabaseOperationResult:
        try:
            item = self._get_content_by_path_operation.execute(
                self,
                file_path=file_path,
                session=session,
            )
            if item is None:
                return DatabaseOperationResult(
                    success=False,
                    code=DatabaseOperationCode.NOT_FOUND,
                    message=f"No content item found for path: {file_path}",
                    data={"item": None},
                )
            return self._success_result(
                message="Content item found.",
                data={"item": item},
            )
        except Exception as exc:
            return self._error_result("Error retrieving content item by path.", exc)

    def get_uncategorized_items(
        self, content_type: Optional[str] = None, session: Optional[Session] = None
    ) -> DatabaseOperationResult:
        try:
            items = self._get_uncategorized_items_operation.execute(
                self,
                content_type=content_type,
                session=session,
            )
            return self._success_result(
                message=f"{len(items)} uncategorized item(s) found.",
                data={"items": items},
            )
        except Exception as exc:
            return self._error_result("Error retrieving uncategorized items.", exc)

    def _build_find_query(
        self,
        session: Session,
        content_filter: Optional[ContentFilter],
        custom_filter: Optional[List[Any]],
        eager_load: bool,
    ) -> Query:
        query = session.query(ContentItem)

        filter_criteria = []

        if content_filter:
            filter_criteria.extend(content_filter.build())

        if custom_filter:
            filter_criteria.extend(custom_filter)

        if filter_criteria:
            query = query.filter(*filter_criteria)

        query = self._configure_loading_options(query, eager_load)

        return query

    def _configure_loading_options(self, query: Query, eager_load: bool) -> Query:
        if eager_load:
            query = query.options(
                joinedload(ContentItem.tags), joinedload(ContentItem.collections)
            )

        query = query.options(self._get_essential_loading_options())

        return query

    def _get_essential_loading_options(self) -> load_only:
        return load_only(
            ContentItem.id,
            ContentItem.path,
            ContentItem.filename,
            ContentItem.directory,
            ContentItem.content_type,
            ContentItem.content_metadata,
            ContentItem.metadata_extracted,
            ContentItem.date_created,
            ContentItem.date_modified,
            ContentItem.date_indexed,
            ContentItem.file_size,
            ContentItem.file_hash,
            ContentItem.category,
            ContentItem.width,
            ContentItem.height,
            ContentItem.format,
            ContentItem.duration,
            ContentItem.year_taken,
        )

    def _apply_sorting(self, query: Query, sort_by: str, sort_desc: bool) -> Query:
        if hasattr(ContentItem, sort_by):
            column = getattr(ContentItem, sort_by)
            if sort_desc:
                query = query.order_by(column.desc())
            else:
                query = query.order_by(column)
        else:
            self.logger.warning(
                f"Invalid sort column specified: '{sort_by}'. Sorting will not be applied."
            )

        return query

    def get_unique_categories(
        self, session: Optional[Session] = None
    ) -> DatabaseOperationResult:
        try:
            categories = self._get_unique_categories_operation.execute(
                self, session=session
            )
            return self._success_result(
                message=f"{len(categories)} unique category(ies) found.",
                data={"categories": categories},
            )
        except Exception as exc:
            return self._error_result("Error retrieving unique categories.", exc)

    def _get_unique_categories_uncached(
        self, session: Optional[Session] = None
    ) -> List[str]:
        external_session = session is not None
        session = session or self.database_service.Session()
        try:
            categories = (
                session.query(ContentItem.category)
                .distinct()
                .filter(ContentItem.category.isnot(None))
                .order_by(ContentItem.category)
                .all()
            )
            return [c[0] for c in categories]
        except SQLAlchemyError as e:
            self.logger.error(f"Error retrieving unique categories: {e}", exc_info=True)
            return []
        finally:
            if not external_session:
                session.close()

    def get_unique_years(
        self, session: Optional[Session] = None
    ) -> DatabaseOperationResult:
        try:
            years = self._get_unique_years_operation.execute(self, session=session)
            return self._success_result(
                message=f"{len(years)} unique year(s) found.",
                data={"years": years},
            )
        except Exception as exc:
            return self._error_result("Error retrieving unique years.", exc)

    def _get_unique_years_uncached(
        self, session: Optional[Session] = None
    ) -> List[int]:
        external_session = session is not None
        session = session or self.database_service.Session()
        try:
            items = session.query(
                ContentItem.path,
                ContentItem.year_taken,
                ContentItem.date_created,
                ContentItem.date_modified,
                ContentItem.date_indexed,
                ContentItem.content_metadata,
            ).all()

            years: set[int] = set()
            for row in items:
                if isinstance(row, (tuple, list)):
                    if len(row) == 6:
                        (
                            item_path,
                            year_taken,
                            date_created,
                            date_modified,
                            date_indexed,
                            metadata,
                        ) = row
                    elif len(row) == 5:
                        (
                            year_taken,
                            date_created,
                            date_modified,
                            date_indexed,
                            metadata,
                        ) = row
                        item_path = None
                    elif len(row) == 1:
                        item_path = None
                        year_taken = row[0]
                        date_created = None
                        date_modified = None
                        date_indexed = None
                        metadata = None
                    else:
                        continue
                else:
                    item_path = None
                    year_taken = row
                    date_created = None
                    date_modified = None
                    date_indexed = None
                    metadata = None

                if isinstance(year_taken, int) and 1900 <= year_taken <= 2100:
                    years.add(year_taken)
                elif year_taken is not None:
                    parsed = self._extract_year(year_taken)
                    if parsed is not None:
                        years.add(parsed)

                for dt in (date_created, date_modified, date_indexed):
                    if hasattr(dt, "year"):
                        y = int(dt.year)
                        if 1900 <= y <= 2100:
                            years.add(y)

                if isinstance(metadata, dict):
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
                        raw_value = metadata.get(key)
                        extracted_year = self._extract_year(raw_value)
                        if extracted_year is not None:
                            years.add(extracted_year)

                if item_path:
                    try:
                        mtime_year = datetime.datetime.fromtimestamp(
                            os.path.getmtime(item_path)
                        ).year
                        if 1900 <= mtime_year <= 2100:
                            years.add(mtime_year)
                    except Exception:
                        pass

            return sorted(years)
        except SQLAlchemyError as e:
            self.logger.error(f"Error retrieving unique years: {e}", exc_info=True)
            return []
        finally:
            if not external_session:
                session.close()

    def _extract_year(self, raw_value: Any) -> Optional[int]:
        """Extract a 4-digit year from a metadata value."""
        if raw_value is None:
            return None

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

    def get_unique_extensions(
        self, session: Optional[Session] = None
    ) -> DatabaseOperationResult:
        try:
            extensions = self._get_unique_extensions_operation.execute(
                self, session=session
            )
            return self._success_result(
                message=f"{len(extensions)} unique extension(s) found.",
                data={"extensions": extensions},
            )
        except Exception as exc:
            return self._error_result("Error retrieving unique extensions.", exc)

    def _get_unique_extensions_uncached(
        self, session: Optional[Session] = None
    ) -> List[str]:
        external_session = session is not None
        session = session or self.database_service.Session()
        try:
            path_rows = (
                session.query(ContentItem.path)
                .filter(ContentItem.path.isnot(None))
                .all()
            )

            normalized_extensions = {
                f".{os.path.basename(path).rsplit('.', 1)[-1].strip().lower()}"
                for (path,) in path_rows
                if path
                and "." in os.path.basename(path)
                and not os.path.basename(path).endswith(".")
            }
            return sorted(normalized_extensions)
        except SQLAlchemyError as e:
            self.logger.error(f"Error retrieving unique extensions: {e}", exc_info=True)
            return []
        finally:
            if not external_session:
                session.close()

    def _build_cache_key(self, *args: Any) -> str:
        key_data = json.dumps(args, default=str, sort_keys=True)
        return hashlib.md5(key_data.encode()).hexdigest()

    def _success_result(
        self, message: str, data: Dict[str, Any]
    ) -> DatabaseOperationResult:
        return DatabaseOperationResult(
            success=True,
            code=DatabaseOperationCode.OK,
            message=message,
            data=data,
        )

    def _error_result(
        self,
        message: str,
        error: Exception,
        default_data: Optional[Dict[str, Any]] = None,
    ) -> DatabaseOperationResult:
        return DatabaseOperationResult(
            success=False,
            code=DatabaseOperationCode.DB_ERROR,
            message=message,
            data={
                **(default_data or {}),
                DatabaseOperationDataKey.ERROR.value: str(error),
            },
        )
