"""golden·violations Vault fixture 생성기. 실행: python tests/fixtures/vaults/gen_golden.py

- golden/brian : 실제 `myelin init` CLI를 임시 폴더에서 실행한 결과를 그대로 복사한다.
                 (Vault는 소스 저장소 안에 직접 만들 수 없으므로 — P2-T10)
- violations   : golden 위에 doctor 규칙별 위반 노트를 하나씩 심는다.
                 기대 결과는 violations.expected.yaml 이다.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from typer.testing import CliRunner

from myelin_cli.main import app

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
GOLDEN = HERE / "golden" / "brian"
VIOLATIONS = HERE / "violations"

GOLDEN_ARGS = [
    "--name", "Brian", "--pack", "brian.physical-ai",
    "--primary", "AI-ML-AX", "--research", "ROBOTICS-LEARNING",
    "--growth", "AUTO-DESIGN", "--extra", "EMBEDDED-SW",
    "--level", "1", "--today", "2026-10-18", "--yes",
]  # fmt: skip


def fm(nid: str, **over: str) -> str:
    data = {
        "id": f"20261018-{nid}",
        "type": "evergreen",
        "domain": "[AI-ML-AX]",
        "status": "verified",
        "origin": "human",
        "created": "2026-10-18",
    }
    data.update(over)
    return "---\n" + "".join(f"{k}: {v}\n" for k, v in data.items() if v != "-") + "---\n"


# (경로, 내용) — 주석은 기대되는 doctor 규칙
VIOLATION_NOTES: list[tuple[str, str]] = [
    # 정상 노트: 다른 노트들이 링크하는 허브 (오탐 0 확인용)
    ("10_Domains/AI-ML-AX/정상 허브.md", fm("1000-hub") + "# 허브\n\n[[중복 A]]\n"),
    # schema — status 누락
    ("10_Domains/AI-ML-AX/스키마 위반.md", fm("1001-schema", status="-") + "# x\n[[정상 허브]]\n"),
    # duplicate_id — 같은 id 두 개 (서로 링크해서 고아는 아님)
    ("10_Domains/EMBEDDED-SW/중복 A.md", fm("1002-dup", domain="[EMBEDDED-SW]") + "[[중복 B]]\n"),
    ("10_Domains/EMBEDDED-SW/중복 B.md", fm("1002-dup", domain="[EMBEDDED-SW]") + "[[중복 A]]\n"),
    # unknown_domain — 설치되지 않은 Domain
    (
        "30_Resources/미등록 도메인.md",
        fm("1003-unknown", domain="[SEC-CONSULT]") + "[[정상 허브]]\n",
    ),
    # share_confidential
    (
        "30_Resources/공유 모순.md",
        fm("1004-share", classification="confidential", share="true") + "[[정상 허브]]\n",
    ),
    # failclosed_link — verified 노트가 검증 안 된 AI 초안을 링크
    ("10_Domains/AI-ML-AX/검증 노트.md", fm("1005-verified") + "[[AI 초안]]\n"),
    (
        "00_Inbox/ai-drafts/AI 초안.md",
        fm("1006-draft", type="literature", status="draft", origin="claude") + "초안\n",
    ),
    # broken_link
    (
        "10_Domains/ROBOTICS-LEARNING/깨진 링크.md",
        fm("1007-broken", domain="[ROBOTICS-LEARNING]") + "[[정상 허브]] [[존재하지 않는 노트]]\n",
    ),
    # orphan
    ("20_Projects/고아 노트.md", fm("1008-orphan", type="adr") + "아무 링크도 없다\n"),
    # inbox_stale — 7일 넘게 Inbox에
    (
        "00_Inbox/오래된 메모.md",
        fm("1009-stale", type="fleeting", status="draft", domain="[]", created="2026-09-01")
        + "처리 안 됨\n",
    ),
    # 정상: 첨부 링크와 경로 링크는 깨진 링크가 아니다
    (
        "10_Domains/AUTO-DESIGN/첨부와 경로 링크.md",
        fm("1010-ok", domain="[AUTO-DESIGN]")
        + "![[bracket.png]] [[10_Domains/AI-ML-AX/정상 허브|허브]]\n",
    ),
]

EXPECTED = """\
# `myelin doctor violations --no-location --today 2026-10-18` 의 기대 결과 (정확히 이것만)
findings:
  - {rule: schema, path: 10_Domains/AI-ML-AX/스키마 위반.md}
  - {rule: duplicate_id, path: 10_Domains/EMBEDDED-SW/중복 A.md}
  - {rule: duplicate_id, path: 10_Domains/EMBEDDED-SW/중복 B.md}
  - {rule: unknown_domain, path: 30_Resources/미등록 도메인.md}
  - {rule: share_confidential, path: 30_Resources/공유 모순.md}
  - {rule: failclosed_link, path: 10_Domains/AI-ML-AX/검증 노트.md}
  - {rule: broken_link, path: 10_Domains/ROBOTICS-LEARNING/깨진 링크.md}
  - {rule: orphan, path: 20_Projects/고아 노트.md}
  - {rule: inbox_stale, path: 00_Inbox/오래된 메모.md}
"""


def build_golden() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "vault"
        result = CliRunner().invoke(
            app, ["init", str(target), *GOLDEN_ARGS, "--packs", str(ROOT / "packs")]
        )
        if result.exit_code != 0:
            sys.exit(result.output)
        shutil.rmtree(GOLDEN, ignore_errors=True)
        shutil.copytree(target, GOLDEN)


def build_violations() -> None:
    shutil.rmtree(VIOLATIONS, ignore_errors=True)
    shutil.copytree(GOLDEN, VIOLATIONS)
    for rel, text in VIOLATION_NOTES:
        path = VIOLATIONS / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    (VIOLATIONS / "10_Domains" / "AUTO-DESIGN" / "bracket.png").write_bytes(b"\x89PNG")
    (HERE / "violations.expected.yaml").write_text(EXPECTED, encoding="utf-8")


if __name__ == "__main__":
    build_golden()
    build_violations()
    print(f"golden -> {GOLDEN}\nviolations -> {VIOLATIONS}")
