"""minimal Vault fixture 전체가 오류 없이 파싱되는지 (P1 Gate 조건)."""

from pathlib import Path

from myelin_core.frontmatter import Origin, Status
from myelin_core.note import parse_note_file

VAULT = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "vaults" / "minimal"


def test_minimal_vault_parses() -> None:
    notes = [parse_note_file(p, root=VAULT) for p in sorted(VAULT.rglob("*.md"))]
    assert len(notes) >= 30
    drafts = [n for n in notes if n.path and n.path.startswith("00_Inbox/ai-drafts/")]
    assert drafts and all(n.frontmatter.origin is Origin.CLAUDE for n in drafts)
    assert all(n.frontmatter.status is not Status.VERIFIED for n in drafts)
    ip = [n for n in notes if n.path and n.path.startswith("40_IP/")]
    assert ip and all(n.frontmatter.classification.value == "confidential" for n in ip)
    assert all(not n.frontmatter.policy_issues() for n in notes)
