"""Generate tests/fixtures/vaults/seeded-violations — a Vault where every doctor rule is seeded.

`.seeded.json` lists the expected (rule, path) findings. The P2 Gate requires doctor to report
exactly that set: 100% detection, 0 false positives. Re-runnable.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests/fixtures/vaults/seeded-violations"

MYELIN_YAML = """owner: { name: Seed, team: QA, email: seed@example.org }
language: ko
packs: [myelin.core, brian.physical-ai]
domains:
  primary: D1
  research: D2
level: 1
"""


def fm(**kw: object) -> str:
    base: dict[str, object] = {
        "type": "evergreen",
        "domain": "[D1]",
        "status": "draft",
        "origin": "human",
        "confidence": "medium",
        "classification": "internal",
        "share": "false",
        "source": "[]",
        "created": "2026-10-01",
        "tags": "[]",
    }
    base.update(kw)
    lines = ["---", *[f"{k}: {v}" for k, v in base.items()], "---"]
    return "\n".join(lines) + "\n"


# path → (content, [expected rules])
FILES: dict[str, tuple[str, list[str]]] = {
    # clean anchors (linked to each other so neither is an orphan)
    "10_Domains/D1/_MOC.md": (
        fm(
            id="20261001-0900-d1-moc",
            type="moc",
            status="verified",
            reviewed="2026-10-01",
            tags="[moc]",
        )
        + "# D1\n- [[Good A]]\n- [[Good B]]\n",
        [],
    ),
    "10_Domains/D1/Good A.md": (fm(id="20261001-0901-good-a") + "# Good A\n[[Good B]]\n", []),
    "10_Domains/D1/Good B.md": (fm(id="20261001-0902-good-b") + "# Good B\n[[Good A]]\n", []),
    # 1 schema: missing frontmatter
    "10_Domains/D1/No Frontmatter.md": ("# no frontmatter at all\n", ["schema"]),
    # 1 schema: invalid enum
    "10_Domains/D1/Bad Status.md": (
        fm(id="20261001-0903-bad-status", status="approved") + "# x\n",
        ["schema"],
    ),
    # 2 fail-closed: verified note links to unverified claude note (the ai draft sits correctly in ai-drafts)
    "00_Inbox/ai-drafts/AI Draft.md": (
        fm(id="20261001-0904-ai-draft", origin="claude") + "# AI Draft\n[[Good A]]\n",
        [],
    ),
    "10_Domains/D1/Verified Links AI.md": (
        fm(id="20261001-0905-verified-links-ai", status="verified", reviewed="2026-10-02")
        + "# Verified Links AI\n[[AI Draft]] [[Good A]]\n",
        ["fail-closed"],
    ),
    # 2 fail-closed: claude draft outside ai-drafts
    "10_Domains/D1/Stray AI Draft.md": (
        fm(id="20261001-0906-stray-ai", origin="claude") + "# Stray\n[[Good A]]\n",
        ["fail-closed"],
    ),
    # 3 orphan: no links in or out, outside Inbox/Archive
    "10_Domains/D1/Lonely.md": (fm(id="20261001-0907-lonely") + "# Lonely\n", ["orphan"]),
    # 4 confidential-share
    "40_IP/candidates/Secret Shared.md": (
        fm(
            id="20261001-0908-secret-shared",
            type="idea-ip",
            classification="confidential",
            share="true",
        )
        + "# Secret\n[[Good A]]\n",
        ["confidential-share"],
    ),
    # 5 broken-link
    "10_Domains/D1/Dangling.md": (
        fm(id="20261001-0909-dangling") + "# Dangling\n[[Does Not Exist]] [[Good A]]\n",
        ["broken-link"],
    ),
    # 6 duplicate-id (two files, same id) — both are reported
    "10_Domains/D1/Dup One.md": (
        fm(id="20261001-0910-dup") + "# Dup One\n[[Good A]]\n",
        ["duplicate-id"],
    ),
    "10_Domains/D1/Dup Two.md": (
        fm(id="20261001-0910-dup") + "# Dup Two\n[[Good A]]\n",
        ["duplicate-id"],
    ),
    # 7 domain: unknown id
    "10_Domains/D1/Unknown Domain.md": (
        fm(id="20261001-0911-unknown-domain", domain="[D9]") + "# Unknown\n[[Good A]]\n",
        ["domain"],
    ),
    # 7 domain: moc without domain
    "10_Domains/D1/Empty MOC.md": (
        fm(
            id="20261001-0912-empty-moc",
            type="moc",
            domain="[]",
            status="verified",
            reviewed="2026-10-01",
        )
        + "# Empty MOC\n[[Good A]]\n",
        ["domain"],
    ),
    # 8 temporal: reviewed before created
    "10_Domains/D1/Time Travel.md": (
        fm(id="20261001-0913-time-travel", status="verified", reviewed="2026-09-01")
        + "# Time\n[[Good A]]\n",
        ["temporal"],
    ),
    # 8 temporal: verified without reviewed
    "10_Domains/D1/Verified No Review.md": (
        fm(id="20261001-0914-verified-no-review", status="verified") + "# VNR\n[[Good A]]\n",
        ["temporal"],
    ),
    # info only (not an error/warning): extra field preserved
    "10_Domains/D1/Has Alias.md": (
        fm(id="20261001-0915-has-alias", aliases="[HA]") + "# Has Alias\n[[Good A]]\n",
        ["extra-field"],
    ),
    # not violations: inbox fleeting without links, archived note without links, image embed
    "00_Inbox/Quick Thought.md": (
        fm(id="20261001-0916-quick", type="fleeting", domain="[]") + "# q\n",
        [],
    ),
    "99_Archive/Old.md": (fm(id="20261001-0917-old", status="deprecated") + "# old\n", []),
    "10_Domains/D1/With Image.md": (
        fm(id="20261001-0918-with-image") + "# img\n![[diagram.png]] [[Good A]]\n",
        [],
    ),
}


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    for d in [
        "00_Inbox/ai-drafts",
        "10_Domains/D1",
        "10_Domains/D2",
        "40_IP/candidates",
        "99_Archive",
        "90_System",
    ]:
        (OUT / d).mkdir(parents=True, exist_ok=True)
    (OUT / "myelin.yaml").write_text(MYELIN_YAML, encoding="utf-8")
    (OUT / "10_Domains/D2/.gitkeep").write_text("", encoding="utf-8")
    expected: list[dict[str, str]] = []
    for rel, (content, rules) in FILES.items():
        p = OUT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        for r in rules:
            expected.append({"rule": r, "path": rel})
    expected.sort(key=lambda e: (e["rule"], e["path"]))
    (OUT / ".seeded.json").write_text(
        json.dumps({"expected": expected, "files": len(FILES)}, ensure_ascii=False, indent=1)
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(FILES)} files, {len(expected)} expected findings to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
