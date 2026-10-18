"""Gate 판정기 자체에 대한 테스트."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("gate", ROOT / "scripts" / "gate.py")
assert _spec is not None and _spec.loader is not None
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


def test_undefined_phase_fails_closed() -> None:
    assert gate.main(["gate.py", "P99"]) == 1


def test_current_phase_is_parsed() -> None:
    assert gate.current_phase().startswith("P")


def test_every_phase_has_a_plan_document() -> None:
    for i in range(9):
        assert (ROOT / "docs" / "phases" / f"P{i}.md").exists()


def test_trademark_review_needs_real_value(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """주석만 있는 reviewed_by 는 사람 검토로 치지 않는다 (fail-closed)."""
    import importlib.util
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("gate_mod", root / "scripts/gate.py")
    assert spec and spec.loader
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    doc = tmp_path / "t.md"
    monkeypatch.setattr(gate, "TRADEMARK", doc)
    for text, ok in [
        ("reviewed_by:            # ← 사람이 기입\n", False),
        ("reviewed_by: null\n", False),
        ('reviewed_by: ""\n', False),
        ("no field\n", False),
        ("reviewed_by: Brian 2026-10-20 KIPRIS 확인  # 메모\n", True),
    ]:
        doc.write_text(text, encoding="utf-8")
        assert gate.p8_trademark_reviewed() is ok, text
