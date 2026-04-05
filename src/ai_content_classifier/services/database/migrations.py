"""
Alembic migration runner for application startup.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.engine import Engine


def _migration_script_location() -> str:
    """Returns the absolute path to the packaged Alembic script directory."""
    return str(Path(__file__).resolve().parents[2] / "db_migrations")


def run_migrations(engine: Engine, db_path: str) -> None:
    """
    Runs Alembic migrations to the latest revision using the provided engine.

    Args:
        engine: SQLAlchemy engine bound to the target database.
        db_path: Database path used to populate Alembic configuration.
    """
    from alembic import command
    from alembic.config import Config

    config = Config()
    config.set_main_option("script_location", _migration_script_location())
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
