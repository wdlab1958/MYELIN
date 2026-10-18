"""Generate a synthetic Vault with N notes for the P4 performance gate (search p95 < 300 ms).

Not committed — written to a temp dir by the perf test (or by hand: `python scripts/gen_perf_vault.py <dir> 5000`).
Deterministic (seeded). Korean + English vocabulary so trigram FTS and LIKE paths are both exercised.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

WORDS_KO = [
    "미엘린",
    "실시간",
    "데드라인",
    "보행",
    "실험",
    "시뮬레이션",
    "마찰",
    "계수",
    "설계",
    "규칙",
    "평가",
    "지표",
    "검증",
    "승격",
    "노트",
    "링크",
    "용어",
    "정규화",
    "보안",
    "진단",
    "체크리스트",
    "교훈",
    "특허",
    "후보",
    "플랫폼",
    "컨설팅",
    "고객",
    "유형",
    "보고서",
    "제안서",
    "로드맵",
]
WORDS_EN = [
    "wcet",
    "executor",
    "ros2",
    "locomotion",
    "sim2real",
    "quantization",
    "guardrail",
    "rag",
    "llmops",
    "macro",
    "parametric",
    "dfm",
    "safety",
    "hil",
    "interrupt",
    "scheduler",
    "latency",
    "throughput",
    "embedding",
    "index",
    "vault",
    "obsidian",
    "claude",
]
TYPES = (
    ["evergreen"] * 5
    + ["lesson"] * 2
    + ["literature"] * 2
    + ["experiment", "checklist", "adr", "fleeting"]
)
STATUSES = ["verified"] * 5 + ["unverified"] * 2 + ["draft"] * 2 + ["deprecated"]
ORIGINS = ["human"] * 5 + ["mixed"] * 3 + ["claude"] * 2
DOMAINS = ["D1", "D2", "D3", "D4"]


def gen(root: Path, n: int, seed: int = 42) -> int:
    rng = random.Random(seed)
    root.mkdir(parents=True, exist_ok=True)
    (root / "myelin.yaml").write_text(
        "owner: {name: Perf}\npacks: [myelin.core, brian.physical-ai]\n"
        "domains: {primary: D1, research: D2, growth: D3, extra: [D4]}\nlevel: 2\n",
        encoding="utf-8",
    )
    for d in DOMAINS:
        (root / "10_Domains" / d).mkdir(parents=True, exist_ok=True)
    (root / "00_Inbox/ai-drafts").mkdir(parents=True, exist_ok=True)
    (root / "30_Resources").mkdir(exist_ok=True)
    titles: list[str] = []
    for i in range(n):
        words = rng.sample(WORDS_KO, 3) + rng.sample(WORDS_EN, 2)
        title = f"{' '.join(words)} {i:05d}"
        titles.append(title)
    for i, title in enumerate(titles):
        t = rng.choice(TYPES)
        status = rng.choice(STATUSES)
        origin = rng.choice(ORIGINS)
        if origin == "claude" and status == "draft":
            folder = "00_Inbox/ai-drafts"
        elif t == "literature":
            folder = "30_Resources"
        else:
            folder = f"10_Domains/{rng.choice(DOMAINS)}"
        doms = sorted(rng.sample(DOMAINS, rng.choice([1, 1, 1, 2])))
        day = 1 + (i % 28)
        month = 1 + (i // 28) % 9
        created = f"2026-{month:02d}-{day:02d}"
        reviewed = (
            f"\nreviewed: 2026-{min(month + 1, 12):02d}-{day:02d}" if status == "verified" else ""
        )
        links = [titles[rng.randrange(n)] for _ in range(rng.choice([0, 1, 2, 3]))]
        body_words = [rng.choice(WORDS_KO + WORDS_EN) for _ in range(rng.randint(60, 220))]
        body = " ".join(body_words)
        text = (
            f"---\nid: 2026{month:02d}{day:02d}-{(i % 1440) // 60:02d}{i % 60:02d}-n{i:05d}\n"
            f"type: {t}\ndomain: [{', '.join(doms)}]\nstatus: {status}\norigin: {origin}\n"
            f"confidence: medium\nclassification: internal\nshare: false\nsource: []\ncreated: {created}{reviewed}\n"
            f"tags: [{rng.choice(WORDS_EN)}, perf]\n---\n# {title}\n\n{body}\n\n"
            + "\n".join(f"- [[{lk}]]" for lk in links)
            + "\n"
        )
        (root / folder / f"{title}.md").write_text(text, encoding="utf-8")
    return n


if __name__ == "__main__":
    out = Path(sys.argv[1])
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
    print(f"wrote {gen(out, count)} notes to {out}")
