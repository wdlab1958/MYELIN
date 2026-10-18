"""MCP 검색 성능 측정 — N개 노트 Vault를 임시로 만들고 search_notes 지연을 잰다 (P4 Gate).

사용: python scripts/bench_mcp.py --notes 5000 --p95-ms 300
측정 대상은 실제 도구 경로(VaultService.search_notes — 증분 갱신 확인 포함)다.
"""

from __future__ import annotations

import argparse
import random
import statistics
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

from myelin_core.config import parse_config
from myelin_core.loader import discover_packs, resolve
from myelin_core.scaffold import apply_plan, plan_init
from myelin_mcp.service import VaultService

ROOT = Path(__file__).resolve().parent.parent
DOMAINS = ["AI-ML-AX", "EMBEDDED-SW", "ROBOTICS-LEARNING", "AUTO-DESIGN"]
WORDS_KO = [
    "예산",
    "추론",
    "지연",
    "실시간",
    "제어",
    "설계",
    "규칙",
    "학습",
    "정책",
    "센서",
    "보안",
    "평가",
    "모델",
    "교훈",
    "실험",
    "구조",
]
WORDS_EN = [
    "WCET",
    "RTOS",
    "Sim2Real",
    "MPC",
    "watchdog",
    "parametric",
    "agent",
    "latency",
    "scheduler",
    "actuator",
]


def make_vault(root: Path, n: int, rng: random.Random) -> Path:
    packs = resolve(["brian.physical-ai"], discover_packs(ROOT / "packs"))
    cfg = parse_config(
        {
            "owner": {"name": "bench"},
            "packs": ["myelin.core", "brian.physical-ai"],
            "domains": {
                "primary": DOMAINS[0],
                "research": DOMAINS[1],
                "growth": DOMAINS[2],
                "extra": [DOMAINS[3]],
            },
        }
    )
    apply_plan(root, plan_init(cfg, packs, date(2026, 10, 18)))
    for i in range(n):
        dom = rng.sample(DOMAINS, k=rng.choice([1, 1, 2]))
        words = rng.choices(WORDS_KO + WORDS_EN, k=120)
        body = " ".join(words)
        path = root / "10_Domains" / dom[0] / f"note-{i:05d} {words[0]} {words[1]}.md"
        path.write_text(
            f"---\nid: 20261018-{i % 10000:04d}-n{i}\ntype: evergreen\ndomain: [{', '.join(dom)}]\n"
            f"status: {'verified' if i % 3 else 'draft'}\norigin: human\ncreated: 2026-10-18\n"
            f"tags: [t{i % 20}]\n---\n# note {i}\n\n{body}\n",
            encoding="utf-8",
        )
    return root


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--notes", type=int, default=5000)
    ap.add_argument("--queries", type=int, default=200)
    ap.add_argument("--p95-ms", type=float, default=300.0)
    args = ap.parse_args()
    rng = random.Random(42)
    with tempfile.TemporaryDirectory() as tmp:
        vault = make_vault(Path(tmp) / "v", args.notes, rng)
        t0 = time.perf_counter()
        svc = VaultService(vault)  # 첫 색인 생성 포함
        build_ms = (time.perf_counter() - t0) * 1000
        queries = [
            rng.choice(
                [
                    rng.choice(WORDS_KO),  # 2글자 → LIKE 경로
                    rng.choice(WORDS_EN),  # trigram
                    f"{rng.choice(WORDS_EN)} {rng.choice(WORDS_KO)}",  # 혼합
                ]
            )
            for _ in range(args.queries)
        ]
        times = []
        for i, q in enumerate(queries):
            if i % 50 == 0:
                svc.index._last_refresh = 0.0  # 주기적으로 증분 갱신 확인까지 포함해 잰다
            t = time.perf_counter()
            svc.search_notes(q, limit=10)
            times.append((time.perf_counter() - t) * 1000)
        p95 = statistics.quantiles(times, n=20)[18]
        ok = p95 < args.p95_ms
        print(
            f"notes={args.notes} index_build={build_ms:.0f}ms "
            f"search p50={statistics.median(times):.1f}ms p95={p95:.1f}ms max={max(times):.1f}ms "
            f"-> {'OK' if ok else 'FAIL'} (p95 < {args.p95_ms:.0f}ms)"
        )
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
