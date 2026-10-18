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
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from myelin_core.note import Note, NoteParseError, dump_note, read_note
from myelin_core.packs.loader import PackError, load_pack
from myelin_core.schema.frontmatter import Classification, Status
from myelin_core.stats import source_refs
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
| SEC-CONSULT | (TBD — 컨설팅 팀) | a3.security-consulting |
| IR | (TBD — 침해사고 대응 팀) | a3.incident-response |
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
    # why push / PR did not happen (the commit on the publish branch is kept either way)
    push_error: str | None = None
    pr_error: str | None = None


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
    remote: str | None = None,
) -> PublishResult:
    """Copy a publishable note into the Commons clone on branch publish/<id> and commit.

    `confirmed` must be True: it is the caller's statement that a human reviewed the check
    (CLI prompt / Hub confirmation). Without it nothing is written (fail-closed).

    `push`/`open_pr` are best effort AFTER the commit exists: a failed push (no `origin`, no
    network, auth) or a missing `gh` never loses the commit — the result carries
    `pushed=False` / `pr_url=None` with `push_error` / `pr_error` so the caller can print the
    manual `git push` / `gh pr create` step. When the clone has no `origin`, `remote`
    (myelin.yaml `commons.remote`) is added as `origin` before pushing.
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
        pr_url: str | None = None
        push_error: str | None = None
        pr_error: str | None = None
        if push:
            pushed, push_error = push_branch(commons, branch, remote=remote)
            if pushed and open_pr:
                pr_url, pr_error = open_pull_request(commons, branch, base)
            elif open_pr:
                pr_error = "push 가 되지 않아 PR 을 열 수 없다"
    finally:
        _git(commons, "checkout", "-q", base, check=False)
    return PublishResult(branch, commit, dest_rel, pushed, pr_url, push_error, pr_error)


def ensure_origin(commons: Path, remote: str | None) -> str | None:
    """Return the clone's `origin` URL, adding `remote` as origin when none is set (gap M9)."""
    proc = _git(commons, "remote", "get-url", "origin", check=False)
    if proc.returncode == 0 and proc.stdout.strip():
        return proc.stdout.strip()
    if remote:
        _git(commons, "remote", "add", "origin", remote)
        return remote
    return None


def push_branch(
    commons: Path, branch: str, *, remote: str | None = None
) -> tuple[bool, str | None]:
    """`git push -u origin <branch>` → (pushed, error). Never raises on a failed push."""
    try:
        if ensure_origin(commons, remote) is None:
            return False, "Commons clone 에 origin 이 없다 (myelin.yaml commons.remote 를 설정한다)"
        _git(commons, "push", "-u", "origin", branch)
    except CommonsError as exc:
        return False, str(exc)
    return True, None


def open_pull_request(commons: Path, branch: str, base: str) -> tuple[str | None, str | None]:
    """`gh pr create` for an already pushed branch → (pr_url, error). Never raises."""
    if not shutil.which("gh"):
        return None, "gh CLI 가 설치되어 있지 않다"
    try:
        proc = subprocess.run(
            ["gh", "pr", "create", "--fill", "--head", branch, "--base", base],
            cwd=commons,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"gh pr create failed: {exc}"
    if proc.returncode != 0:
        return None, f"gh pr create failed: {proc.stderr.strip() or proc.stdout.strip()}"
    return proc.stdout.strip() or None, None


def manual_next_step(commons: Path, res: PublishResult) -> str | None:
    """Korean instruction for what the human still has to do; None when the PR is open."""
    if res.pr_url:
        return None
    if not res.pushed:
        why = f" ({res.push_error})" if res.push_error else ""
        return (
            f"브랜치가 로컬 Commons clone 에만 있다{why}. 터미널에서: "
            f"cd {commons} && git push -u origin {res.branch} && "
            f"gh pr create --fill --head {res.branch}"
        )
    why = f" ({res.pr_error})" if res.pr_error else ""
    return (
        f"브랜치는 push 되었지만 PR 이 열리지 않았다{why}. 터미널에서: "
        f"cd {commons} && gh pr create --fill --head {res.branch} "
        "— 또는 원격 저장소 웹에서 PR 을 연다"
    )


# ----------------------------------------------------------------------------- citations (ADR-0012)
@dataclass(frozen=True)
class CommonsNote:
    """A note published to the Commons clone (`notes/<DOMAIN>/<id>-<slug>.md`)."""

    path: str  # Commons-relative
    id: str  # frontmatter id in the Commons copy
    published_from: str  # original note id (= id unless the copy was re-keyed)
    author: str
    title: str
    targets: tuple[str, ...]
    source: tuple[str, ...]

    def cited_by(self, title: str, targets: set[str], source: Sequence[str]) -> bool:
        """Does a note with this body-link `targets` / `source:` list cite this Commons note?"""
        if self.title in targets:
            return True
        keys = {self.id, self.published_from, self.title}
        return any(k in keys for k in source_refs(source)) or any(
            self.id in s or self.published_from in s for s in source
        )


def commons_notes(commons: Path) -> list[CommonsNote]:
    """Parse every published note in the clone's working tree (unparsable files are skipped)."""
    root = Path(commons) / "notes"
    out: list[CommonsNote] = []
    if not root.is_dir():
        return out
    for p in sorted(root.rglob("*.md")):
        try:
            note = read_note(p)
        except (NoteParseError, OSError):
            continue
        raw = note.raw_frontmatter
        out.append(
            CommonsNote(
                path=p.relative_to(commons).as_posix(),
                id=note.id,
                published_from=str(raw.get("published_from") or note.id),
                author=str(raw.get("author") or ""),
                title=note.title,
                targets=tuple(sorted(note.link_targets)),
                source=tuple(note.frontmatter.source),
            )
        )
    return out


def commons_citations(vault: Vault, commons: Path) -> dict[str, int]:
    """Commons note (keyed by original id) → number of THIS vault's notes citing it.

    A citation is a body wikilink to the Commons note's title, or a `source:` entry naming its
    id / title. Notes this vault published itself (the original id lives here) are skipped: the
    §11.2 "재사용" KPI counts citations by OTHER people's notes ("타인 노트에 인용된 횟수").
    """
    published = commons_notes(commons)
    if not published:
        return {}
    notes, _ = vault.read_all()
    own_ids = {n.id for n in notes}
    counts: dict[str, int] = {}
    for cn in published:
        if cn.published_from in own_ids:
            continue
        n_cited = sum(
            1 for n in notes if cn.cited_by(n.title, n.link_targets, n.frontmatter.source)
        )
        if n_cited:
            counts[cn.published_from] = counts.get(cn.published_from, 0) + n_cited
    return counts


def _metrics_payloads(commons: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for f in sorted(Path(commons).glob("metrics/*/*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            out.append(data)
    return out


def commons_reuse(commons: Path, *, exclude_owner: str | None = None) -> dict[str, int]:
    """Original note id → citations of its Commons copy, aggregated across the organisation.

    Sources (ADR-0012): (1) `cited_commons_ids` reported in `metrics/<owner>/*.json` — each
    citing owner counts once per note (weekly files repeat, owners do not), `exclude_owner`
    drops the caller's own report; (2) other Commons notes in the clone citing it.
    """
    commons = Path(commons)
    citing_owners: dict[str, set[str]] = {}
    for payload in _metrics_payloads(commons):
        owner = str(payload.get("owner") or "")
        if not owner or owner == exclude_owner:
            continue
        ids = payload.get("cited_commons_ids")
        if isinstance(ids, list):
            for i in ids:
                if isinstance(i, str):
                    citing_owners.setdefault(i, set()).add(owner)
    counts: dict[str, int] = {k: len(v) for k, v in citing_owners.items()}
    published = commons_notes(commons)
    for cn in published:
        n_cited = sum(
            1
            for other in published
            if other.path != cn.path and cn.cited_by(other.title, set(other.targets), other.source)
        )
        if n_cited:
            counts[cn.published_from] = counts.get(cn.published_from, 0) + n_cited
    return dict(sorted(counts.items()))


def contributors(commons: Path) -> list[dict[str, Any]]:
    """`top_contributors` (정본 §9.1 기여가 평판이 된다): {author, published, cited} per author.

    `author` is the public Commons `author` field (real name by design); nothing here goes
    into the anonymous metrics payloads.
    """
    reuse = commons_reuse(commons)
    rows: dict[str, dict[str, Any]] = {}
    for cn in commons_notes(commons):
        r = rows.setdefault(cn.author, {"author": cn.author, "published": 0, "cited": 0})
        r["published"] += 1
        r["cited"] += reuse.get(cn.published_from, 0)
    return sorted(rows.values(), key=lambda r: (-r["cited"], -r["published"], r["author"]))


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
    "CommonsNote",
    "DeidHit",
    "DeidRule",
    "PublishCheck",
    "PublishResult",
    "add_pack_to_registry",
    "candidates",
    "check_publishable",
    "commons_citations",
    "commons_notes",
    "commons_reuse",
    "contributors",
    "ensure_origin",
    "init_commons",
    "manual_next_step",
    "open_pull_request",
    "owner_hash",
    "propose_pack",
    "publish_note",
    "push_branch",
    "registry",
    "scan_text",
]
