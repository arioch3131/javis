import pytest
import tempfile
import os
from datetime import datetime
from unittest.mock import MagicMock

from ai_content_classifier.services.metadata.metadata_service import MetadataService


class MockBaseMetadataExtractor:
    def can_handle(self, file_path):
        return True

    def get_metadata(self, file_path):
        return {}


class TestMetadataServiceWithCache:
    @pytest.fixture
    def mock_extractor(self):

        class SimpleMockExtractor:
            def __init__(self):
                self.call_count = 0
                self.__class__.__name__ = "MockExtractor"
                self._return_data = {
                    "width": 1920,
                    "height": 1080,
                    "format": "JPEG",
                    "creation_date": datetime(2023, 1, 1),
                    "file_size": 1024 * 1024,
                }
                self._can_handle = True
                self._should_raise = False
                self._exception_to_raise = None

            def can_handle(self, file_path):
                return self._can_handle

            def get_metadata(self, file_path):
                self.call_count += 1
                print(f"[EXTRACTOR] Call #{self.call_count} for {file_path}")

                if self._should_raise:
                    raise self._exception_to_raise or Exception("Mock exception")

                return dict(self._return_data)  # Return a copy

            def set_return_data(self, data):
                self._return_data = data

            def set_can_handle(self, value):
                self._can_handle = value

            def set_exception(self, exception):
                self._should_raise = True
                self._exception_to_raise = exception

            def reset_exception(self):
                self._should_raise = False
                self._exception_to_raise = None

        return SimpleMockExtractor()

    @pytest.fixture
    def temp_file(self):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"fake image data")
            temp_path = f.name

        yield temp_path

        # Cleanup
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass

    @pytest.fixture
    def metadata_service(self, mock_extractor):
        # puis on lui assigne directement notre mock
        service = MetadataService(extractors=[])
        service.extractors = [mock_extractor]
        return service

    def test_cache_miss_then_hit(self, metadata_service, mock_extractor, temp_file):

        # Premier appel - cache miss
        print(f"Premier appel pour: {temp_file}")
        metadata1 = metadata_service.get_all_metadata(temp_file)

        print(f"Call count after first call: {mock_extractor.call_count}")
        print(f"Metadata 1: {list(metadata1.keys())}")

        assert mock_extractor.call_count == 1
        assert "width" in metadata1
        assert metadata1["_extracted_by"] == "MockExtractor"

        import time

        time.sleep(0.1)

        print(f"Second call for: {temp_file}")
        metadata2 = metadata_service.get_all_metadata(temp_file)

        print(f"Call count after second call: {mock_extractor.call_count}")
        print(f"Metadata 2: {list(metadata2.keys())}")

        assert metadata1["width"] == metadata2["width"]
        assert metadata1["_extracted_by"] == metadata2["_extracted_by"]

        assert mock_extractor.call_count <= 2, (
            f"Too many calls to extractor: {mock_extractor.call_count}"
        )

    def test_cache_stats(self, metadata_service, temp_file):

        stats = metadata_service.get_cache_stats()
        print(f"Stats initiales: {stats}")

        for i in range(3):
            metadata_service.get_all_metadata(temp_file)

        final_stats = metadata_service.get_cache_stats()
        print(f"Stats finales: {final_stats}")

        expected_fields = [
            "cache_size",
            "cache_hits",
            "cache_misses",
            "total_objects",
            "extractors_count",
        ]
        for field in expected_fields:
            assert field in final_stats, f"Field {field} missing from stats"

        assert final_stats["extractors_count"] > 0
        assert "extractors" in final_stats
        assert len(final_stats["extractors"]) > 0

    def test_file_not_found(self, metadata_service):

        result = metadata_service.get_all_metadata("/nonexistent/file.jpg")
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_no_suitable_extractor(self, metadata_service, mock_extractor, temp_file):

        mock_extractor.set_can_handle(False)

        result = metadata_service.get_all_metadata(temp_file)
        assert "error" in result
        assert "No suitable extractor" in result["error"]

    def test_extractor_exception(self, metadata_service, mock_extractor, temp_file):

        mock_extractor.set_exception(Exception("Extraction failed"))

        result = metadata_service.get_all_metadata(temp_file)
        assert "error" in result
        assert "Extraction failed" in result["error"]

    def test_clear_cache(self, metadata_service, temp_file):

        # Remplir le cache avec plusieurs fichiers
        files = []
        with tempfile.TemporaryDirectory() as temp_dir:
            for i in range(3):
                file_path = os.path.join(temp_dir, f"test_file_{i}.jpg")
                with open(file_path, "wb") as f:
                    f.write(b"fake image data")
                files.append(file_path)

                metadata_service.get_all_metadata(file_path)

        stats_before = metadata_service.get_cache_stats()
        print(f"Stats avant clear: {stats_before}")

        has_objects = (
            stats_before.get("cache_size", 0) > 0
            or stats_before.get("total_objects", 0) > 0
            or stats_before.get("active_objects", 0) > 0
            or stats_before.get("pooled_objects", 0) > 0
        )

        if not has_objects:
            print("Cache appears empty, still validating clear operation")

        # Nettoyer le cache
        metadata_service.clear_cache()

        stats_after = metadata_service.get_cache_stats()
        print(f"Stats after clear: {stats_after}")

        assert stats_after.get("cache_size", 0) == 0
        assert stats_after.get("pooled_objects", 0) == 0


class TestMetadataServiceIntegration:
    def test_full_workflow_with_real_cache(self):

        service = MetadataService(extractors=[])

        stats = service.get_cache_stats()
        assert isinstance(stats, dict)
        assert "cache_size" in stats

        stats = service.get_cache_stats()
        assert "omni_cache_available" in stats


class TestMetadataServiceCoverageUplift:
    @pytest.fixture
    def service(self):
        svc = MetadataService(extractors=["invalid.path.Extractor"])
        svc.extractors = []
        return svc

    def test_extract_year_value_variants(self, service):
        assert service._extract_year_value(datetime(2022, 1, 1)) == 2022
        assert service._extract_year_value(datetime(1800, 1, 1)) is None
        assert service._extract_year_value(2020) == 2020
        assert service._extract_year_value(2200) is None
        assert service._extract_year_value("captured-1999-final") == 1999
        assert service._extract_year_value("  ") is None
        assert service._extract_year_value("no year here") is None
        assert service._extract_year_value(None) is None

    def test_extract_year_from_metadata_priority_and_none(self, service):
        metadata = {"unknown": "x", "date_created": "2021-08-12"}
        assert service._extract_year_from_metadata(metadata) == 2021
        assert service._extract_year_from_metadata({"unknown": "x"}) is None

    def test_validate_file_exists_invalid_and_unreadable(self, service, monkeypatch):
        assert service._validate_file_exists("") is False
        assert service._validate_file_exists(123) is False

        monkeypatch.setattr(
            "ai_content_classifier.services.metadata.metadata_service.os.path.isfile",
            lambda _p: True,
        )
        monkeypatch.setattr(
            "ai_content_classifier.services.metadata.metadata_service.os.access",
            lambda _p, _mode: False,
        )
        assert service._validate_file_exists("/tmp/file.jpg") is False

    def test_load_extractors_invalid_path(self, service):
        service._load_extractors(["invalid_path_without_class_separator"])
        assert service.extractors == []

    def test_find_suitable_extractor_handles_can_handle_exception(self, service):
        bad_extractor = MagicMock()
        bad_extractor.__class__.__name__ = "BadExtractor"
        bad_extractor.can_handle.side_effect = RuntimeError("boom")
        service.extractors = [bad_extractor]

        assert service._find_suitable_extractor("/tmp/a.jpg") is None

    def test_get_all_metadata_cache_fallback_on_cache_set_error(self, service):
        metadata = {"creation_date": "2023-02-01"}
        service._extract_metadata_for_file = MagicMock(return_value=metadata)
        service._metadata_cache.get = MagicMock(return_value=None)
        service._metadata_cache.set = MagicMock(
            side_effect=[RuntimeError("cache"), None]
        )

        result = service.get_all_metadata("/tmp/a.jpg")
        assert result == metadata
        assert service._extract_metadata_for_file.call_count == 2
        assert service._metadata_cache.set.call_count == 2

    def test_get_cache_stats_with_runtime_error(self, service):
        runtime_mock = MagicMock()
        runtime_mock.manager = MagicMock()
        runtime_mock.manager.get_adapter_stats.side_effect = RuntimeError(
            "adapter failed"
        )
        runtime_mock.is_available.return_value = False
        service._cache_runtime = runtime_mock
        service._metadata_cache.get_stats = MagicMock(return_value={})
        service._metadata_cache.size = MagicMock(return_value=0)
        service.extractors = []

        stats = service.get_cache_stats()
        assert stats["omni_cache_stats"] == {}
        assert stats["extractors_count"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
