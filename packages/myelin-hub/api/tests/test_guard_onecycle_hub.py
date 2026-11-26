"""Hub side of the customer-information guard (ADR-0017) and the One Cycle hand-off (ADR-0018):
drafts other platforms drop into 00_Inbox/ai-drafts go through the ordinary Review Gate."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from myelin_core.note import read_note

from .conftest import CLICK, REPO_ROOT, tree_hash

DRAFTS = "00_Inbox/ai-drafts"
SAMPLES = REPO_ROOT / "docs/onecycle/samples"


def _draft(vault: Path, name: str, body: str, extra_fm: str = "", domain: str = "[D2]") -> str:
    rel = f"{DRAFTS}/{name}.md"
    (vault / rel).write_text(
        f"---\nid: 20261126-0900-{abs(hash(name)) % 10**8:08d}\ntype: lesson\ndomain: {domain}\n"
        f"status: draft\norigin: claude\ncreated: 2026-11-26\n{extra_fm}---\n# {name}\n\n{body}\n",
        encoding="utf-8",
    )
    return rel


def _promote(client: TestClient, rel: str, **body: object) -> object:
    n = client.get(f"/api/notes/{rel}").json()
    return client.post(
        f"/api/review/promote/{rel}", headers=CLICK, json={"digest": n["digest"], **body}
    )


def test_promote_blocks_secrets_and_customer_names(client: TestClient, vault_root: Path) -> None:
    (vault_root / ".myelin").mkdir(exist_ok=True)
    (vault_root / ".myelin/customer-names.txt").write_text("테스트고객사\n", encoding="utf-8")
    leak = _draft(vault_root, "누출", "접속 정보 password=Sup3rS3cret!! 로 들어갔다")
    cust = _draft(vault_root, "고객", "테스트고객사 프로젝트에서 배운 것")
    before = tree_hash(vault_root)
    for rel, word in ((leak, "Sup3rS3cret"), (cust, "테스트고객사")):
        g = client.get(f"/api/notes/{rel}").json()["guard"]
        assert g["blocked"] and word not in str(g)
        r = _promote(client, rel, guard_ack=True)  # an acknowledgement never lifts a block
        assert r.status_code == 422 and "고객정보 가드" in r.json()["detail"]  # type: ignore[attr-defined]
        assert word not in r.text  # type: ignore[attr-defined]
    assert tree_hash(vault_root) == before
    # must-pass: the same lesson without the identifiers
    ok = _draft(vault_root, "정상", "금융 고객 유형에서 비밀번호 정책은 12자 이상으로 권고한다")
    assert client.get(f"/api/notes/{ok}").json()["guard"] == {
        "blocked": False,
        "flagged": False,
        "hits": [],
    }
    assert _promote(client, ok).status_code == 200  # type: ignore[attr-defined]


def test_promote_of_flagged_draft_needs_acknowledgement(
    client: TestClient, vault_root: Path
) -> None:
    code = "```\n" + "\n".join(f"call_{i}();" for i in range(40)) + "\n```"
    rel = _draft(vault_root, "긴 코드", code + "\n\n서버 10.20.30.40")
    g = client.get(f"/api/notes/{rel}").json()["guard"]
    assert g["flagged"] and not g["blocked"]
    assert {h["rule"] for h in g["hits"]} == {"large-code-block", "ip-address"}
    before = tree_hash(vault_root)
    r = _promote(client, rel)
    assert r.status_code == 409 and "guard_ack" in r.json()["detail"]  # type: ignore[attr-defined]
    assert tree_hash(vault_root) == before
    r = _promote(client, rel, guard_ack=True)
    assert r.status_code == 200, r.text  # type: ignore[attr-defined]


def test_unreadable_guard_policy_refuses_promotion(client: TestClient, vault_root: Path) -> None:
    rel = _draft(vault_root, "정책", "본문")
    (vault_root / "90_System/infoguard.yaml").write_text("what: ever\n", encoding="utf-8")
    assert client.get(f"/api/notes/{rel}").json()["guard"]["blocked"] is True
    assert _promote(client, rel, guard_ack=True).status_code == 409  # type: ignore[attr-defined]
    assert (vault_root / rel).is_file()


def test_patch_that_adds_a_secret_is_refused(client: TestClient, vault_root: Path) -> None:
    name = "20261018-1700-d2-moc-missing-links.patch.md"
    shutil.copy(REPO_ROOT / "tests/fixtures/skill-outputs/link" / name, vault_root / "_patches")
    plan = client.get(f"/api/patches/{name}/preview").json()
    assert plan["ok"]
    pfile = vault_root / "_patches" / name
    text = pfile.read_text(encoding="utf-8")
    added = "- [[ISR 안에서 로그를 찍지 않는다]]"
    assert added in text
    pfile.write_text(text.replace(added, added + " api_key=abcd1234efgh5678", 1), encoding="utf-8")
    plan2 = client.get(f"/api/patches/{name}/preview").json()
    before = tree_hash(vault_root)
    r = client.post(f"/api/patches/{name}/apply", headers=CLICK, json={"digest": plan2["digest"]})
    assert r.status_code == 422 and "고객정보 가드" in r.json()["detail"]
    assert "abcd1234efgh5678" not in r.text and tree_hash(vault_root) == before
    pfile.write_text(text, encoding="utf-8")
    r = client.post(f"/api/patches/{name}/apply", headers=CLICK, json={"digest": plan["digest"]})
    assert r.status_code == 200, r.text


# ------------------------------------------------------------------ One Cycle drafts
@pytest.mark.parametrize("platform", ["llmops", "ssc", "argus", "proof-skills"])
def test_platform_drafts_are_accepted_by_the_review_flow(
    client: TestClient, vault_root: Path, platform: str
) -> None:
    """A draft with `source_platform` is an ordinary AI draft: listed, readable, promotable."""
    rel = _draft(
        vault_root,
        f"{platform} 초안",
        "다른 플랫폼이 넘긴 초안 본문",
        extra_fm=f"source_platform: {platform}\nsimulated: true\n",
    )
    row = next(d for d in client.get("/api/review").json()["drafts"] if d["path"] == rel)
    assert row["doctor_ok"] is True and row["status"] == "draft" and row["origin"] == "claude"
    assert client.get("/api/doctor").json()["errors"] == 0
    r = _promote(client, rel)
    assert r.status_code == 200, r.text  # type: ignore[attr-defined]
    dest = vault_root / r.json()["path"]  # type: ignore[attr-defined]
    fm = read_note(dest).frontmatter
    assert fm.status.value == "verified" and fm.origin.value == "mixed"
    assert fm.extra_fields["source_platform"] == platform  # provenance survives promotion
    assert fm.extra_fields["simulated"] is True
    log = subprocess.run(
        ["git", "log", "-1", "--format=%s"], cwd=vault_root, capture_output=True, text=True
    ).stdout
    assert log.startswith("[myelin:review] promote")


def test_sample_drafts_including_the_rediagnosis_twin_are_accepted(
    client: TestClient, vault_root: Path
) -> None:
    samples = sorted(SAMPLES.glob("draft.*.sample.md"))
    assert len(samples) == 3
    for s in samples:
        shutil.copy(s, vault_root / DRAFTS / s.name)
    drafts = {d["path"]: d for d in client.get("/api/review").json()["drafts"]}
    for s in samples:
        assert drafts[f"{DRAFTS}/{s.name}"]["doctor_ok"] is True
    # no Domain in the draft and none configured for the platform → the human must choose
    twin = f"{DRAFTS}/draft.argus-rediagnosis.sample.md"
    r = _promote(client, twin)
    assert r.status_code == 422 and "choose one" in r.json()["detail"]  # type: ignore[attr-defined]
    r = _promote(client, twin, domain="D2")
    assert r.status_code == 200, r.text  # type: ignore[attr-defined]


def test_routing_rule_sends_a_domainless_draft_to_the_platform_domain(
    client: TestClient, vault_root: Path
) -> None:
    assert client.post("/api/domains", headers=CLICK, json={"id": "ARGUS"}).status_code == 200
    rel = _draft(vault_root, "관제 초안", "본문", extra_fm="source_platform: argus\n", domain="[]")
    r = _promote(client, rel)
    assert r.status_code == 200, r.text  # type: ignore[attr-defined]
    assert r.json()["domain"] == "ARGUS"  # type: ignore[attr-defined]
    assert r.json()["path"].startswith("10_Domains/ARGUS/")  # type: ignore[attr-defined]
    # an unknown platform value routes nowhere (fail-closed: ask the human)
    rel2 = _draft(
        vault_root, "모르는 출처", "본문", extra_fm="source_platform: other\n", domain="[]"
    )
    assert _promote(client, rel2).status_code == 422  # type: ignore[attr-defined]
