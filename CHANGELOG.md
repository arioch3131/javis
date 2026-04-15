# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.5.0] - 2026-04-15

### Changed
- Merged reader behavior into one explicit implementation by moving enhanced/cached read logic into `ContentReader`.
- Converted `EnhancedContentReader` to a transitional compatibility shim inheriting `ContentReader` (no implicit magic delegation).

### Fixed
- Added explicit rollback in `QueryOptimizer._execute_query` for internally managed sessions when query execution fails.
- Removed the transactional anti-pattern `BEGIN IMMEDIATE` + immediate rollback from `ContentReader.find_items`.
- Added non-regression tests for:
  - rollback behavior in query optimizer (internal vs external session handling)
  - explicit merged reader behavior and API parity
  - content reader session lifecycle after transaction-pattern removal

## [1.4.0] - 2026-04-14

### Added
- Added an `Open file` action in file details (`FileDetailsDialog`) with dedicated signal wiring (`open_file_requested(str)`).
- Added a structured file-operation contract with `FileOperationResult` and `FileOperationCode` for consistent service/UI behavior.
- Added dedicated file operation modules under `services/file/operations/` and accompanying documentation (`docs/FILE_OPERATIONS_V1.fr.md`).
- Added targeted unit/integration coverage for open-file flow:
  - service-level OS opening behavior and error mapping
  - dialog signal/button states
  - presenter/UI error-message propagation

### Changed
- Implemented cross-platform open-file behavior via default OS app:
  - Windows: `os.startfile`
  - macOS: `open`
  - Linux: `xdg-open`
- Improved failure handling in the UI with actionable error messages for:
  - file not found (including non-file paths like folders/broken links)
  - missing default app association
  - access denied
  - unexpected system errors

### Fixed
- Prevented UI crashes during open-file failures by enforcing safe-fail handling and preserving dialog state.
- Improved diagnostics with warning/error logs around open-file failures and operation-level error context.

## [1.3.0] - 2026-04-13

### Added
- Added unified thumbnail disk-cache settings:
  - `thumbnails.cache.enabled`
  - `thumbnails.cache.ttl_sec`
  - `thumbnails.cache.cleanup_interval_sec`
  - `thumbnails.cache.max_size_mb`
  - `thumbnails.cache.renew_on_hit`
  - `thumbnails.cache.renew_threshold`
- Added a dedicated Tools action to clear thumbnail cache (`Tools > Database > Clear Thumbnail Cache`).
- Added a settings action button to clear thumbnail cache directly from the Thumbnails tab.

### Changed
- Upgraded `omni-cache` to `2.0.0` for DISK adapter support used by V1.3 thumbnail cache management.
- Extended `OmniCacheRuntime` with idempotent DISK adapter registration for thumbnails.
- Added compatibility strategy for `omni-cache` DISK max-size support:
  - `2.0.0`: `max_size` is ignored with explicit debug logging.
  - `2.1.0+`: `max_size` is auto-enabled from app settings without app-level API changes.
- `FilePresenter` now loads thumbnail cache settings from `ConfigService` with safe fallbacks and uses the registered DISK adapter when available.
- Unified thumbnail caching flow to rely on `omni-cache` DISK as the single source of truth for TTL/cleanup (removed app-managed duplicate disk TTL cleanup logic).
- Grid thumbnail pipeline now consumes generated pixmaps through cache-backed payloads instead of requiring app-managed thumbnail file paths.

### Fixed
- Added strict settings validation fallback behavior in `ConfigService` using per-key validation rules.

## [1.2.0] - 2026-04-13

### Added
- Centralized file-type helpers in `FileTypeService` (extension normalization, longest-match extension detection, content-type resolution, text-like detection, text format mapping).
- Added cross-module consistency tests for file type handling (`tests/unit/services/file/test_file_type_cross_module_consistency.py`).
- Expanded `FileTypeService` unit coverage for normalization/content-type/text-format behaviors.

### Changed
- Refactored scan, categorization, LLM, metadata extraction, text extraction, and thumbnail utilities to reuse `FileTypeService` instead of maintaining duplicated extension lists.
- Updated Windows release workflow to `softprops/action-gh-release@v3`.
- Updated tooling dependencies (`setuptools>=82.0.1`, `pytest==9.0.3`).

### Fixed
- Improved cross-module consistency for image/document detection and content-type assignment.
- Restored a clean `ruff check` state by fixing lint issues in examples and tests.

## [1.1.0] - 2026-04-12

### Changed
- Upgraded `omni-cache` to `v1.2.0` to align runtime caching behavior with recent SmartPool improvements.
- Optimized DB-backed filtering paths (`category`, `year`, `uncategorized`) to avoid repeated per-item lookups on large datasets.
- Added caching for filter option lists (unique categories, years, extensions) with proper invalidation on DB writes.
- Reworked file-data preparation for UI views to use batched reads instead of per-file DB access.
- Switched search index creation in the main window to lazy initialization so initial loads stay fast when no search is active.
- Removed thumbnail generation from the scan pipeline; thumbnails are now generated on demand by the view flow.

### Fixed
- Fixed SQLAlchemy detached-instance failures during year filtering by loading required fields eagerly.
- Improved query cache invalidation after content writes (create/update/delete/clear) to avoid stale reads.
- Clearing the content database now also clears the thumbnail disk cache (and runtime thumbnail cache when available), preventing stale thumbnail leftovers.

### Security
- Upgraded `pypdf` to `6.10.0` to address a memory-usage vulnerability where a crafted PDF could trigger excessive memory consumption when parsing XMP metadata.

## [1.0.0] - 2026-04-05

### Added
- Alembic migration infrastructure (`src/ai_content_classifier/db_migrations/`) with an initial baseline schema migration.
- Migration runner integration (`src/ai_content_classifier/services/database/migrations.py`) used during database initialization.
- Decategorization MVP to clear category on a single file from file details/contextual actions.
- Windows setup helper script (`install_windows.ps1`) for source-based installation.
- Developer tooling and contribution assets (`.githooks/pre-commit`, `scripts/install_git_hooks.sh`, `scripts/check_coverage_threshold.py`, `CONTRIBUTING.md`).
- New documentation screenshots under `docs/assets/`.
- New unit tests for migrations, scan pipeline, i18n service, dependency manager, text extraction, app context, and metadata extractors.

### Changed
- Database initialization now applies versioned migrations instead of relying on direct metadata table creation.
- CI/documentation/project metadata files were updated (`.github/workflows/ci.yml`, `README.md`, `README.fr.md`, `pyproject.toml`, `.gitignore`, `LICENSE`).
- CI quality gates were tightened with `ruff format --check` and per-module coverage threshold enforcement (>=80% for non-`views` scope).
- Large update and expansion of the existing unit test suite across services, repositories, models, controllers, and UI components.
- Adjustments in core application layers (database services, content models/writers, file manager/presenter, and main window UI components).
- Scan workflow UI now displays the currently scanned directory during scan operations.

## [1.0.0-beta.1] - 2026-03-20

### Added
- Initial public beta release of Javis.
- PyQt6 desktop application for AI-assisted content classification and organization.
- Support for local model inference with Ollama for document and image categorization.
- English/French internationalization support.
- Test suite, linting, and CI workflow for code quality checks.
- Windows build pipeline with packaged executable output.
