"""Pilot measurement (P7 Gate: 파일럿 5명 이상 온보딩 15분 이내).

    python scripts/pilot.py record --vault <path> [--note "팀/메모"] [--minutes 12.5]
    python scripts/pilot.py report
    python scripts/pilot.py check            # exit 0 when ≥ 5 participants recorded and all ≤ 15 min

Stores docs/reports/P7/pilot-results.jsonl (anonymous owner hash + minutes + note). Names are never stored.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "docs/reports/P7/pilot-results.jsonl"
REPORT = ROOT / "docs/reports/P7/pilot-results.md"
TARGET_MIN = 15.0
TARGET_N = 5


def _rows() -> list[dict[str, object]]:
    if not RESULTS.exists():
        return []
    return [json.loads(ln) for ln in RESULTS.read_text(encoding="utf-8").splitlines() if ln.strip()]


def record(args: argparse.Namespace) -> int:
    sys.path.insert(0, str(ROOT / "packages/myelin-core/src"))
    from myelin_core.commons import owner_hash
    from myelin_core.metrics import onboarding_minutes
    from myelin_core.vault import Vault

    vault = Vault.open(Path(args.vault))
    minutes = args.minutes if args.minutes is not None else onboarding_minutes(vault.root)
    if minutes is None:
        print(
            "no onboarding measurement yet (needs onboard_start + first_promote events) — pass --minutes",
            file=sys.stderr,
        )
        return 2
    row = {
        "owner": owner_hash(vault),
        "minutes": round(float(minutes), 2),
        "note": args.note,
        "date": date.today().isoformat(),
    }
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    with RESULTS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"recorded {row}")
    return report(args)


def report(_: argparse.Namespace) -> int:
    rows = _rows()
    ok = [r for r in rows if float(r["minutes"]) <= TARGET_MIN]  # type: ignore[arg-type]
    lines = [
        "# P7 파일럿 온보딩 결과 (자동 생성 — scripts/pilot.py)",
        "",
        f"- 참가자: {len(rows)} (목표 ≥ {TARGET_N}) · 15분 이내: {len(ok)}/{len(rows)} · 목표 ≤ {TARGET_MIN:.0f}분",
        "",
        "| # | owner(hash) | onboarding (min) | 판정 | 메모 | 일자 |",
        "|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(rows, 1):
        m = float(r["minutes"])  # type: ignore[arg-type]
        lines.append(
            f"| {i} | {r['owner']} | {m:.1f} | {'ok' if m <= TARGET_MIN else 'over'} | {r.get('note', '')} | {r.get('date', '')} |"
        )
    verdict = "PASS" if len(rows) >= TARGET_N and len(ok) == len(rows) else "PENDING"
    lines += ["", f"**Gate 판정: {verdict}** (5명 이상, 전원 15분 이내일 때 PASS)", ""]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"{REPORT.relative_to(ROOT)}: {len(rows)} rows, verdict {verdict}")
    return 0


def check(_: argparse.Namespace) -> int:
    rows = _rows()
    ok = [r for r in rows if float(r["minutes"]) <= TARGET_MIN]  # type: ignore[arg-type]
    if len(rows) >= TARGET_N and len(ok) == len(rows):
        print(f"pilot: {len(rows)} participants, all ≤ {TARGET_MIN:.0f} min")
        return 0
    print(
        f"pilot PENDING: {len(rows)} recorded (need ≥ {TARGET_N}), {len(ok)} within 15 min — human pilot not complete",
        file=sys.stderr,
    )
    return 1


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="pilot.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record")
    r.add_argument("--vault", required=True)
    r.add_argument("--note", default="")
    r.add_argument("--minutes", type=float, default=None)
    r.set_defaults(fn=record)
    sub.add_parser("report").set_defaults(fn=report)
    sub.add_parser("check").set_defaults(fn=check)
    ns = ap.parse_args(argv)
    return int(ns.fn(ns))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
