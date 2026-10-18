"""MYELIN Commons — 팀 공유 저장소 (정본 §9.1, §P7, ADR-0010).

Commons is a separate git repository (사내, e.g. git@git.a3sc.internal:myelin/commons.git):

    commons/
    ├── README.md
    ├── CHAMPIONS.md                 # Domain champions who review publish PRs
    ├── registry/index.yaml          # Pack Registry: {packs: [{name, version, kind, …, champions}]}
    ├── registry/packs/<name>/…      # Org / Reference packs (from the MYELIN repo or proposals)
    ├── notes/<DOMAIN>/<id>-<slug>.md# published Evergreen notes (frontmatter + provenance)
    ├── proposals/packs/<name>/      # Personal → Org Pack proposals
    └── metrics/<owner-hash>/<week>.json  # opt-in anonymous metrics (counts only)

Publishing never pushes to the default branch: a note goes to branch `publish/<note-id>` as one
commit; the PR is opened by `gh` when available, otherwise the branch is pushed and the PR URL is
printed. Everything here requires the caller to have passed the human confirmation step.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from myelin_core.note import Note, NoteParseError, dump_note, read_note
from myelin_core.packs.loader import PackError, load_pack
from myelin_core.schema.frontmatter import Classification, Status
from myelin_core.vault import IP, Vault

REGISTRY_INDEX = "registry/index.yaml"
DEID_FILE = (
    "deid.yaml"  # <Commons>/deid.yaml and/or <Vault>/90_System/deid.yaml: extra patterns/terms
)


class CommonsError(ValueError):
    pass


# ----------------------------------------------------------------------------- structure
README = """# MYELIN Commons

팀 공유 저장소 (정본 §9.1). 개인 Vault 는 불가침 — 여기에는 개인이 **명시적으로 publish** 한
`share: true` + `status: verified` + `classification ≤ internal` 노트와,
사내 Pack Registry 만 들어온다.

- `registry/` Pack Registry (Org/Reference Pack) · `registry/index.yaml` 이 목록
- `notes/<DOMAIN>/` 공개 승인된 Evergreen 노트 (작성자·원 id 보존 → 인용 시 기여가 보임)
- `proposals/packs/` 개인 Pack → Org Pack 제안
- `metrics/` opt-in 익명 지표 (숫자만, 노트 내용·제목·경로 없음)

## 절차
1. 개인이 Hub/CLI 에서 "Commons 제안" → 브랜치 `publish/<id>` 에 커밋 → PR
2. Domain 챔피언이 PR 리뷰 (고객명·IP·기밀 비식별 확인) 후 merge
3. 재사용 시 `[[…]]` 인용 링크 유지 — 기여가 평판이 되는 구조
"""

CHAMPIONS = """# Domain Champions

| Domain | Champion | Pack |
|---|---|---|
| SEC-CONSULT | (TBD — 컨설팅 팀) | org.security-consulting |
| IR | (TBD — 침해사고 대응 팀) | org.incident-response |
"""


def init_commons(root: Path, *, git: bool = True) -> list[str]:
    """Create the Commons skeleton (idempotent, never overwrites existing files)."""
    root = Path(root)
    created: list[str] = []
    for d in ("registry/packs", "notes", "proposals/packs", "metrics"):
        (root / d).mkdir(parents=True, exist_ok=True)
        keep = root / d / ".gitkeep"
        if not any((root / d).iterdir()):
            keep.write_text("", encoding="utf-8")
            created.append(f"{d}/.gitkeep")
    files = {
        "README.md": README,
        "CHAMPIONS.md": CHAMPIONS,
        REGISTRY_INDEX: (
            "# MYELIN Pack Registry — `myelin commons add-pack` 가 갱신한다\npacks: []\n"
        ),
        DEID_FILE: (
            "# 비식별 규칙 (Commons 전체). 각 Vault 의 90_System/deid.yaml 로 보강한다.\n"
            "terms: []          # 고객명·시스템명 등 그대로 나오면 안 되는 문자열\n"
            "patterns: []       # 추가 정규식\n"
        ),
    }
    for rel, content in files.items():
        p = root / rel
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            created.append(rel)
    if git and not (root / ".git").exists():
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
        _git(root, "add", "-A")
        _git(
            root,
            "-c",
            "user.name=MYELIN",
            "-c",
            "user.email=myelin@local",
            "commit",
            "-q",
            "-m",
            "[myelin:commons] init",
        )
    return created


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise CommonsError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc


# ----------------------------------------------------------------------------- registry
def registry(root: Path) -> list[dict[str, Any]]:
    p = Path(root) / REGISTRY_INDEX
    if not p.exists():
        return []
    data = YAML(typ="safe").load(io.StringIO(p.read_text(encoding="utf-8"))) or {}
    packs = data.get("packs") or []
    return [dict(x) for x in packs]


def add_pack_to_registry(
    root: Path, pack_dir: Path, champions: list[str] | None = None
) -> dict[str, Any]:
    """Copy a validated pack into registry/packs/<name>/ and update index.yaml."""
    root = Path(root)
    lp = load_pack(pack_dir)
    dest = root / "registry" / "packs" / lp.name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(pack_dir, dest, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    entries = [e for e in registry(root) if e.get("name") != lp.name]
    entry = {
        "name": lp.name,
        "version": lp.pack.version,
        "kind": lp.pack.kind.value,
        "maintainer": lp.pack.maintainer,
        "path": f"registry/packs/{lp.name}",
        "domains": lp.pack.domain_ids,
        "champions": champions or [],
        "updated": date.today().isoformat(),
    }
    entries.append(entry)
    entries.sort(key=lambda e: str(e["name"]))
    y = YAML()
    y.default_flow_style = False
    buf = io.StringIO()
    buf.write("# MYELIN Pack Registry — `myelin commons add-pack` 가 갱신한다\n")
    y.dump({"packs": entries}, buf)
    (root / REGISTRY_INDEX).write_text(buf.getvalue(), encoding="utf-8")
    return entry


# ----------------------------------------------------------------------------- de-identification
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\b0\d{1,2}-\d{3,4}-\d{4}\b")
RRN_RE = re.compile(r"\b\d{6}-[1-4]\d{6}\b")
SECRET_RE = re.compile(r"(?i)\b(?:api[_-]?key|secret|password|passwd|token)\s*[:=]\s*\S+")
URL_INTERNAL_RE = re.compile(r"https?://[^\s)]*\.(?:internal|local|corp|lan)\b[^\s)]*")
CONFIDENTIAL_MARK_RE = re.compile(r"(?i)\b(confidential|대외비|기밀)\b")
BUILTIN_PATTERNS: dict[str, re.Pattern[str]] = {
    "ip-address": IP_RE,
    "email": EMAIL_RE,
    "phone": PHONE_RE,
    "resident-number": RRN_RE,
    "secret": SECRET_RE,
    "internal-url": URL_INTERNAL_RE,
    "confidential-marker": CONFIDENTIAL_MARK_RE,
}


@dataclass
class DeidRule:
    terms: list[str] = field(default_factory=list)
    patterns: dict[str, re.Pattern[str]] = field(default_factory=dict)

    @classmethod
    def load(cls, *files: Path) -> DeidRule:
        rule = cls(patterns=dict(BUILTIN_PATTERNS))
        for f in files:
            if not f or not Path(f).exists():
                continue
            data = YAML(typ="safe").load(io.StringIO(Path(f).read_text(encoding="utf-8"))) or {}
            rule.terms += [str(t) for t in data.get("terms") or []]
            for i, pat in enumerate(data.get("patterns") or []):
                try:
                    rule.patterns[f"custom-{Path(f).name}-{i}"] = re.compile(str(pat))
                except re.error as exc:
                    raise CommonsError(f"{f}: bad pattern {pat!r}: {exc}") from None
        return rule


@dataclass(frozen=True)
class DeidHit:
    kind: str
    line: int
    excerpt: str


def scan_text(text: str, rule: DeidRule) -> list[DeidHit]:
    hits: list[DeidHit] = []
    for n, line in enumerate(text.splitlines(), 1):
        for kind, pat in rule.patterns.items():
            for m in pat.finditer(line):
                if kind == "ip-address" and m.group(0).startswith(("0.", "127.", "255.")):
                    continue
                hits.append(DeidHit(kind, n, m.group(0)[:60]))
        for term in rule.terms:
            if term and term.casefold() in line.casefold():
                hits.append(DeidHit(f"term:{term}", n, line.strip()[:60]))
    return hits


# ----------------------------------------------------------------------------- eligibility
@dataclass
class PublishCheck:
    path: str
    eligible: bool
    reasons: list[str]
    deid_hits: list[DeidHit]
    note: Note | None = None

    @property
    def ok(self) -> bool:
        return self.eligible and not self.deid_hits

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "eligible": self.eligible,
            "ok": self.ok,
            "reasons": self.reasons,
            "deid_hits": [h.__dict__ for h in self.deid_hits],
            "title": self.note.title if self.note else Path(self.path).stem,
        }


def check_publishable(vault: Vault, rel: str, rule: DeidRule | None = None) -> PublishCheck:
    """Hard gates (정본 §9.1): share:true + verified + classification ≤ internal, not under 40_IP,
    no links to confidential notes; then the de-identification scan."""
    reasons: list[str] = []
    path = vault.root / rel
    try:
        note = read_note(path)
    except (NoteParseError, OSError) as exc:
        return PublishCheck(rel, False, [f"cannot read note: {exc}"], [], None)
    fm = note.frontmatter
    if not fm.share:
        reasons.append("share: false — 공개 후보가 아니다 (사람이 share: true 로 바꿔야 한다)")
    if fm.status is not Status.VERIFIED:
        reasons.append(f"status: {fm.status.value} — verified 만 공개할 수 있다")
    if fm.classification is Classification.CONFIDENTIAL:
        reasons.append("classification: confidential — 공개 불가")
    if rel.startswith(IP + "/"):
        reasons.append("40_IP/ 아래 노트는 공개 불가")
    for target in note.link_targets:
        for cand in vault.root.rglob(f"{target}.md"):
            try:
                if read_note(cand).frontmatter.classification is Classification.CONFIDENTIAL:
                    reasons.append(f"confidential 노트 [[{target}]] 를 링크한다")
            except NoteParseError:
                continue
    rule = rule or DeidRule.load(vault.root / "90_System" / DEID_FILE)
    hits = scan_text(dump_note(note), rule)
    return PublishCheck(rel, not reasons, reasons, hits, note)


def candidates(vault: Vault, rule: DeidRule | None = None) -> list[PublishCheck]:
    """Every share:true note in the vault with its publish check (for the Hub list)."""
    out = []
    for p in vault.iter_note_paths():
        try:
            fm = read_note(p).frontmatter
        except NoteParseError:
            continue
        if fm.share:
            out.append(check_publishable(vault, vault.rel(p), rule))
    return out


# ----------------------------------------------------------------------------- publish
@dataclass(frozen=True)
class PublishResult:
    branch: str
    commit: str
    dest: str
    pushed: bool
    pr_url: str | None


def owner_hash(vault: Vault) -> str:
    """Stable anonymous id: sha256(email or name) truncated — never the email itself."""
    seed = vault.config.owner.email or vault.config.owner.name
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]


def publish_note(
    vault: Vault,
    rel: str,
    commons: Path,
    *,
    confirmed: bool,
    rule: DeidRule | None = None,
    push: bool = False,
    open_pr: bool = False,
    now: datetime | None = None,
) -> PublishResult:
    """Copy a publishable note into the Commons clone on branch publish/<id> and commit.

    `confirmed` must be True: it is the caller's statement that a human reviewed the check
    (CLI prompt / Hub confirmation). Without it nothing is written (fail-closed).
    """
    if not confirmed:
        raise CommonsError("publish requires explicit human confirmation (confirmed=True)")
    commons = Path(commons)
    if not (commons / ".git").exists():
        raise CommonsError(f"{commons} is not a Commons git clone (run `myelin commons init`)")
    check = check_publishable(vault, rel, rule)
    if not check.ok:
        why = check.reasons + [f"deid {h.kind} line {h.line}: {h.excerpt}" for h in check.deid_hits]
        raise CommonsError("publish blocked: " + "; ".join(why))
    assert check.note is not None
    note = check.note
    fm = note.frontmatter
    now = now or datetime.now()
    domain = fm.domain[0] if fm.domain else "GENERAL"
    slug = re.sub(r"[^a-z0-9]+", "-", note.title.lower()).strip("-")[:48] or "note"
    dest_rel = f"notes/{domain}/{fm.id}-{slug}.md"
    raw = note.raw_frontmatter
    raw["published_by"] = owner_hash(vault)
    raw["published_from"] = fm.id
    raw["published"] = now.date()
    raw["author"] = vault.config.owner.name  # 출처 보존 (정본 §9.1)
    text = dump_note(note)
    branch = f"publish/{fm.id}"
    base = _git(commons, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if _git(commons, "rev-parse", "--verify", "--quiet", branch, check=False).returncode == 0:
        raise CommonsError(
            f"branch {branch} already exists — a publish for this note is pending review"
        )
    if (commons / dest_rel).exists():
        raise CommonsError(f"{dest_rel} already exists in Commons")
    _git(commons, "checkout", "-q", "-b", branch)
    try:
        dest = commons / dest_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            raise CommonsError(f"{dest_rel} already exists in Commons")
        dest.write_text(text, encoding="utf-8")
        _git(commons, "add", "--", dest_rel)
        _git(
            commons,
            "-c",
            f"user.name={vault.config.owner.name}",
            "-c",
            f"user.email={vault.config.owner.email or 'myelin@local'}",
            "commit",
            "-q",
            "-m",
            f"[myelin:publish] {note.title} ({domain}) by {vault.config.owner.name}",
        )
        commit = _git(commons, "rev-parse", "HEAD").stdout.strip()
        pushed = False
        pr_url = None
        if push:
            _git(commons, "push", "-u", "origin", branch)
            pushed = True
            if open_pr and shutil.which("gh"):
                proc = subprocess.run(
                    ["gh", "pr", "create", "--fill", "--head", branch, "--base", base],
                    cwd=commons,
                    capture_output=True,
                    text=True,
                )
                pr_url = proc.stdout.strip() or None
    finally:
        _git(commons, "checkout", "-q", base, check=False)
    return PublishResult(branch, commit, dest_rel, pushed, pr_url)


def propose_pack(vault: Vault, pack_dir: Path, commons: Path, *, confirmed: bool) -> PublishResult:
    """Personal Pack → Org Pack proposal: proposals/packs/<name>/ on branch propose/<name>."""
    if not confirmed:
        raise CommonsError("proposal requires explicit human confirmation (confirmed=True)")
    commons = Path(commons)
    try:
        lp = load_pack(pack_dir)
    except PackError as exc:
        raise CommonsError(str(exc)) from None
    rule = DeidRule.load(commons / DEID_FILE, vault.root / "90_System" / DEID_FILE)
    for f in Path(pack_dir).rglob("*"):
        if f.is_file() and f.suffix in (".yaml", ".md"):
            hits = scan_text(f.read_text(encoding="utf-8"), rule)
            if hits:
                raise CommonsError(
                    f"proposal blocked: {f.name} has {len(hits)} de-identification hit(s)"
                )
    branch = f"propose/{lp.name}"
    base = _git(commons, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    _git(commons, "checkout", "-q", "-B", branch)
    try:
        dest = commons / "proposals" / "packs" / lp.name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(pack_dir, dest, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        (dest / "PROPOSAL.md").write_text(
            f"# Org Pack 제안: {lp.name}\n\n"
            f"- 제안자: {vault.config.owner.name} ({owner_hash(vault)})\n"
            f"- Domains: {', '.join(lp.pack.domain_ids)}\n"
            "- 근거: 개인 Pack 으로 3개월 이상 운영 (정본 §9.1 Pack 진화)\n",
            encoding="utf-8",
        )
        _git(commons, "add", "-A", "--", f"proposals/packs/{lp.name}")
        _git(
            commons,
            "-c",
            "user.name=MYELIN",
            "-c",
            "user.email=myelin@local",
            "commit",
            "-q",
            "-m",
            f"[myelin:propose] pack {lp.name}",
        )
        commit = _git(commons, "rev-parse", "HEAD").stdout.strip()
    finally:
        _git(commons, "checkout", "-q", base, check=False)
    return PublishResult(branch, commit, f"proposals/packs/{lp.name}", False, None)


__all__ = [
    "BUILTIN_PATTERNS",
    "CommonsError",
    "DeidHit",
    "DeidRule",
    "PublishCheck",
    "PublishResult",
    "add_pack_to_registry",
    "candidates",
    "check_publishable",
    "init_commons",
    "owner_hash",
    "propose_pack",
    "publish_note",
    "registry",
    "scan_text",
]
_ = json  # reserved for registry JSON export
