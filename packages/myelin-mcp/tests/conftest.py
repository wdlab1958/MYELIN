from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from myelin_core.config import parse_config
from myelin_core.loader import discover_packs, resolve
from myelin_core.scaffold import apply_plan, plan_init

ROOT = Path(__file__).resolve().parents[3]


def note(vault: Path, rel: str, *, classification: str = "internal", **fm: str) -> Path:
    data = {
        "id": fm.pop("id", f"20261018-0900-{abs(hash(rel)) % 10**8}"),
        "type": fm.pop("type", "evergreen"),
        "domain": fm.pop("domain", "[AI-ML-AX]"),
        "status": fm.pop("status", "verified"),
        "origin": fm.pop("origin", "human"),
        "classification": classification,
        "created": fm.pop("created", "2026-10-18"),
        "tags": fm.pop("tags", "[]"),
    }
    body = fm.pop("body", "본문")
    path = vault / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    head = "".join(f"{k}: {v}\n" for k, v in data.items())
    path.write_text(f"---\n{head}---\n{body}\n", encoding="utf-8")
    return path


def make_vault(path: Path, *, level: int = 1, write_drafts: bool = False) -> Path:
    packs = resolve(["brian.physical-ai"], discover_packs(ROOT / "packs"))
    cfg = parse_config(
        {
            "owner": {"name": "t"},
            "packs": ["myelin.core", "brian.physical-ai"],
            "domains": {"primary": "AI-ML-AX", "research": "EMBEDDED-SW"},
            "level": level,
            "mcp": {"write_drafts": write_drafts},
        }
    )
    apply_plan(path, plan_init(cfg, packs, date(2026, 10, 18)))
    note(path, "10_Domains/AI-ML-AX/WCET 예산은 추론 지연을 포함해야 한다.md",
         body="제어 주기 안에 정책 추론이 들어간다. WCET budget", tags="[rtos]")  # fmt: skip
    note(path, "10_Domains/EMBEDDED-SW/Watchdog은 정책이다.md", domain="[EMBEDDED-SW]",
         body="워치독 타이머 설계 교훈")  # fmt: skip
    note(path, "00_Inbox/ai-drafts/AI 초안.md", status="draft", origin="claude",
         type="literature", body="검토 전 초안 WCET")  # fmt: skip
    note(path, "30_Resources/고객 진단 결과.md", classification="confidential",
         body="비밀 WCET 고객명")  # fmt: skip
    note(path, "40_IP/아이디어.md", classification="confidential", type="idea-ip",
         body="출원 전 WCET 아이디어")  # fmt: skip
    note(path, "40_IP/candidates/후보.md", type="idea-ip", status="draft", origin="claude",
         body="후보 WCET")  # fmt: skip
    return path


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    return make_vault(tmp_path / "v")
