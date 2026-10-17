"""`minimal/` Vault fixture 생성기 (결정론적). 실행: python tests/fixtures/vaults/gen_minimal.py

생성 결과도 커밋한다. 노트를 바꾸려면 이 파일을 고친 뒤 다시 실행한다.
실제 개인·고객 정보는 넣지 않는다.
"""

from __future__ import annotations

import shutil
from pathlib import Path

OUT = Path(__file__).resolve().parent / "minimal"

# (경로, frontmatter 줄들, 본문)
NOTES: list[tuple[str, list[str], str]] = []


def note(path: str, fm: dict[str, str], body: str) -> None:
    NOTES.append((path, [f"{k}: {v}" for k, v in fm.items()], body))


def base(
    nid: str, ntype: str, domain: str, status: str = "verified", origin: str = "human"
) -> dict[str, str]:
    return {
        "id": f"20261018-{nid}",
        "type": ntype,
        "domain": domain,
        "status": status,
        "origin": origin,
        "created": "2026-10-18",
    }


# ── MOC 5 ────────────────────────────────────────────────────────────────
MOCS = {
    "AI-ML-AX": [
        "Fail-closed Agent 게이트",
        "평가 지표와 실서비스의 간극",
        "Thin Routing Shell 패턴",
    ],
    "EMBEDDED-SW": [
        "WCET 예산은 추론 지연을 포함해야 한다",
        "Watchdog은 정책이다",
        "HIL 시험의 범위",
    ],
    "ROBOTICS-LEARNING": ["Sim2Real 간극은 액추에이터에서 시작된다", "Domain Randomization의 범위"],
    "AUTO-DESIGN": ["설계 규칙은 코드로 쓴다", "Design Table로 구성 폭발을 막는다"],
    "SEC-CONSULT": ["진단 체크리스트는 lesson에서 자란다"],
}
for dom, links in MOCS.items():
    linked = "\n".join(f"- [[{t}]]" for t in links)
    note(
        f"10_Domains/{dom}/_MOC.md",
        {**base(f"0900-moc-{dom.lower()}", "moc", f"[{dom}]"), "tags": "[moc]"},
        f"# {dom} MOC\n\n## 핵심 Evergreen\n{linked}\n",
    )

# ── Evergreen 12 ─────────────────────────────────────────────────────────
EVERGREEN = [
    ("AI-ML-AX", "Fail-closed Agent 게이트", "[AI-ML-AX]", "[[HITL 승인 위치]] 와 함께 본다."),
    ("AI-ML-AX", "평가 지표와 실서비스의 간극", "[AI-ML-AX]", "[[Lit - LLM 평가 서베이]] 참고."),
    (
        "AI-ML-AX",
        "Thin Routing Shell 패턴",
        "[AI-ML-AX]",
        "코어는 단순하게. [[ADR - Pack은 데이터]]",
    ),
    ("AI-ML-AX", "HITL 승인 위치", "[AI-ML-AX]", "승인은 되돌리기 어려운 지점에 둔다."),
    (
        "EMBEDDED-SW",
        "WCET 예산은 추론 지연을 포함해야 한다",
        "[EMBEDDED-SW, ROBOTICS-LEARNING]",
        "제어 주기 안에 정책 추론이 들어간다. [[실험 - 정책 추론 지연 측정#결과|지연 측정]]",
    ),
    ("EMBEDDED-SW", "Watchdog은 정책이다", "[EMBEDDED-SW]", "[[Lesson - 1987 비행제어 리셋]]"),
    ("EMBEDDED-SW", "HIL 시험의 범위", "[EMBEDDED-SW]", "![[hil-bench.png]] 구성도."),
    (
        "ROBOTICS-LEARNING",
        "Sim2Real 간극은 액추에이터에서 시작된다",
        "[ROBOTICS-LEARNING, AUTO-DESIGN]",
        "[[실험 - 관절 토크 포화]] 에서 확인.",
    ),
    (
        "ROBOTICS-LEARNING",
        "Domain Randomization의 범위",
        "[ROBOTICS-LEARNING]",
        "과하면 학습이 안 된다.",
    ),
    ("AUTO-DESIGN", "설계 규칙은 코드로 쓴다", "[AUTO-DESIGN]", "[[ADR - 매크로는 C# API로]]"),
    ("AUTO-DESIGN", "Design Table로 구성 폭발을 막는다", "[AUTO-DESIGN]", "구성 수를 표로 통제."),
    (
        "SEC-CONSULT",
        "진단 체크리스트는 lesson에서 자란다",
        "[SEC-CONSULT]",
        "[[체크리스트 - 웹 진단 기본]]",
    ),
]
for i, (dom, title, domain, body) in enumerate(EVERGREEN):
    fm = base(f"{1000 + i}-evergreen-{i}", "evergreen", domain)
    fm["confidence"] = "high" if i % 2 == 0 else "medium"
    fm["tags"] = "['#core', pattern]" if i == 0 else "[]"
    if i == 4:
        fm["source"] = '"[[Lit - ROS2 Executor]]"'  # 스칼라 source → list 로 정규화
        fm["projects"] = '["[[Dogbot]]"]'
    note(f"10_Domains/{dom}/{title}.md", fm, f"# {title}\n\n{body}\n")

# ── Literature 4 ─────────────────────────────────────────────────────────
for i, (title, dom) in enumerate(
    [
        ("Lit - LLM 평가 서베이", "[AI-ML-AX]"),
        ("Lit - ROS2 Executor", "[ROBOTICS-LEARNING, EMBEDDED-SW]"),
        ("Lit - SolidWorks API 가이드", "[AUTO-DESIGN]"),
        ("Lit - 위협 모델링 입문", "[SEC-CONSULT]"),
    ]
):
    fm = base(f"{1100 + i}-lit-{i}", "literature", dom)
    fm["source"] = '["https://example.com/doc"]'
    body = (
        f"# {title}\n\n## 핵심 주장\n요약.\n\n```text\n[[코드 안의 가짜 링크]]\n```\n"
        "`[[인라인 가짜 링크]]`\n"
    )
    note(f"30_Resources/{title}.md", fm, body)

# ── Lesson 3 (era 추가 필드) ──────────────────────────────────────────────
for i, (title, dom, era) in enumerate(
    [
        ("Lesson - 1987 비행제어 리셋", "[EMBEDDED-SW]", "1980s"),
        ("Lesson - 현장에서만 나던 타이밍 버그", "[EMBEDDED-SW]", "1990s"),
        ("Lesson - 평가는 좋았는데 실패한 챗봇", "[AI-ML-AX]", "2020s"),
    ]
):
    fm = base(f"{1200 + i}-lesson-{i}", "lesson", dom, origin="mixed")
    fm["era"] = era
    note(f"10_Domains/{dom.strip('[]')}/{title}.md", fm, f"# {title}\n\n## 원칙화\n규칙 한 줄.\n")

# ── Experiment 2 ─────────────────────────────────────────────────────────
for i, title in enumerate(["실험 - 정책 추론 지연 측정", "실험 - 관절 토크 포화"]):
    fm = base(f"{1300 + i}-exp-{i}", "experiment", "[ROBOTICS-LEARNING]", status="unverified")
    fm["confidence"] = "low"
    fm["projects"] = '["[[Dogbot]]"]'
    note(f"20_Projects/Dogbot/{title}.md", fm, f"# {title}\n\n## 결과\n표 참조.\n")

# ── ADR 2 ────────────────────────────────────────────────────────────────
for i, (title, dom) in enumerate(
    [("ADR - Pack은 데이터", "[AI-ML-AX]"), ("ADR - 매크로는 C# API로", "[AUTO-DESIGN]")]
):
    note(
        f"20_Projects/{title}.md",
        base(f"{1400 + i}-adr-{i}", "adr", dom),
        f"# {title}\n\n## 결정\n...\n",
    )

# ── Checklist 1 ──────────────────────────────────────────────────────────
note(
    "10_Domains/SEC-CONSULT/체크리스트 - 웹 진단 기본.md",
    base("1500-checklist-web", "checklist", "[SEC-CONSULT]"),
    "# 체크리스트 - 웹 진단 기본\n\n- [ ] 인증 우회\n- [ ] 입력 검증\n",
)

# ── Inbox: fleeting 2, ai-drafts 3 ───────────────────────────────────────
for i, title in enumerate(["회의 메모 - 로봇 전원", "아이디어 - 설계 Agent"]):
    note(
        f"00_Inbox/{title}.md",
        base(f"{1600 + i}-fleeting-{i}", "fleeting", "[]", status="draft"),
        f"# {title}\n\n떠오른 생각.\n",
    )
for i, (title, dom) in enumerate(
    [
        ("Sim2Real 도메인 랜덤화 요약", "[ROBOTICS-LEARNING]"),
        ("SolidWorks API 매크로 카탈로그", "[AUTO-DESIGN]"),
        ("MCP 경로 제한 패턴", "[AI-ML-AX]"),
    ]
):
    fm = base(f"{1700 + i}-draft-{i}", "literature", dom, status="draft", origin="claude")
    fm["confidence"] = "low"
    note(f"00_Inbox/ai-drafts/{title}.md", fm, f"# {title}\n\n(AI 초안 — 검토 필요)\n")

# ── IP 1 (confidential) ──────────────────────────────────────────────────
fm = base("1800-ip-safe-autonomy", "idea-ip", "[AI-ML-AX, ROBOTICS-LEARNING]", status="draft")
fm["classification"] = "confidential"
fm["share"] = "false"
note(
    "40_IP/아이디어 - 승인 게이트 기반 로봇 행동 계획.md",
    fm,
    "# 아이디어\n\n[[Fail-closed Agent 게이트]] x [[Sim2Real 간극은 액추에이터에서 시작된다]]\n",
)


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    for rel, fm_lines, body in NOTES:
        target = OUT / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("---\n" + "\n".join(fm_lines) + "\n---\n" + body, encoding="utf-8")
    print(f"{len(NOTES)} notes -> {OUT}")


if __name__ == "__main__":
    main()
