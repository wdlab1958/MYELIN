"""ADR-0011 기밀 라우팅 장치 — guard_read.py (Read|Grep|Glob) and the Bash read channel.

Every case runs the real hook as a subprocess. A session is LOCAL iff MYELIN_LLM=local; the
conftest strips that variable from the inherited environment so each case sets it explicitly.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pytest

from tests.plugin.conftest import HookResult, make_vault, run_hook

R = "guard_read.py"
B = "guard_bash.py"
CONFIDENTIAL = (
    "---\nid: 20261001-0901-s\ntype: evergreen\nclassification: confidential\n"
    "created: 2026-10-01\n---\n# secret\nbody\n"
)
INTERNAL = "---\nid: 20261001-0902-i\ntype: evergreen\nclassification: internal\n---\nbody\n"


def ip_vault(root: Path, level: int = 1, *, ip_file: bool = True) -> Path:
    v = make_vault(root, level=level)
    if ip_file:
        (v / "40_IP/candidates/idea.md").write_text(CONFIDENTIAL, encoding="utf-8")
    (v / "10_Domains/D1/secret.md").write_text(CONFIDENTIAL, encoding="utf-8")
    (v / "10_Domains/D2").mkdir()
    (v / "10_Domains/D2/plain.md").write_text(INTERNAL, encoding="utf-8")
    (v / "10_Domains/D2/attachment.pdf").write_bytes(b"%PDF-1.4 binary")
    return v


def rd(path: object, **extra: object) -> dict[str, object]:
    return {"tool_name": "Read", "tool_input": {"file_path": path}, **extra}


def gr(tool: str = "Grep", path: object = None, **extra: object) -> dict[str, object]:
    ti: dict[str, object] = {"pattern": "x"}
    if path is not None:
        ti["path"] = path
    return {"tool_name": tool, "tool_input": ti, **extra}


def bash(cmd: str) -> dict[str, object]:
    return {"tool_name": "Bash", "tool_input": {"command": cmd}}


def env(v: Path, local: bool = False) -> dict[str, str]:
    e = {"MYELIN_VAULT": str(v)}
    if local:
        e["MYELIN_LLM"] = "local"
    return e


def _blocked(r: HookResult, why: str) -> None:
    assert r.code == 2, f"{why}: expected BLOCK, got exit {r.code}; stderr={r.stderr!r}"
    assert r.stderr.startswith("MYELIN guard: ") and re.search(r"[가-힣]", r.stderr), r.stderr


@pytest.fixture
def v(tmp_path: Path) -> Path:
    return ip_vault(tmp_path / "vault")


# ----------------------------------------------------------------------------------- Read
def test_read_ip_blocked_external_allowed_local(v: Path) -> None:
    target = str(v / "40_IP/candidates/idea.md")
    r = run_hook(R, rd(target), env(v))
    _blocked(r, "40_IP read")
    assert "40_IP" in r.stderr and "MYELIN_LLM=local" in r.stderr
    _blocked(run_hook(R, rd(str(v / "40_IP")), env(v)), "40_IP dir")
    _blocked(run_hook(R, rd(str(v / "40_IP/new-file.pdf")), env(v)), "nonexistent under 40_IP")
    assert run_hook(R, rd(target), env(v, local=True)).allowed


@pytest.mark.parametrize("value", ["local ", "Local", "LOCAL", "", "true", "1"])
def test_only_exact_local_counts(v: Path, value: str) -> None:
    e = {**env(v), "MYELIN_LLM": value}
    _blocked(run_hook(R, rd(str(v / "40_IP/candidates/idea.md")), e), repr(value))


def test_read_confidential_outside_ip_blocked(v: Path) -> None:
    r = run_hook(R, rd(str(v / "10_Domains/D1/secret.md")), env(v))
    _blocked(r, "confidential note")
    assert "confidential" in r.stderr
    assert run_hook(R, rd(str(v / "10_Domains/D1/secret.md")), env(v, local=True)).allowed


@pytest.mark.parametrize(
    "fm",
    [
        'classification: "confidential"',
        "classification: 'confidential'",
        "classification: confidential   # locked",
        "classification: Confidential",
        "classification:\tconfidential",
    ],
)
def test_read_confidential_spellings(v: Path, fm: str) -> None:
    p = v / "10_Domains/D2/spelled.md"
    p.write_text(f"---\nid: x\n{fm}\n---\nbody\n", encoding="utf-8")
    _blocked(run_hook(R, rd(str(p)), env(v)), fm)


@pytest.mark.parametrize(
    "text",
    [
        "---\nid: x\nclassification: confidential\n",  # never closed → cannot judge
        "---\nid: x\nclassification: secret\n---\n",  # unknown value
        "---\nid: x\nclassification: confidential\nclassification: public\n---\n",  # duplicated
        "---\nid: x\nclassification:\n---\n",  # empty value
        "﻿---\nclassification: confidential\n---\n",  # BOM + confidential
    ],
)
def test_read_unjudgeable_frontmatter_blocks(v: Path, text: str) -> None:
    p = v / "10_Domains/D2/odd.md"
    p.write_text(text, encoding="utf-8")
    _blocked(run_hook(R, rd(str(p)), env(v)), repr(text[:40]))


@pytest.mark.parametrize(
    "text",
    [
        INTERNAL,
        "---\nid: x\nclassification: public\n---\n",
        "---\nid: x\n---\nbody with the word classification: confidential in it\n",  # body only
        "# no frontmatter at all\nclassification: confidential\n",  # not a frontmatter block
        "---\nid: x\n  classification: confidential\n---\n",  # nested key, not top-level
        "",
    ],
)
def test_read_non_confidential_allowed(v: Path, text: str) -> None:
    p = v / "10_Domains/D2/ok.md"
    p.write_text(text, encoding="utf-8")
    r = run_hook(R, rd(str(p)), env(v))
    assert r.allowed, r.stderr


def test_read_non_notes_and_outside_allowed(v: Path, tmp_path: Path) -> None:
    assert run_hook(R, rd(str(v / "10_Domains/D2/attachment.pdf")), env(v)).allowed
    assert run_hook(R, rd(str(v / "myelin.yaml")), env(v)).allowed
    assert run_hook(R, rd(str(v / "10_Domains/D2/missing.md")), env(v)).allowed
    outside = tmp_path / "elsewhere.md"
    outside.write_text(CONFIDENTIAL, encoding="utf-8")  # outside the Vault: not governed
    assert run_hook(R, rd(str(outside)), env(v)).allowed
    assert run_hook(R, rd("/etc/hostname"), env(v)).allowed


def test_read_symlink_and_dotdot_into_ip(v: Path, tmp_path: Path) -> None:
    (v / "00_Inbox/ai-drafts/ip").symlink_to(v / "40_IP/candidates", target_is_directory=True)
    _blocked(run_hook(R, rd(str(v / "00_Inbox/ai-drafts/ip/idea.md")), env(v)), "dir symlink")
    (v / "00_Inbox/ai-drafts/s.md").symlink_to(v / "10_Domains/D1/secret.md")
    _blocked(run_hook(R, rd(str(v / "00_Inbox/ai-drafts/s.md")), env(v)), "file symlink")
    _blocked(run_hook(R, rd(str(v / "10_Domains/../40_IP/candidates/idea.md")), env(v)), "..")
    outside_link = tmp_path / "link.md"
    outside_link.symlink_to(v / "40_IP/candidates/idea.md")
    _blocked(run_hook(R, rd(str(outside_link)), env(v)), "outside symlink into 40_IP")
    _blocked(run_hook(R, rd("40_IP/candidates/idea.md"), env(v)), "relative path")


def test_read_nfd_filename_still_judged(v: Path) -> None:
    name = unicodedata.normalize("NFD", "기밀 설계") + ".md"
    p = v / "10_Domains/D2" / name
    p.write_text(CONFIDENTIAL, encoding="utf-8")
    _blocked(run_hook(R, rd(str(p)), env(v)), "NFD confidential")
    nfc = v / "10_Domains/D2" / (unicodedata.normalize("NFC", "기밀 설계") + ".md")
    if nfc.exists():  # case-folding FS (macOS): same file
        _blocked(run_hook(R, rd(str(nfc)), env(v)), "NFC alias")
    # 40_IP spelled with a fullwidth-free NFD path component is still 40_IP
    ipn = v / unicodedata.normalize("NFD", "40_IP") / "candidates/idea.md"
    _blocked(run_hook(R, rd(str(ipn)), env(v)), "NFD 40_IP")


@pytest.mark.parametrize(
    "ev",
    [
        {"tool_name": "Write", "tool_input": {"file_path": "x"}},
        {"tool_name": "Read"},
        {"tool_name": "Read", "tool_input": {}},
        {"tool_name": "Read", "tool_input": {"file_path": ""}},
        {"tool_name": "Read", "tool_input": {"file_path": 7}},
        {"tool_name": "Read", "tool_input": {"file_path": "a\x00b"}},
        "not json",
        "[]",
    ],
)
def test_read_bad_input_blocks(v: Path, ev: object) -> None:
    r = run_hook(R, ev, env(v))
    assert r.blocked and r.stderr.startswith("MYELIN guard: "), (ev, r.stderr)


def test_read_without_vault_blocks(tmp_path: Path) -> None:
    _blocked(run_hook(R, rd(str(tmp_path / "x.md")), {}, cwd=tmp_path), "no vault")


# ------------------------------------------------------------------------------ Grep / Glob
@pytest.mark.parametrize("tool", ["Grep", "Glob"])
def test_search_covering_ip_blocked(v: Path, tool: str) -> None:
    for path in (str(v / "40_IP"), str(v / "40_IP/candidates"), str(v), str(v.parent)):
        r = run_hook(R, gr(tool, path), env(v))
        _blocked(r, f"{tool} {path}")
    r = run_hook(R, gr(tool, str(v)), env(v))
    assert "path" in r.stderr and "40_IP" in r.stderr  # tells the user how to proceed
    # path absent → cwd; cwd absent → cannot judge
    _blocked(run_hook(R, gr(tool, None, cwd=str(v)), env(v)), f"{tool} no path")
    _blocked(run_hook(R, gr(tool, None), env(v)), f"{tool} no path no cwd")
    assert run_hook(R, gr(tool, str(v)), env(v, local=True)).allowed


def test_search_subdir_without_confidential_allowed(v: Path, tmp_path: Path) -> None:
    for tool in ("Grep", "Glob"):
        assert run_hook(R, gr(tool, str(v / "10_Domains/D2")), env(v)).allowed
        assert run_hook(R, gr(tool, str(v / "00_Inbox")), env(v)).allowed
        assert run_hook(R, gr(tool, str(tmp_path / "other")), env(v)).allowed  # outside


def test_grep_dir_with_confidential_blocked_glob_allowed(v: Path) -> None:
    r = run_hook(R, gr("Grep", str(v / "10_Domains/D1")), env(v))
    _blocked(r, "Grep over dir with confidential note")
    assert "secret.md" in r.stderr
    assert run_hook(R, gr("Glob", str(v / "10_Domains/D1")), env(v)).allowed  # names only
    assert run_hook(R, gr("Grep", str(v / "10_Domains/D1")), env(v, local=True)).allowed


def test_grep_whole_vault_when_ip_empty(tmp_path: Path) -> None:
    v = ip_vault(tmp_path / "v", ip_file=False)
    (v / "40_IP/candidates/.gitkeep").write_text("", encoding="utf-8")  # placeholder is ignored
    # Glob: 40_IP has no files → whole-Vault listing allowed
    assert run_hook(R, gr("Glob", str(v)), env(v)).allowed
    # Grep: the confidential note in 10_Domains/D1 still blocks a whole-Vault content search
    r = run_hook(R, gr("Grep", str(v)), env(v))
    _blocked(r, "Grep whole vault with confidential note")
    (v / "10_Domains/D1/secret.md").unlink()
    assert run_hook(R, gr("Grep", str(v)), env(v)).allowed
    (v / "40_IP/candidates/x.pdf").write_bytes(b"x")
    _blocked(run_hook(R, gr("Glob", str(v)), env(v)), "any real file in 40_IP")


def test_search_on_file_paths(v: Path) -> None:
    _blocked(run_hook(R, gr("Grep", str(v / "10_Domains/D1/secret.md")), env(v)), "conf file")
    _blocked(run_hook(R, gr("Grep", str(v / "40_IP/candidates/idea.md")), env(v)), "ip file")
    assert run_hook(R, gr("Grep", str(v / "10_Domains/D2/plain.md")), env(v)).allowed


def test_search_symlink_into_ip(v: Path) -> None:
    (v / "00_Inbox/clips").mkdir(exist_ok=True)
    (v / "00_Inbox/clips/ip").symlink_to(v / "40_IP", target_is_directory=True)
    _blocked(run_hook(R, gr("Grep", str(v / "00_Inbox/clips/ip")), env(v)), "symlink root")
    _blocked(run_hook(R, gr("Glob", str(v / "00_Inbox/clips/ip")), env(v)), "symlink root glob")
    # a symlink *inside* the searched directory that points into 40_IP is found by the scan
    _blocked(run_hook(R, gr("Grep", str(v / "00_Inbox/clips")), env(v)), "symlink inside root")


def test_nested_vault_ancestor_search_blocked(tmp_path: Path) -> None:
    outer = tmp_path / "outer"
    inner = ip_vault(outer / "projects" / "inner")
    _blocked(run_hook(R, gr("Grep", str(outer)), env(inner)), "ancestor of nested vault")
    _blocked(run_hook(R, gr("Glob", str(outer / "projects")), env(inner)), "ancestor glob")
    # sibling directory is not governed
    (outer / "sibling").mkdir()
    assert run_hook(R, gr("Grep", str(outer / "sibling")), env(inner)).allowed


# ------------------------------------------------------------------------------ Bash reads
BASH_BLOCKED_EXTERNAL = [
    "cat 40_IP/candidates/idea.md",
    "cat ./40_ip/candidates/idea.md",
    'cat "40_""IP/candidates/idea.md"',
    "echo 40_IP",
    "ls 40_IP",
    "head -n 5 10_Domains/D1/secret.md",
    "sed -n 1,5p 10_Domains/D1/secret.md",
    "cat 00_Inbox/ai-drafts/link.md",  # symlink → 40_IP (created by the test)
    "cat 4*_IP/candidates/*.md",
    "cat */candidates/*.md",
    "cat {4,5}0_IP/candidates/idea.md",
    "cat 10_Domains/*/secret.md",
    "cat 10_Domains/D1/*.md",
    "grep -r foo .",
    "grep -rn foo",
    "grep -R foo 10_Domains",
    "grep -r foo 10_Domains/D1",
    "rg foo",
    "rg foo 10_Domains",
    "ag foo .",
    "find . -name '*.md'",
    "find -name '*.md'",
    "fd .md",
    "tree",
    "ls -R",
    "ls -laR .",
    "git grep foo",
    "git grep foo -- 10_Domains/D1",
    "git show",
    "git show HEAD",
    "git show HEAD:10_Domains/D1/secret.md",
    "git diff",
    "git diff HEAD~1",
    "git log -p",
    "git log --patch -n 1",
    "git log -U3",
    "cd 10_Domains && cat D1/secret.md",
    "cd 10_Domains; grep -r foo .",
    "wc -l 10_Domains/D1/secret.md",
    "python3 /usr/bin/tool.py 40_IP/candidates/idea.md",
    "timeout 5 cat 10_Domains/D1/secret.md",
    "uv run myelin doctor --vault 40_IP",
]
BASH_ALLOWED_EXTERNAL = [
    "cat 10_Domains/D2/plain.md",
    "cat 10_Domains/D1/note.md",
    "head 10_Domains/D2/plain.md",
    "ls",
    "ls 10_Domains",
    "ls -la 10_Domains/D1",
    "grep foo 10_Domains/D2/plain.md",
    "grep -r foo 10_Domains/D2",
    "rg foo 10_Domains/D2",
    "find 10_Domains/D2 -name '*.md'",
    "git status",
    "git log",
    "git log --oneline -n 5",
    "git show --stat",
    "git show --name-only HEAD",
    "git diff --stat",
    "git diff --name-only",
    "git show -- 10_Domains/D2",
    "git diff -- 10_Domains/D2/plain.md",
    "git log -p -- 10_Domains/D2",
    "git grep foo -- 10_Domains/D2",
    "cat 10_Domains/D2/*.md",
    "awk '{print}' 10_Domains/D2/plain.md",
    "cat /etc/hostname",
    "uv run pytest -q",
    "myelin doctor",
]


@pytest.fixture
def bv(tmp_path: Path) -> Path:
    v = ip_vault(tmp_path / "vault")
    (v / "00_Inbox/ai-drafts/link.md").symlink_to(v / "40_IP/candidates/idea.md")
    return v


@pytest.mark.parametrize("cmd", BASH_BLOCKED_EXTERNAL)
def test_bash_read_blocked_external(bv: Path, cmd: str) -> None:
    ev = {**bash(cmd), "cwd": str(bv)}
    _blocked(run_hook(B, ev, env(bv), cwd=bv), cmd)
    assert "ADR-0011" in run_hook(B, ev, env(bv), cwd=bv).stderr


@pytest.mark.parametrize("cmd", BASH_ALLOWED_EXTERNAL)
def test_bash_read_allowed_external(bv: Path, cmd: str) -> None:
    ev = {**bash(cmd), "cwd": str(bv)}
    r = run_hook(B, ev, env(bv), cwd=bv)
    assert r.allowed, f"{cmd!r}: {r.stderr}"


@pytest.mark.parametrize(
    "cmd",
    ["cat 40_IP/candidates/idea.md", "grep -r foo .", "git show", "cat 10_Domains/D1/secret.md"],
)
def test_bash_read_allowed_local(bv: Path, cmd: str) -> None:
    r = run_hook(B, {**bash(cmd), "cwd": str(bv)}, env(bv, local=True), cwd=bv)
    assert r.allowed, f"{cmd!r}: {r.stderr}"


def test_bash_whole_vault_search_allowed_when_nothing_confidential(tmp_path: Path) -> None:
    v = make_vault(tmp_path / "clean", level=1)
    for cmd in ("grep -r foo .", "rg foo", "find . -name '*.md'", "git show", "ls -R"):
        r = run_hook(B, {**bash(cmd), "cwd": str(v)}, env(v), cwd=v)
        assert r.allowed, f"{cmd!r}: {r.stderr}"
    (v / "10_Domains/D1/secret.md").write_text(CONFIDENTIAL, encoding="utf-8")
    _blocked(run_hook(B, {**bash("grep -r foo ."), "cwd": str(v)}, env(v), cwd=v), "now conf")
    _blocked(run_hook(B, {**bash("git show"), "cwd": str(v)}, env(v), cwd=v), "git show conf")
    assert run_hook(B, {**bash("ls -R"), "cwd": str(v)}, env(v), cwd=v).allowed  # names only


def test_bash_write_to_ip_blocked_external_even_at_level_3(tmp_path: Path) -> None:
    v = make_vault(tmp_path / "v3", level=3)
    r = run_hook(B, bash("echo x > 40_IP/candidates/i.md"), env(v), cwd=v)
    _blocked(r, "L3 external 40_IP write")
    assert "외부 LLM" in r.stderr
    assert run_hook(B, bash("echo x > 40_IP/candidates/i.md"), env(v, local=True), cwd=v).allowed
    assert run_hook(B, bash("cp 10_Domains/D1/note.md 40_IP/candidates/i.md"), env(v)).blocked
