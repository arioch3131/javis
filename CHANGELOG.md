# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
