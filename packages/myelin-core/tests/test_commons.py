"""P7-T1~T4/T6 — Commons structure, registry, de-id scan, publish gates (차단 100%), proposals."""

from __future__ import annotations

import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from myelin_core.commons import (
    CommonsError,
    DeidRule,
    add_pack_to_registry,
    candidates,
    check_publishable,
    init_commons,
    owner_hash,
    propose_pack,
    publish_note,
    registry,
    scan_text,
)
from myelin_core.vault import Vault

NOW = datetime(2026, 10, 18, 12, 0)


@pytest.fixture
def vault(fixtures_dir: Path, tmp_path: Path) -> Vault:
    dst = tmp_path / "vault"
    shutil.copytree(fixtures_dir / "vaults/basic", dst)
    return Vault.open(dst)


@pytest.fixture
def commons(tmp_path: Path) -> Path:
    root = tmp_path / "commons"
    init_commons(root)
    return root


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()


def test_init_commons_structure_and_idempotent(commons: Path) -> None:
    for d in ("registry/packs", "notes", "proposals/packs", "metrics"):
        assert (commons / d).is_dir(), d
    assert (commons / "README.md").exists() and (commons / "CHAMPIONS.md").exists()
    assert (commons / "deid.yaml").exists() and (commons / ".git").exists()
    assert _git(commons, "log", "--pretty=%s") == "[myelin:commons] init"
    (commons / "README.md").write_text("custom", encoding="utf-8")
    assert init_commons(commons) == []  # never overwrites
    assert (commons / "README.md").read_text(encoding="utf-8") == "custom"


def test_registry_add_pack(commons: Path, packs_dir: Path) -> None:
    assert registry(commons) == []
    e = add_pack_to_registry(commons, packs_dir / "a3.security-consulting")
    assert (
        e["name"] == "a3.security-consulting"
        and e["champions"] == []
        and e["domains"] == ["SEC-CONSULT"]
    )
    e2 = add_pack_to_registry(commons, packs_dir / "a3.incident-response", champions=["김챔피언"])
    assert e2["champions"] == ["김챔피언"] and e2["domains"] == ["IR"]
    assert (commons / "registry/packs/a3.incident-response/pack.yaml").exists()
    names = [r["name"] for r in registry(commons)]
    assert names == ["a3.incident-response", "a3.security-consulting"]
    add_pack_to_registry(commons, packs_dir / "a3.security-consulting", champions=["이챔피언"])
    assert len(registry(commons)) == 2 and registry(commons)[1]["champions"] == ["이챔피언"]
    # the registry dir is a valid pack search root
    from myelin_core.packs.loader import discover_packs

    assert set(discover_packs([commons / "registry/packs"])) == {
        "a3.security-consulting",
        "a3.incident-response",
    }


@pytest.mark.parametrize(
    "text,kinds",
    [
        ("서버 10.20.30.40 에서", {"ip-address"}),
        ("담당자 gildong@a3sc.co.kr", {"email"}),
        ("연락 010-1234-5678", {"phone"}),
        ("주민번호 901010-1234567", {"resident-number"}),
        ("api_key = sk-abcdef", {"secret"}),
        ("보고서 https://wiki.a3sc.internal/x", {"internal-url"}),
        ("이 문서는 대외비", {"confidential-marker"}),
        ("localhost 127.0.0.1 is fine", set()),
        ("평범한 문장", set()),
    ],
)
def test_builtin_deid_patterns(text: str, kinds: set[str]) -> None:
    hits = scan_text(text, DeidRule.load())
    assert {h.kind for h in hits} == kinds


def test_custom_terms_and_patterns(tmp_path: Path) -> None:
    f = tmp_path / "deid.yaml"
    f.write_text("terms: [삼성화재, ACME]\npatterns: ['PROJ-\\d{4}']\n", encoding="utf-8")
    rule = DeidRule.load(f, tmp_path / "missing.yaml")
    hits = scan_text("acme 와 PROJ-1234 건", rule)
    assert {h.kind for h in hits} == {"term:ACME", f"custom-{f.name}-0"}
    bad = tmp_path / "bad.yaml"
    bad.write_text("patterns: ['(']\n", encoding="utf-8")
    with pytest.raises(CommonsError, match="bad pattern"):
        DeidRule.load(bad)


def test_check_publishable_gates(vault: Vault) -> None:
    ok = check_publishable(vault, "10_Domains/D2/WCET 예산은 측정값의 1.5배로 잡는다.md")
    assert ok.ok and ok.reasons == [] and ok.deid_hits == []
    unshared = check_publishable(
        vault, "10_Domains/D4/구멍 간 최소 간격 규칙.md"
    )  # verified, share false
    assert not unshared.eligible and any("share: false" in r for r in unshared.reasons)
    conf = check_publishable(vault, "40_IP/candidates/Agentic CAD 검증 루프.md")
    assert (
        not conf.eligible
        and any("confidential" in r for r in conf.reasons)
        and any("40_IP" in r for r in conf.reasons)
    )
    draft = check_publishable(vault, "00_Inbox/ai-drafts/Lit - 양자화 서베이.md")
    assert any("status: draft" in r for r in draft.reasons)
    missing = check_publishable(vault, "nope.md")
    assert not missing.eligible and "cannot read" in missing.reasons[0]
    d = ok.to_dict()
    assert d["ok"] is True and d["title"].startswith("WCET")


def test_candidates_lists_share_true_only(vault: Vault) -> None:
    cs = candidates(vault)
    assert len(cs) == 6 and all(c.note is not None and c.note.frontmatter.share for c in cs)
    assert all(c.ok for c in cs)


def test_publish_blocks_confidential_and_share_false_100_percent(
    vault: Vault, commons: Path
) -> None:
    notes, _ = vault.read_all()
    blocked = 0
    attempted = 0
    for n in notes:
        fm = n.frontmatter
        assert n.path is not None
        rel = vault.rel(n.path)
        if (
            fm.classification.value == "confidential"
            or not fm.share
            or fm.status.value != "verified"
        ):
            attempted += 1
            with pytest.raises(CommonsError, match="publish blocked"):
                publish_note(vault, rel, commons, confirmed=True, now=NOW)
            blocked += 1
    assert attempted >= 25 and blocked == attempted  # 100%
    assert not list((commons / "notes").rglob("*.md"))  # nothing written
    assert _git(commons, "rev-parse", "--abbrev-ref", "HEAD") == "main"


def test_publish_requires_confirmation_and_deid(vault: Vault, commons: Path) -> None:
    rel = "10_Domains/D2/WCET 예산은 측정값의 1.5배로 잡는다.md"
    with pytest.raises(CommonsError, match="confirmation"):
        publish_note(vault, rel, commons, confirmed=False, now=NOW)
    # inject an IP → blocked by de-identification
    p = vault.root / rel
    p.write_text(p.read_text(encoding="utf-8") + "\n접속 10.0.0.5\n", encoding="utf-8")
    with pytest.raises(CommonsError, match="deid ip-address"):
        publish_note(vault, rel, commons, confirmed=True, now=NOW)
    # vault-level deid terms
    (vault.root / "90_System/deid.yaml").write_text("terms: [Executor]\n", encoding="utf-8")
    p.write_text(p.read_text(encoding="utf-8").replace("\n접속 10.0.0.5\n", "\n"), encoding="utf-8")
    with pytest.raises(CommonsError, match="term:Executor"):
        publish_note(vault, rel, commons, confirmed=True, now=NOW)
    with pytest.raises(CommonsError, match="not a Commons git clone"):
        publish_note(vault, rel, commons / "nope", confirmed=True, now=NOW)


def test_publish_success_branch_commit_provenance(vault: Vault, commons: Path) -> None:
    rel = "10_Domains/D2/WCET 예산은 측정값의 1.5배로 잡는다.md"
    res = publish_note(vault, rel, commons, confirmed=True, now=NOW)
    assert (
        res.branch == "publish/20260907-0800-wcet-budget" and not res.pushed and res.pr_url is None
    )
    assert res.dest.startswith("notes/D2/20260907-0800-wcet-budget-")
    assert _git(commons, "rev-parse", "--abbrev-ref", "HEAD") == "main"  # back on base branch
    assert not (commons / res.dest).exists()  # only on the publish branch
    _git(commons, "checkout", "-q", res.branch)
    text = (commons / res.dest).read_text(encoding="utf-8")
    assert f"published_by: {owner_hash(vault)}" in text and "author: Brian" in text
    assert "published_from: 20260907-0800-wcet-budget" in text and "published: 2026-10-18" in text
    assert (
        "brian@example.org" not in text.split("---")[1].split("author")[0]
    )  # email never in frontmatter
    assert _git(commons, "log", "-1", "--pretty=%s").startswith("[myelin:publish] WCET")
    _git(commons, "checkout", "-q", "main")
    with pytest.raises(CommonsError, match="pending review"):
        publish_note(vault, rel, commons, confirmed=True, now=NOW)
    assert _git(commons, "rev-parse", "--abbrev-ref", "HEAD") == "main"


def test_publish_push_to_bare_remote(vault: Vault, commons: Path, tmp_path: Path) -> None:
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    _git(commons, "remote", "add", "origin", str(bare))
    _git(commons, "push", "-q", "-u", "origin", "main")
    res = publish_note(
        vault,
        "10_Domains/D1/AX 저항은 통제감 상실에서 온다.md",
        commons,
        confirmed=True,
        now=NOW,
        push=True,
    )
    assert res.pushed
    branches = subprocess.run(
        ["git", "branch", "-a"], cwd=bare, capture_output=True, text=True
    ).stdout
    assert res.branch in branches


def test_propose_pack(vault: Vault, commons: Path, tmp_path: Path) -> None:
    pdir = vault.root / "packs" / "me.side"
    pdir.mkdir(parents=True)
    (pdir / "pack.yaml").write_text(
        "pack: me.side\nkind: personal\nmaintainer: me\nrequires: [myelin.core>=1.0]\n"
        "domains:\n  - {id: SIDE, name: Side, sub_mocs: [a]}\n",
        encoding="utf-8",
    )
    with pytest.raises(CommonsError, match="confirmation"):
        propose_pack(vault, pdir, commons, confirmed=False)
    res = propose_pack(vault, pdir, commons, confirmed=True)
    assert res.branch == "propose/me.side"
    _git(commons, "checkout", "-q", res.branch)
    assert (commons / "proposals/packs/me.side/PROPOSAL.md").exists()
    assert (commons / "proposals/packs/me.side/pack.yaml").exists()
    _git(commons, "checkout", "-q", "main")
    (pdir / "pack.yaml").write_text(
        (pdir / "pack.yaml").read_text(encoding="utf-8") + "description: 고객 ACME 전용\n",
        encoding="utf-8",
    )
    (commons / "deid.yaml").write_text("terms: [ACME]\n", encoding="utf-8")
    with pytest.raises(CommonsError, match="de-identification"):
        propose_pack(vault, pdir, commons, confirmed=True)
    with pytest.raises(CommonsError):
        propose_pack(vault, tmp_path / "nope", commons, confirmed=True)
