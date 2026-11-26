"""One source of version (packages/myelin-core/src/myelin_core/_version.py); the rest are copies."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import myelin_cli
import myelin_core
import myelin_hub_api
import myelin_mcp

ROOT = Path(__file__).resolve().parents[1]


def _sync() -> object:
    spec = importlib.util.spec_from_file_location("sync_version", ROOT / "scripts/sync_version.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["sync_version"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_every_package_reports_the_one_version() -> None:
    v = myelin_core.__version__
    assert re.fullmatch(r"\d+\.\d+\.\d+", v)
    assert myelin_cli.__version__ == myelin_mcp.__version__ == myelin_hub_api.__version__ == v
    for pkg in ("myelin-cli", "myelin-mcp", "myelin-hub/api"):
        init = next((ROOT / "packages" / pkg / "src").glob("*/__init__.py"))
        assert "__version__ =" not in init.read_text(encoding="utf-8")  # imported, not restated


def test_copies_do_not_drift() -> None:
    sync = _sync()
    version = sync.source_version()  # type: ignore[attr-defined]
    assert version == myelin_core.__version__
    assert sync.drift(version) == []  # type: ignore[attr-defined]


def test_drift_is_detected(tmp_path: Path, monkeypatch: object) -> None:
    sync = _sync()
    assert "README.md" in sync.drift("9.9.9")  # type: ignore[attr-defined]
