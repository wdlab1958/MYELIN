"""비식별 검사 패턴과 익명 지표."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from myelin_cli.main import app
from myelin_core.config import update_config
from myelin_core.deid import DeidPolicy, _mask, scan_text
from myelin_core.metrics import MetricsError, anonymous_metrics, bucket

TODAY = date(2026, 10, 18)


@pytest.mark.parametrize(
    ("line", "kind"),
    [
        ("서버 192.168.10.5 에서", "ip"),
        ("주소 2001:db8::ff00:42:8329", "ip"),
        ("연락 hong.gildong@example.com", "email"),
        ("010-1234-5678 로 연락", "phone"),
        ("02-345-6789", "phone"),
        ("주민번호 900101-1234567", "rrn"),
        ("카드 4111 1111 1111 1111", "card"),
        ("-----BEGIN RSA PRIVATE KEY-----", "private_key"),
        ("key AKIAABCDEFGHIJKLMNOP", "cloud_key"),
        ("ghp_abcdefghijklmnopqrstuvwxyz0123", "token"),
        ("password = hunter2pass", "secret"),
        ("비밀번호: Sup3rSecret!", "secret"),
        ("https://wiki.corp/page", "internal_url"),
        ("http://localhost:8080/x", "internal_url"),
    ],
)
def test_detects(line: str, kind: str) -> None:
    kinds = {f.kind for f in scan_text(line).findings}
    assert kind in kinds


@pytest.mark.parametrize(
    "line",
    [
        "id: 20261018-0900-wcet-budget",
        "created: 2026-10-18",
        "버전 v1.2.3 과 Python 3.12",
        "https://docs.python.org/3/ 참고",
        "카드처럼 보이는 숫자 1234 5678 9012 3456",  # Luhn 불일치
        "p99 지연 12.5ms, 주기 1000Hz",
    ],
)
def test_no_false_positive(line: str) -> None:
    assert scan_text(line).clean, scan_text(line).findings


def test_policy_allow_deny_internal_domains() -> None:
    policy = DeidPolicy(
        deny=["ACME Bank"], allow=["192.0.2.10"], internal_domains=["corp.example.com"]
    )
    text = "문서 예시 192.0.2.10\nACME BANK 사례\nhttps://git.corp.example.com/x\n"
    kinds = [f.kind for f in scan_text(text, policy).findings]
    assert kinds == ["deny_term", "internal_url"]


def test_mask_never_echoes_secret() -> None:
    f = scan_text("password = hunter2pass").findings[0]
    assert "hunter2pass" not in f.excerpt and f.excerpt.startswith("hu")
    assert _mask("abc") == "***"


# ── 지표 ─────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("n", "label"),
    [(0, "0"), (1, "1-4"), (4, "1-4"), (5, "5-9"), (999, "500-999"), (5000, "1000+")],
)
def test_bucket(n: int, label: str) -> None:
    assert bucket(n) == label


def _opt_in(vault: Path) -> None:
    def mutate(data: Any) -> None:
        data["metrics"] = {"opt_in": True}

    _, text = update_config(vault, mutate)
    (vault / "myelin.yaml").write_text(text, encoding="utf-8")


def test_metrics_opt_in_and_anonymity(vault: Path, put: Callable[[str, str], str]) -> None:
    with pytest.raises(MetricsError):
        anonymous_metrics(vault, TODAY)
    _opt_in(vault)
    data = anonymous_metrics(vault, TODAY)
    assert data["week"] == "2026-W42" and data["packs"] == ["myelin.core"]
    blob = json.dumps(data, ensure_ascii=False)
    for secret in ("Tester", "AI-ML-AX", "brian", str(vault), "2026-10-18"):
        assert secret not in blob
    assert set(data) == {
        "schema", "week", "level", "packs", "domains", "notes", "verified_notes",
        "verified_last_7d", "ai_drafts_pending", "ai_promotion_rate", "orphan_ratio",
        "cross_domain_ratio", "inbox_items", "commons_enabled", "mcp_write_drafts",
    }  # fmt: skip


def test_cli_metrics_and_commons(vault: Path, commons: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    today = ["--today", "2026-10-18"]
    assert runner.invoke(app, ["metrics", str(vault), *today]).exit_code == 1
    _opt_in(vault)
    out = tmp_path / "m.json"
    res = runner.invoke(app, ["metrics", str(vault), "--out", str(out), *today])
    assert res.exit_code == 0 and json.loads(out.read_text(encoding="utf-8"))["schema"] == 1
    assert '"week"' in runner.invoke(app, ["metrics", str(vault), *today]).output

    new = tmp_path / "c-new"
    res = runner.invoke(app, ["commons", "init", str(new), "--org", "Org"])
    assert res.exit_code == 0, res.output
    assert runner.invoke(app, ["commons", "init", str(new), "--org", "Org"]).exit_code == 1
    assert (
        runner.invoke(app, ["commons", "link", str(vault), str(tmp_path / "none")]).exit_code == 1
    )
    assert "enabled: false" in (vault / "myelin.yaml").read_text(encoding="utf-8")  # 실패 시 미변경
    res = runner.invoke(app, ["commons", "link", str(vault), str(commons)])
    assert res.exit_code == 0, res.output
    text = (vault / "myelin.yaml").read_text(encoding="utf-8")
    assert "enabled: true" in text and str(commons) in text and "# 3+1" in text

    note = (
        "---\nid: 20261018-0900-ok\ntype: evergreen\ndomain: [AI-ML-AX]\nstatus: verified\n"
        "origin: human\nshare: true\ncreated: 2026-10-17\n---\n# 교훈\n"
    )
    (vault / "30_Resources/a.md").write_text(note, encoding="utf-8")
    ok = runner.invoke(app, ["commons", "check", str(vault), "30_Resources/a.md", *today])
    assert ok.exit_code == 0 and "공개 가능" in ok.output
    (vault / "30_Resources/b.md").write_text(note.replace("# 교훈", "# 1.2.3.4"), encoding="utf-8")
    bad = runner.invoke(app, ["commons", "check", str(vault), "30_Resources/b.md", *today])
    assert bad.exit_code == 1 and "비식별" in bad.output
    missing = runner.invoke(app, ["commons", "check", str(vault), "30_Resources/zz.md", *today])
    assert missing.exit_code == 1
