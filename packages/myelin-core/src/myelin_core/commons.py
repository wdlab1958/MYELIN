"""MYELIN Commons — 조직 내부 Git에 '공개 승인된 노트'와 Pack Registry를 둔다 (명세 §9, ADR-0009).

원칙
- 공개는 개인의 행위다. 자격(verified + share:true + classification ≤ internal)·비식별 검사·
  사람 확인을 모두 통과한 노트만, 사람이 누를 때 Commons 저장소의 **새 브랜치**에 commit 된다.
- 브랜치 commit 은 사용자의 Commons 작업 트리·index를 건드리지 않는다 (임시 index + commit-tree).
- 원격으로 보내는 것(push)은 별도의 두 번째 사람 행위다. MYELIN은 PR 자체를 만들지 않는다 —
  git 호스트가 push 결과로 PR 링크를 준다. Vault 파일은 공개 과정에서 바뀌지 않는다.
"""

from __future__ import annotations

import io
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from fnmatch import fnmatch
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from ruamel.yaml import YAML

from myelin_core import gitops
from myelin_core.config import VaultConfig, load_config
from myelin_core.deid import MANUAL_CHECKLIST, POLICY_FILE, DeidReport, load_policy, scan_text
from myelin_core.errors import Issue, MyelinError, PackError, issues_from_validation
from myelin_core.frontmatter import Classification, NoteType, Status
from myelin_core.gitops import Author, GitError
from myelin_core.loader import load_pack
from myelin_core.note import Note
from myelin_core.review import read_note
from myelin_core.safety import find_source_root
from myelin_core.scaffold import ScaffoldError
from myelin_core.vault import scan_vault
from myelin_core.yamlio import load_yaml

REGISTRY_FILE = "registry/packs.yaml"
NOTES_DIR = "notes"
BRANCH_PREFIX = "publish/"
PUBLISHABLE = (Classification.PUBLIC, Classification.INTERNAL)
NOT_PUBLISHABLE_TYPES = (NoteType.MOC, NoteType.FLEETING, NoteType.IDEA_IP)
# 공개본에서 빼는 필드 — 개인 Vault 구조(출처 노트 제목·프로젝트)가 새지 않게
DROP_FIELDS = ("share", "source", "projects")


class CommonsError(MyelinError):
    """Commons 공개를 할 수 없음 (fail-closed)."""


# ── Pack Registry ────────────────────────────────────────────────────────
class RegistryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: Annotated[
        str, Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*(?:\.[a-z0-9]+(?:-[a-z0-9]+)*)+$")
    ]
    version: Annotated[str, Field(pattern=r"^\d+\.\d+\.\d+$")]
    source: Annotated[str, Field(min_length=1)]  # git URL 또는 Commons 안의 상대경로
    status: Literal["draft", "pilot", "stable", "deprecated"] = "draft"
    champions: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    description: str = ""


class PackRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    registry: Literal[1] = 1
    org: Annotated[str, Field(min_length=1)]
    packs: list[RegistryEntry] = Field(default_factory=list)


def load_registry(commons: Path) -> PackRegistry:
    path = commons / REGISTRY_FILE
    if not path.is_file():
        raise CommonsError(
            "Commons 저장소가 아닙니다", [Issue(REGISTRY_FILE, "없음", "not_commons")]
        )
    data = load_yaml(path.read_text(encoding="utf-8"), REGISTRY_FILE, CommonsError)
    try:
        reg = PackRegistry.model_validate(data)
    except ValidationError as exc:
        raise CommonsError(
            "Pack Registry 검증 실패", issues_from_validation(exc, prefix=REGISTRY_FILE)
        ) from exc
    names = [p.name for p in reg.packs]
    if len(set(names)) != len(names):
        raise CommonsError("Pack Registry에 중복 Pack", [Issue(REGISTRY_FILE, "중복", "dup")])
    return reg


# ── Commons 저장소 만들기 ────────────────────────────────────────────────
PR_CHECKLIST = "\n".join(f"- [ ] {text}" for text in MANUAL_CHECKLIST.values())
PR_TEMPLATE = f"## Commons 공개 확인 (비식별)\n\n{PR_CHECKLIST}\n"


def render_layout(org: str) -> dict[str, str]:
    return {
        "README.md": (
            f"# {org} — MYELIN Commons\n\n"
            "조직 내부 전용 저장소. **공개 저장소(GitHub public 등)에 두지 마세요.**\n\n"
            "- `notes/<DOMAIN>/` — 구성원이 공개 승인한 verified 노트 (작성자·원 id 표기)\n"
            "- `registry/packs.yaml` — 조직 Pack Registry\n"
            "- `policy/deid.yaml` — 비식별 정책 (고객명 등 금지어, 오탐 허용 목록)\n\n"
            "공개는 MYELIN Hub의 'Commons 제안'으로만 들어옵니다. 각 Domain 챔피언이\n"
            "비식별을 확인한 뒤 merge 합니다 (명세 §9.1).\n"
        ),
        "CONTRIBUTING.md": (
            "# 공개 규칙\n\n"
            "1. 자격: `status: verified` + `share: true` + `classification: public|internal`.\n"
            "   `40_IP`, `confidential`, MOC·fleeting·idea-ip 는 공개할 수 없습니다.\n"
            "2. 자동 비식별 검사(이메일·IP·전화·주민번호·카드·키·내부 URL·금지어)를\n"
            "   통과해야 합니다.\n"
            "3. 작성자가 아래 항목을 직접 확인합니다. 챔피언이 PR에서 다시 확인합니다.\n\n"
            f"{PR_CHECKLIST}\n"
        ),
        ".github/PULL_REQUEST_TEMPLATE.md": PR_TEMPLATE,
        ".gitlab/merge_request_templates/Default.md": PR_TEMPLATE,
        "CODEOWNERS": "# Domain별 챔피언 (예)\n# notes/SEC-CONSULT/  @champion-id\n",
        REGISTRY_FILE: (
            "# 조직 Pack Registry — Pack은 데이터다. 새 Domain은 코드가 아니라 Pack으로 추가한다.\n"
            "registry: 1\n"
            f"org: {org!r}\n"
            "packs: []\n"
        ),
        POLICY_FILE: (
            "# 비식별 정책 — 이 파일 자체가 민감할 수 있다. Commons(내부) 밖으로 내보내지 않는다.\n"
            "deid: 1\n"
            "deny: []            # 고객사·기관명, 내부 프로젝트 코드명 (대소문자 무시)\n"
            "allow: []           # 오탐 허용 (예: 문서용 예시 IP 192.0.2.10)\n"
            "internal_domains: []  # 예: corp.example.com\n"
        ),
        f"{NOTES_DIR}/.gitkeep": "",
    }


def init_commons(target: Path, org: str, author: Author) -> str:
    """새 Commons 저장소를 만들고 첫 commit. 비어 있지 않거나 위험한 위치면 거부."""
    if target.exists() and any(target.iterdir()):
        raise ScaffoldError(
            "비어 있지 않은 폴더입니다", [Issue(str(target), "not empty", "exists")]
        )
    if find_source_root(target) is not None:
        raise ScaffoldError("MYELIN 소스 안에는 만들 수 없습니다", [Issue(str(target), "source")])
    if (target / "myelin.yaml").exists() or any(
        (p / "myelin.yaml").is_file() for p in target.absolute().parents
    ):
        raise ScaffoldError("Vault 안에는 만들 수 없습니다", [Issue(str(target), "vault")])
    target.mkdir(parents=True, exist_ok=True)
    for rel, text in render_layout(org).items():
        path = target / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    load_registry(target)
    return gitops.init_repo(target, author)


# ── 자격 ─────────────────────────────────────────────────────────────────
def _route_local(cfg: VaultConfig, rel: str, note: Note) -> bool:
    for key, route in cfg.llm.route.items():
        if route != "local":
            continue
        if key == note.frontmatter.classification.value or fnmatch(rel, key):
            return True
    return False


def eligibility_issues(cfg: VaultConfig, rel: str, note: Note) -> list[Issue]:
    """공개 자격 — 하나라도 있으면 차단."""
    fm = note.frontmatter
    out: list[Issue] = []
    if not cfg.commons.enabled:
        out.append(Issue("commons.enabled", "Commons가 꺼져 있습니다", "commons_disabled"))
    if fm.status is not Status.VERIFIED:
        out.append(Issue("status", f"{fm.status.value} — verified 만 공개", "not_verified"))
    if not fm.share:
        out.append(Issue("share", "share: true 가 아닙니다", "not_shared"))
    if fm.classification not in PUBLISHABLE:
        out.append(Issue("classification", fm.classification.value, "classified"))
    if rel.startswith("40_IP/"):
        out.append(Issue("path", "40_IP 는 공개할 수 없습니다", "ip_area"))
    if fm.type in NOT_PUBLISHABLE_TYPES:
        out.append(Issue("type", f"{fm.type.value} 는 공개 대상이 아닙니다", "type"))
    if _route_local(cfg, rel, note):
        out.append(Issue("llm.route", "로컬 전용 경로입니다", "route_local"))
    out += fm.policy_issues()
    return out


# ── 공개본 ───────────────────────────────────────────────────────────────
def _rt() -> YAML:
    rt = YAML(typ="rt")
    rt.width = 4096
    rt.indent(mapping=2, sequence=4, offset=2)
    return rt


def render_public(note: Note, author: str, today: date) -> str:
    """공개본: 개인 Vault 구조가 드러나는 필드를 빼고, 작성자·원 id·공개일을 붙인다."""
    fm = {
        k: (
            v.value
            if isinstance(v, Enum)
            else [x.value if isinstance(x, Enum) else x for x in v]
            if isinstance(v, list)
            else v
        )
        for k, v in note.frontmatter.model_dump(exclude_none=True).items()
    }  # 날짜는 date 그대로 → YAML에 따옴표 없이
    for key in DROP_FIELDS:
        fm.pop(key, None)
    fm["title"] = note.title
    fm["author"] = author
    fm["commons_of"] = note.frontmatter.id
    fm["published"] = today.isoformat()
    buf = io.StringIO()
    _rt().dump(fm, buf)
    return f"---\n{buf.getvalue()}---\n{note.body}"


_SAFE_NAME = re.compile(r"[^\w\-. ]+", re.UNICODE)


def public_path(note: Note) -> str:
    domain = note.frontmatter.domain[0] if note.frontmatter.domain else "_"
    name = _SAFE_NAME.sub("_", note.title).strip(" .") or note.frontmatter.id
    return f"{NOTES_DIR}/{domain}/{name}.md"


# ── 검사 (쓰지 않음) ─────────────────────────────────────────────────────
@dataclass
class Check:
    rel: str
    note_id: str
    title: str
    target: str
    branch: str
    content: str
    blocks: list[Issue] = field(default_factory=list)
    deid: DeidReport = field(default_factory=DeidReport)

    @property
    def ok(self) -> bool:
        return not self.blocks and self.deid.clean

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.rel,
            "id": self.note_id,
            "title": self.title,
            "target": self.target,
            "branch": self.branch,
            "content": self.content,
            "ok": self.ok,
            "blocks": [i.__dict__ for i in self.blocks],
            "deid": [f.issue().__dict__ for f in self.deid.findings],
            "checklist": MANUAL_CHECKLIST,
        }


def commons_dir(vault: Path, cfg: VaultConfig) -> Path:
    if not cfg.commons.enabled:
        raise CommonsError(
            "Commons가 꺼져 있습니다", [Issue("commons.enabled", "false", "commons_disabled")]
        )
    if not cfg.commons.path:
        raise CommonsError("Commons 경로가 없습니다", [Issue("commons.path", "null", "no_path")])
    path = Path(os.path.expanduser(cfg.commons.path))
    if not path.is_absolute():
        raise CommonsError("Commons 경로는 절대경로여야 합니다", [Issue("commons.path", str(path))])
    v, c = vault.resolve(), path.resolve()
    if c == v or c.is_relative_to(v) or v.is_relative_to(c):
        raise CommonsError(
            "Commons와 Vault는 서로 분리되어야 합니다", [Issue("commons.path", str(c))]
        )
    if not gitops.is_repo(path):
        raise CommonsError(
            "Commons 경로가 git 저장소가 아닙니다", [Issue("commons.path", str(c), "no_repo")]
        )
    load_registry(path)
    return path


def check_note(vault: Path, rel: str, today: date) -> Check:
    cfg = load_config(vault)
    note, _ = read_note(vault, rel)
    blocks = eligibility_issues(cfg, rel, note)
    content = render_public(note, cfg.owner.name, today)
    commons: Path | None = None
    if not any(i.code == "commons_disabled" for i in blocks):
        try:
            commons = commons_dir(vault, cfg)
        except CommonsError as err:
            blocks += err.issues
    policy = load_policy(commons) if commons else None
    deid = scan_text(content, policy)
    chk = Check(
        rel=rel,
        note_id=note.frontmatter.id,
        title=note.title,
        target=public_path(note),
        branch=f"{BRANCH_PREFIX}{note.frontmatter.id}",
        content=content,
        blocks=blocks,
        deid=deid,
    )
    if commons is not None:
        if _branch_exists(commons, chk.branch):
            chk.blocks.append(Issue("branch", f"이미 제안됨: {chk.branch}", "already_proposed"))
        if _exists_in_head(commons, chk.target):
            chk.blocks.append(Issue(chk.target, "Commons에 같은 이름이 있습니다", "exists"))
    return chk


def candidates(vault: Path) -> list[dict[str, Any]]:
    """공개 후보: verified + share:true 노트 (자격 미달도 이유와 함께 보여 준다)."""
    cfg = load_config(vault)
    out = []
    for n in scan_vault(vault).notes:
        if n.frontmatter.status is Status.VERIFIED and n.frontmatter.share:
            issues = eligibility_issues(cfg, n.path or "", n)
            out.append(
                {
                    "path": n.path,
                    "id": n.frontmatter.id,
                    "title": n.title,
                    "domain": list(n.frontmatter.domain),
                    "classification": n.frontmatter.classification.value,
                    "blocks": [i.__dict__ for i in issues if i.code != "commons_disabled"],
                }
            )
    return sorted(out, key=lambda x: str(x["path"]))


# ── git (Commons 쪽) ─────────────────────────────────────────────────────
def _git(repo: Path, *args: str, env: dict[str, str] | None = None, check: bool = True) -> str:
    res = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "GIT_TERMINAL_PROMPT": "0",
            "LC_ALL": "C",
            "GIT_LITERAL_PATHSPECS": "1",
            **(env or {}),
        },
        timeout=60,
        check=False,
    )
    if check and res.returncode != 0:
        tail = (res.stderr or res.stdout).strip().splitlines()[-1:] or ["(출력 없음)"]
        raise GitError(f"git {args[0]} 실패", [Issue("git", tail[0], "git_failed")])
    return res.stdout


def _branch_exists(repo: Path, branch: str) -> bool:
    return bool(_git(repo, "branch", "--list", branch).strip())


def _exists_in_head(repo: Path, rel: str) -> bool:
    return bool(_git(repo, "ls-tree", "--name-only", "HEAD", "--", rel, check=False).strip())


def proposals(repo: Path) -> list[dict[str, str]]:
    out = _git(
        repo,
        "for-each-ref",
        "--format=%(refname:short)%09%(subject)",
        f"refs/heads/{BRANCH_PREFIX}",
        f"refs/heads/{PROPOSE_PREFIX}",
    )
    rows = []
    for line in out.splitlines():
        branch, _, subject = line.partition("\t")
        upstream = _git(
            repo, "rev-parse", "--abbrev-ref", f"{branch}@{{upstream}}", check=False
        ).strip()
        rows.append({"branch": branch, "subject": subject, "pushed": "yes" if upstream else "no"})
    return rows


# ── 쓰기 (사람 행위) ─────────────────────────────────────────────────────
def propose(
    vault: Path, rel: str, expected_id: str, confirmed: list[str], author: Author, today: date
) -> dict[str, str]:
    """사람 확인 후 Commons에 `publish/<id>` 브랜치 commit 을 만든다. Vault는 바뀌지 않는다."""
    missing = [k for k in MANUAL_CHECKLIST if k not in confirmed]
    if missing:
        raise CommonsError(
            "사람 확인 항목을 모두 체크해야 합니다",
            [Issue(k, MANUAL_CHECKLIST[k], "unconfirmed") for k in missing],
        )
    chk = check_note(vault, rel, today)
    if chk.note_id != expected_id:
        raise CommonsError(
            "화면의 노트와 파일이 다릅니다", [Issue("id", chk.note_id, "id_mismatch")]
        )
    if not chk.ok:
        raise CommonsError(
            "공개할 수 없습니다", chk.blocks + [f.issue() for f in chk.deid.findings]
        )
    cfg = load_config(vault)
    repo = commons_dir(vault, cfg)
    sha = _commit_on_branch(repo, chk.branch, chk.target, chk.content, author, chk)
    return {"branch": chk.branch, "commit": sha, "target": chk.target}


def _commit_files(
    repo: Path, branch: str, files: dict[str, bytes], message: str, author: Author
) -> str:
    """작업 트리·index를 건드리지 않고 HEAD 위에 파일들을 더한 commit 을 새 브랜치로 만든다."""
    with tempfile.TemporaryDirectory() as tmp:
        env = {
            "GIT_INDEX_FILE": str(Path(tmp) / "index"),
            "GIT_AUTHOR_NAME": author.name,
            "GIT_AUTHOR_EMAIL": author.email,
            "GIT_COMMITTER_NAME": author.name,
            "GIT_COMMITTER_EMAIL": author.email,
        }
        _git(repo, "read-tree", "HEAD", env=env)
        for rel, data in sorted(files.items()):
            blob = (
                subprocess.run(
                    ["git", "-C", str(repo), "hash-object", "-w", "--stdin"],
                    input=data,
                    capture_output=True,
                    check=True,
                    timeout=60,
                )
                .stdout.decode()
                .strip()
            )
            _git(repo, "update-index", "--add", "--cacheinfo", f"100644,{blob},{rel}", env=env)
        tree = _git(repo, "write-tree", env=env).strip()
        commit = _git(repo, "commit-tree", tree, "-p", "HEAD", "-m", message, env=env).strip()
    # 브랜치가 없을 때만 만든다 (덮어쓰지 않음)
    _git(repo, "update-ref", f"refs/heads/{branch}", commit, "0" * 40)
    return commit


def _commit_on_branch(
    repo: Path, branch: str, rel: str, content: str, author: Author, chk: Check
) -> str:
    message = (
        f"commons: {chk.title}\n\n"
        f"commons_of: {chk.note_id}\nauthor: {author.name}\n\n"
        "자동 비식별 검사 통과 · 작성자 확인 완료 — 챔피언 검토 필요\n"
    )
    return _commit_files(repo, branch, {rel: content.encode("utf-8")}, message, author)


# ── Personal Pack → Org Pack 제안 (명세 §9.1 Pack 진화, P9) ──────────────
PROPOSE_PREFIX = "propose/"
PROPOSALS_DIR = "proposals/packs"
MAX_PACK_BYTES = 1_000_000


def pack_proposal(vault: Path, pack_dir: Path) -> dict[str, Any]:
    """제안 전 검사 결과 (쓰지 않는다): 파일 목록, 비식별 결과, 막는 이유."""
    cfg = load_config(vault)
    blocks: list[Issue] = []
    files: dict[str, bytes] = {}
    try:
        repo: Path | None = commons_dir(vault, cfg)
    except CommonsError as err:
        repo = None
        blocks += err.issues
    try:
        lp = load_pack(pack_dir)
    except PackError as err:
        return {"ok": False, "blocks": [i.__dict__ for i in err.issues], "files": [], "deid": []}
    name = lp.name
    if lp.manifest.kind.value != "personal":
        blocks.append(Issue("kind", f"{lp.manifest.kind.value} — 개인 Pack만 제안", "not_personal"))
    total = 0
    for f in sorted(pack_dir.rglob("*")):
        rel = f.relative_to(pack_dir).as_posix()
        if any(part.startswith(".") for part in Path(rel).parts):
            continue
        if f.is_symlink():
            blocks.append(Issue(rel, "심볼릭 링크", "symlink"))
            continue
        if f.is_file():
            data = f.read_bytes()
            total += len(data)
            files[f"{PROPOSALS_DIR}/{name}/{rel}"] = data
    if total > MAX_PACK_BYTES:
        blocks.append(Issue("size", f"{total} bytes > {MAX_PACK_BYTES}", "too_large"))
    policy = load_policy(repo) if repo else None
    deid: list[Issue] = []
    for rel, data in files.items():
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            blocks.append(Issue(rel, "UTF-8 텍스트가 아님", "binary"))
            continue
        for finding in scan_text(text, policy).findings:
            issue = finding.issue()
            deid.append(Issue(f"{rel}:{issue.loc}", issue.msg, issue.code))
    branch = f"{PROPOSE_PREFIX}{name}"
    if repo is not None:
        if _branch_exists(repo, branch):
            blocks.append(Issue("branch", f"이미 제안됨: {branch}", "already_proposed"))
        if _exists_in_head(repo, f"{PROPOSALS_DIR}/{name}"):
            blocks.append(Issue(f"{PROPOSALS_DIR}/{name}", "이미 있습니다", "exists"))
    return {
        "ok": not blocks and not deid,
        "name": name,
        "version": lp.manifest.version,
        "domains": [d.id for d in lp.domains],
        "branch": branch,
        "files": sorted(files),
        "blocks": [i.__dict__ for i in blocks],
        "deid": [i.__dict__ for i in deid],
        "_payload": files,
    }


def propose_pack(
    vault: Path, pack_dir: Path, *, confirmed: bool, author: Author, today: date
) -> dict[str, str]:
    """사람 확인 후 Commons에 `propose/<pack>` 브랜치 commit 을 만든다. Vault·작업 트리는 그대로."""
    if not confirmed:
        raise CommonsError(
            "Pack 제안은 사람의 확인이 필요합니다", [Issue("confirm", "false", "unconfirmed")]
        )
    check = pack_proposal(vault, pack_dir)
    if not check["ok"]:
        issues = [Issue(**i) for i in (*check["blocks"], *check["deid"])]
        raise CommonsError("Pack을 제안할 수 없습니다", issues)
    repo = commons_dir(vault, load_config(vault))
    name = check["name"]
    files: dict[str, bytes] = dict(check["_payload"])
    files[f"{PROPOSALS_DIR}/{name}/PROPOSAL.md"] = (
        f"# Org Pack 제안: {name} {check['version']}\n\n"
        f"- 제안자: {author.name}\n- 제안일: {today.isoformat()}\n"
        f"- Domains: {', '.join(check['domains'])}\n"
        "- 근거: 개인 Pack으로 운영해 온 구조를 조직 공용 Pack 후보로 제안 (명세 §9.1 Pack 진화)\n"
        "- 다음: 챔피언 검토 → org.* 이름으로 확정 → registry/packs.yaml 등록\n"
    ).encode()
    message = (
        f"commons: propose pack {name} {check['version']}\n\n"
        f"author: {author.name}\n자동 비식별 검사 통과 · 작성자 확인 — 챔피언 검토 필요\n"
    )
    sha = _commit_files(repo, check["branch"], files, message, author)
    return {"branch": check["branch"], "commit": sha, "target": f"{PROPOSALS_DIR}/{name}"}


def push(vault: Path, branch: str, remote: str = "origin") -> str:
    """두 번째 사람 행위: 제안 브랜치를 원격으로 보낸다. PR 링크는 git 호스트가 알려 준다."""
    allowed = branch.startswith((BRANCH_PREFIX, PROPOSE_PREFIX))
    if not allowed or ".." in branch or not re.fullmatch(r"[\w./-]+", branch):
        raise CommonsError("제안 브랜치가 아닙니다", [Issue("branch", branch, "bad_branch")])
    cfg = load_config(vault)
    repo = commons_dir(vault, cfg)
    if not _branch_exists(repo, branch):
        raise CommonsError("없는 브랜치입니다", [Issue("branch", branch, "not_found")])
    res = subprocess.run(
        ["git", "-C", str(repo), "push", "--porcelain", "-u", remote, f"{branch}:{branch}"],
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"},
        timeout=120,
        check=False,
    )
    if res.returncode != 0:
        tail = (res.stderr or res.stdout).strip().splitlines()[-1:] or ["(출력 없음)"]
        raise GitError("git push 실패", [Issue("git", tail[0], "push_failed")])
    return (res.stderr + res.stdout).strip()
