"""
This module provides the ContentReader class, which is responsible for all read-only
operations on the content database.
"""

import datetime
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


class ContentReader(LoggableMixin):
    """Handles all read-only database operations for content items."""

    def __init__(self, database_service: DatabaseService):
        self.__init_logger__()
        self.database_service = database_service

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
    ) -> List[ContentItem]:
        external_session = session is not None
        session = session or self.database_service.Session()

        try:
            if not external_session:
                try:
                    session.execute("BEGIN IMMEDIATE;")
                    session.rollback()
                except Exception:
                    pass

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

    def count_all_items(self, session: Optional[Session] = None) -> int:
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
    ) -> List[ContentItem]:
        external_session = session is not None
        session = session or self.database_service.Session()

        try:
            query = session.query(ContentItem).filter(
                not ContentItem.metadata_extracted
            )

            if content_type:
                query = query.filter(ContentItem.content_type == content_type)

            query = self._configure_loading_options(query, eager_load)

            if limit is not None:
                query = query.limit(limit)

            results = list(query.all())
            self.logger.debug(
                f"Found {len(results)} items pending metadata extraction."
            )
            return results

        except Exception as e:
            self.logger.error(f"Error retrieving pending metadata items: {e}")
            raise
        finally:
            if not external_session:
                session.close()

    def find_duplicates(
        self, session: Optional[Session] = None
    ) -> Dict[str, List[ContentItem]]:
        external_session = session is not None
        session = session or self.database_service.Session()

        try:
            duplicate_hashes = (
                session.query(ContentItem.file_hash)
                .filter(ContentItem.file_hash.isnot(None))
                .group_by(ContentItem.file_hash)
                .having(func.count(ContentItem.id) > 1)
                .all()
            )

            if not duplicate_hashes:
                return {}

            hash_values = [h[0] for h in duplicate_hashes]
            duplicates = (
                session.query(ContentItem)
                .filter(ContentItem.file_hash.in_(hash_values))
                .all()
            )

            result = {}
            for item in duplicates:
                if item.file_hash not in result:
                    result[item.file_hash] = []
                result[item.file_hash].append(item)

            self.logger.debug(f"Found {len(result)} sets of duplicate files.")
            return result

        except SQLAlchemyError as e:
            self.logger.error(f"Error finding duplicate content items: {e}")
            raise
        finally:
            if not external_session:
                session.close()

    def get_statistics(self, session: Optional[Session] = None) -> Dict[str, Any]:
        external_session = session is not None
        session = session or self.database_service.Session()

        try:
            total_items = session.query(func.count(ContentItem.id)).scalar()

            type_counts = (
                session.query(ContentItem.content_type, func.count(ContentItem.id))
                .group_by(ContentItem.content_type)
                .all()
            )

            extracted_count = (
                session.query(func.count(ContentItem.id))
                .filter(ContentItem.metadata_extracted)
                .scalar()
            )

            stats = {
                "total_items": total_items,
                "items_by_type": dict(type_counts),
                "metadata_extracted": extracted_count,
                "metadata_pending": total_items - extracted_count,
            }

            self.logger.debug(f"Generated database statistics: {stats}")
            return stats

        except SQLAlchemyError as e:
            self.logger.error(f"Error generating database statistics: {e}")
            raise
        finally:
            if not external_session:
                session.close()

    def get_content_by_path(
        self, file_path: str, session: Optional[Session] = None
    ) -> Optional[ContentItem]:
        external_session = session is not None
        session = session or self.database_service.Session()

        try:
            item = (
                session.query(ContentItem)
                .options(joinedload(ContentItem.tags))
                .filter(ContentItem.path == file_path)
                .first()
            )

            if item and not external_session:
                # If the session is not external, detach the object after loading tags
                session.expunge(item)

            return item

        except Exception as e:
            self.logger.error(f"Error retrieving content by path {file_path}: {e}")
            return None
        finally:
            if not external_session:
                session.close()

    def get_uncategorized_items(
        self, content_type: Optional[str] = None, session: Optional[Session] = None
    ) -> List[ContentItem]:
        external_session = session is not None
        session = session or self.database_service.Session()

        try:
            query = session.query(ContentItem).filter(ContentItem.category.is_(None))

            if content_type:
                query = query.filter(ContentItem.content_type == content_type)

            results = list(query.all())
            self.logger.debug(f"Found {len(results)} uncategorized items.")
            return results
        except SQLAlchemyError as e:
            self.logger.error(
                f"Error retrieving uncategorized items: {e}", exc_info=True
            )
            return []
        finally:
            if not external_session:
                session.close()

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

    def get_unique_categories(self, session: Optional[Session] = None) -> List[str]:
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

    def get_unique_years(self, session: Optional[Session] = None) -> List[int]:
        external_session = session is not None
        session = session or self.database_service.Session()
        try:
            # Build years from all relevant sources, not only date_created.
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
                # Backward-compatible row parsing for tests/mocks that may return
                # legacy 1-column tuples.
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

                # 1) Dedicated image field
                if isinstance(year_taken, int) and 1900 <= year_taken <= 2100:
                    years.add(year_taken)
                elif year_taken is not None:
                    parsed = self._extract_year(year_taken)
                    if parsed is not None:
                        years.add(parsed)

                # 2) SQL date fields
                for dt in (date_created, date_modified, date_indexed):
                    if hasattr(dt, "year"):
                        y = int(dt.year)
                        if 1900 <= y <= 2100:
                            years.add(y)

                # 3) Flexible metadata dates (EXIF and extractor-specific keys)
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

                # 4) Filesystem fallback (align with columns Date display)
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

        # Direct integer case.
        if isinstance(raw_value, int):
            return raw_value if 1900 <= raw_value <= 2100 else None

        text = str(raw_value).strip()
        if not text:
            return None

        # Common date strings: keep first valid 4-digit year.
        match = re.search(r"(19\d{2}|20\d{2}|2100)", text)
        if not match:
            return None

        year = int(match.group(1))
        return year if 1900 <= year <= 2100 else None

    def get_unique_extensions(self, session: Optional[Session] = None) -> List[str]:
        external_session = session is not None
        session = session or self.database_service.Session()
        try:
            # Build extensions from basename and keep only last suffix part.
            # Example: "archive.tar.gz" -> "gz"
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
