"""Commons 공개 — 자격 차단 100%, 사람 확인, Vault·작업 트리 불변, push는 별도 행위."""

from __future__ import annotations

import hashlib
import itertools
import subprocess
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest

from myelin_core.commons import (
    CommonsError,
    candidates,
    check_note,
    commons_dir,
    init_commons,
    load_registry,
    proposals,
    propose,
    push,
)
from myelin_core.config import load_config
from myelin_core.deid import MANUAL_CHECKLIST
from myelin_core.errors import MyelinError
from myelin_core.gitops import Author

TODAY = date(2026, 10, 18)
ME = Author("Tester", "tester@localhost")
ALL = list(MANUAL_CHECKLIST)
Put = Callable[[str, str], str]
Link = Callable[..., None]


def note(
    note_id: str = "20261018-0900-ok",
    *,
    status: str = "verified",
    share: bool = True,
    classification: str = "internal",
    type_: str = "evergreen",
    body: str = "# 공개 가능한 교훈\n\n제어 루프 예산에는 추론 지연을 포함한다.\n",
) -> str:
    return (
        "---\n"
        f"id: {note_id}\n"
        f"type: {type_}\n"
        "domain: [AI-ML-AX]\n"
        f"status: {status}\n"
        "origin: human\n"
        f"classification: {classification}\n"
        f"share: {'true' if share else 'false'}\n"
        'source: ["[[개인 문헌 노트]]"]\n'
        "created: 2026-10-17\n"
        "reviewed: 2026-10-18\n"
        "---\n"
        f"{body}"
    )


def _tree(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file() and not p.relative_to(root).as_posix().startswith(".git/")
    }


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "core.quotepath=false", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


# ── 차단 100% (Gate: block_matrix) ──────────────────────────────────────
MATRIX = list(
    itertools.product(
        ("draft", "unverified", "verified", "deprecated"),
        (True, False),
        ("public", "internal", "confidential"),
        ("30_Resources", "40_IP"),
    )
)


@pytest.mark.parametrize(("status", "share", "cls", "folder"), MATRIX)
def test_block_matrix(
    vault: Path,
    commons: Path,
    put: Put,
    link: Link,
    status: str,
    share: bool,
    cls: str,
    folder: str,
) -> None:
    link(vault, commons)
    rel = put(f"{folder}/n.md", note(status=status, share=share, classification=cls))
    eligible = (
        status == "verified" and share and cls in ("public", "internal") and folder != "40_IP"
    )
    if cls == "confidential" and share:  # 스키마 정책상 모순 — 그래도 차단되어야 한다
        pass
    chk = check_note(vault, rel, TODAY)
    assert chk.ok is eligible, [i.code for i in chk.blocks]
    before = _tree(vault)
    if eligible:
        assert propose(vault, rel, "20261018-0900-ok", ALL, ME, TODAY)["branch"]
    else:
        with pytest.raises(CommonsError):
            propose(vault, rel, "20261018-0900-ok", ALL, ME, TODAY)
        assert proposals(commons) == []
    assert _tree(vault) == before  # 공개는 Vault를 바꾸지 않는다


@pytest.mark.parametrize("type_", ["moc", "fleeting", "idea-ip"])
def test_block_matrix_types(vault: Path, commons: Path, put: Put, link: Link, type_: str) -> None:
    link(vault, commons)
    rel = put("30_Resources/t.md", note(type_=type_))
    assert not check_note(vault, rel, TODAY).ok


def test_block_matrix_disabled_or_unlinked(
    vault: Path, commons: Path, put: Put, link: Link
) -> None:
    rel = put("30_Resources/n.md", note())
    chk = check_note(vault, rel, TODAY)  # 기본: Commons 꺼짐
    assert not chk.ok and chk.blocks[0].code == "commons_disabled"
    link(vault, None)
    assert "no_path" in {i.code for i in check_note(vault, rel, TODAY).blocks}
    link(vault, vault / "20_Projects")  # Vault 안
    assert not check_note(vault, rel, TODAY).ok


def test_block_matrix_route_local(vault: Path, commons: Path, put: Put, link: Link) -> None:
    link(vault, commons)
    text = (vault / "myelin.yaml").read_text(encoding="utf-8")
    text = text.replace('"40_IP/**": local', '"40_IP/**": local\n    "30_Resources/**": local')
    (vault / "myelin.yaml").write_text(text, encoding="utf-8")
    rel = put("30_Resources/n.md", note())
    assert "route_local" in {i.code for i in check_note(vault, rel, TODAY).blocks}


# ── 제안 ─────────────────────────────────────────────────────────────────
def test_propose_flow(vault: Path, commons: Path, put: Put, link: Link) -> None:
    link(vault, commons)
    rel = put("30_Resources/교훈.md", note())
    commons_before = _tree(commons)
    index_before = (commons / ".git/index").read_bytes()

    with pytest.raises(CommonsError) as exc:
        propose(vault, rel, "20261018-0900-ok", ALL[:-1], ME, TODAY)
    assert exc.value.issues[0].code == "unconfirmed"
    with pytest.raises(CommonsError):
        propose(vault, rel, "20261018-0900-other", ALL, ME, TODAY)

    out = propose(vault, rel, "20261018-0900-ok", ALL, ME, TODAY)
    assert out["branch"] == "publish/20261018-0900-ok"
    assert out["target"] == "notes/AI-ML-AX/교훈.md"
    # 사용자의 Commons 작업 트리·index·현재 브랜치는 그대로
    assert _tree(commons) == commons_before
    assert (commons / ".git/index").read_bytes() == index_before
    assert _git(commons, "status", "--porcelain") == ""

    published = _git(commons, "show", f"{out['branch']}:{out['target']}")
    assert "commons_of: 20261018-0900-ok" in published and "author: Tester" in published
    assert "share:" not in published and "개인 문헌 노트" not in published  # 개인 구조 제거
    assert published.endswith("제어 루프 예산에는 추론 지연을 포함한다.\n")
    files = _git(commons, "show", "--name-only", "--format=", out["branch"]).split()
    assert files == ["notes/AI-ML-AX/교훈.md"]

    again = check_note(vault, rel, TODAY)
    assert "already_proposed" in {i.code for i in again.blocks}
    rows = proposals(commons)
    assert rows == [{"branch": out["branch"], "subject": "commons: 교훈", "pushed": "no"}]

    # 두 번째 사람 행위: push
    push(vault, out["branch"])
    assert proposals(commons)[0]["pushed"] == "yes"
    remote = commons.parent / "remote.git"
    assert out["branch"] in _git(remote, "branch", "--list")
    for bad in ("main", "publish/../x", "publish/x;rm", "publish/none"):
        with pytest.raises(CommonsError):
            push(vault, bad)


def test_deid_blocks_propose(vault: Path, commons: Path, put: Put, link: Link) -> None:
    link(vault, commons)
    rel = put(
        "30_Resources/x.md", note(body="# 진단\n\n대상 서버 10.20.30.40, 담당 kim@corp.example\n")
    )
    chk = check_note(vault, rel, TODAY)
    assert not chk.ok and {f.kind for f in chk.deid.findings} == {"ip", "email"}
    with pytest.raises(CommonsError) as exc:
        propose(vault, rel, "20261018-0900-ok", ALL, ME, TODAY)
    assert {"deid_ip", "deid_email"} <= {i.code for i in exc.value.issues}


def test_deny_terms_from_commons_policy(vault: Path, commons: Path, put: Put, link: Link) -> None:
    link(vault, commons)
    (commons / "policy/deid.yaml").write_text(
        "deid: 1\ndeny: [ACME Bank]\nallow: []\ninternal_domains: []\n", encoding="utf-8"
    )
    rel = put("30_Resources/x.md", note(body="# 교훈\n\nacme bank 진단에서 배운 점\n"))
    assert [f.kind for f in check_note(vault, rel, TODAY).deid.findings] == ["deny_term"]


def test_existing_target_in_commons(vault: Path, commons: Path, put: Put, link: Link) -> None:
    link(vault, commons)
    (commons / "notes/AI-ML-AX").mkdir(parents=True)
    (commons / "notes/AI-ML-AX/교훈.md").write_text("x", encoding="utf-8")
    _git(commons, "add", "-A")
    _git(commons, "-c", "user.name=a", "-c", "user.email=a@b", "commit", "-q", "-m", "x")
    rel = put("30_Resources/교훈.md", note())
    assert "exists" in {i.code for i in check_note(vault, rel, TODAY).blocks}


def test_candidates(vault: Path, commons: Path, put: Put, link: Link) -> None:
    put("30_Resources/a.md", note("20261018-0900-a"))
    put("40_IP/b.md", note("20261018-0900-b"))
    put("30_Resources/c.md", note("20261018-0900-c", share=False))
    rows = candidates(vault)
    assert [r["id"] for r in rows] == ["20261018-0900-a", "20261018-0900-b"]
    assert rows[0]["blocks"] == [] and rows[1]["blocks"][0]["code"] == "ip_area"


# ── 저장소·Registry ──────────────────────────────────────────────────────
def test_init_commons_layout_and_refusals(tmp_path: Path, vault: Path) -> None:
    repo = tmp_path / "c2"
    init_commons(repo, "Org", ME)
    reg = load_registry(repo)
    assert reg.org == "Org" and reg.packs == []
    for rel in (".github/PULL_REQUEST_TEMPLATE.md", "policy/deid.yaml", "CONTRIBUTING.md"):
        assert "비식별" in (repo / rel).read_text(encoding="utf-8") or rel.endswith(".yaml")
    with pytest.raises(MyelinError):
        init_commons(repo, "Org", ME)  # 비어 있지 않음
    with pytest.raises(MyelinError):
        init_commons(vault / "30_Resources/c", "Org", ME)  # Vault 안
    with pytest.raises(MyelinError):
        init_commons(Path(__file__).resolve().parents[3] / "x-commons", "Org", ME)  # 소스 안


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("registry: 1\norg: O\npacks: [{name: bad, version: 1.0.0, source: x}]\n", "invalid"),
        ("registry: 2\norg: O\n", "invalid"),
        (
            "registry: 1\norg: O\npacks:\n  - {name: a.b, version: 1.0.0, source: x}\n"
            "  - {name: a.b, version: 1.0.1, source: y}\n",
            "dup",
        ),
    ],
)
def test_registry_validation(commons: Path, text: str, code: str) -> None:
    (commons / "registry/packs.yaml").write_text(text, encoding="utf-8")
    with pytest.raises(CommonsError) as exc:
        load_registry(commons)
    assert code == "invalid" or exc.value.issues[0].code == code


def test_registry_entries(commons: Path) -> None:
    (commons / "registry/packs.yaml").write_text(
        "registry: 1\norg: O\npacks:\n"
        "  - name: org.security-consulting\n    version: 0.1.1\n"
        "    source: packs/org.security-consulting\n    status: pilot\n"
        "    champions: ['@sec-champ']\n    domains: [SEC-CONSULT]\n",
        encoding="utf-8",
    )
    assert load_registry(commons).packs[0].status == "pilot"
    (commons / "registry/packs.yaml").unlink()
    with pytest.raises(CommonsError):
        load_registry(commons)


def test_commons_dir_needs_repo(vault: Path, tmp_path: Path, link: Link) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    link(vault, plain)
    with pytest.raises(CommonsError) as exc:
        commons_dir(vault, load_config(vault))
    assert exc.value.issues[0].code == "no_repo"
