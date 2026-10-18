"""Guard 로직의 in-process 테스트 (커버리지용). 실제 Hook 동작은 tests/plugin/test_guard.py."""

import io
import json
from datetime import date
from pathlib import Path

from myelin_core.config import parse_config
from myelin_core.loader import discover_packs, resolve
from myelin_core.resources import myelin_guard as g
from myelin_core.scaffold import apply_plan, plan_init

ROOT = Path(__file__).resolve().parents[3]


def vault(tmp_path: Path, level: int) -> Path:
    packs = resolve(["brian.physical-ai"], discover_packs(ROOT / "packs"))
    cfg = parse_config(
        {
            "owner": {"name": "t"},
            "packs": ["myelin.core", "brian.physical-ai"],
            "domains": {"primary": "AI-ML-AX"},
            "level": level,
        }
    )
    v = tmp_path / "v"
    apply_plan(v, plan_init(cfg, packs, date(2026, 10, 18)))
    return v


def ev(tool: str, path: str, cwd: Path) -> dict[str, object]:
    return {"tool_name": tool, "tool_input": {"file_path": path}, "cwd": str(cwd)}


def test_allowed_prefixes_are_cumulative() -> None:
    assert g.allowed_prefixes(0) == ()
    assert "00_Inbox/ai-drafts/" in g.allowed_prefixes(3)
    assert "40_IP/candidates/" in g.allowed_prefixes(9)
    assert g.allowed_prefixes(-1) == ()


def test_check_with_home(tmp_path: Path) -> None:
    v = vault(tmp_path, 2)
    assert g.check(ev("Write", "_patches/a.md", v), v) is None
    reason = g.check(ev("Write", "10_Domains/AI-ML-AX/a.md", v), v)
    assert reason is not None and "Level 2" in reason
    assert g.check(ev("Write", str(tmp_path / "out.md"), v), v) is not None
    assert g.check(ev("Read", str(tmp_path / "out.md"), v), v) is None
    assert g.check({"tool_name": "Glob", "tool_input": {}}, v) is None


def test_read_rules(tmp_path: Path) -> None:
    v = vault(tmp_path, 1)
    (v / "40_IP/idea.md").write_text("x", encoding="utf-8")
    secret = v / "30_Resources/s.md"
    secret.write_text("---\nclassification: 'confidential'\n---\n", encoding="utf-8")
    plain = v / "30_Resources/p.md"
    plain.write_text("no frontmatter", encoding="utf-8")
    binary = v / "30_Resources/b.md"
    binary.write_bytes(b"\xff\xfe")
    assert g.check(ev("Read", "40_IP/idea.md", v), v) is not None
    assert g.check(ev("Read", "30_Resources/s.md", v), v) is not None
    assert g.check(ev("Read", "30_Resources/p.md", v), v) is None
    assert g.check(ev("Read", "30_Resources/b.md", v), v) is None
    assert g.is_confidential(v / "missing.md") is False


def test_main_exit_codes(tmp_path: Path) -> None:
    v = vault(tmp_path, 1)
    err = io.StringIO()
    ok = json.dumps(ev("Write", str(v / "00_Inbox/ai-drafts/a.md"), v))
    assert g.main(io.StringIO(ok), err) == 0 and err.getvalue() == ""
    bad = json.dumps(ev("Write", str(v / "30_Resources/a.md"), v))
    assert g.main(io.StringIO(bad), err) == 2
    assert g.main(io.StringIO("{"), err) == 2
    assert g.main(io.StringIO("[]"), err) == 2
    assert g.main(io.StringIO('{"tool_name": "Write", "tool_input": 1}'), err) == 2
    assert g.home_vault() is None  # 패키지 안에서는 Vault Hook이 아님
