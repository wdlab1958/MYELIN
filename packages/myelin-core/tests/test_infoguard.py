"""Customer-information guard (ADR-0017): must-block and must-pass samples, policy loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from myelin_core.infoguard import (
    BLOCK,
    FLAG,
    GuardError,
    GuardPolicy,
    scan_text,
)

# Synthetic values only: shaped like secrets, issued by nobody.
AWS = "AKIA" + "ABCDEFGHIJKLMNOP"
GH = "ghp_" + "a1B2c3D4e5F6g7H8i9J0" * 2
JWT = "eyJhbGciOiJIUzI1NiJ9" + "." + "eyJzdWIiOiJ0ZXN0In0x" + "." + "c2lnbmF0dXJlLXRlc3Q"

MUST_BLOCK = {
    "private-key": "-----BEGIN RSA PRIVATE KEY-----\nMIIB\n",
    "aws-access-key": f"키는 {AWS} 였다",
    "github-token": f"token {GH}",
    "jwt": f"세션 {JWT}",
    "bearer-token": "Authorization: Bearer abcdefghijklmnop1234567890",
    "url-credentials": "postgres://svc:hunter2pass@db.example.org:5432/app",
    "credential-assignment": "password = S3cretValue!9",
    "credential-assignment-ko": "비밀번호: qwerty123456",
    "credential-assignment-json": '"api_key": "abcd1234efgh5678"',
    "resident-number": "주민번호 900101-1234567",
}

MUST_PASS = [
    "비밀번호 정책은 12자 이상으로 한다.",
    "password: <비밀번호>  # 자리표시자",
    "token = {{token}}",
    "api_key=$API_KEY",
    "password: ********",
    "토큰 수(token count)는 4096 이다",
    "secret 관리 절차를 문서화한다",
    "예시 주소 192.0.2.10 과 127.0.0.1 은 식별자가 아니다",
    "버전 1.2.3.4567 로 올렸다",
    "```python\nprint('짧은 예시')\n```",
    "ISO/IEC 27001:2022 A.8.5 — 다중 인증",
    "https://example.org/docs 를 참고",
]


@pytest.mark.parametrize("rule", sorted(MUST_BLOCK))
def test_must_block(rule: str) -> None:
    rep = scan_text(f"# 노트\n\n{MUST_BLOCK[rule]}\n")
    assert rep.blocked, f"{rule} was not blocked"
    expected = rule.split("-ko")[0].split("-json")[0]
    assert expected in {h.rule for h in rep.blocks}


@pytest.mark.parametrize("text", MUST_PASS)
def test_must_pass(text: str) -> None:
    rep = scan_text(f"# 노트\n\n{text}\n")
    assert rep.clean, rep.summary()


def test_excerpts_never_repeat_the_secret() -> None:
    for sample in MUST_BLOCK.values():
        rep = scan_text(sample)
        for h in rep.hits:
            assert len(h.excerpt) <= 8 and h.excerpt.endswith("***")
            assert h.excerpt.rstrip("*") in sample
    assert AWS not in str(scan_text(MUST_BLOCK["aws-access-key"]).to_dict())


def test_flags_code_block_ip_and_internal_url() -> None:
    code = "```\n" + "\n".join(f"line {i}" for i in range(31)) + "\n```\n"
    rep = scan_text("# n\n" + code)
    assert rep.flagged and not rep.blocked
    assert [h.rule for h in rep.flags] == ["large-code-block"] and rep.flags[0].line == 2
    assert scan_text("# n\n```\n" + "x\n" * 30 + "```\n").clean  # exactly at the threshold
    assert scan_text("# n\n```\n" + "x\n" * 31).flagged  # unterminated block still counts
    rep = scan_text("서버 10.20.30.40 과 http://wiki.corp/page 를 봤다")
    assert {h.rule for h in rep.flags} == {"ip-address", "internal-url"}
    assert all(h.severity == FLAG for h in rep.hits)


def test_customer_names_from_every_source(tmp_path: Path) -> None:
    root = tmp_path / "v"
    (root / "90_System").mkdir(parents=True)
    (root / ".myelin").mkdir()
    (root / ".myelin/customer-names.txt").write_text(
        "# 로컬 목록\n테스트고객사\n\n", encoding="utf-8"
    )
    (root / "90_System/deid.yaml").write_text("terms: [Globex]\n", encoding="utf-8")
    extra = tmp_path / "names.txt"
    extra.write_text("Initech\n", encoding="utf-8")
    (root / "90_System/infoguard.yaml").write_text(
        "max_code_block_lines: 5\nterms: [Umbrella]\nnames_file: ../names.txt\n"
        "block_patterns: ['PRJ-\\d{4}']\nflag_patterns: ['사내망']\n",
        encoding="utf-8",
    )
    envf = tmp_path / "env.txt"
    envf.write_text("Hooli\n", encoding="utf-8")
    policy = GuardPolicy.load(root, env={"MYELIN_CUSTOMER_NAMES": str(envf)})
    assert set(policy.customer_terms) == {"테스트고객사", "Globex", "Initech", "Umbrella", "Hooli"}
    assert policy.max_code_block_lines == 5
    for name in (
        "테스트고객사",
        "GLOBEX",
        "initech",
        "\uff35\uff4d\uff42\uff52\uff45\uff4c\uff4c\uff41",  # full-width "Umbrella"
        "hooli",
    ):  # case/width-insensitive
        rep = scan_text(f"{name} 프로젝트에서 배운 것", policy)
        assert [h.rule for h in rep.blocks] == ["customer-name"], name
        assert name not in rep.blocks[0].excerpt
    assert scan_text("코드 PRJ-2041 건", policy).blocked
    assert scan_text("사내망 구성", policy).flagged
    assert scan_text("```\n" + "x\n" * 6 + "```", policy).flagged
    assert scan_text("금융 고객 유형에서 배운 것", policy).clean


def test_policy_is_fail_closed(tmp_path: Path) -> None:
    root = tmp_path / "v"
    (root / "90_System").mkdir(parents=True)
    f = root / "90_System/infoguard.yaml"
    for bad in (
        "unknown_key: 1\n",
        "max_code_block_lines: 0\n",
        "max_code_block_lines: many\n",
        "block_patterns: ['(']\n",
        "terms: notalist\n",
        "names_file: missing.txt\n",
        "- a\n- b\n",
        "a: [unclosed\n",
    ):
        f.write_text(bad, encoding="utf-8")
        with pytest.raises(GuardError):
            GuardPolicy.load(root)
    f.unlink()
    with pytest.raises(GuardError):
        GuardPolicy.load(root, env={"MYELIN_CUSTOMER_NAMES": str(tmp_path / "nope.txt")})
    assert GuardPolicy.load(root, env={}).customer_terms == []  # nothing configured → built-ins
    assert GuardPolicy.load(None, env={}).max_code_block_lines == 30


def test_fixture_vault_and_packs_are_clean(repo_root: Path) -> None:
    """The shipped templates and synthetic fixtures must not trip the block rules."""
    files = [
        *sorted((repo_root / "packs").rglob("*.md")),
        *sorted((repo_root / "tests/fixtures/vaults/basic").rglob("*.md")),
        *sorted((repo_root / "docs/onecycle/samples").glob("*.md")),
    ]
    assert len(files) > 40
    for f in files:
        rep = scan_text(f.read_text(encoding="utf-8"))
        assert not rep.blocked, f"{f}: {rep.summary()}"
    assert BLOCK == "block"
