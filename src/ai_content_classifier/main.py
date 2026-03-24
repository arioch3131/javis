#!/usr/bin/env python3
"""
Main entry point for the Javis application.
Initializes the application, configures dependencies, and launches the main user interface.

ADAPTED VERSION with centralized exception handling system.
"""

import logging
import os
import shutil
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from ai_content_classifier.app_context import build_application_services
from ai_content_classifier.views.main_view import MainView


def setup_logging():
    """Configures logging for the application."""
    log_file_path = _resolve_log_file_path()
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    if log_file_path is not None:
        handlers.append(
            RotatingFileHandler(
                log_file_path,
                maxBytes=5 * 1024 * 1024,
                backupCount=3,
                encoding="utf-8",
            )
        )

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,  # Console + rotating log file
    )

    if log_file_path is not None:
        logging.info(f"Logging to file: {log_file_path}")


def _resolve_log_file_path() -> str | None:
    """Resolve a writable OS-specific log file location."""
    try:
        app_folder = "Javis"
        if sys.platform.startswith("win"):
            base_dir = Path(
                os.getenv("APPDATA", str(Path.home() / "AppData" / "Roaming"))
            )
        elif sys.platform == "darwin":
            base_dir = Path.home() / "Library" / "Logs"
        else:
            base_dir = Path(
                os.getenv("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))
            )

        log_dir = base_dir / app_folder / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        return str(log_dir / "javis.log")
    except Exception:
        return None


def _resolve_app_data_dir() -> Path | None:
    """Resolve a writable OS-specific persistent app data directory."""
    try:
        app_folder = "Javis"
        if sys.platform.startswith("win"):
            base_dir = Path(
                os.getenv("APPDATA", str(Path.home() / "AppData" / "Roaming"))
            )
        elif sys.platform == "darwin":
            base_dir = Path.home() / "Library" / "Application Support"
        else:
            base_dir = Path(
                os.getenv("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
            )

        data_dir = base_dir / app_folder
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir
    except Exception:
        return None


def _migrate_legacy_db_if_needed(target_db_path: Path) -> None:
    """
    Migrate an existing DB from legacy locations to the persistent data directory.

    Migration runs only when target DB does not already exist.
    """
    try:
        if target_db_path.exists():
            return

        legacy_candidates = [
            Path.cwd() / "app_settings.db",
            Path(__file__).resolve().parent / "app_settings.db",
            Path(sys.argv[0]).resolve().parent / "app_settings.db",
        ]

        target_resolved = target_db_path.resolve()
        for candidate in legacy_candidates:
            try:
                if not candidate.exists():
                    continue
                candidate_resolved = candidate.resolve()
                if candidate_resolved == target_resolved:
                    continue
                target_db_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(candidate, target_db_path)
                logging.info(
                    "Migrated database from legacy location to persistent path: %s -> %s",
                    candidate,
                    target_db_path,
                )
                return
            except Exception as e:
                logging.warning(
                    "Failed DB migration candidate %s -> %s: %s",
                    candidate,
                    target_db_path,
                    e,
                )
    except Exception as e:
        logging.warning("Legacy DB migration check failed: %s", e)


def _resolve_database_path() -> str:
    """Resolve persistent DB path, with fallback to legacy in-source path."""
    data_dir = _resolve_app_data_dir()
    if data_dir is not None:
        target_db_path = data_dir / "app_settings.db"
        _migrate_legacy_db_if_needed(target_db_path)
        return str(target_db_path)
    return str(Path(__file__).resolve().parent / "app_settings.db")


def main():
    """Main entry point of the application."""
    # 1. Logging configuration (EXISTING - unchanged)
    setup_logging()
    logging.info("Starting Javis application")

    # 2. Qt application initialization (EXISTING - unchanged)
    app = QApplication(sys.argv)
    app.setApplicationName("Javis")
    app.setOrganizationName("Javis")

    db_path = _resolve_database_path()
    logging.info("Using database path: %s", db_path)
    services = build_application_services(db_path)

    main_view = MainView(app, services)
    main_view.show()

    # 6. Start the Qt event loop (EXISTING - unchanged)
    logging.info("Entering application event loop")

    try:
        exit_code = app.exec()
    except KeyboardInterrupt:
        logging.info("Keyboard interruption detected")
        exit_code = 0

    # 7. Cleanup on exit (MODIFIED - added exception cleanup)
    logging.info("Application is closing")

    main_view.cleanup()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
