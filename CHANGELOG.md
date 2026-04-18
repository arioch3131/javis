# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.8.0] - 2026-04-18

### Added
- Added a unified contract for auto-organization under `services/auto_organization_service.py`:
  - `AutoOrganizationOperationResult`
  - `AutoOrganizationOperationCode`
  - canonical `data` keys (`source_path`, `target_path`, `action`, `error`) with V1.8 extensions (`size_bytes`, `file_hash`)
- Added a dedicated DB path update API for move workflows:
  - `ContentWriter.update_content_path(...)`
  - `ContentDatabaseService.update_content_path(...)`
- Added V1.8 documentation for the service contract in `docs/ORGANIZATION_SERVICE_V1.fr.md`, including explicit V1.9 dependency notes.

### Changed
- Refactored `AutoOrganizationService` to return the unified contract on file organization operations.
- Refactored `AutoOrganizationService` into a dedicated package layout:
  - `services/auto_organization/types.py`
  - `services/auto_organization/operations/`
  - `services/auto_organization/service.py`
- Updated organization controller/worker flow to consume unified operation results.
- Structured organization logs around `code`, `source_path`, `target_path`, `action`.
- Move path update now preserves stored `file_hash` without forced recomputation.

### Fixed
- Explicitly maps move-DB inconsistencies to standardized auto-organization codes (`database_error` / `conflict_error`) instead of generic failures.

## [1.7.0] - 2026-04-17

### Added
- Added a dedicated extensible filtering architecture under `services/filtering/`:
  - `ContentFilterService` orchestration pipeline
  - `FilterRegistry` explicit plugin registration
  - unified filtering contracts (`FilterCriterion`, `FilterOperationResult`, `FilterOperationCode`, `FilterOperator`, `FilterScope`)
  - built-in plugins: `file_type`, `category`, `year`, `extension`
- Added filter failure signaling/event flow for UI-level differentiation:
  - `FileManager.filter_failed` signal
  - `EventType.FILTER_ERROR` publishing in `SignalRouter`
  - category-aware status/log notifications (`validation_error`, `unknown_filter`, `database_error`, `unknown_error`)
- Added localized (`en`/`fr`) end-user templates for filter failure notifications in i18n catalogs.
- Added unit test coverage for the new filtering layer:
  - registry behavior (register/resolve/duplicate key)
  - service pipeline behavior (validation/unknown plugin/combined filtering)
  - plugin fallback behavior (year metadata fallback)
  - strict filter-result contract tests for `FilterOperationResult` (`code`/`message`/`data` shape)

### Changed
- Migrated `FileManager` cumulative filtering to consume `ContentFilterService` directly.
- Removed remaining filtering call-sites that routed through `FileOperationService`.
- Kept filter behavior parity for cumulative `AND` filtering across file type, category, year, and extension.
- Aligned filtering error mapping with file-operation contracts:
  - added `validation_error`, `unknown_filter`, `database_error` in `FileOperationCode`
  - mapped `FilterOperationCode` -> `FileOperationCode` in `FileManager` and `FileOperationService`
- Made DB error propagation explicit in filtering when fallback is disabled:
  - `ContentFilterService.apply_filters(..., allow_db_fallback=False)` now emits `FilterOperationCode.DATABASE_ERROR`.

### Removed
- Removed legacy filter operation module `services/file/operations/apply_filter_operation.py`.
- Removed residual filtering shim API from `FileOperationService`:
  - `apply_filter(...)`
  - `apply_filter_to_list(...)`
  - `apply_multi_category_filter_to_list(...)`
  - `apply_multi_year_filter_to_list(...)`
  - `apply_multi_extension_filter_to_list(...)`

### Security
- Bumped `pypdf` from `6.10.1` to `6.10.2` to address:
  - manipulated FlateDecode image dimensions can exhaust RAM
  - manipulated FlateDecode predictor parameters can exhaust RAM
  - possible long runtimes for wrong size values in incremental mode

## [1.6.0] - 2026-04-16

### Added
- Added a unified DB mutation contract in `services/database/types.py`:
  - `DatabaseOperationCode`
  - `DatabaseOperationResult`
  - canonical `data` keys (`deleted_count`, `ignored_count`, `failed_ids`, `failed_paths`, `normalized_paths`, `error`)

### Changed
- Refactored `ContentWriter` so all public mutations return `DatabaseOperationResult`:
  - `create_content_item`
  - `save_item_batch`
  - `update_metadata_batch`
  - `update_content_category`
  - `clear_content_category`
  - `clear_all_content`
  - `delete_content_by_paths`
- Refactored `ContentReader` so all public reads now return `DatabaseOperationResult` internally:
  - `find_items`, `count_all_items`, `get_items_pending_metadata`, `find_duplicates`
  - `get_statistics`, `get_content_by_path`, `get_uncategorized_items`
  - `get_unique_categories`, `get_unique_years`, `get_unique_extensions`
- Refactored `ContentDatabaseService` into a thinner facade:
  - reads now return `DatabaseOperationResult` publicly (no facade unwrapping)
  - reads delegate directly to `ContentReader` with aligned contracts
  - writes delegate to `ContentWriter` with cache invalidation on success
  - `get_unique_*` signatures now accept `session: Optional[Session] = None`
  - `force_database_sync` now uses `DatabaseService.get_session()`
- Updated UI/service call-sites to consume structured DB results for both write and read paths (file scan pipeline, file presenter, refresh/filter operations, UI handlers, categorization controller, auto-organization service).
- Removed legacy DB package split by migrating `QueryOptimizer` to `services/database/query_optimizer.py` and dropping `services/database/core` and `services/database/operations`.

### Fixed
- Stopped propagating raw SQLAlchemy exceptions through UI-facing DB mutation paths by mapping DB failures to `code=db_error` with safe-fail messages.

### Security
- Bumped `pypdf` from `6.10.0` to `6.10.1` to address long runtimes caused by wrong size values in cross-reference and object streams.

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
