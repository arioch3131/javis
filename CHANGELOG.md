# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
