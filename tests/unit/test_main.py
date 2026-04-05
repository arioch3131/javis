from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import Mock


def _load_main_module():
    for module_name in ("PyQt6", "PyQt6.QtCore", "PyQt6.QtGui", "PyQt6.QtWidgets"):
        module_obj = sys.modules.get(module_name)
        if isinstance(module_obj, Mock):
            del sys.modules[module_name]
    main_module = importlib.import_module("ai_content_classifier.main")
    return importlib.reload(main_module)


def test_resolve_log_and_data_paths_and_fallbacks(monkeypatch, tmp_path):
    main_module = _load_main_module()
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setattr(main_module.sys, "platform", "linux")

    log_path = main_module._resolve_log_file_path()
    data_dir = main_module._resolve_app_data_dir()
    assert log_path is not None and log_path.endswith("javis.log")
    assert data_dir is not None and data_dir.name == "Javis"

    class _BoomPath(type(Path())):
        def mkdir(self, *args, **kwargs):
            raise OSError("boom")

    monkeypatch.setattr(main_module, "Path", _BoomPath)
    assert main_module._resolve_log_file_path() is None
    assert main_module._resolve_app_data_dir() is None


def test_migrate_legacy_db_and_resolve_database_path(monkeypatch, tmp_path):
    main_module = _load_main_module()
    target_dir = tmp_path / "data"
    target_dir.mkdir()
    target = target_dir / "app_settings.db"
    legacy = tmp_path / "app_settings.db"
    legacy.write_text("db", encoding="utf-8")

    monkeypatch.setattr(main_module, "Path", Path)
    real_migrate = main_module._migrate_legacy_db_if_needed
    monkeypatch.setattr(main_module, "_resolve_app_data_dir", lambda: target_dir)
    monkeypatch.setattr(main_module, "_migrate_legacy_db_if_needed", lambda _p: None)
    assert main_module._resolve_database_path() == str(target)
    monkeypatch.setattr(main_module, "_migrate_legacy_db_if_needed", real_migrate)

    copied = []
    monkeypatch.setattr(main_module.Path, "cwd", lambda: tmp_path)
    monkeypatch.setattr(main_module.sys, "argv", [str(tmp_path / "runner.py")])
    monkeypatch.setattr(
        main_module.shutil, "copy2", lambda src, dst: copied.append((src, dst))
    )
    main_module._migrate_legacy_db_if_needed(target)
    assert copied

    monkeypatch.setattr(main_module, "_resolve_app_data_dir", lambda: None)
    fallback = main_module._resolve_database_path()
    assert fallback.endswith("app_settings.db")


def test_setup_logging_uses_resolved_log_path(monkeypatch):
    main_module = _load_main_module()
    monkeypatch.setattr(main_module, "_resolve_log_file_path", lambda: "/tmp/javis.log")
    calls = []
    monkeypatch.setattr(
        main_module.logging, "basicConfig", lambda **kwargs: calls.append(kwargs)
    )
    monkeypatch.setattr(main_module.logging, "info", lambda *_a, **_k: None)

    main_module.setup_logging()
    assert calls
    assert len(calls[0]["handlers"]) == 2


def test_main_happy_path_and_keyboard_interrupt(monkeypatch):
    main_module = _load_main_module()

    class _App:
        def __init__(self, _argv):
            self.name = None
            self.org = None
            self._raise_keyboard = False

        def setApplicationName(self, value):
            self.name = value

        def setOrganizationName(self, value):
            self.org = value

        def exec(self):
            if self._raise_keyboard:
                raise KeyboardInterrupt()
            return 7

    class _View:
        def __init__(self, app, services):
            self.app = app
            self.services = services
            self.cleaned = False
            self.shown = False

        def show(self):
            self.shown = True

        def cleanup(self):
            self.cleaned = True

    exits = []
    monkeypatch.setattr(main_module, "setup_logging", lambda: None)
    monkeypatch.setattr(main_module, "QApplication", _App)
    monkeypatch.setattr(main_module, "_resolve_database_path", lambda: "/tmp/app.db")
    monkeypatch.setattr(
        main_module, "build_application_services", lambda _p: {"ok": True}
    )
    monkeypatch.setattr(main_module, "MainView", _View)
    monkeypatch.setattr(main_module.sys, "exit", lambda code: exits.append(code))
    monkeypatch.setattr(main_module.logging, "info", lambda *_a, **_k: None)

    main_module.main()
    assert exits[-1] == 7

    app = _App([])
    app._raise_keyboard = True
    monkeypatch.setattr(main_module, "QApplication", lambda _argv: app)
    main_module.main()
    assert exits[-1] == 0
