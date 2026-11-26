#!/usr/bin/env python3
"""Copy the product version from its single source to every file that has to state it.

Source: packages/myelin-core/src/myelin_core/_version.py (`__version__`).
Copies: the workspace + four package `pyproject.toml`, `uv.lock` (workspace members), the Hub web
`package.json` / `package-lock.json`, and the README status line (`상태: **v<version>**`).
Not a copy: `plugin/.claude-plugin/plugin.json` — the Claude Code plugin is versioned on its own
(named inline in the CHANGELOG as "plugin x.y.z").

    python scripts/sync_version.py            # write the copies
    python scripts/sync_version.py --check    # exit 1 and list the files that drifted

Standard library only. `tests/test_version.py` runs the check.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "packages/myelin-core/src/myelin_core/_version.py"
PYPROJECTS = (
    "pyproject.toml",
    "packages/myelin-core/pyproject.toml",
    "packages/myelin-cli/pyproject.toml",
    "packages/myelin-mcp/pyproject.toml",
    "packages/myelin-hub/api/pyproject.toml",
)
MEMBERS = ("myelin-workspace", "myelin-core", "myelin-cli", "myelin-mcp", "myelin-hub-api")
WEB = "packages/myelin-hub/web"


def source_version() -> str:
    m = re.search(r'^__version__ = "([^"]+)"$', SOURCE.read_text(encoding="utf-8"), re.M)
    if not m or not re.fullmatch(r"\d+\.\d+\.\d+", m.group(1)):
        raise SystemExit(f'{SOURCE}: no `__version__ = "X.Y.Z"` line')
    return m.group(1)


def _sub(text: str, pattern: str, repl: str, path: str, count: int = 1) -> str:
    new, n = re.subn(pattern, repl, text, count=count, flags=re.M)
    if n == 0:
        raise SystemExit(f"{path}: nothing matches {pattern!r} — update scripts/sync_version.py")
    return new


def expected(version: str) -> dict[str, str]:
    """path → the content each copy must have."""
    out: dict[str, str] = {}
    for rel in PYPROJECTS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        out[rel] = _sub(text, r'^version = "[^"]*"$', f'version = "{version}"', rel)
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
    for name in MEMBERS:
        lock = _sub(
            lock,
            rf'(^name = "{re.escape(name)}"\nversion = )"[^"]*"',
            rf'\g<1>"{version}"',
            "uv.lock",
        )
    out["uv.lock"] = lock
    pkg = (ROOT / WEB / "package.json").read_text(encoding="utf-8")
    out[f"{WEB}/package.json"] = _sub(
        pkg, r'^(  "version": )"[^"]*"', rf'\g<1>"{version}"', "package.json"
    )
    plock = (ROOT / WEB / "package-lock.json").read_text(encoding="utf-8")
    plock = _sub(plock, r'^(  "version": )"[^"]*"', rf'\g<1>"{version}"', "package-lock.json")
    out[f"{WEB}/package-lock.json"] = _sub(
        plock,
        r'(^    "": \{\n      "name": "myelin-hub-web",\n      "version": )"[^"]*"',
        rf'\g<1>"{version}"',
        "package-lock.json",
    )
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    out["README.md"] = _sub(
        readme, r"^(상태: \*\*v)\d+\.\d+\.\d+(\*\*)", rf"\g<1>{version}\g<2>", "README.md"
    )
    return out


def drift(version: str) -> list[str]:
    bad = [
        rel
        for rel, want in expected(version).items()
        if (ROOT / rel).read_text(encoding="utf-8") != want
    ]
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    first = re.search(r"^## v(\d+\.\d+\.\d+)", changelog, re.M)
    if not first or first.group(1) != version:
        bad.append(f"CHANGELOG.md (newest entry is v{first.group(1) if first else '?'})")
    return bad


def main(argv: list[str]) -> int:
    version = source_version()
    if "--check" in argv:
        bad = drift(version)
        for rel in bad:
            print(f"version drift: {rel} != {version}")
        print(f"version {version}: {'OK' if not bad else 'DRIFT'}")
        return 1 if bad else 0
    for rel, want in expected(version).items():
        p = ROOT / rel
        if p.read_text(encoding="utf-8") != want:
            p.write_text(want, encoding="utf-8")
            print(f"updated {rel}")
    print(f"version {version} written (CHANGELOG.md is edited by hand)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
