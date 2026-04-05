import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ai_content_classifier.services.database.content_writer import ContentWriter
from ai_content_classifier.models.content_models import (
    ContentItem,
    Image,
    Document,
    Video,
    Audio,
)


class TestContentWriter:
    @pytest.fixture
    def mock_database_service(self):
        mock_service = Mock()
        mock_session = Mock(spec=Session)
        mock_service.Session.return_value = mock_session
        return mock_service, mock_session

    @pytest.fixture
    def mock_repos(self):
        return Mock()

    @pytest.fixture
    def content_writer(self, mock_database_service, mock_repos):
        db_service, _ = mock_database_service
        return ContentWriter(db_service, mock_repos)

    @pytest.fixture
    def sample_metadata(self):
        return {
            "camera": "Canon EOS R5",
            "iso": 800,
            "created_date": datetime(2023, 1, 15),
            "tags": ["landscape", "nature"],
        }

    def test_create_content_item_success_image(
        self, content_writer, mock_database_service, sample_metadata
    ):
        db_service, mock_session = mock_database_service

        with (
            patch("os.path.exists", return_value=True),
            patch("os.path.getsize", return_value=1024000),
            patch(
                "ai_content_classifier.services.database.utils.serialize_metadata_for_json"
            ) as mock_serialize,
        ):
            mock_serialize.return_value = {"serialized": "metadata"}

            result = content_writer.create_content_item(
                path="/test/image.jpg",
                content_type="image",
                extract_basic_info=True,
                metadata=sample_metadata,
            )

            assert isinstance(result, Image)
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()
            mock_session.refresh.assert_called_once()
            mock_serialize.assert_called_once_with(sample_metadata)

    def test_create_content_item_success_document(
        self, content_writer, mock_database_service
    ):
        db_service, mock_session = mock_database_service

        with patch("os.path.exists", return_value=False):
            result = content_writer.create_content_item(
                path="/test/document.pdf",
                content_type="document",
                extract_basic_info=False,
            )

            assert isinstance(result, Document)
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()

    def test_create_content_item_success_video(
        self, content_writer, mock_database_service
    ):
        db_service, mock_session = mock_database_service

        result = content_writer.create_content_item(
            path="/test/video.mp4", content_type="video"
        )

        assert isinstance(result, Video)

    def test_create_content_item_success_audio(
        self, content_writer, mock_database_service
    ):
        db_service, mock_session = mock_database_service

        result = content_writer.create_content_item(
            path="/test/audio.mp3", content_type="audio"
        )

        assert isinstance(result, Audio)

    def test_create_content_item_success_generic(
        self, content_writer, mock_database_service
    ):
        db_service, mock_session = mock_database_service

        result = content_writer.create_content_item(
            path="/test/file.txt", content_type="unknown"
        )

        assert isinstance(result, ContentItem)
        assert not isinstance(result, (Image, Document, Video, Audio))

    def test_create_content_item_with_external_session(
        self, content_writer, mock_database_service
    ):
        db_service, mock_session = mock_database_service
        external_session = Mock(spec=Session)

        content_writer.create_content_item(
            path="/test/image.jpg", content_type="image", session=external_session
        )

        external_session.add.assert_called_once()
        external_session.flush.assert_called_once()
        external_session.commit.assert_not_called()
        external_session.close.assert_not_called()

    def test_create_content_item_no_refresh(
        self, content_writer, mock_database_service
    ):
        db_service, mock_session = mock_database_service

        content_writer.create_content_item(
            path="/test/image.jpg", content_type="image", refresh=False
        )

        mock_session.refresh.assert_not_called()

    def test_create_content_item_validation_errors(self, content_writer):
        # Path vide
        with pytest.raises(ValueError, match="File path cannot be empty"):
            content_writer.create_content_item("", "image")

        # Content type vide
        with pytest.raises(ValueError, match="Content type cannot be empty"):
            content_writer.create_content_item("/test/file.jpg", "")

    def test_create_content_item_os_error_file_size(
        self, content_writer, mock_database_service
    ):
        db_service, mock_session = mock_database_service

        with (
            patch("os.path.exists", return_value=True),
            patch("os.path.getsize", side_effect=OSError("Permission denied")),
        ):
            result = content_writer.create_content_item(
                path="/test/image.jpg", content_type="image", extract_basic_info=True
            )

            assert isinstance(result, Image)
            mock_session.add.assert_called_once()

    def test_create_content_item_sqlalchemy_error(
        self, content_writer, mock_database_service
    ):
        db_service, mock_session = mock_database_service
        mock_session.add.side_effect = SQLAlchemyError("Database error")

        with pytest.raises(SQLAlchemyError):
            content_writer.create_content_item(
                path="/test/image.jpg", content_type="image"
            )

        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()

    def test_create_content_item_sqlalchemy_error_external_session(
        self, content_writer, mock_database_service
    ):
        db_service, mock_session = mock_database_service
        external_session = Mock(spec=Session)
        external_session.add.side_effect = SQLAlchemyError("Database error")

        with pytest.raises(SQLAlchemyError):
            content_writer.create_content_item(
                path="/test/image.jpg", content_type="image", session=external_session
            )

        external_session.rollback.assert_not_called()
        external_session.close.assert_not_called()

    def test_create_content_item_returns_existing_item(
        self, content_writer, mock_database_service
    ):
        db_service, mock_session = mock_database_service
        existing = ContentItem(
            path="/test/existing.jpg",
            filename="existing.jpg",
            directory="/test",
            content_type="image",
        )
        mock_session.query.return_value.filter.return_value.first.return_value = (
            existing
        )

        with patch.object(content_writer, "_update_existing_item") as mock_update:
            result = content_writer.create_content_item(
                path="/test/existing.jpg",
                content_type="image",
                metadata={"year": 2020},
            )

        assert result is existing
        mock_update.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once_with(existing)

    def test_save_item_batch_success(self, content_writer, mock_database_service):
        db_service, mock_session = mock_database_service

        items = [
            {
                "path": "/test/image1.jpg",
                "content_type": "image",
                "filename": "image1.jpg",
                "width": 1920,
                "height": 1080,
            },
            {
                "path": "/test/doc1.pdf",
                "content_type": "document",
                "filename": "doc1.pdf",
                "page_count": 10,
            },
        ]

        with patch.object(
            content_writer, "_create_content_item_from_data"
        ) as mock_create:
            mock_items = [Mock(), Mock()]
            mock_create.side_effect = mock_items

            result = content_writer.save_item_batch(items)

            assert len(result) == 2
            assert mock_session.add.call_count == 2
            mock_session.commit.assert_called_once()
            assert mock_session.refresh.call_count == 2

    def test_save_item_batch_empty_list(self, content_writer):
        result = content_writer.save_item_batch([])
        assert result == []

    def test_save_item_batch_with_invalid_items(
        self, content_writer, mock_database_service
    ):
        db_service, mock_session = mock_database_service

        items = [
            {"path": "/test/image1.jpg", "content_type": "image"},  # Valide
            {"content_type": "image"},  # Invalide - pas de path
            {"path": "", "content_type": "image"},  # Invalide - path vide
            {"path": "/test/doc1.pdf", "content_type": "document"},  # Valide
        ]

        with (
            patch.object(
                content_writer,
                "_is_valid_item_data",
                side_effect=[True, False, False, True],
            ),
            patch.object(
                content_writer, "_create_content_item_from_data"
            ) as mock_create,
        ):
            mock_items = [Mock(), Mock()]
            mock_create.side_effect = mock_items

            result = content_writer.save_item_batch(items)

            assert len(result) == 2
            assert mock_create.call_count == 2

    def test_save_item_batch_with_external_session(
        self, content_writer, mock_database_service
    ):
        db_service, mock_session = mock_database_service
        external_session = Mock(spec=Session)

        items = [{"path": "/test/image1.jpg", "content_type": "image"}]

        with patch.object(
            content_writer, "_create_content_item_from_data", return_value=Mock()
        ):
            content_writer.save_item_batch(items, session=external_session)

            external_session.flush.assert_called_once()
            external_session.commit.assert_not_called()

    def test_save_item_batch_no_refresh(self, content_writer, mock_database_service):
        db_service, mock_session = mock_database_service

        items = [{"path": "/test/image1.jpg", "content_type": "image"}]

        with patch.object(
            content_writer, "_create_content_item_from_data", return_value=Mock()
        ):
            content_writer.save_item_batch(items, refresh=False)

            mock_session.refresh.assert_not_called()

    def test_save_item_batch_sqlalchemy_error(
        self, content_writer, mock_database_service
    ):
        db_service, mock_session = mock_database_service
        mock_session.commit.side_effect = SQLAlchemyError("Database error")

        items = [{"path": "/test/image1.jpg", "content_type": "image"}]

        with patch.object(
            content_writer, "_create_content_item_from_data", return_value=Mock()
        ):
            with pytest.raises(SQLAlchemyError):
                content_writer.save_item_batch(items)

            mock_session.rollback.assert_called_once()

    def test_save_item_batch_updates_existing_item(
        self, content_writer, mock_database_service
    ):
        db_service, mock_session = mock_database_service
        existing = ContentItem(
            path="/test/existing.jpg",
            filename="existing.jpg",
            directory="/test",
            content_type="image",
        )
        mock_session.query.return_value.filter.return_value.first.return_value = (
            existing
        )

        with patch.object(content_writer, "_update_existing_item") as mock_update:
            result = content_writer.save_item_batch(
                [
                    {
                        "path": "/test/existing.jpg",
                        "content_type": "image",
                        "metadata": {"year": 2021},
                    }
                ]
            )

        assert result == [existing]
        mock_update.assert_called_once()

    def test_update_metadata_batch_success(self, content_writer, mock_database_service):
        db_service, mock_session = mock_database_service

        metadata_updates = [(1, {"key1": "value1"}), (2, {"key2": "value2"})]

        mock_items = [Mock(), Mock()]
        with patch.object(
            content_writer, "_process_metadata_updates", return_value=mock_items
        ):
            result = content_writer.update_metadata_batch(metadata_updates)

            assert result == 2
            mock_session.commit.assert_called_once()
            assert mock_session.refresh.call_count == 0  # refresh=False by default

    def test_update_metadata_batch_empty_list(self, content_writer):
        result = content_writer.update_metadata_batch([])
        assert result == 0

    def test_update_metadata_batch_with_refresh(
        self, content_writer, mock_database_service
    ):
        db_service, mock_session = mock_database_service

        metadata_updates = [(1, {"key1": "value1"})]
        mock_items = [Mock()]

        with patch.object(
            content_writer, "_process_metadata_updates", return_value=mock_items
        ):
            content_writer.update_metadata_batch(metadata_updates, refresh=True)

            mock_session.refresh.assert_called_once()

    def test_update_metadata_batch_with_external_session(
        self, content_writer, mock_database_service
    ):
        db_service, mock_session = mock_database_service
        external_session = Mock(spec=Session)

        metadata_updates = [(1, {"key1": "value1"})]

        with patch.object(
            content_writer, "_process_metadata_updates", return_value=[Mock()]
        ):
            content_writer.update_metadata_batch(
                metadata_updates, session=external_session
            )

            external_session.commit.assert_not_called()

    def test_update_metadata_batch_sqlalchemy_error(
        self, content_writer, mock_database_service
    ):
        db_service, mock_session = mock_database_service

        with patch.object(
            content_writer,
            "_process_metadata_updates",
            side_effect=SQLAlchemyError("Database error"),
        ):
            with pytest.raises(SQLAlchemyError):
                content_writer.update_metadata_batch([(1, {"key": "value"})])

            mock_session.rollback.assert_called_once()

    def test_update_content_category_success(
        self, content_writer, mock_database_service
    ):
        db_service, mock_session = mock_database_service

        mock_item = MagicMock()
        mock_item.content_metadata = {}
        # Mock the _sa_instance_state for flag_modified to work
        mock_item._sa_instance_state = MagicMock()
        mock_item._sa_instance_state.manager = MagicMock()
        mock_item._sa_instance_state.manager.__getitem__.return_value.impl = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_item
        )

        with patch(
            "ai_content_classifier.models.content_models.datetime_utcnow"
        ) as mock_datetime:
            mock_now = datetime(2023, 1, 15, 12, 0, 0)
            mock_datetime.return_value = mock_now

            result = content_writer.update_content_category(
                file_path="/test/image.jpg",
                category="landscape",
                confidence=0.95,
                extraction_method="AI",
                extraction_details="CNN model",
            )

            assert result == mock_item
            assert mock_item.category == "landscape"
            assert mock_item.classification_confidence == 0.95
            assert (
                mock_item.content_metadata["classification"]["category"] == "landscape"
            )
            assert mock_item.content_metadata["classification"]["confidence"] == 0.95

            mock_session.commit.assert_called_once()

    def test_update_content_category_none_metadata(
        self, content_writer, mock_database_service
    ):
        db_service, mock_session = mock_database_service

        mock_item = MagicMock()
        mock_item.content_metadata = None
        # Mock the _sa_instance_state for flag_modified to work
        mock_item._sa_instance_state = MagicMock()
        mock_item._sa_instance_state.manager = MagicMock()
        mock_item._sa_instance_state.manager.__getitem__.return_value.impl = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_item
        )

        with patch("ai_content_classifier.models.content_models.datetime_utcnow"):
            content_writer.update_content_category(
                file_path="/test/image.jpg",
                category="landscape",
                confidence=0.95,
                extraction_method="AI",
                extraction_details="CNN model",
            )

            assert mock_item.classification_confidence == 0.95
            assert "classification" in mock_item.content_metadata
            assert (
                mock_item.content_metadata["classification"]["category"] == "landscape"
            )
            assert mock_item.content_metadata["classification"]["confidence"] == 0.95
            assert (
                mock_item.content_metadata["classification"]["extraction_method"]
                == "AI"
            )
            assert (
                mock_item.content_metadata["classification"]["extraction_details"]
                == "CNN model"
            )
            assert "timestamp" in mock_item.content_metadata["classification"]

    def test_update_content_category_item_not_found(
        self, content_writer, mock_database_service
    ):
        db_service, mock_session = mock_database_service
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = content_writer.update_content_category(
            file_path="/test/nonexistent.jpg",
            category="landscape",
            confidence=0.95,
            extraction_method="AI",
            extraction_details="CNN model",
        )

        assert result is None

    def test_update_content_category_with_external_session(
        self, content_writer, mock_database_service
    ):
        db_service, mock_session = mock_database_service
        external_session = Mock(spec=Session)

        mock_item = MagicMock()
        mock_item.content_metadata = {}
        # Mock the _sa_instance_state for flag_modified to work
        mock_item._sa_instance_state = MagicMock()
        mock_item._sa_instance_state.manager = MagicMock()
        mock_item._sa_instance_state.manager.__getitem__.return_value.impl = MagicMock()
        external_session.query.return_value.filter.return_value.first.return_value = (
            mock_item
        )

        with (
            patch("ai_content_classifier.models.content_models.datetime_utcnow"),
            patch("sqlalchemy.orm.attributes.flag_modified"),
        ):
            content_writer.update_content_category(
                file_path="/test/image.jpg",
                category="landscape",
                confidence=0.95,
                extraction_method="AI",
                extraction_details="CNN model",
                session=external_session,
            )

            external_session.commit.assert_not_called()

    def test_update_content_category_sqlalchemy_error(
        self, content_writer, mock_database_service
    ):
        db_service, mock_session = mock_database_service
        mock_session.query.side_effect = SQLAlchemyError("Database error")

        with pytest.raises(SQLAlchemyError):
            content_writer.update_content_category(
                file_path="/test/image.jpg",
                category="landscape",
                confidence=0.95,
                extraction_method="AI",
                extraction_details="CNN model",
            )

        mock_session.rollback.assert_called_once()

    def test_clear_content_category_success(
        self, content_writer, mock_database_service
    ):
        db_service, mock_session = mock_database_service

        mock_item = MagicMock()
        mock_item.category = "landscape"
        mock_item.classification_confidence = 0.95
        mock_item.content_metadata = {"classification": {"category": "landscape"}}
        mock_item._sa_instance_state = MagicMock()
        mock_item._sa_instance_state.manager = MagicMock()
        mock_item._sa_instance_state.manager.__getitem__.return_value.impl = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_item
        )

        with patch("ai_content_classifier.models.content_models.datetime_utcnow"):
            result = content_writer.clear_content_category("/test/image.jpg")

            assert result == mock_item
            assert mock_item.category is None
            assert mock_item.classification_confidence is None
            assert "classification" not in mock_item.content_metadata
            mock_session.commit.assert_called_once()

    def test_clear_content_category_item_not_found(
        self, content_writer, mock_database_service
    ):
        db_service, mock_session = mock_database_service
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = content_writer.clear_content_category("/test/nonexistent.jpg")

        assert result is None

    def test_clear_content_category_sqlalchemy_error(
        self, content_writer, mock_database_service
    ):
        db_service, mock_session = mock_database_service
        mock_session.query.side_effect = SQLAlchemyError("Database error")

        with pytest.raises(SQLAlchemyError):
            content_writer.clear_content_category("/test/image.jpg")

        mock_session.rollback.assert_called_once()

    def test_extract_file_info_file_exists(self, content_writer):
        with (
            patch("os.path.exists", return_value=True),
            patch("os.path.getsize", return_value=2048),
            patch("os.path.basename", return_value="test.jpg"),
            patch("os.path.dirname", return_value="/path/to"),
        ):
            result = content_writer._extract_file_info("/path/to/test.jpg", True)

            expected = {
                "filename": "test.jpg",
                "directory": "/path/to",
                "file_size": 2048,
            }
            assert result == expected

    def test_extract_file_info_file_not_exists(self, content_writer):
        with (
            patch("os.path.exists", return_value=False),
            patch("os.path.basename", return_value="test.jpg"),
            patch("os.path.dirname", return_value="/path/to"),
        ):
            result = content_writer._extract_file_info("/path/to/test.jpg", True)

            expected = {
                "filename": "test.jpg",
                "directory": "/path/to",
                "file_size": None,
            }
            assert result == expected

    def test_extract_file_info_no_basic_info(self, content_writer):
        with (
            patch("os.path.basename", return_value="test.jpg"),
            patch("os.path.dirname", return_value="/path/to"),
        ):
            result = content_writer._extract_file_info("/path/to/test.jpg", False)

            expected = {
                "filename": "test.jpg",
                "directory": "/path/to",
                "file_size": None,
            }
            assert result == expected

    def test_is_valid_item_data(self, content_writer):
        valid_data = {"path": "/test/file.jpg", "content_type": "image"}
        assert content_writer._is_valid_item_data(valid_data) is True

        assert content_writer._is_valid_item_data(None) is False
        assert content_writer._is_valid_item_data("not_a_dict") is False
        assert content_writer._is_valid_item_data({}) is False
        assert content_writer._is_valid_item_data({"content_type": "image"}) is False
        assert content_writer._is_valid_item_data({"path": ""}) is False
        assert content_writer._is_valid_item_data({"path": "/test/file.jpg"}) is False

    def test_create_content_item_from_data_image(self, content_writer):
        item_data = {
            "path": "/test/image.jpg",
            "content_type": "image",
            "filename": "image.jpg",
            "directory": "/test",
            "width": 1920,
            "height": 1080,
            "format": "jpeg",
            "year_taken": 2023,
        }

        with patch(
            "ai_content_classifier.services.database.utils.serialize_metadata_for_json",
            return_value={},
        ):
            result = content_writer._create_content_item_from_data(item_data)

            assert isinstance(result, Image)
            assert result.path == "/test/image.jpg"
            assert result.width == 1920
            assert result.height == 1080

    def test_create_content_item_from_data_document(self, content_writer):
        item_data = {
            "path": "/test/document.pdf",
            "content_type": "document",
            "language": "en",
            "page_count": 10,
            "text_content": "Sample text",
        }

        with patch(
            "ai_content_classifier.services.database.utils.serialize_metadata_for_json",
            return_value={},
        ):
            result = content_writer._create_content_item_from_data(item_data)

            assert isinstance(result, Document)
            assert result.language == "en"
            assert result.page_count == 10

    def test_create_content_item_from_data_video(self, content_writer):
        item_data = {
            "path": "/test/video.mp4",
            "content_type": "video",
            "duration": 120,
            "width": 1920,
            "height": 1080,
            "format": "mp4",
        }

        with patch(
            "ai_content_classifier.services.database.utils.serialize_metadata_for_json",
            return_value={},
        ):
            result = content_writer._create_content_item_from_data(item_data)

            assert isinstance(result, Video)
            assert result.duration == 120

    def test_create_content_item_from_data_audio(self, content_writer):
        item_data = {
            "path": "/test/audio.mp3",
            "content_type": "audio",
            "duration": 180,
            "bit_rate": 320,
            "sample_rate": 44100,
            "format": "mp3",
        }

        with patch(
            "ai_content_classifier.services.database.utils.serialize_metadata_for_json",
            return_value={},
        ):
            result = content_writer._create_content_item_from_data(item_data)

            assert isinstance(result, Audio)
            assert result.bit_rate == 320
            assert result.sample_rate == 44100

    def test_create_content_item_from_data_generic(self, content_writer):
        item_data = {"path": "/test/file.txt", "content_type": "text"}

        with patch(
            "ai_content_classifier.services.database.utils.serialize_metadata_for_json",
            return_value={},
        ):
            result = content_writer._create_content_item_from_data(item_data)

            assert isinstance(result, ContentItem)
            assert not isinstance(result, (Image, Document, Video, Audio))

    def test_create_content_item_from_data_error(self, content_writer):
        item_data = None  # Intentionally incomplete data to trigger an error

        result = content_writer._create_content_item_from_data(item_data)
        assert result is None

    def test_process_metadata_updates(self, content_writer, mock_database_service):
        db_service, mock_session = mock_database_service

        mock_item1 = MagicMock()
        mock_item1.content_metadata = {"existing": "data"}
        # Mock the _sa_instance_state for flag_modified to work
        mock_item1._sa_instance_state = MagicMock()
        mock_item1._sa_instance_state.manager = MagicMock()
        mock_item1._sa_instance_state.manager.__getitem__.return_value.impl = (
            MagicMock()
        )
        mock_item2 = MagicMock()
        mock_item2.content_metadata = None
        # Mock the _sa_instance_state for flag_modified to work
        mock_item2._sa_instance_state = MagicMock()
        mock_item2._sa_instance_state.manager = MagicMock()
        mock_item2._sa_instance_state.manager.__getitem__.return_value.impl = (
            MagicMock()
        )

        mock_session.query.return_value.filter.return_value.first.side_effect = [
            mock_item1,
            mock_item2,
        ]

        metadata_updates = [
            (1, {"new_key": "new_value"}),
            (2, {"another_key": "another_value"}),
        ]

        with (
            patch(
                "ai_content_classifier.services.database.utils.serialize_metadata_for_json",
                side_effect=lambda x: x,
            ),
            patch(
                "ai_content_classifier.models.content_models.datetime_utcnow"
            ) as mock_datetime,
        ):
            mock_now = datetime(2023, 1, 15, 12, 0, 0)
            mock_datetime.return_value = mock_now

            result = content_writer._process_metadata_updates(
                mock_session, metadata_updates
            )

            assert len(result) == 2
            assert mock_item1.metadata_extracted is True
            assert mock_item2.metadata_extracted is True

    def test_update_existing_item_sets_fields_and_metadata(self, content_writer):
        item = ContentItem(
            path="/test/file.jpg",
            filename="file.jpg",
            directory="/test",
            content_type="image",
        )
        item.content_metadata = None

        with (
            patch("os.path.exists", return_value=True),
            patch("os.path.getsize", return_value=2048),
            patch(
                "ai_content_classifier.services.database.utils.compute_file_hash",
                return_value="abc",
            ),
            patch(
                "ai_content_classifier.services.database.utils.serialize_metadata_for_json",
                return_value={"creation_date": "2020-01-01"},
            ),
        ):
            content_writer._update_existing_item(
                existing_item=item,
                path="/test/file.jpg",
                extract_basic_info=True,
                metadata={"creation_date": "2020-01-01"},
            )

        assert item.file_size == 2048
        assert item.file_hash == "abc"
        assert item.metadata_extracted is True
        assert item.year_taken == 2020
        assert item.content_metadata["creation_date"] == "2020-01-01"

    def test_resolve_and_extract_year_helpers(self, content_writer):
        assert content_writer._extract_year_from_metadata("not-a-dict") is None
        assert content_writer._extract_year_value(None) is None
        assert content_writer._extract_year_value(2201) is None
        assert content_writer._extract_year_value("taken in 2019") == 2019
        assert (
            content_writer._extract_year_from_metadata({"created": "2018-05-01"})
            == 2018
        )

        with patch.object(
            content_writer, "_extract_year_from_metadata", return_value=2022
        ):
            assert (
                content_writer._resolve_year_taken("/tmp/a.jpg", {"year": 2022}) == 2022
            )

        with (
            patch.object(
                content_writer, "_extract_year_from_metadata", return_value=None
            ),
            patch("os.path.getmtime", side_effect=OSError("no file")),
        ):
            assert content_writer._resolve_year_taken("/tmp/a.jpg", {}) is None

    def test_compute_hash_if_exists_handles_errors(self, content_writer):
        assert content_writer._compute_hash_if_exists("") is None

        with (
            patch("os.path.exists", return_value=True),
            patch(
                "ai_content_classifier.services.database.utils.compute_file_hash",
                side_effect=RuntimeError("hash error"),
            ),
        ):
            assert content_writer._compute_hash_if_exists("/tmp/a.jpg") is None


class TestContentWriterIntegration:
    @pytest.fixture
    def mock_database_service(self):
        mock_service = Mock()
        mock_session = Mock(spec=Session)
        mock_service.Session.return_value = mock_session
        return mock_service, mock_session

    @pytest.fixture
    def mock_repos(self):
        return Mock()

    @pytest.fixture
    def content_writer(self, mock_database_service, mock_repos):
        db_service, _ = mock_database_service
        return ContentWriter(db_service, mock_repos)

    def test_full_workflow_create_and_update(
        self, content_writer, mock_database_service
    ):
        db_service, mock_session = mock_database_service

        with (
            patch("os.path.exists", return_value=True),
            patch("os.path.getsize", return_value=1024),
        ):
            created_item = content_writer.create_content_item(
                path="/test/image.jpg", content_type="image"
            )

        mock_item = MagicMock()
        mock_item.content_metadata = {}
        # Mock the _sa_instance_state for flag_modified to work
        mock_item._sa_instance_state = MagicMock()
        mock_item._sa_instance_state.manager = MagicMock()
        mock_item._sa_instance_state.manager.__getitem__.return_value.impl = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_item
        )

        with (
            patch("ai_content_classifier.models.content_models.datetime_utcnow"),
            patch("sqlalchemy.orm.attributes.flag_modified"),
        ):
            updated_item = content_writer.update_content_category(
                file_path="/test/image.jpg",
                category="nature",
                confidence=0.9,
                extraction_method="AI",
                extraction_details="Classification model",
            )

        assert isinstance(created_item, Image)
        assert updated_item is not None
        assert mock_session.add.call_count >= 1
        assert mock_session.commit.call_count >= 2

    def test_batch_operations_mixed_types(self, content_writer, mock_database_service):
        db_service, mock_session = mock_database_service

        items = [
            {"path": "/test/image.jpg", "content_type": "image", "width": 1920},
            {"path": "/test/doc.pdf", "content_type": "document", "page_count": 5},
            {"path": "/test/video.mp4", "content_type": "video", "duration": 120},
            {"path": "/test/audio.mp3", "content_type": "audio", "bit_rate": 320},
        ]

        with patch.object(
            content_writer, "_create_content_item_from_data"
        ) as mock_create:
            mock_items = [Mock() for _ in items]
            mock_create.side_effect = mock_items

            result = content_writer.save_item_batch(items)

            assert len(result) == 4
            assert mock_session.add.call_count == 4
            assert mock_create.call_count == 4

    def test_error_recovery_rollback(self, content_writer, mock_database_service):
        db_service, mock_session = mock_database_service

        mock_session.add.side_effect = [None, None, SQLAlchemyError("Database full")]

        items = [
            {"path": "/test/image1.jpg", "content_type": "image"},
            {"path": "/test/image2.jpg", "content_type": "image"},
            {"path": "/test/image3.jpg", "content_type": "image"},
        ]

        with patch.object(
            content_writer, "_create_content_item_from_data", return_value=Mock()
        ):
            with pytest.raises(SQLAlchemyError):
                content_writer.save_item_batch(items)

            mock_session.rollback.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])
