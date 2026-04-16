from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ai_content_classifier.services.auto_organization_service import (
    AutoOrganizationService,
    OrganizationConfig,
    OrganizationResult,
)
from ai_content_classifier.services.database.types import (
    DatabaseOperationCode,
    DatabaseOperationResult,
)


def _db_ok(**data):
    return DatabaseOperationResult(
        success=True,
        code=DatabaseOperationCode.OK,
        message="ok",
        data=data,
    )


def _db_not_found():
    return DatabaseOperationResult(
        success=False,
        code=DatabaseOperationCode.NOT_FOUND,
        message="not found",
        data={"item": None},
    )


@pytest.fixture
def db_service():
    return MagicMock()


@pytest.fixture
def service(db_service):
    svc = AutoOrganizationService(content_database_service=db_service)
    svc.logger = MagicMock()
    return svc


def test_validate_config_rejects_empty_target(service):
    config = OrganizationConfig(
        target_directory="", organization_structure="By Category"
    )

    ok, error = service.validate_config(config)

    assert ok is False
    assert error == "No target directory specified"


def test_validate_config_rejects_invalid_structure(service, tmp_path):
    config = OrganizationConfig(
        target_directory=str(tmp_path / "target"),
        organization_structure="By Planet",
    )

    ok, error = service.validate_config(config)

    assert ok is False
    assert "Unsupported organization structure" in error


def test_validate_config_rejects_invalid_action(service, tmp_path):
    config = OrganizationConfig(
        target_directory=str(tmp_path / "target"),
        organization_structure="By Type",
        organization_action="delete",
    )

    ok, error = service.validate_config(config)

    assert ok is False
    assert "Invalid organization action" in error


def test_validate_config_rejects_missing_parent_dir(service, tmp_path):
    config = OrganizationConfig(
        target_directory=str(tmp_path / "missing_parent" / "target"),
        organization_structure="By Type",
    )

    ok, error = service.validate_config(config)

    assert ok is False
    assert "Parent directory does not exist" in error


def test_prepare_target_structure_by_category_creates_sanitized_dirs(
    service, db_service, tmp_path
):
    db_service.get_unique_categories.return_value = _db_ok(
        categories=["Work/Docs", "CON"]
    )
    target = tmp_path / "organized"
    config = OrganizationConfig(
        target_directory=str(target),
        organization_structure="By Category",
    )

    result = service.prepare_target_structure(config)

    assert result is True
    assert (target / "Work_Docs").is_dir()
    assert (target / "CON_folder").is_dir()


def test_prepare_target_structure_by_type_and_year(service, tmp_path):
    by_type = OrganizationConfig(
        target_directory=str(tmp_path / "by_type"),
        organization_structure="By Type",
    )
    by_year = OrganizationConfig(
        target_directory=str(tmp_path / "by_year"),
        organization_structure="By Year",
    )

    assert service.prepare_target_structure(by_type) is True
    assert (tmp_path / "by_type" / "Documents").is_dir()
    assert (tmp_path / "by_type" / "Images").is_dir()

    assert service.prepare_target_structure(by_year) is True
    current = datetime.now().year
    assert (tmp_path / "by_year" / str(current)).is_dir()


def test_prepare_target_structure_handles_exception(service, tmp_path, monkeypatch):
    config = OrganizationConfig(
        target_directory=str(tmp_path / "target"),
        organization_structure="By Type",
    )
    monkeypatch.setattr(
        "ai_content_classifier.services.auto_organization_service.os.makedirs",
        lambda *_a, **_k: (_ for _ in ()).throw(OSError("mkdir fail")),
    )

    assert service.prepare_target_structure(config) is False


def test_organize_single_file_by_category_copy_handles_name_conflict(
    service, db_service, tmp_path
):
    source = tmp_path / "report.txt"
    source.write_text("hello", encoding="utf-8")

    target_root = tmp_path / "target"
    category_dir = target_root / "Work"
    category_dir.mkdir(parents=True)
    (category_dir / "report.txt").write_text("existing", encoding="utf-8")

    db_service.get_content_by_path.return_value = _db_ok(
        item=SimpleNamespace(category="Work")
    )
    config = OrganizationConfig(
        target_directory=str(target_root),
        organization_structure="By Category",
        organization_action="copy",
    )

    result = service.organize_single_file(str(source), config)

    assert result.success is True
    assert result.action == "copy"
    assert result.target_path.endswith("report_1.txt")
    assert source.exists()
    assert (category_dir / "report_1.txt").exists()
    assert result.size_bytes == 5


def test_organize_single_file_by_year_uses_creation_date_year(
    service, db_service, tmp_path
):
    source = tmp_path / "invoice.pdf"
    source.write_text("pdf", encoding="utf-8")

    db_service.get_content_by_path.return_value = _db_ok(
        item=SimpleNamespace(creation_date=datetime(2021, 5, 4))
    )
    config = OrganizationConfig(
        target_directory=str(tmp_path / "target"),
        organization_structure="By Year",
        organization_action="copy",
    )

    result = service.organize_single_file(str(source), config)

    assert result.success is True
    assert "/2021/" in result.target_path
    assert source.exists()


def test_organize_single_file_by_type_category_move(service, db_service, tmp_path):
    source = tmp_path / "photo.jpg"
    source.write_bytes(b"img")

    db_service.get_content_by_path.return_value = _db_ok(
        item=SimpleNamespace(category="Travel")
    )
    config = OrganizationConfig(
        target_directory=str(tmp_path / "target"),
        organization_structure="By Type/Category",
        organization_action="move",
    )

    result = service.organize_single_file(str(source), config)

    assert result.success is True
    assert result.action == "move"
    assert "/Images/Travel/" in result.target_path
    assert source.exists() is False


def test_perform_file_action_returns_error_when_source_missing(service, tmp_path):
    target = tmp_path / "x.txt"

    result = service._perform_file_action("/missing/file.txt", str(target), "copy")

    assert result.success is False
    assert result.error_message == "Source file does not exist"


def test_organize_single_file_handles_missing_structure(service, tmp_path):
    config = OrganizationConfig(
        target_directory=str(tmp_path / "target"),
        organization_structure="DoesNotExist",
    )
    result = service.organize_single_file("/tmp/a.txt", config)
    assert result.success is False
    assert result.error_message


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("document.pdf", "Documents"),
        ("image.png", "Images"),
        ("video.mp4", "Videos"),
        ("music.mp3", "Audio"),
        ("archive.bin", "Others"),
    ],
)
def test_determine_file_type(service, name, expected):
    assert service.determine_file_type(name) == expected


def test_get_organization_preview_builds_structure_and_detects_conflict(
    service, db_service, tmp_path
):
    source = tmp_path / "a.txt"
    source.write_text("abc", encoding="utf-8")

    target = tmp_path / "target"
    docs_dir = target / "Documents"
    docs_dir.mkdir(parents=True)
    (docs_dir / "a.txt").write_text("already-there", encoding="utf-8")

    config = OrganizationConfig(
        target_directory=str(target),
        organization_structure="By Type",
    )
    db_service.get_content_by_path.return_value = _db_not_found()

    preview = service.get_organization_preview([str(source)], config)

    assert preview["file_count"] == 1
    assert preview["total_size_mb"] > 0
    assert len(preview["conflicts"]) == 1
    assert str(docs_dir) in preview["structure"]
    assert "a.txt" in preview["structure"][str(docs_dir)]


def test_internal_extractors_and_helpers_cover_fallbacks(
    service, db_service, tmp_path, monkeypatch
):
    db_service.get_content_by_path.side_effect = RuntimeError("db down")
    assert service._safe_get_content_item("/tmp/file.txt") is None

    assert service._extract_category(None) == "Uncategorized"
    assert service._extract_category(SimpleNamespace(category="  ")) == "Uncategorized"
    assert service._extract_category(SimpleNamespace(category="Work")) == "Work"

    iso_item = SimpleNamespace(creation_date="2022-03-01T10:00:00")
    assert service._extract_year("/tmp/missing", iso_item) == 2022
    dict_item = {"creation_date": datetime(2020, 1, 1)}
    assert service._extract_year("/tmp/missing", dict_item) == 2020

    monkeypatch.setattr(
        "ai_content_classifier.services.auto_organization_service.os.path.getmtime",
        lambda _p: (_ for _ in ()).throw(OSError("mtime fail")),
    )
    assert isinstance(service._extract_year("/tmp/missing", None), int)

    db_service.get_unique_categories.return_value = _db_ok(categories=[])
    assert "Work" in service._get_available_categories()
    db_service.get_unique_categories.side_effect = RuntimeError("broken")
    assert "Personal" in service._get_available_categories()

    long_name = "A" * 120
    assert len(service._sanitize_dirname(long_name)) == 100
    assert service._sanitize_dirname("CON") == "CON_folder"


def test_safe_get_content_item_handles_non_not_found_db_failure(service, db_service):
    db_service.get_content_by_path.return_value = DatabaseOperationResult(
        success=False,
        code=DatabaseOperationCode.DB_ERROR,
        message="db read error",
        data={"error": "db"},
    )
    assert service._safe_get_content_item("/tmp/file.txt") is None


def test_get_available_categories_handles_failed_result_object(service, db_service):
    db_service.get_unique_categories.return_value = DatabaseOperationResult(
        success=False,
        code=DatabaseOperationCode.DB_ERROR,
        message="db read error",
        data={"error": "db"},
    )
    categories = service._get_available_categories()
    assert "Work" in categories


def test_organize_custom_and_resolve_name_conflicts(service, db_service, tmp_path):
    source = tmp_path / "doc.txt"
    source.write_text("x", encoding="utf-8")
    db_service.get_content_by_path.return_value = _db_ok(
        item=SimpleNamespace(category="Work")
    )

    config = OrganizationConfig(
        target_directory=str(tmp_path / "target"),
        organization_structure="Custom",
        organization_action="copy",
    )
    result = service._organize_custom(str(source), config)
    assert result.success is True

    conflict = tmp_path / "name.txt"
    conflict.write_text("1", encoding="utf-8")
    (tmp_path / "name_1.txt").write_text("2", encoding="utf-8")
    resolved = service._resolve_name_conflict(str(conflict))
    assert resolved.endswith("name_2.txt")


def test_preview_year_and_statistics_error_paths(service, tmp_path, monkeypatch):
    src = tmp_path / "year.txt"
    src.write_text("abc", encoding="utf-8")
    config = OrganizationConfig(
        target_directory=str(tmp_path / "target"),
        organization_structure="By Year",
    )
    preview = service.get_organization_preview([str(src)], config)
    assert preview["file_count"] == 1

    monkeypatch.setattr(
        "ai_content_classifier.services.auto_organization_service.datetime",
        SimpleNamespace(
            fromtimestamp=lambda *_a, **_k: (_ for _ in ()).throw(ValueError("bad")),
            now=datetime.now,
        ),
    )
    errored = service.get_organization_preview([str(src)], config)
    assert errored["file_count"] == 0

    bad_results = [
        SimpleNamespace(
            success=True, size_bytes="oops", action="copy", source_path="a.txt"
        )
    ]
    stats = service.calculate_statistics(bad_results, config)
    assert "error" in stats


def test_calculate_statistics_returns_aggregates(service, tmp_path):
    src_doc = str(tmp_path / "doc.pdf")
    src_img = str(tmp_path / "img.png")
    src_other = str(tmp_path / "data.xyz")

    results = [
        OrganizationResult(True, src_doc, "/x/doc.pdf", "copy", size_bytes=100),
        OrganizationResult(True, src_img, "/x/img.png", "move", size_bytes=200),
        OrganizationResult(
            False, src_other, "/x/data.xyz", "copy", error_message="fail"
        ),
    ]
    config = OrganizationConfig(
        target_directory=str(tmp_path / "target"),
        organization_structure="By Type",
        organization_action="copy",
    )

    stats = service.calculate_statistics(results, config)

    assert stats["total_files"] == 3
    assert stats["successful"] == 2
    assert stats["failed"] == 1
    assert stats["copied"] == 1
    assert stats["moved"] == 1
    assert stats["by_type"]["Documents"] == 1
    assert stats["by_type"]["Images"] == 1
