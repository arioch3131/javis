from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ai_content_classifier.services.auto_organization.operations.generate_preview_operation import (
    GeneratePreviewOperation,
)
from ai_content_classifier.services.auto_organization.operations.organize_single_file_operation import (
    OrganizeSingleFileOperation,
)
from ai_content_classifier.services.auto_organization.types import (
    AutoOrganizationOperationCode,
    OrganizationConfig,
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
def logger():
    return MagicMock()


@pytest.fixture
def db_service():
    service = MagicMock()
    service.get_content_by_path.return_value = _db_not_found()
    return service


def test_generate_preview_covers_all_structure_variants(logger, tmp_path):
    src = tmp_path / "doc.txt"
    src.write_text("abc", encoding="utf-8")
    target = tmp_path / "target"

    resolver = MagicMock(return_value=("Work/Docs", 2022))
    operation = GeneratePreviewOperation(logger=logger, category_year_resolver=resolver)

    for structure in [
        "By Category",
        "By Type",
        "By Year",
        "By Category/Year",
        "By Type/Category",
        "Unknown",
    ]:
        config = OrganizationConfig(
            target_directory=str(target),
            organization_structure=structure,
        )
        preview = operation.execute([str(src)], config)
        assert preview["file_count"] == 1
        assert isinstance(preview["structure"], dict)


def test_generate_preview_handles_per_file_and_top_level_errors(logger, tmp_path):
    src = tmp_path / "doc.txt"
    src.write_text("abc", encoding="utf-8")

    def resolver(file_path: str):
        if file_path.endswith("doc.txt"):
            raise RuntimeError("resolver error")
        return ("Work", 2022)

    operation = GeneratePreviewOperation(logger=logger, category_year_resolver=resolver)
    config = OrganizationConfig(
        target_directory=str(tmp_path / "target"),
        organization_structure="By Category",
    )

    preview = operation.execute([str(src)], config)
    assert preview["file_count"] == 0

    errored = operation.execute(None, config)  # type: ignore[arg-type]
    assert "error" in errored


def test_organize_single_file_operation_core_paths(
    db_service, logger, tmp_path, monkeypatch
):
    operation = OrganizeSingleFileOperation(db_service=db_service, logger=logger)

    source = tmp_path / "a.txt"
    source.write_text("abc", encoding="utf-8")
    target_dir = tmp_path / "target"
    target_dir.mkdir(parents=True, exist_ok=True)

    db_service.get_content_by_path.return_value = _db_ok(
        item=SimpleNamespace(category="Work", file_hash="h1")
    )

    copy_result = operation._perform_file_action(
        str(source),
        str(target_dir / "a.txt"),
        "copy",
    )
    assert copy_result.success is True

    invalid_action = operation._perform_file_action(
        str(source),
        str(target_dir / "b.txt"),
        "delete",
    )
    assert invalid_action.code == AutoOrganizationOperationCode.VALIDATION_ERROR

    monkeypatch.setattr(
        "ai_content_classifier.services.auto_organization.operations.organize_single_file_operation.shutil.copy2",
        lambda *_a, **_k: (_ for _ in ()).throw(FileExistsError("exists")),
    )
    conflict = operation._perform_file_action(
        str(source),
        str(target_dir / "c.txt"),
        "copy",
    )
    assert conflict.code == AutoOrganizationOperationCode.CONFLICT_ERROR

    monkeypatch.setattr(
        "ai_content_classifier.services.auto_organization.operations.organize_single_file_operation.shutil.copy2",
        lambda *_a, **_k: (_ for _ in ()).throw(OSError("io")),
    )
    fs_error = operation._perform_file_action(
        str(source),
        str(target_dir / "d.txt"),
        "copy",
    )
    assert fs_error.code == AutoOrganizationOperationCode.FILESYSTEM_ERROR

    monkeypatch.setattr(
        "ai_content_classifier.services.auto_organization.operations.organize_single_file_operation.os.path.getsize",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    unknown = operation._perform_file_action(
        str(source),
        str(target_dir / "e.txt"),
        "copy",
    )
    assert unknown.code == AutoOrganizationOperationCode.UNKNOWN_ERROR


def test_organize_single_file_operation_build_and_safe_getters(
    db_service, logger, tmp_path, monkeypatch
):
    operation = OrganizeSingleFileOperation(db_service=db_service, logger=logger)

    src = tmp_path / "file.txt"
    src.write_text("x", encoding="utf-8")
    config = OrganizationConfig(
        target_directory=str(tmp_path / "target"),
        organization_structure="By Category/Year",
    )

    db_service.get_content_by_path.return_value = _db_ok(
        item=SimpleNamespace(category="Work", creation_date=datetime(2023, 1, 1))
    )
    target = operation._build_target_path(str(src), config)
    assert "/Work/2023/" in target

    db_service.get_content_by_path.return_value = DatabaseOperationResult(
        success=False,
        code=DatabaseOperationCode.DB_ERROR,
        message="db error",
        data={"error": "db"},
    )
    assert operation._safe_get_content_item(str(src)) is None

    db_service.get_content_by_path.side_effect = RuntimeError("db crash")
    assert operation._safe_get_content_item(str(src)) is None

    monkeypatch.setattr(
        operation,
        "_build_target_path",
        lambda *_a, **_k: (_ for _ in ()).throw(ValueError("bad structure")),
    )
    result = operation.execute(str(src), config)
    assert result.code == AutoOrganizationOperationCode.UNKNOWN_ERROR
