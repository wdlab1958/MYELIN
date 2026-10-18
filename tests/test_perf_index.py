"""P4-T8 — 5,000-note Vault: index build and search p95 < 300 ms (gate). Run with MYELIN_PERF=1."""

from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

import pytest

from myelin_core.index import open_index
from myelin_core.vault import Vault

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import gen_perf_vault  # type: ignore[import-not-found]

QUERIES = [
    "미엘린",
    "실시간 데드라인",
    "wcet",
    "executor ros2",
    "보행 실험",
    "설계 규칙",
    "평가",
    "quantization guardrail",
    "sim2real",
    "교훈 특허",
    "플랫폼",
    "latency",
    "컨설팅 고객",
    "로드맵 제안서",
    "scheduler",
    "검증 승격 노트",
]


@pytest.mark.perf
def test_search_p95_under_300ms_on_5000_notes(tmp_path: Path) -> None:
    root = tmp_path / "perf"
    n = gen_perf_vault.gen(root, 5000)
    vault = Vault.open(root)
    t0 = time.perf_counter()
    idx = open_index(vault)
    build = time.perf_counter() - t0
    assert idx.count() == n, idx.parse_errors()[:3]
    # warm
    idx.search("미엘린")
    samples: list[float] = []
    for _ in range(4):
        for q in QUERIES:
            t = time.perf_counter()
            hits = idx.search(q, limit=20)
            samples.append((time.perf_counter() - t) * 1000)
            assert isinstance(hits, list)
    for q in ("wcet", "미엘린"):
        t = time.perf_counter()
        idx.search(q, domain="D2", status="verified")
        samples.append((time.perf_counter() - t) * 1000)
    samples.sort()
    p95 = samples[int(len(samples) * 0.95) - 1]
    median = statistics.median(samples)
    t = time.perf_counter()
    r = idx.refresh()
    incremental = (time.perf_counter() - t) * 1000
    idx.close()
    print(
        f"\nindex build {build:.1f}s · search p50 {median:.1f}ms p95 {p95:.1f}ms · "
        f"no-op refresh {incremental:.0f}ms"
    )
    assert p95 < 300.0, f"p95 {p95:.1f}ms ≥ 300ms"
    assert r.changed == 0
