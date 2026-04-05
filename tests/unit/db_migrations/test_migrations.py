from __future__ import annotations

import importlib
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

from sqlalchemy import create_engine


class _TxCtx:
    def __init__(self, owner):
        self.owner = owner

    def __enter__(self):
        self.owner.begin_calls += 1
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _DummyConfig:
    def __init__(self):
        self.config_file_name = None
        self.attributes = {}
        self.config_ini_section = "alembic"

    def get_main_option(self, _name):
        return "sqlite:///tmp.db"

    def get_section(self, _name, default=None):
        return {"sqlalchemy.url": "sqlite:///tmp.db"} if default is None else default


class _DummyContext:
    def __init__(self, offline: bool):
        self._offline = offline
        self.config = _DummyConfig()
        self.configure_calls = []
        self.begin_calls = 0
        self.run_calls = 0

    def configure(self, **kwargs):
        self.configure_calls.append(kwargs)

    def begin_transaction(self):
        return _TxCtx(self)

    def run_migrations(self):
        self.run_calls += 1

    def is_offline_mode(self):
        return self._offline


def _load_env_module(monkeypatch, offline: bool):
    module_name = "test_alembic_env_module"
    context = _DummyContext(offline=offline)
    fake_alembic = types.ModuleType("alembic")
    fake_alembic.context = context
    monkeypatch.setitem(sys.modules, "alembic", fake_alembic)
    monkeypatch.setitem(sys.modules, module_name, None)

    env_path = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "ai_content_classifier"
        / "db_migrations"
        / "env.py"
    )
    spec = importlib.util.spec_from_file_location(module_name, env_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, context


def test_env_runs_offline_at_import(monkeypatch):
    _, ctx = _load_env_module(monkeypatch, offline=True)
    assert ctx.run_calls == 1
    assert ctx.begin_calls == 1
    cfg = ctx.configure_calls[-1]
    assert cfg["literal_binds"] is True
    assert cfg["render_as_batch"] is True


def test_env_online_with_provided_connection_and_engine(monkeypatch):
    module, ctx = _load_env_module(monkeypatch, offline=True)
    called = []
    monkeypatch.setattr(
        module, "_run_migrations_with_connection", lambda conn: called.append(conn)
    )

    engine = create_engine("sqlite://")
    conn = engine.connect()
    try:
        module.config.attributes["connection"] = conn
        module.run_migrations_online()
        assert called and called[-1] is conn

        module.config.attributes["connection"] = engine
        module.run_migrations_online()
        assert len(called) >= 2
    finally:
        conn.close()
        engine.dispose()

    assert ctx.run_calls == 1


def test_env_online_uses_engine_from_config_when_no_connection(monkeypatch):
    module, _ctx = _load_env_module(monkeypatch, offline=True)
    called = []
    monkeypatch.setattr(
        module, "_run_migrations_with_connection", lambda conn: called.append(conn)
    )

    class _Connectable:
        def connect(self):
            class _ConnCtx:
                def __enter__(self_inner):
                    return "fake-conn"

                def __exit__(self_inner, exc_type, exc, tb):
                    return False

            return _ConnCtx()

    monkeypatch.setattr(module, "engine_from_config", lambda *a, **k: _Connectable())
    module.config.attributes["connection"] = None
    module.run_migrations_online()
    assert called == ["fake-conn"]


def test_baseline_upgrade_and_downgrade_paths(monkeypatch):
    baseline = importlib.import_module(
        "ai_content_classifier.db_migrations.versions.0001_baseline_schema"
    )

    bind = object()
    monkeypatch.setattr(baseline.op, "get_bind", lambda: bind)
    create_all = MagicMock()
    monkeypatch.setattr(baseline.Base.metadata, "create_all", create_all)

    class _InspectorNoColumn:
        def get_table_names(self):
            return ["content_items"]

        def get_columns(self, _table_name):
            return [{"name": "id"}]

    added = []
    monkeypatch.setattr(baseline.sa, "inspect", lambda _b: _InspectorNoColumn())
    monkeypatch.setattr(
        baseline.op,
        "add_column",
        lambda table, column: added.append((table, column.name)),
    )
    baseline.upgrade()
    create_all.assert_called_once_with(bind=bind)
    assert added == [("content_items", "classification_confidence")]

    class _InspectorWithColumn:
        def get_table_names(self):
            return ["content_items"]

        def get_columns(self, _table_name):
            return [{"name": "classification_confidence"}]

    monkeypatch.setattr(baseline.sa, "inspect", lambda _b: _InspectorWithColumn())
    baseline.upgrade()

    class _InspectorSubset:
        def get_table_names(self):
            return ["tags", "content_items"]

    dropped = []
    monkeypatch.setattr(baseline.sa, "inspect", lambda _b: _InspectorSubset())
    monkeypatch.setattr(baseline.op, "drop_table", lambda name: dropped.append(name))
    baseline.downgrade()
    assert dropped == ["tags", "content_items"]


def test_baseline_table_and_column_helpers():
    baseline = importlib.import_module(
        "ai_content_classifier.db_migrations.versions.0001_baseline_schema"
    )

    class _Inspector:
        def get_table_names(self):
            return ["a"]

        def get_columns(self, _table_name):
            return [{"name": "x"}]

    insp = _Inspector()
    assert baseline._has_table(insp, "a") is True
    assert baseline._has_table(insp, "b") is False
    assert baseline._has_column(insp, "a", "x") is True
    assert baseline._has_column(insp, "a", "y") is False
    assert baseline._has_column(insp, "b", "x") is False
