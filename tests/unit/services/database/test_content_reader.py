import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.exc import SQLAlchemyError

from ai_content_classifier.services.database.content_reader import ContentReader
from ai_content_classifier.services.database.database_service import DatabaseService
from ai_content_classifier.models.content_models import ContentItem, datetime_utcnow
from ai_content_classifier.repositories.content_repository import ContentFilter


class TestContentReader:
    """
    Comprehensive test suite for ContentReader class.
    
    This test suite covers all public methods with various scenarios including
    success cases, error conditions, parameter combinations, and edge cases.
    """

    @pytest.fixture
    def mock_content_item(self):
        """Create a mock ContentItem with realistic attributes."""
        item = MagicMock(spec=ContentItem)
        item.id = 1
        item.path = "/test/path.jpg"
        item.filename = "path.jpg"
        item.directory = "/test"
        item.content_type = "image"
        item.metadata_extracted = True
        item.category = "test_category"
        item.file_hash = "test_hash_123"
        item.date_created = datetime_utcnow()
        item.date_modified = datetime_utcnow()
        item.file_size = 1024
        item.width = 800
        item.height = 600
        item.format = "jpeg"
        item.duration = None
        item.tags = []
        item.collections = []
        item.content_metadata = {}
        return item

    @pytest.fixture
    def mock_db_session(self):
        """Create a comprehensive mock SQLAlchemy session."""
        session = MagicMock()
        
        # Setup query chain methods
        query_mock = MagicMock()
        session.query.return_value = query_mock
        query_mock.filter.return_value = query_mock
        query_mock.options.return_value = query_mock
        query_mock.distinct.return_value = query_mock
        query_mock.group_by.return_value = query_mock
        query_mock.having.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.limit.return_value = query_mock
        query_mock.offset.return_value = query_mock
        
        # Setup default returns
        query_mock.all.return_value = []
        query_mock.first.return_value = None
        query_mock.scalar.return_value = 0  # Pour les appels directs sur query
        session.scalar.return_value = 0     # Pour les appels directs sur session
        session.execute.return_value = MagicMock()
        session.expunge.return_value = None
        
        # Setup session management
        session.close.return_value = None
        session.rollback.return_value = None
        session.commit.return_value = None
        
        return session

    @pytest.fixture
    def mock_database_service(self, mock_db_session):
        """Create a mock DatabaseService."""
        db_service = MagicMock(spec=DatabaseService)
        # Configure Session as a callable that returns mock_db_session
        db_service.Session = MagicMock(return_value=mock_db_session)
        return db_service

    @pytest.fixture
    def mock_content_filter(self):
        """Create a mock ContentFilter."""
        content_filter = MagicMock(spec=ContentFilter)
        content_filter.criteria = []
        content_filter.build.return_value = []
        return content_filter

    @pytest.fixture
    def reader(self, mock_database_service):
        """Create ContentReader instance with mocked dependencies."""
        with patch('ai_content_classifier.services.database.content_reader.ContentItem', ContentItem):
            # Mock the logger initialization to avoid any issues
            with patch.object(ContentReader, '__init_logger__'):
                reader = ContentReader(mock_database_service)
                # Manually set the logger mock
                reader.logger = MagicMock()
                return reader

    # ==================== INITIALIZATION TESTS ====================

    def test_init_success(self, mock_database_service):
        """Test successful ContentReader initialization."""
        with patch('ai_content_classifier.services.database.content_reader.ContentItem', ContentItem):
            with patch.object(ContentReader, '__init_logger__'):
                reader = ContentReader(mock_database_service)
                assert reader.database_service == mock_database_service

    # ==================== FIND_ITEMS TESTS ====================

    def test_find_items_basic(self, reader, mock_db_session, mock_content_item):
        """Test basic find_items functionality."""
        mock_db_session.query.return_value.all.return_value = [mock_content_item]
        
        items = reader.find_items()
        
        assert len(items) == 1
        assert items[0] == mock_content_item
        mock_db_session.query.assert_called_once_with(ContentItem)
        reader.logger.debug.assert_called()

    def test_find_items_with_content_filter(self, reader, mock_db_session, mock_content_filter, mock_content_item):
        """Test find_items with ContentFilter."""
        mock_content_filter.build.return_value = [ContentItem.content_type == "image"]
        mock_content_filter.criteria = [ContentItem.content_type == "image"]
        mock_db_session.query.return_value.all.return_value = [mock_content_item]

        items = reader.find_items(content_filter=mock_content_filter)
        
        assert len(items) == 1
        mock_content_filter.build.assert_called_once()
        mock_db_session.query.return_value.filter.assert_called_once()

    def test_find_items_with_custom_filter(self, reader, mock_db_session, mock_content_item):
        """Test find_items with custom filter criteria."""
        custom_filter = [ContentItem.file_size > 100]
        mock_db_session.query.return_value.all.return_value = [mock_content_item]

        items = reader.find_items(custom_filter=custom_filter)
        
        assert len(items) == 1
        mock_db_session.query.return_value.filter.assert_called_once_with(*custom_filter)

    def test_find_items_with_both_filters(self, reader, mock_db_session, mock_content_filter, mock_content_item):
        """Test find_items with both content_filter and custom_filter."""
        mock_content_filter.build.return_value = [ContentItem.content_type == "image"]
        custom_filter = [ContentItem.file_size > 100]
        mock_db_session.query.return_value.all.return_value = [mock_content_item]

        items = reader.find_items(content_filter=mock_content_filter, custom_filter=custom_filter)
        
        assert len(items) == 1
        # Should call filter once with all criteria combined
        mock_db_session.query.return_value.filter.assert_called_once()
        # Verify the filter was called with some arguments (exact matching is complex due to SQLAlchemy objects)
        call_args = mock_db_session.query.return_value.filter.call_args
        assert call_args is not None
        assert len(call_args[0]) == 2  # Should have 2 filter criteria

    def test_find_items_with_sorting(self, reader, mock_db_session, mock_content_item):
        """Test find_items with sorting parameters."""
        mock_db_session.query.return_value.all.return_value = [mock_content_item]

        # Test ascending sort
        items = reader.find_items(sort_by="path", sort_desc=False)
        assert len(items) == 1
        mock_db_session.query.return_value.order_by.assert_called_once()

        # Reset and test descending sort
        mock_db_session.reset_mock()
        mock_db_session.query.return_value.all.return_value = [mock_content_item]
        
        items = reader.find_items(sort_by="path", sort_desc=True)
        assert len(items) == 1
        mock_db_session.query.return_value.order_by.assert_called_once()

    def test_find_items_with_pagination(self, reader, mock_db_session, mock_content_item):
        """Test find_items with limit and offset."""
        mock_db_session.query.return_value.all.return_value = [mock_content_item]

        items = reader.find_items(limit=10, offset=5)
        
        assert len(items) == 1
        mock_db_session.query.return_value.limit.assert_called_once_with(10)
        mock_db_session.query.return_value.offset.assert_called_once_with(5)

    def test_find_items_offset_without_limit(self, reader, mock_db_session, mock_content_item):
        """Test find_items with offset but no limit."""
        mock_db_session.query.return_value.all.return_value = [mock_content_item]

        items = reader.find_items(offset=5)
        
        assert len(items) == 1
        # Limit should not be called when not specified
        mock_db_session.query.return_value.limit.assert_not_called()
        mock_db_session.query.return_value.offset.assert_not_called()

    def test_find_items_with_eager_load(self, reader, mock_db_session, mock_content_item):
        """Test find_items with eager loading enabled."""
        mock_db_session.query.return_value.all.return_value = [mock_content_item]

        items = reader.find_items(eager_load=True)
        
        assert len(items) == 1
        # Should call options for eager loading
        mock_db_session.query.return_value.options.assert_called()
        # Check that multiple options calls were made (for eager load and essential loading)
        assert mock_db_session.query.return_value.options.call_count >= 1

    def test_find_items_complex_combination(self, reader, mock_db_session, mock_content_filter, mock_content_item):
        """Test find_items with multiple parameters combined."""
        mock_content_filter.build.return_value = [ContentItem.content_type == "image"]
        custom_filter = [ContentItem.file_size > 100]
        mock_db_session.query.return_value.all.return_value = [mock_content_item]

        items = reader.find_items(
            content_filter=mock_content_filter,
            custom_filter=custom_filter,
            sort_by="path",
            sort_desc=True,
            limit=5,
            offset=10,
            eager_load=True
        )
        
        assert len(items) == 1
        # Verify all components were called
        mock_db_session.query.return_value.filter.assert_called_once()
        mock_db_session.query.return_value.options.assert_called()
        mock_db_session.query.return_value.order_by.assert_called_once()
        mock_db_session.query.return_value.limit.assert_called_once_with(5)
        mock_db_session.query.return_value.offset.assert_called_once_with(10)

    def test_find_items_no_results_debug_case(self, reader, mock_db_session):
        """Test find_items debug logging when no results found."""
        # Reset any previous side_effects
        mock_db_session.query.side_effect = None
        
        # Setup main query to return empty results
        main_query = MagicMock()
        main_query.filter.return_value = main_query
        main_query.options.return_value = main_query
        main_query.all.return_value = []
        
        # Setup count query
        count_query = MagicMock()
        count_query.scalar.return_value = 5
        
        # Setup simple debug query
        simple_query = MagicMock()
        simple_query.limit.return_value.all.return_value = []
        
        # Configure multiple query calls in order
        mock_db_session.query.side_effect = [main_query, count_query, simple_query]

        items = reader.find_items()
        
        assert len(items) == 0
        # Should have called query 3 times (main, count, simple)
        assert mock_db_session.query.call_count >= 3
        reader.logger.warning.assert_called_once()
        reader.logger.info.assert_called_once()

    def test_find_items_sqlalchemy_error(self, reader, mock_db_session):
        """Test find_items with SQLAlchemy error."""
        mock_db_session.query.return_value.all.side_effect = SQLAlchemyError("Database error")

        with pytest.raises(SQLAlchemyError, match="Database error"):
            reader.find_items()
        
        reader.logger.error.assert_called_once()

    def test_find_items_with_external_session(self, reader, mock_db_session, mock_content_item):
        """Test find_items with external session provided."""
        mock_db_session.query.return_value.all.return_value = [mock_content_item]

        items = reader.find_items(session=mock_db_session)
        
        assert len(items) == 1
        # External session should not be closed
        mock_db_session.close.assert_not_called()

    def test_find_items_invalid_sort_column(self, reader, mock_db_session, mock_content_item):
        """Test find_items with invalid sort column."""
        mock_db_session.query.return_value.all.return_value = [mock_content_item]

        items = reader.find_items(sort_by="invalid_column")
        
        assert len(items) == 1
        reader.logger.warning.assert_called_once()
        # order_by should not be called for invalid column
        mock_db_session.query.return_value.order_by.assert_not_called()

    # ==================== COUNT_ALL_ITEMS TESTS ====================

    def test_count_all_items_success(self, reader, mock_db_session):
        """Test successful count_all_items."""
        # Configure the query chain to return 10
        mock_db_session.query.return_value.scalar.return_value = 10

        count = reader.count_all_items()
        
        assert count == 10
        mock_db_session.query.assert_called_once()
        reader.logger.debug.assert_called_once()

    def test_count_all_items_exception(self, reader, mock_db_session):
        """Test count_all_items with exception."""
        # Reset any previous side_effects
        mock_db_session.query.side_effect = None
        mock_db_session.query.return_value.scalar.side_effect = Exception("Count error")

        count = reader.count_all_items()
        
        assert count == 0
        reader.logger.error.assert_called_once()

    def test_count_all_items_with_external_session(self, reader, mock_db_session):
        """Test count_all_items with external session."""
        mock_db_session.query.return_value.scalar.return_value = 15

        count = reader.count_all_items(session=mock_db_session)
        
        assert count == 15
        mock_db_session.close.assert_not_called()

    # ==================== GET_ITEMS_PENDING_METADATA TESTS ====================

    def test_get_items_pending_metadata_basic(self, reader, mock_db_session, mock_content_item):
        """Test basic get_items_pending_metadata."""
        mock_content_item.metadata_extracted = False
        mock_db_session.query.return_value.all.return_value = [mock_content_item]

        items = reader.get_items_pending_metadata()
        
        assert len(items) == 1
        mock_db_session.query.return_value.filter.assert_called()
        reader.logger.debug.assert_called_once()

    def test_get_items_pending_metadata_with_content_type(self, reader, mock_db_session, mock_content_item):
        """Test get_items_pending_metadata with content type filter."""
        mock_content_item.metadata_extracted = False
        mock_db_session.query.return_value.all.return_value = [mock_content_item]

        items = reader.get_items_pending_metadata(content_type="image")
        
        assert len(items) == 1
        # Should have two filter calls: metadata_extracted and content_type
        assert mock_db_session.query.return_value.filter.call_count == 2

    def test_get_items_pending_metadata_with_limit(self, reader, mock_db_session, mock_content_item):
        """Test get_items_pending_metadata with limit."""
        mock_content_item.metadata_extracted = False
        mock_db_session.query.return_value.all.return_value = [mock_content_item]

        items = reader.get_items_pending_metadata(limit=5)
        
        assert len(items) == 1
        mock_db_session.query.return_value.limit.assert_called_once_with(5)

    def test_get_items_pending_metadata_with_eager_load(self, reader, mock_db_session, mock_content_item):
        """Test get_items_pending_metadata with eager loading."""
        mock_content_item.metadata_extracted = False
        mock_db_session.query.return_value.all.return_value = [mock_content_item]

        items = reader.get_items_pending_metadata(eager_load=True)
        
        assert len(items) == 1
        mock_db_session.query.return_value.options.assert_called()

    def test_get_items_pending_metadata_combination(self, reader, mock_db_session, mock_content_item):
        """Test get_items_pending_metadata with multiple parameters."""
        mock_content_item.metadata_extracted = False
        mock_db_session.query.return_value.all.return_value = [mock_content_item]

        items = reader.get_items_pending_metadata(
            content_type="image",
            limit=10,
            eager_load=True
        )
        
        assert len(items) == 1
        assert mock_db_session.query.return_value.filter.call_count == 2
        mock_db_session.query.return_value.limit.assert_called_once_with(10)
        mock_db_session.query.return_value.options.assert_called()

    def test_get_items_pending_metadata_exception(self, reader, mock_db_session):
        """Test get_items_pending_metadata with exception."""
        mock_db_session.query.return_value.all.side_effect = Exception("Pending error")

        with pytest.raises(Exception, match="Pending error"):
            reader.get_items_pending_metadata()
        
        reader.logger.error.assert_called_once()

    def test_get_items_pending_metadata_with_external_session(self, reader, mock_db_session, mock_content_item):
        """Test get_items_pending_metadata with external session."""
        mock_content_item.metadata_extracted = False
        mock_db_session.query.return_value.all.return_value = [mock_content_item]

        items = reader.get_items_pending_metadata(session=mock_db_session)
        
        assert len(items) == 1
        mock_db_session.close.assert_not_called()

    # ==================== FIND_DUPLICATES TESTS ====================

    def test_find_duplicates_no_duplicates(self, reader, mock_db_session):
        """Test find_duplicates when no duplicates exist."""
        mock_db_session.query.return_value.all.return_value = []

        duplicates = reader.find_duplicates()
        
        assert duplicates == {}

    def test_find_duplicates_with_duplicates(self, reader, mock_db_session, mock_content_item):
        """Test find_duplicates with actual duplicates."""
        # First call returns duplicate hashes
        # Second call returns the actual items with those hashes
        item1 = MagicMock(spec=ContentItem)
        item1.file_hash = "hash1"
        item1.id = 1
        item2 = MagicMock(spec=ContentItem) 
        item2.file_hash = "hash1"
        item2.id = 2
        item3 = MagicMock(spec=ContentItem)
        item3.file_hash = "hash2"
        item3.id = 3
        
        mock_db_session.query.return_value.all.side_effect = [
            [("hash1",), ("hash2",)],  # First call for duplicate hashes
            [item1, item2, item3]      # Second call for items with those hashes
        ]

        duplicates = reader.find_duplicates()
        
        assert len(duplicates) == 2
        assert "hash1" in duplicates
        assert "hash2" in duplicates
        assert len(duplicates["hash1"]) == 2
        assert len(duplicates["hash2"]) == 1
        reader.logger.debug.assert_called_once()

    def test_find_duplicates_sqlalchemy_error(self, reader, mock_db_session):
        """Test find_duplicates with SQLAlchemy error."""
        mock_db_session.query.return_value.all.side_effect = SQLAlchemyError("Duplicate error")

        with pytest.raises(SQLAlchemyError, match="Duplicate error"):
            reader.find_duplicates()
        
        reader.logger.error.assert_called_once()

    def test_find_duplicates_with_external_session(self, reader, mock_db_session):
        """Test find_duplicates with external session."""
        mock_db_session.query.return_value.all.return_value = []

        duplicates = reader.find_duplicates(session=mock_db_session)
        
        assert duplicates == {}
        mock_db_session.close.assert_not_called()

    # ==================== GET_STATISTICS TESTS ====================

    def test_get_statistics_success(self, reader, mock_db_session):
        """Test successful get_statistics."""
        # Reset any previous side_effects  
        mock_db_session.query.side_effect = None
        # Configure multiple scalar calls and one all call
        mock_db_session.query.return_value.scalar.side_effect = [10, 7]  # total_items, extracted_count
        mock_db_session.query.return_value.all.return_value = [("image", 6), ("document", 4)]

        stats = reader.get_statistics()
        
        assert stats["total_items"] == 10
        assert stats["items_by_type"] == {"image": 6, "document": 4}
        assert stats["metadata_extracted"] == 7
        assert stats["metadata_pending"] == 3
        reader.logger.debug.assert_called_once()

    def test_get_statistics_sqlalchemy_error(self, reader, mock_db_session):
        """Test get_statistics with SQLAlchemy error."""
        # Reset any previous side_effects
        mock_db_session.query.side_effect = None
        mock_db_session.query.return_value.scalar.side_effect = SQLAlchemyError("Stats error")

        with pytest.raises(SQLAlchemyError, match="Stats error"):
            reader.get_statistics()
        
        reader.logger.error.assert_called_once()

    def test_get_statistics_with_external_session(self, reader, mock_db_session):
        """Test get_statistics with external session."""
        # Reset any previous side_effects
        mock_db_session.query.side_effect = None
        mock_db_session.query.return_value.scalar.side_effect = [5, 3]
        mock_db_session.query.return_value.all.return_value = [("image", 5)]

        stats = reader.get_statistics(session=mock_db_session)
        
        assert stats["total_items"] == 5
        mock_db_session.close.assert_not_called()

    # ==================== GET_CONTENT_BY_PATH TESTS ====================

    def test_get_content_by_path_found(self, reader, mock_db_session, mock_content_item):
        """Test get_content_by_path when item is found."""
        mock_db_session.query.return_value.first.return_value = mock_content_item

        item = reader.get_content_by_path("/test/path.jpg")
        
        assert item == mock_content_item
        mock_db_session.query.return_value.options.assert_called_once()
        mock_db_session.query.return_value.filter.assert_called_once()
        # Should call expunge when using internal session
        mock_db_session.expunge.assert_called_once_with(mock_content_item)

    def test_get_content_by_path_not_found(self, reader, mock_db_session):
        """Test get_content_by_path when item is not found."""
        mock_db_session.query.return_value.first.return_value = None

        item = reader.get_content_by_path("/notfound/path.jpg")
        
        assert item is None
        # Should not call expunge when no item found
        mock_db_session.expunge.assert_not_called()

    def test_get_content_by_path_exception(self, reader, mock_db_session):
        """Test get_content_by_path with exception."""
        mock_db_session.query.return_value.first.side_effect = Exception("Path error")

        item = reader.get_content_by_path("/error/path.jpg")
        
        assert item is None
        reader.logger.error.assert_called_once()

    def test_get_content_by_path_with_external_session(self, reader, mock_db_session, mock_content_item):
        """Test get_content_by_path with external session."""
        mock_db_session.query.return_value.first.return_value = mock_content_item

        item = reader.get_content_by_path("/test/path.jpg", session=mock_db_session)
        
        assert item == mock_content_item
        mock_db_session.close.assert_not_called()
        # Should not call expunge with external session
        mock_db_session.expunge.assert_not_called()

    # ==================== GET_UNCATEGORIZED_ITEMS TESTS ====================

    def test_get_uncategorized_items_basic(self, reader, mock_db_session, mock_content_item):
        """Test basic get_uncategorized_items."""
        mock_content_item.category = None
        mock_db_session.query.return_value.all.return_value = [mock_content_item]

        items = reader.get_uncategorized_items()
        
        assert len(items) == 1
        mock_db_session.query.return_value.filter.assert_called_once()
        reader.logger.debug.assert_called_once()

    def test_get_uncategorized_items_with_content_type(self, reader, mock_db_session, mock_content_item):
        """Test get_uncategorized_items with content type filter."""
        mock_content_item.category = None
        mock_db_session.query.return_value.all.return_value = [mock_content_item]

        items = reader.get_uncategorized_items(content_type="image")
        
        assert len(items) == 1
        # Should have two filter calls
        assert mock_db_session.query.return_value.filter.call_count == 2

    def test_get_uncategorized_items_sqlalchemy_error(self, reader, mock_db_session):
        """Test get_uncategorized_items with SQLAlchemy error."""
        mock_db_session.query.return_value.all.side_effect = SQLAlchemyError("Uncategorized error")

        items = reader.get_uncategorized_items()
        
        assert items == []
        reader.logger.error.assert_called_once()

    def test_get_uncategorized_items_with_external_session(self, reader, mock_db_session, mock_content_item):
        """Test get_uncategorized_items with external session."""
        mock_content_item.category = None
        mock_db_session.query.return_value.all.return_value = [mock_content_item]

        items = reader.get_uncategorized_items(session=mock_db_session)
        
        assert len(items) == 1
        mock_db_session.close.assert_not_called()

    # ==================== GET_UNIQUE_CATEGORIES TESTS ====================

    def test_get_unique_categories_success(self, reader, mock_db_session):
        """Test successful get_unique_categories."""
        mock_db_session.query.return_value.all.return_value = [("image",), ("document",)]

        categories = reader.get_unique_categories()
        
        assert categories == ["image", "document"]

    def test_get_unique_categories_sqlalchemy_error(self, reader, mock_db_session):
        """Test get_unique_categories with SQLAlchemy error."""
        mock_db_session.query.return_value.all.side_effect = SQLAlchemyError("Categories error")

        categories = reader.get_unique_categories()
        
        assert categories == []
        reader.logger.error.assert_called_once()

    def test_get_unique_categories_with_external_session(self, reader, mock_db_session):
        """Test get_unique_categories with external session."""
        mock_db_session.query.return_value.all.return_value = [("test",)]

        categories = reader.get_unique_categories(session=mock_db_session)
        
        assert categories == ["test"]
        mock_db_session.close.assert_not_called()

    # ==================== GET_UNIQUE_YEARS TESTS ====================

    def test_get_unique_years_success(self, reader, mock_db_session):
        """Test successful get_unique_years."""
        mock_db_session.query.return_value.all.return_value = [("2022",), ("2023",)]

        years = reader.get_unique_years()
        
        assert years == [2022, 2023]

    def test_get_unique_years_with_invalid_data(self, reader, mock_db_session):
        """Test get_unique_years with invalid year data."""
        mock_db_session.query.return_value.all.return_value = [("invalid",), ("2023",)]

        years = reader.get_unique_years()
        
        assert years == [2023]  # Should filter out invalid year

    def test_get_unique_years_sqlalchemy_error(self, reader, mock_db_session):
        """Test get_unique_years with SQLAlchemy error."""
        mock_db_session.query.return_value.all.side_effect = SQLAlchemyError("Years error")

        years = reader.get_unique_years()
        
        assert years == []
        reader.logger.error.assert_called_once()

    def test_get_unique_years_with_external_session(self, reader, mock_db_session):
        """Test get_unique_years with external session."""
        mock_db_session.query.return_value.all.return_value = [("2024",)]

        years = reader.get_unique_years(session=mock_db_session)
        
        assert years == [2024]
        mock_db_session.close.assert_not_called()

    # ==================== GET_UNIQUE_EXTENSIONS TESTS ====================

    def test_get_unique_extensions_success(self, reader, mock_db_session):
        """Test successful get_unique_extensions."""
        mock_db_session.query.return_value.all.return_value = [(".jpg",), (".pdf",)]

        extensions = reader.get_unique_extensions()
        
        assert extensions == [".jpg", ".pdf"]

    def test_get_unique_extensions_with_empty_results(self, reader, mock_db_session):
        """Test get_unique_extensions with empty or None results."""
        mock_db_session.query.return_value.all.return_value = [("",), (".pdf",), (None,)]

        extensions = reader.get_unique_extensions()
        
        assert extensions == [".pdf"]  # Should filter out empty and None

    def test_get_unique_extensions_sqlalchemy_error(self, reader, mock_db_session):
        """Test get_unique_extensions with SQLAlchemy error."""
        mock_db_session.query.return_value.all.side_effect = SQLAlchemyError("Extensions error")

        extensions = reader.get_unique_extensions()
        
        assert extensions == []
        reader.logger.error.assert_called_once()

    def test_get_unique_extensions_with_external_session(self, reader, mock_db_session):
        """Test get_unique_extensions with external session."""
        mock_db_session.query.return_value.all.return_value = [(".txt",)]

        extensions = reader.get_unique_extensions(session=mock_db_session)
        
        assert extensions == [".txt"]
        mock_db_session.close.assert_not_called()

    # ==================== PRIVATE METHODS INTEGRATION TESTS ====================

    def test_private_methods_integration(self, reader, mock_db_session, mock_content_item):
        """Test that private methods are properly called through public methods."""
        mock_db_session.query.return_value.all.return_value = [mock_content_item]
        
        # Test _build_find_query, _configure_loading_options, _get_essential_loading_options
        items = reader.find_items(eager_load=True, sort_by="path")
        
        assert len(items) == 1
        # Verify that options was called (from _configure_loading_options)
        mock_db_session.query.return_value.options.assert_called()
        # Verify that order_by was called (from _apply_sorting)
        mock_db_session.query.return_value.order_by.assert_called()

    def test_session_transaction_handling(self, reader, mock_db_session):
        """Test that session transaction handling works correctly."""
        # Test that BEGIN IMMEDIATE is attempted for internal sessions
        mock_db_session.execute.return_value = None
        mock_db_session.rollback.return_value = None
        mock_db_session.query.return_value.all.return_value = []
        
        reader.find_items()
        
        # Should attempt to execute transaction setup
        mock_db_session.execute.assert_called()
        mock_db_session.close.assert_called_once()

    # ==================== EDGE CASES AND ERROR CONDITIONS ====================

    def test_logging_behavior(self, reader, mock_db_session, mock_content_item):
        """Test that appropriate logging occurs in various scenarios."""
        mock_db_session.query.return_value.all.return_value = [mock_content_item]
        
        # Test debug logging for successful operations
        reader.find_items()
        reader.logger.debug.assert_called()
        
        # Reset and test warning for invalid sort
        reader.logger.reset_mock()
        reader.find_items(sort_by="invalid_column")
        reader.logger.warning.assert_called()

    def test_empty_database_scenarios(self, reader, mock_db_session):
        """Test behavior with empty database."""
        mock_db_session.query.return_value.all.return_value = []
        mock_db_session.query.return_value.scalar.return_value = 0
        
        # Test various methods with empty results
        assert reader.find_items() == []
        assert reader.count_all_items() == 0
        assert reader.get_items_pending_metadata() == []
        assert reader.find_duplicates() == {}
        assert reader.get_uncategorized_items() == []
        assert reader.get_unique_categories() == []
        assert reader.get_unique_years() == []
        assert reader.get_unique_extensions() == []
