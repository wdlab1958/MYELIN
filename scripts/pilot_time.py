"""파일럿 측정 보조 — Vault의 git 기록에서 '온보딩 시작 → 첫 verified 승격' 시간을 계산한다.

사용: uv run python scripts/pilot_time.py <Vault 경로> [--install-start 2026-10-20T10:00]
- 시작: `--install-start`(설치를 시작한 시각, 직접 기록)
  또는 Vault 첫 commit("myelin: start vault history").
- 끝: 첫 "myelin: promote" commit.
노트 내용은 읽지 않는다. 출력은 분 단위 숫자 하나 — results.yaml 에 옮겨 적는다.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def commit_times(vault: Path) -> list[tuple[datetime, str]]:
    out = subprocess.run(
        ["git", "-C", str(vault), "log", "--reverse", "--format=%cI%x1f%s"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    rows = []
    for line in out.splitlines():
        when, _, subject = line.partition("\x1f")
        rows.append((datetime.fromisoformat(when), subject))
    return rows


def onboarding_minutes(vault: Path, install_start: datetime | None = None) -> float:
    rows = commit_times(vault)
    if not rows:
        raise ValueError("git 기록이 없습니다 — 온보딩에서 '로컬 git으로 기록'을 켜야 합니다")
    start = install_start or rows[0][0]
    promoted = [t for t, s in rows if s.startswith("myelin: promote ")]
    if not promoted:
        raise ValueError("아직 verified 승격 기록이 없습니다")
    if start.tzinfo is None:
        start = start.replace(tzinfo=promoted[0].tzinfo)
    return round((promoted[0] - start).total_seconds() / 60, 1)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    ap.add_argument("vault", type=Path)
    ap.add_argument("--install-start", type=datetime.fromisoformat, default=None)
    args = ap.parse_args(argv)
    try:
        print(onboarding_minutes(args.vault, args.install_start))
    except (ValueError, subprocess.CalledProcessError) as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
