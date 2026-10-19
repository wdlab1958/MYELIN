"""Generate tests/fixtures/vaults/basic — a clean, deterministic MYELIN Vault (정본 §6.1 구조).

30+ synthetic notes covering every note type, status, origin, confidence and classification,
with wikilinks between them. Re-runnable (`python scripts/gen_fixture_vault.py`); output is
committed so tests do not depend on this script at runtime. No real customer/personal data.
"""

from __future__ import annotations

import json
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests/fixtures/vaults/basic"

# (path, id, type, domain, status, origin, confidence, classification, share, source, created, reviewed, tags, title, links)
N: list[dict[str, Any]] = []


def note(
    path: str,
    id_: str,
    type_: str,
    domain: Sequence[str],
    status: str,
    origin: str,
    conf: str,
    cls: str,
    share: bool,
    created: str,
    reviewed: str | None,
    tags: Sequence[str],
    title: str,
    links: Sequence[str] = (),
    source: Sequence[str] = (),
) -> None:
    N.append(
        dict(
            path=path,
            id=id_,
            type=type_,
            domain=list(domain),
            status=status,
            origin=origin,
            confidence=conf,
            classification=cls,
            share=share,
            source=list(source),
            created=created,
            reviewed=reviewed,
            tags=list(tags),
            title=title,
            links=list(links),
        )
    )


# --- MOCs (one per Domain of brian.physical-ai)
note(
    "10_Domains/D1/_MOC.md",
    "20260901-0900-d1-moc",
    "moc",
    ["D1"],
    "verified",
    "human",
    "high",
    "internal",
    False,
    "2026-09-01",
    "2026-10-01",
    ["moc"],
    "D1 AI/ML/AX Platform",
    links=[
        "LLM 평가는 오프라인 지표만으로 충분하지 않다",
        "RAG 청킹 전략 비교",
        "AX 저항은 통제감 상실에서 온다",
    ],
)
note(
    "10_Domains/D2/_MOC.md",
    "20260901-0901-d2-moc",
    "moc",
    ["D2"],
    "verified",
    "human",
    "high",
    "internal",
    False,
    "2026-09-01",
    "2026-10-01",
    ["moc"],
    "D2 Embedded SW",
    links=[
        "WCET 예산은 측정값의 1.5배로 잡는다",
        "ISR 안에서 로그를 찍지 않는다",
        "Safety 리뷰 체크리스트",
    ],
)
note(
    "10_Domains/D3/_MOC.md",
    "20260901-0902-d3-moc",
    "moc",
    ["D3"],
    "verified",
    "human",
    "high",
    "internal",
    False,
    "2026-09-01",
    "2026-10-01",
    ["moc"],
    "D3 자율학습 Robotics",
    links=[
        "Sim2Real 갭의 첫 용의자는 마찰 계수다",
        "Dogbot 보행 실험 07",
        "ROS2 Executor 선택 ADR",
    ],
)
note(
    "10_Domains/D4/_MOC.md",
    "20260901-0903-d4-moc",
    "moc",
    ["D4"],
    "verified",
    "human",
    "high",
    "internal",
    False,
    "2026-09-01",
    "2026-10-01",
    ["moc"],
    "D4 Auto Design (SolidWorks)",
    links=["설계 규칙은 실패에서 태어난다", "구멍 간 최소 간격 규칙", "DFM 검토 체크리스트"],
)

# --- D1 evergreen / literature / lesson / adr / idea-ip
note(
    "10_Domains/D1/LLM 평가는 오프라인 지표만으로 충분하지 않다.md",
    "20260905-1010-llm-eval-offline",
    "evergreen",
    ["D1"],
    "verified",
    "mixed",
    "high",
    "internal",
    True,
    "2026-09-05",
    "2026-09-20",
    ["llmops", "evaluation"],
    "LLM 평가는 오프라인 지표만으로 충분하지 않다",
    links=["Lit - LLM-as-a-Judge 한계", "_MOC"],
    source=["[[Lit - LLM-as-a-Judge 한계]]"],
)
note(
    "10_Domains/D1/RAG 청킹 전략 비교.md",
    "20260906-1400-rag-chunking",
    "evergreen",
    ["D1"],
    "unverified",
    "human",
    "medium",
    "internal",
    False,
    "2026-09-06",
    None,
    ["rag"],
    "RAG 청킹 전략 비교",
    links=["_MOC"],
)
note(
    "10_Domains/D1/AX 저항은 통제감 상실에서 온다.md",
    "20260910-0930-ax-resistance",
    "lesson",
    ["D1"],
    "verified",
    "human",
    "high",
    "internal",
    True,
    "2026-09-10",
    "2026-09-30",
    ["lesson", "ax"],
    "AX 저항은 통제감 상실에서 온다",
    links=["_MOC"],
)
note(
    "30_Resources/Lit - LLM-as-a-Judge 한계.md",
    "20260904-2200-lit-llm-judge",
    "literature",
    ["D1"],
    "verified",
    "claude",
    "medium",
    "public",
    False,
    "2026-09-04",
    "2026-09-05",
    ["llmops"],
    "Lit - LLM-as-a-Judge 한계",
    source=["https://example.org/llm-judge-limits"],
)
note(
    "10_Domains/D1/ADR - 평가 파이프라인은 오프라인+온라인 2단으로.md",
    "20260912-1100-adr-eval-pipeline",
    "adr",
    ["D1"],
    "verified",
    "mixed",
    "high",
    "internal",
    False,
    "2026-09-12",
    "2026-09-15",
    ["adr"],
    "ADR - 평가 파이프라인은 오프라인+온라인 2단으로",
    links=["LLM 평가는 오프라인 지표만으로 충분하지 않다"],
)
note(
    "40_IP/candidates/프롬프트 인젭션 다층 가드 아이디어.md",
    "20260915-1500-ip-prompt-guard",
    "idea-ip",
    ["D1"],
    "draft",
    "human",
    "low",
    "confidential",
    False,
    "2026-09-15",
    None,
    ["ip", "ai-security"],
    "프롬프트 인젭션 다층 가드 아이디어",
    links=["LLM 평가는 오프라인 지표만으로 충분하지 않다"],
)

# --- D2
note(
    "10_Domains/D2/WCET 예산은 측정값의 1.5배로 잡는다.md",
    "20260907-0800-wcet-budget",
    "evergreen",
    ["D2", "D3"],
    "verified",
    "mixed",
    "high",
    "internal",
    True,
    "2026-09-07",
    "2026-09-21",
    ["rtos", "control-loop"],
    "WCET 예산은 측정값의 1.5배로 잡는다",
    links=["Lit - ROS2 Executor", "_MOC"],
    source=["[[Lit - ROS2 Executor]]"],
)
note(
    "10_Domains/D2/ISR 안에서 로그를 찍지 않는다.md",
    "20260908-0815-isr-no-log",
    "lesson",
    ["D2"],
    "verified",
    "human",
    "high",
    "internal",
    True,
    "2026-09-08",
    "2026-09-22",
    ["lesson", "isr"],
    "ISR 안에서 로그를 찍지 않는다",
    links=["_MOC"],
)
note(
    "10_Domains/D2/Safety 리뷰 체크리스트.md",
    "20260909-0900-safety-checklist",
    "checklist",
    ["D2"],
    "verified",
    "mixed",
    "medium",
    "internal",
    False,
    "2026-09-09",
    "2026-09-23",
    ["checklist", "safety"],
    "Safety 리뷰 체크리스트",
    links=["ISR 안에서 로그를 찍지 않는다", "WCET 예산은 측정값의 1.5배로 잡는다"],
)
note(
    "30_Resources/Lit - ROS2 Executor.md",
    "20260903-2100-lit-ros2-executor",
    "literature",
    ["D2", "D3"],
    "verified",
    "human",
    "high",
    "public",
    False,
    "2026-09-03",
    "2026-09-04",
    ["ros2"],
    "Lit - ROS2 Executor",
    source=["https://docs.ros.org/en/rolling/Concepts/Intermediate/About-Executors.html"],
)
note(
    "10_Domains/D2/Edge AI 양자화 결정.md",
    "20260918-1300-edge-quant",
    "adr",
    ["D2"],
    "unverified",
    "claude",
    "medium",
    "internal",
    False,
    "2026-09-18",
    None,
    ["adr", "edge-ai"],
    "Edge AI 양자화 결정",
    links=["_MOC"],
)

# --- D3
note(
    "10_Domains/D3/Sim2Real 갭의 첫 용의자는 마찰 계수다.md",
    "20260911-1000-sim2real-friction",
    "evergreen",
    ["D3"],
    "verified",
    "human",
    "medium",
    "internal",
    True,
    "2026-09-11",
    "2026-09-25",
    ["sim2real"],
    "Sim2Real 갭의 첫 용의자는 마찰 계수다",
    links=["Dogbot 보행 실험 07", "_MOC"],
)
note(
    "10_Domains/D3/Dogbot 보행 실험 07.md",
    "20260913-1600-dogbot-exp-07",
    "experiment",
    ["D3"],
    "verified",
    "mixed",
    "medium",
    "internal",
    False,
    "2026-09-13",
    "2026-09-14",
    ["experiment", "dogbot"],
    "Dogbot 보행 실험 07",
    links=["Sim2Real 갭의 첫 용의자는 마찰 계수다"],
)
note(
    "10_Domains/D3/Dogbot 보행 실험 08.md",
    "20260920-1600-dogbot-exp-08",
    "experiment",
    ["D3"],
    "draft",
    "human",
    "low",
    "internal",
    False,
    "2026-09-20",
    None,
    ["experiment", "dogbot"],
    "Dogbot 보행 실험 08",
    links=["Dogbot 보행 실험 07"],
)
note(
    "10_Domains/D3/ROS2 Executor 선택 ADR.md",
    "20260914-0900-adr-ros2-executor",
    "adr",
    ["D3"],
    "verified",
    "human",
    "high",
    "internal",
    False,
    "2026-09-14",
    "2026-09-16",
    ["adr", "ros2"],
    "ROS2 Executor 선택 ADR",
    links=["Lit - ROS2 Executor", "WCET 예산은 측정값의 1.5배로 잡는다"],
)
note(
    "10_Domains/D3/보상 함수 악용 교훈.md",
    "20260916-1700-reward-hack",
    "lesson",
    ["D3"],
    "unverified",
    "claude",
    "medium",
    "internal",
    False,
    "2026-09-16",
    None,
    ["lesson", "rl"],
    "보상 함수 악용 교훈",
    links=["_MOC"],
)

# --- D4
note(
    "10_Domains/D4/설계 규칙은 실패에서 태어난다.md",
    "20260917-1000-rules-from-failure",
    "evergreen",
    ["D4"],
    "verified",
    "human",
    "high",
    "internal",
    True,
    "2026-09-17",
    "2026-09-27",
    ["design-rule"],
    "설계 규칙은 실패에서 태어난다",
    links=["구멍 간 최소 간격 규칙", "_MOC"],
)
note(
    "10_Domains/D4/구멍 간 최소 간격 규칙.md",
    "20260918-1030-hole-spacing-rule",
    "evergreen",
    ["D4"],
    "verified",
    "human",
    "high",
    "internal",
    False,
    "2026-09-18",
    "2026-09-28",
    ["design-rule", "dfm"],
    "구멍 간 최소 간격 규칙",
    links=["설계 규칙은 실패에서 태어난다"],
)
note(
    "10_Domains/D4/DFM 검토 체크리스트.md",
    "20260919-1100-dfm-checklist",
    "checklist",
    ["D4"],
    "unverified",
    "mixed",
    "medium",
    "internal",
    False,
    "2026-09-19",
    None,
    ["checklist", "dfm"],
    "DFM 검토 체크리스트",
    links=["구멍 간 최소 간격 규칙"],
)
note(
    "10_Domains/D4/매크로 재사용 교훈.md",
    "20260921-1500-macro-reuse",
    "lesson",
    ["D4"],
    "verified",
    "human",
    "medium",
    "internal",
    False,
    "2026-09-21",
    "2026-09-29",
    ["lesson", "macro"],
    "매크로 재사용 교훈",
    links=["_MOC"],
)
note(
    "40_IP/candidates/Agentic CAD 검증 루프.md",
    "20260922-1200-ip-agentic-cad",
    "idea-ip",
    ["D4", "D1"],
    "draft",
    "mixed",
    "low",
    "confidential",
    False,
    "2026-09-22",
    None,
    ["ip", "agentic-cad"],
    "Agentic CAD 검증 루프",
    links=["설계 규칙은 실패에서 태어난다", "LLM 평가는 오프라인 지표만으로 충분하지 않다"],
)

# --- Inbox: fleeting (human) + ai-drafts (claude)
note(
    "00_Inbox/오늘 회의 메모 - 평가 지표.md",
    "20261015-0930-meeting-eval",
    "fleeting",
    [],
    "draft",
    "human",
    "low",
    "internal",
    False,
    "2026-10-15",
    None,
    [],
    "오늘 회의 메모 - 평가 지표",
)
note(
    "00_Inbox/읽을 것 - executor 논문.md",
    "20261015-1000-read-executor",
    "fleeting",
    ["D3"],
    "draft",
    "human",
    "low",
    "internal",
    False,
    "2026-10-15",
    None,
    ["todo"],
    "읽을 것 - executor 논문",
)
note(
    "00_Inbox/clips/클립 - 양자화 블로그.md",
    "20261016-0800-clip-quant",
    "fleeting",
    ["D2"],
    "draft",
    "human",
    "low",
    "public",
    False,
    "2026-10-16",
    None,
    ["clip"],
    "클립 - 양자화 블로그",
    source=["https://example.org/quant"],
)
note(
    "00_Inbox/ai-drafts/Lit - 양자화 서베이.md",
    "20261016-0900-ai-lit-quant",
    "literature",
    ["D2"],
    "draft",
    "claude",
    "medium",
    "internal",
    False,
    "2026-10-16",
    None,
    ["edge-ai"],
    "Lit - 양자화 서베이",
    source=["https://example.org/quant-survey"],
)
note(
    "00_Inbox/ai-drafts/평가 지표 회의 - 원자 노트 1.md",
    "20261016-0910-ai-atomic-1",
    "evergreen",
    ["D1"],
    "draft",
    "claude",
    "low",
    "internal",
    False,
    "2026-10-16",
    None,
    ["evaluation"],
    "평가 지표 회의 - 원자 노트 1",
    links=["LLM 평가는 오프라인 지표만으로 충분하지 않다"],
)
note(
    "00_Inbox/ai-drafts/인터뷰 - 데드라인 미스 교훈.md",
    "20261017-1100-ai-interview-deadline",
    "lesson",
    ["D2"],
    "draft",
    "claude",
    "medium",
    "internal",
    False,
    "2026-10-17",
    None,
    ["lesson", "interview"],
    "인터뷰 - 데드라인 미스 교훈",
    links=["WCET 예산은 측정값의 1.5배로 잡는다"],
)
note(
    "00_Inbox/ai-drafts/Dogbot 실험 09 초안.md",
    "20261017-1500-ai-dogbot-09",
    "experiment",
    ["D3"],
    "draft",
    "claude",
    "low",
    "internal",
    False,
    "2026-10-17",
    None,
    ["experiment"],
    "Dogbot 실험 09 초안",
    links=["Dogbot 보행 실험 08"],
)

# --- Journal / Outputs / deprecated
note(
    "50_Journal/2026-W41 주간 리뷰.md",
    "20261012-1800-weekly-w41",
    "fleeting",
    [],
    "verified",
    "mixed",
    "medium",
    "internal",
    False,
    "2026-10-12",
    "2026-10-12",
    ["weekly"],
    "2026-W41 주간 리뷰",
    links=["Dogbot 보행 실험 08", "DFM 검토 체크리스트"],
)
note(
    "80_Outputs/Physical AI 로드맵 v0.md",
    "20261010-1000-roadmap-v0",
    "evergreen",
    ["D1", "D2", "D3", "D4"],
    "unverified",
    "mixed",
    "medium",
    "internal",
    False,
    "2026-10-10",
    None,
    ["roadmap", "cross-domain"],
    "Physical AI 로드맵 v0",
    links=[
        "Sim2Real 갭의 첫 용의자는 마찰 계수다",
        "WCET 예산은 측정값의 1.5배로 잡는다",
        "설계 규칙은 실패에서 태어난다",
        "LLM 평가는 오프라인 지표만으로 충분하지 않다",
    ],
)
note(
    "99_Archive/구 평가 체크리스트.md",
    "20260801-0900-old-eval-checklist",
    "checklist",
    ["D1"],
    "deprecated",
    "human",
    "low",
    "internal",
    False,
    "2026-08-01",
    "2026-09-12",
    ["checklist"],
    "구 평가 체크리스트",
    links=["ADR - 평가 파이프라인은 오프라인+온라인 2단으로"],
)

MYELIN_YAML = """# <Vault>/myelin.yaml (정본 §5.3) — fixture: Brian 개인 Vault
owner: { name: Brian, team: A3-AI WG, email: brian@example.org }
language: ko
packs: [myelin.core, brian.physical-ai]
domains:
  primary: D1
  research: D3
  growth: D4
  extra: [D2]
level: 2
llm:
  default: claude
  route: { confidential: local, "40_IP/**": local }
commons: { enabled: false }
"""

CLAUDE_MD = """# Vault 운영 규칙 (렌더링 자리표시 — P2 CLI 가 Pack 에서 생성)

- AI 쓰기는 00_Inbox/ai-drafts/ 와 _patches/ 만 허용.
"""


def fm_yaml(n: dict[str, Any]) -> str:
    def lst(xs: Sequence[str]) -> str:
        return "[" + ", ".join(xs) + "]"

    def qlst(xs: Sequence[str]) -> str:
        return "[" + ", ".join(json.dumps(x, ensure_ascii=False) for x in xs) + "]"

    lines = [
        "---",
        f"id: {n['id']}",
        f"type: {n['type']}",
        f"domain: {lst(n['domain'])}",
        f"status: {n['status']}",
        f"origin: {n['origin']}",
        f"confidence: {n['confidence']}",
        f"classification: {n['classification']}",
        f"share: {'true' if n['share'] else 'false'}",
        f"source: {qlst(n['source'])}",
        f"created: {n['created']}",
    ]
    if n["reviewed"]:
        lines.append(f"reviewed: {n['reviewed']}")
    lines.append(f"tags: {lst(n['tags'])}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def qualify_moc_links() -> None:
    """`_MOC` → `10_Domains/<D>/_MOC` (Level 2 link-patch, Brian 2026-10-19).

    Every Domain folder has its own `_MOC.md`, so a bare `[[_MOC]]` is ambiguous in Obsidian and
    opens whichever file Obsidian picks first, not the MOC of the note's own Domain. The written
    link is `[[10_Domains/D1/_MOC|_MOC]]`: path-qualified (unambiguous), alias keeps the display.
    """
    for n in N:
        if "_MOC" not in n["links"]:
            continue
        folder = n["path"].rsplit("/", 1)[0]
        assert folder.startswith("10_Domains/"), n["path"]
        n["links"] = [f"{folder}/_MOC" if t == "_MOC" else t for t in n["links"]]


def body(n: dict[str, Any]) -> str:
    out = [
        f"# {n['title']}",
        "",
        f"> fixture note ({n['type']}, {n['status']}, origin {n['origin']})",
        "",
    ]
    if n["links"]:
        out.append("## 연결")
        out += [f"- [[{t}|_MOC]]" if t.endswith("/_MOC") else f"- [[{t}]]" for t in n["links"]]
        out.append("")
    if n["type"] == "moc":
        out += ["## Sub-MOC", "- (fixture)", ""]
    return "\n".join(out)


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    for d in [
        "00_Inbox/ai-drafts",
        "00_Inbox/clips",
        "20_Projects",
        "30_Resources",
        "40_IP/candidates",
        "50_Journal",
        "80_Outputs/drafts",
        "90_System/templates",
        "90_System/prompts",
        "99_Archive",
        "_patches",
    ]:
        (OUT / d).mkdir(parents=True, exist_ok=True)
        if not any((OUT / d).iterdir()):
            (OUT / d / ".gitkeep").write_text("", encoding="utf-8")
    (OUT / "myelin.yaml").write_text(MYELIN_YAML, encoding="utf-8")
    (OUT / "CLAUDE.md").write_text(CLAUDE_MD, encoding="utf-8")
    (OUT / "90_System/taxonomy.md").write_text("# Taxonomy (fixture)\n", encoding="utf-8")
    ids = [n["id"] for n in N]
    assert len(ids) == len(set(ids)), "duplicate ids in fixture definition"
    qualify_moc_links()
    for n in N:
        p = OUT / n["path"]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(fm_yaml(n) + body(n), encoding="utf-8")
    manifest = {
        "count": len(N),
        "notes": [{k: v for k, v in n.items() if k != "links"} | {"links": n["links"]} for n in N],
    }
    (OUT / ".fixture-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    # remove .gitkeep from dirs that now have files
    for gk in OUT.rglob(".gitkeep"):
        if len(list(gk.parent.iterdir())) > 1:
            gk.unlink()
    print(f"wrote {len(N)} notes to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
