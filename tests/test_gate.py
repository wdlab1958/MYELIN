"""Gate 판정기 자체에 대한 테스트."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("gate", ROOT / "scripts" / "gate.py")
assert _spec is not None and _spec.loader is not None
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


def test_undefined_phase_fails_closed() -> None:
    assert gate.main(["gate.py", "P9"]) == 1


def test_current_phase_is_parsed() -> None:
    assert gate.current_phase().startswith("P")


def test_every_phase_has_a_plan_document() -> None:
    for i in range(9):
        assert (ROOT / "docs" / "phases" / f"P{i}.md").exists()
