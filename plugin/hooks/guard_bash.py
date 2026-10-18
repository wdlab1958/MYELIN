"""MYELIN Fail-closed Guard — PreToolUse for Bash (ADR-0002 D6, ADR-0005).

Blocks shell commands that could write outside the Level-allowed directories. Standard library
only. Heuristic, so it errs toward blocking:

- redirections (`>`, `>>`, `&>`, `n>`) and writer commands (tee, sed -i, mv, cp, rm, rmdir,
  touch, truncate, dd, install, ln, chmod, chown, mkdir, shred) must target allowed dirs;
- inline interpreters (`python -c`, `bash -c`, `node -e`, `perl -e`, `ruby -e`, `eval`,
  `exec`) are blocked — their effects cannot be inspected;
- destructive/outward git (checkout, restore, reset, clean, stash, rm, mv, rebase, merge, pull,
  push, filter-branch) is blocked; `git commit/add/status/diff/log` are allowed;
- `cd` together with a writer, command substitution `$(…)`/backticks, variables in paths,
  and unparseable quoting are blocked (cannot judge → fail-closed).
"""

from __future__ import annotations

import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guard_common import (
    ALLOW,
    BlockedError,
    block,
    check_allowed,
    find_vault,
    read_event,
    resolve_inside,
    vault_level,
)

REDIRECT_RE = re.compile(r"^(?:\d*>>?|&>>?|>\|)(.*)$")
WRITERS = {
    "tee",
    "mv",
    "cp",
    "rm",
    "rmdir",
    "touch",
    "truncate",
    "dd",
    "install",
    "ln",
    "chmod",
    "chown",
    "mkdir",
    "shred",
    "rsync",
    "unzip",
    "tar",
}
SED_LIKE = {"sed", "perl"}  # in-place flags
INLINE_INTERPRETERS = {
    "python",
    "python3",
    "python3.12",
    "node",
    "perl",
    "ruby",
    "bash",
    "sh",
    "zsh",
    "eval",
    "exec",
}
GIT_BLOCKED = {
    "checkout",
    "restore",
    "reset",
    "clean",
    "stash",
    "rm",
    "mv",
    "rebase",
    "merge",
    "pull",
    "push",
    "filter-branch",
    "switch",
    "worktree",
}
SEPARATORS = {";", "&&", "||", "|", "&", "(", ")"}
SUBST_RE = re.compile(r"\$\(|`|\$\{?[A-Za-z_]")
OPTION_WITH_VALUE_RE = re.compile(r"^-[a-zA-Z]*$")


def split_commands(tokens: list[str]) -> list[list[str]]:
    cmds: list[list[str]] = [[]]
    for t in tokens:
        if t in SEPARATORS:
            if cmds[-1]:
                cmds.append([])
        else:
            cmds[-1].append(t)
    return [c for c in cmds if c]


def strip_path(p: str) -> str:
    return p


def check_command(cmd: list[str], vault: Path, level: int, saw_cd: bool) -> None:
    # redirections anywhere in this simple command
    args: list[str] = []
    i = 0
    while i < len(cmd):
        t = cmd[i]
        m = REDIRECT_RE.match(t)
        if m and t not in ("2>&1", "1>&2", ">&2", "&>1"):
            target = m.group(1)
            if not target:
                i += 1
                if i >= len(cmd):
                    raise BlockedError("리다이렉션 대상이 없습니다 — 차단")
                target = cmd[i]
            if target.startswith("&") or target == "/dev/null":
                i += 1
                continue
            if saw_cd:
                raise BlockedError("cd 와 함께 쓰는 리다이렉션은 판단할 수 없습니다 — 차단")
            check_allowed(resolve_inside(vault, target), level, target)
        elif t in ("<", "<<", "<<<", "2>&1", "1>&2", ">&2"):
            pass
        else:
            args.append(t)
        i += 1
    if not args:
        return
    prog = Path(args[0]).name
    if prog == "sudo" or prog == "env":
        raise BlockedError(f"{prog} 는 허용하지 않습니다 — 차단")
    inline = any(a in ("-c", "-e", "-E") for a in args[1:]) or prog in ("eval", "exec")
    if prog in INLINE_INTERPRETERS and inline:
        raise BlockedError(
            f"{prog} 인라인 코드 실행은 검사할 수 없습니다 — 차단 (스크립트 파일로 실행하세요)"
        )
    if prog == "git":
        sub = next((a for a in args[1:] if not a.startswith("-")), "")
        if sub in GIT_BLOCKED:
            raise BlockedError(f"git {sub} 는 사람만 수행합니다 — 차단")
        return
    in_place = prog in SED_LIKE and any(a.startswith("-i") or a == "--in-place" for a in args[1:])
    if in_place or prog in WRITERS:
        _check_targets(args[1:], vault, level, saw_cd, prog)


def _check_targets(rest: list[str], vault: Path, level: int, saw_cd: bool, prog: str) -> None:
    targets = [a for a in rest if not a.startswith("-") and not (OPTION_WITH_VALUE_RE.match(a))]
    if prog in ("sed", "perl"):
        targets = targets[1:]  # first positional is the script
    if not targets:
        raise BlockedError(f"{prog} 대상 경로를 판단할 수 없습니다 — 차단")
    if saw_cd:
        raise BlockedError(f"cd 와 함께 쓰는 {prog} 는 판단할 수 없습니다 — 차단")
    for t in targets:
        if t in ("-", "/dev/null"):
            continue
        check_allowed(resolve_inside(vault, t), level, t)


def decide(ev: dict) -> int:
    if ev.get("tool_name") != "Bash":
        raise BlockedError(
            f"guard_bash 는 Bash 전용입니다 (tool_name={ev.get('tool_name')!r}) — 차단"
        )
    ti = ev.get("tool_input")
    command = ti.get("command") if isinstance(ti, dict) else None
    if not isinstance(command, str) or not command.strip():
        raise BlockedError("command 가 없습니다 — 차단")
    if SUBST_RE.search(command):
        raise BlockedError(
            "명령 치환 `$(...)`/백틱/변수 가 포함된 명령은 판단할 수 없습니다 — 차단"
        )
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError as exc:
        raise BlockedError(f"명령을 파싱할 수 없습니다 ({exc}) — 차단") from None
    vault = find_vault(ev)
    level = vault_level(vault)
    cmds = split_commands(tokens)
    saw_cd = any(c and Path(c[0]).name in ("cd", "pushd", "popd") for c in cmds)
    for cmd in cmds:
        check_command(cmd, vault, level, saw_cd)
    return ALLOW


def main() -> int:
    try:
        return decide(read_event())
    except BlockedError as exc:
        return block(str(exc))
    except Exception as exc:
        return block(f"내부 오류 ({type(exc).__name__}: {exc}) — 차단")


if __name__ == "__main__":
    sys.exit(main())
