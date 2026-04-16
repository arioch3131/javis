"""Read operation classes for content database queries."""

from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from ai_content_classifier.models.content_models import ContentItem
from ai_content_classifier.repositories.content_repository import ContentFilter


class FindItemsOperation:
    def execute(
        self,
        reader: Any,
        content_filter: Optional[ContentFilter] = None,
        sort_by: Optional[str] = None,
        sort_desc: bool = False,
        limit: Optional[int] = None,
        offset: int = 0,
        eager_load: bool = False,
        custom_filter: Optional[List[Any]] = None,
        session: Optional[Session] = None,
    ) -> List[ContentItem]:
        if session is not None or reader.query_optimizer is None:
            results = reader._find_items_uncached(
                content_filter=content_filter,
                sort_by=sort_by,
                sort_desc=sort_desc,
                limit=limit,
                offset=offset,
                eager_load=eager_load,
                custom_filter=custom_filter,
                session=session,
            )
        else:
            cache_key = reader._build_cache_key(
                "find_items",
                getattr(content_filter, "criteria", None) if content_filter else None,
                sort_by,
                sort_desc,
                limit,
                offset,
                eager_load,
                custom_filter,
            )

            results = reader.query_optimizer.execute_cached(
                lambda cached_session: reader._find_items_uncached(
                    content_filter=content_filter,
                    sort_by=sort_by,
                    sort_desc=sort_desc,
                    limit=limit,
                    offset=offset,
                    eager_load=eager_load,
                    custom_filter=custom_filter,
                    session=cached_session,
                ),
                cache_key=cache_key,
            )

        if reader.metrics is not None and hasattr(reader.metrics, "visible_items"):
            reader.metrics.visible_items = len(results)
        return results


class CountAllItemsOperation:
    def execute(self, reader: Any, session: Optional[Session] = None) -> int:
        if session is None and reader.query_optimizer is not None:
            count = reader.query_optimizer.execute_cached(
                lambda cached_session: reader._count_all_items_uncached(cached_session),
                cache_key="count_all_items",
            )
        else:
            count = reader._count_all_items_uncached(session)

        if reader.metrics is not None and hasattr(reader.metrics, "total_files"):
            reader.metrics.total_files = count
        return count


class GetItemsPendingMetadataOperation:
    def execute(
        self,
        reader: Any,
        content_type: Optional[str] = None,
        limit: Optional[int] = None,
        eager_load: bool = False,
        session: Optional[Session] = None,
    ) -> List[ContentItem]:
        external_session = session is not None
        session = session or reader.database_service.Session()

        try:
            query = session.query(ContentItem).filter(
                not ContentItem.metadata_extracted
            )

            if content_type:
                query = query.filter(ContentItem.content_type == content_type)

            query = reader._configure_loading_options(query, eager_load)

            if limit is not None:
                query = query.limit(limit)

            results = list(query.all())
            reader.logger.debug(
                f"Found {len(results)} items pending metadata extraction."
            )
            return results

        except Exception as exc:
            reader.logger.error(f"Error retrieving pending metadata items: {exc}")
            raise
        finally:
            if not external_session:
                session.close()


class FindDuplicatesOperation:
    def execute(
        self,
        reader: Any,
        session: Optional[Session] = None,
    ) -> Dict[str, List[ContentItem]]:
        external_session = session is not None
        session = session or reader.database_service.Session()

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

            result: Dict[str, List[ContentItem]] = {}
            for item in duplicates:
                if item.file_hash not in result:
                    result[item.file_hash] = []
                result[item.file_hash].append(item)

            reader.logger.debug(f"Found {len(result)} sets of duplicate files.")
            return result

        except SQLAlchemyError as exc:
            reader.logger.error(f"Error finding duplicate content items: {exc}")
            raise
        finally:
            if not external_session:
                session.close()


class GetStatisticsOperation:
    def execute(
        self,
        reader: Any,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        external_session = session is not None
        session = session or reader.database_service.Session()

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

            reader.logger.debug(f"Generated database statistics: {stats}")
            return stats

        except SQLAlchemyError as exc:
            reader.logger.error(f"Error generating database statistics: {exc}")
            raise
        finally:
            if not external_session:
                session.close()


class GetContentByPathOperation:
    def execute(
        self,
        reader: Any,
        file_path: str,
        session: Optional[Session] = None,
    ) -> Optional[ContentItem]:
        external_session = session is not None
        session = session or reader.database_service.Session()

        try:
            item = (
                session.query(ContentItem)
                .options(joinedload(ContentItem.tags))
                .filter(ContentItem.path == file_path)
                .first()
            )

            if item and not external_session:
                session.expunge(item)

            return item

        except Exception as exc:
            reader.logger.error(f"Error retrieving content by path {file_path}: {exc}")
            return None
        finally:
            if not external_session:
                session.close()


class GetUncategorizedItemsOperation:
    def execute(
        self,
        reader: Any,
        content_type: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> List[ContentItem]:
        external_session = session is not None
        session = session or reader.database_service.Session()

        try:
            query = session.query(ContentItem).filter(ContentItem.category.is_(None))

            if content_type:
                query = query.filter(ContentItem.content_type == content_type)

            results = list(query.all())
            reader.logger.debug(f"Found {len(results)} uncategorized items.")
            return results
        except SQLAlchemyError as exc:
            reader.logger.error(
                f"Error retrieving uncategorized items: {exc}", exc_info=True
            )
            return []
        finally:
            if not external_session:
                session.close()


class GetUniqueCategoriesOperation:
    def execute(self, reader: Any, session: Optional[Session] = None) -> List[str]:
        if session is None and reader.query_optimizer is not None:
            return reader.query_optimizer.execute_cached(
                lambda cached_session: reader._get_unique_categories_uncached(
                    cached_session
                ),
                cache_key="unique_categories",
            )
        return reader._get_unique_categories_uncached(session)


class GetUniqueYearsOperation:
    def execute(self, reader: Any, session: Optional[Session] = None) -> List[int]:
        if session is None and reader.query_optimizer is not None:
            return reader.query_optimizer.execute_cached(
                lambda cached_session: reader._get_unique_years_uncached(
                    cached_session
                ),
                cache_key="unique_years",
            )
        return reader._get_unique_years_uncached(session)


class GetUniqueExtensionsOperation:
    def execute(self, reader: Any, session: Optional[Session] = None) -> List[str]:
        if session is None and reader.query_optimizer is not None:
            return reader.query_optimizer.execute_cached(
                lambda cached_session: reader._get_unique_extensions_uncached(
                    cached_session
                ),
                cache_key="unique_extensions",
            )
        return reader._get_unique_extensions_uncached(session)
