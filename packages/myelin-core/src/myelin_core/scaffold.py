"""Vault scaffolder: `init_vault` (fail-closed, never overwrites) and `add_domain`.

정본 §6.1 folder standard. Packs supply MOCs, templates, taxonomy, CLAUDE.md rules.
"""

from __future__ import annotations

import shutil
import stat
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from myelin_core.config import CONFIG_FILE, MyelinConfig, dump_config
from myelin_core.packs.loader import LoadedPack, PackRegistry, discover_packs, resolve_packs
from myelin_core.render import render_claude_md, render_moc, render_taxonomy_md
from myelin_core.schema.pack import Domain
from myelin_core.settings_template import render_claude_settings
from myelin_core.vault import (
    AI_WRITE_ALLOW,
    DOMAINS,
    MOC_FILE,
    OBSIDIAN_DIR,
    OBSIDIAN_THEME_NAME,
    RUNTIME,
    STANDARD_DIRS,
    SYSTEM,
    TAXONOMY_MD,
    TEMPLATES,
    Vault,
    default_pack_roots,
    default_theme_dir,
)

CLAUDE_MD = "CLAUDE.md"
CLAUDE_SETTINGS = ".claude/settings.json"
OBSIDIAN_APPEARANCE = f"{OBSIDIAN_DIR}/appearance.json"
# Light only (정본 §8.3 guardrail 5); "moonstone" is Obsidian's light base scheme.
OBSIDIAN_APPEARANCE_BODY = (
    '{\n  "cssTheme": "'
    + OBSIDIAN_THEME_NAME
    + '",\n  "theme": "moonstone",\n  "baseFontSize": 16\n}\n'
)


def obsidian_files(theme_dir: Path | None = None) -> dict[str, str]:
    """Files that make a fresh Vault open in Obsidian with MYELIN Emboss already selected.

    Obsidian keeps a pre-existing .obsidian/ folder, so writing the theme and appearance.json
    before the first open means no manual Settings > Appearance step (user guide 9.1).
    Returns {} when the generated theme cannot be found (e.g. core installed without the repo).
    """
    theme_dir = theme_dir or default_theme_dir()
    if theme_dir is None:
        return {}
    base = f"{OBSIDIAN_DIR}/themes/{OBSIDIAN_THEME_NAME}"
    return {
        f"{base}/manifest.json": (theme_dir / "manifest.json").read_text(encoding="utf-8"),
        f"{base}/theme.css": (theme_dir / "theme.css").read_text(encoding="utf-8"),
        OBSIDIAN_APPEARANCE: OBSIDIAN_APPEARANCE_BODY,
    }


# ADR-0011 §5 — Vault git pre-commit device (works outside Claude Code: Obsidian Git, terminal, …)
HOOKS_DIR = f"{SYSTEM}/hooks"
PRE_COMMIT = f"{HOOKS_DIR}/pre-commit"
PRE_COMMIT_MARKER = "myelin-pre-commit"
PRE_COMMIT_BODY = f"""#!/bin/sh
# {PRE_COMMIT_MARKER} v1 — MYELIN Vault 승인 장치 (ADR-0011 §5).
# `myelin init` / `myelin doctor --install-hook` 가 .git/hooks/pre-commit 으로 복사한다.
# 스테이지된 노트에 ERROR 급 doctor 위반이 있으면 커밋을 거부한다:
#   origin: claude 노트가 Level 의 AI 쓰기 범위 밖 · verified 인데 reviewed 없음 ·
#   confidential + share: true · frontmatter 스키마 위반 · 미등록 domain.
# 사람이 의도적으로 건너뛸 때만: git commit --no-verify
set -u
ROOT=$(git rev-parse --show-toplevel) || exit 1
VAULT="${{MYELIN_VAULT:-$ROOT}}"
# shellcheck disable=SC2086 — MYELIN_BIN may carry arguments ("python -m myelin_cli")
set -- ${{MYELIN_BIN:-myelin}}
if ! command -v "$1" >/dev/null 2>&1; then
  echo "MYELIN pre-commit: '$1' 을 찾을 수 없습니다 — MYELIN CLI 를 설치하거나" >&2
  echo "  MYELIN_BIN 을 지정하세요. 판단 불가 → 커밋 거부 (fail-closed)." >&2
  echo "  사람이 의도적으로 건너뛸 때: git commit --no-verify" >&2
  exit 1
fi
exec "$@" doctor --staged --vault "$VAULT"
"""

GITIGNORE = ".gitignore"
GITIGNORE_BODY = (
    "# MYELIN runtime (index, logs) — never commit\n.myelin/\n"
    "# Obsidian workspace state\n.obsidian/workspace*.json\n"
    "# Claude Code local overrides (team policy lives in .claude/settings.json)\n"
    ".claude/settings.local.json\n"
)


class ScaffoldError(RuntimeError):
    pass


class VaultExistsError(ScaffoldError):
    """Raised when init would touch existing files (fail-closed)."""

    def __init__(self, root: Path, conflicts: list[str]) -> None:
        self.root = root
        self.conflicts = conflicts
        shown = ", ".join(conflicts[:8]) + (" …" if len(conflicts) > 8 else "")
        super().__init__(
            f"{root}: 기존 파일이 있어 중단합니다 (덮어쓰기 금지). "
            f"충돌 {len(conflicts)}건: {shown}\n"
            "→ 빈 디렉터리를 지정하거나, 기존 Vault라면 `myelin add-domain` / `myelin doctor` 를 "
            "사용하세요."
        )


@dataclass
class ScaffoldPlan:
    """Files to create (relative path → content). Directories are implied."""

    files: dict[str, str] = field(default_factory=dict)
    dirs: list[str] = field(default_factory=list)

    def paths(self) -> list[str]:
        return sorted(set(self.dirs) | set(self.files))


def _domain_lookup(packs: list[LoadedPack]) -> dict[str, tuple[Domain, LoadedPack]]:
    return {d.id: (d, lp) for lp in packs for d in lp.pack.domains}


def _template_files(packs: list[LoadedPack], domain_ids: set[str]) -> dict[str, str]:
    """90_System/templates/<name>.md — core templates, then `<DOMAIN>-<name>.md` per domain."""
    out: dict[str, str] = {}
    for lp in packs:
        if lp.pack.templates:
            for f in lp.template_files.get(lp.pack.templates, []):
                out[f"{TEMPLATES}/{f.name}"] = f.read_text(encoding="utf-8")
        for d in lp.pack.domains:
            if d.id in domain_ids and d.templates:
                for f in lp.template_files.get(d.templates, []):
                    out[f"{TEMPLATES}/{d.id}-{f.name}"] = f.read_text(encoding="utf-8")
    return out


def _taxonomy_entries(packs: list[LoadedPack]) -> list[tuple[str, object]]:
    entries: list[tuple[str, object]] = []
    for lp in packs:
        seen: set[str] = set()
        for rel, tax in lp.taxonomies.items():
            if rel not in seen:
                seen.add(rel)
                entries.append((lp.name, tax))
    return entries


def resolve_config_packs(cfg: MyelinConfig, roots: list[Path]) -> list[LoadedPack]:
    registry: PackRegistry = discover_packs(roots)
    packs = resolve_packs(cfg.packs, registry)
    known = _domain_lookup(packs)
    missing = [d for d in cfg.domains.all_ids if d not in known]
    if missing:
        available = ", ".join(sorted(known)) or "(none)"
        raise ScaffoldError(
            f"domains {missing} are not declared by packs {cfg.pack_names}. available: {available}"
        )
    return packs


def plan_init(cfg: MyelinConfig, packs: list[LoadedPack], now: datetime) -> ScaffoldPlan:
    plan = ScaffoldPlan(dirs=list(STANDARD_DIRS))
    plan.files[CONFIG_FILE] = dump_config(cfg)
    plan.files[GITIGNORE] = GITIGNORE_BODY
    plan.files[f"{RUNTIME}/.gitkeep"] = ""
    lookup = _domain_lookup(packs)
    for did in cfg.domains.all_ids:
        d, lp = lookup[did]
        plan.dirs.append(f"{DOMAINS}/{did}")
        plan.files[f"{DOMAINS}/{did}/{MOC_FILE}"] = render_moc(d, lp, cfg, now)
    plan.files.update(_template_files(packs, set(cfg.domains.all_ids)))
    plan.files[TAXONOMY_MD] = render_taxonomy_md(_taxonomy_entries(packs), now)  # type: ignore[arg-type]
    plan.files[CLAUDE_MD] = render_claude_md(cfg, packs, now, None, ai_write_allow=AI_WRITE_ALLOW)
    plan.files[CLAUDE_SETTINGS] = render_claude_settings()
    plan.files[PRE_COMMIT] = PRE_COMMIT_BODY
    plan.files.update(obsidian_files())
    return plan


def _git_hooks_dir(root: Path) -> Path:
    """`git rev-parse --git-path hooks` (worktrees, core.hooksPath); fallback `.git/hooks`."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--git-path", "hooks"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
        hooks = Path(proc.stdout.strip())
        return hooks if hooks.is_absolute() else root / hooks
    except (OSError, subprocess.CalledProcessError):
        return root / ".git" / "hooks"


def install_git_hook(root: Path) -> Path:
    """Install `90_System/hooks/pre-commit` into the Vault repo's hooks dir (chmod 755).

    Fail-closed: refuses when the Vault is not a git repository, and never overwrites a foreign
    pre-commit hook (one without the MYELIN marker). A missing `90_System/hooks/pre-commit`
    is (re)created from the template; an existing one is kept as the user's copy.
    Returns the installed hook path. Shared by the CLI and (to be wired) the Hub's ensure_git.
    """
    root = Path(root).resolve()
    if not (root / ".git").exists():
        raise ScaffoldError(f"{root} 은 git 저장소가 아닙니다 — 먼저 `git init` 하세요")
    source = root / PRE_COMMIT
    if not source.exists():
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(PRE_COMMIT_BODY, encoding="utf-8")
    elif PRE_COMMIT_MARKER not in source.read_text(encoding="utf-8", errors="replace"):
        raise ScaffoldError(f"{PRE_COMMIT} 은 MYELIN 이 만든 hook 이 아닙니다 — 덮어쓰지 않습니다")
    _chmod_exec(source)
    hooks_dir = _git_hooks_dir(root)
    hooks_dir.mkdir(parents=True, exist_ok=True)
    dest = hooks_dir / "pre-commit"
    if dest.exists() and PRE_COMMIT_MARKER not in dest.read_text(
        encoding="utf-8", errors="replace"
    ):
        raise ScaffoldError(
            f"{dest} 에 다른 pre-commit hook 이 있습니다 — 덮어쓰지 않습니다. "
            f"직접 합치거나 {PRE_COMMIT} 를 호출하도록 추가하세요"
        )
    shutil.copyfile(source, dest)
    _chmod_exec(dest)
    return dest


def _chmod_exec(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)


def init_vault(
    root: Path, cfg: MyelinConfig, now: datetime, pack_roots: list[Path] | None = None
) -> ScaffoldPlan:
    """Create a new Vault at `root`. Fail-closed: aborts before writing if any target exists."""
    root = Path(root)
    packs = resolve_config_packs(
        cfg, pack_roots if pack_roots is not None else default_pack_roots(root)
    )
    plan = plan_init(cfg, packs, now)
    if root.exists() and not root.is_dir():
        raise ScaffoldError(f"{root} exists and is not a directory")
    conflicts = [p for p in plan.files if (root / p).exists()]
    if root.exists() and (root / CONFIG_FILE).exists() and CONFIG_FILE not in conflicts:
        conflicts.append(CONFIG_FILE)
    if conflicts:
        raise VaultExistsError(root, conflicts)
    root.mkdir(parents=True, exist_ok=True)
    for d in plan.dirs:
        (root / d).mkdir(parents=True, exist_ok=True)
    for rel, content in plan.files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("x", encoding="utf-8") as fh:  # 'x' = exclusive create; never overwrite
            fh.write(content)
    _chmod_exec(root / PRE_COMMIT)
    return plan


def add_domain(
    vault: Vault,
    domain_id: str,
    now: datetime,
    *,
    pack_name: str | None = None,
    pack_roots: list[Path] | None = None,
) -> list[str]:
    """Add a Domain declared by a pack. Existing notes are never touched; returns touched paths."""
    roots = pack_roots if pack_roots is not None else default_pack_roots(vault.root)
    registry = discover_packs(roots)
    cfg = vault.config
    if domain_id in cfg.domains.all_ids:
        raise ScaffoldError(
            f"domain {domain_id!r} is already configured ({cfg.domains.roles[domain_id]})"
        )
    # find the pack that declares it
    candidates = [lp for lp in registry.values() if domain_id in lp.pack.domain_ids]
    if pack_name:
        candidates = [lp for lp in candidates if lp.name == pack_name]
    if not candidates:
        raise ScaffoldError(
            f"no pack declares domain {domain_id!r}" + (f" (pack {pack_name})" if pack_name else "")
        )
    if len(candidates) > 1:
        raise ScaffoldError(
            f"domain {domain_id!r} is declared by several packs "
            f"{[c.name for c in candidates]}; use --pack"
        )
    lp = candidates[0]
    new_packs = list(cfg.packs)
    if lp.name not in cfg.pack_names:
        new_packs.append(lp.name)
    new_cfg = cfg.model_copy(
        update={
            "packs": new_packs,
            "domains": cfg.domains.model_copy(update={"extra": [*cfg.domains.extra, domain_id]}),
        }
    )
    new_cfg = MyelinConfig.model_validate(new_cfg.model_dump(mode="json"))
    packs = resolve_packs(new_cfg.packs, registry)
    domain = next(d for d in lp.pack.domains if d.id == domain_id)

    touched: list[str] = []
    moc = vault.root / DOMAINS / domain_id / MOC_FILE
    if moc.exists():
        raise ScaffoldError(f"{vault.rel(moc)} already exists — refusing to overwrite")
    moc.parent.mkdir(parents=True, exist_ok=True)
    moc.write_text(render_moc(domain, lp, new_cfg, now), encoding="utf-8")
    touched.append(vault.rel(moc))
    for rel, content in _template_files([lp], {domain_id}).items():
        if not rel.rsplit("/", 1)[-1].startswith(f"{domain_id}-"):
            continue
        target = vault.root / rel
        if not target.exists():
            target.write_text(content, encoding="utf-8")
            touched.append(rel)
    tax = vault.root / TAXONOMY_MD
    prev_tax = tax.read_text(encoding="utf-8") if tax.exists() else None
    new_tax = render_taxonomy_md(_taxonomy_entries(packs), now)  # type: ignore[arg-type]
    if prev_tax and "<!-- myelin:personal:start -->" in prev_tax:
        from myelin_core.render import PERSONAL_END, PERSONAL_START

        personal = prev_tax.split(PERSONAL_START, 1)[1].split(PERSONAL_END, 1)[0]
        new_tax = (
            new_tax.split(PERSONAL_START, 1)[0] + PERSONAL_START + personal + PERSONAL_END + "\n"
        )
    tax.write_text(new_tax, encoding="utf-8")
    touched.append(TAXONOMY_MD)
    claude = vault.root / CLAUDE_MD
    prev = claude.read_text(encoding="utf-8") if claude.exists() else None
    claude.write_text(
        render_claude_md(new_cfg, packs, now, prev, ai_write_allow=AI_WRITE_ALLOW), encoding="utf-8"
    )
    touched.append(CLAUDE_MD)
    (vault.root / CONFIG_FILE).write_text(dump_config(new_cfg), encoding="utf-8")
    touched.append(CONFIG_FILE)
    vault.config = new_cfg
    return touched
