"""MYELIN Fail-closed Guard — PreToolUse for Bash (ADR-0002 D6, ADR-0005).

Blocks shell commands that could write outside the Level-allowed directories. Standard library
only. Heuristic, so it errs toward blocking:

- redirections (`>`, `>>`, `>|`, `&>`, `>&`, `<>`, `n>`) and writer commands (tee, sed -i, mv, cp,
  rm, rmdir, touch, truncate, dd of=, install, ln, chmod, chown, mkdir, shred, gzip, wget -O,
  curl -o, …) must target allowed dirs; glob/brace targets cannot be judged → blocked;
- inline interpreters (`python -c`, `bash -c`, `node -e`, `perl -e`, `ruby -e`, `eval`,
  `exec`, combined flags like `-lc`/`-pi -e`, stdin scripts `curl … | sh`, `python3 - < x`)
  are blocked, and so is running a script that lives inside the Vault — their effects cannot be
  inspected; `python3 /outside/tool.py` and `uv run pytest` (project tooling) stay allowed;
- git: read-only subcommands plus `add`/`commit` (no `--amend`) are allowed, everything else
  (checkout, reset, push, apply, am, update-ref, cherry-pick, …) is blocked;
- wrappers that hide the real command (`sudo`, `env`, `xargs`, `find -exec/-delete`, `nice`,
  `su`, `patch`, `at`, `alias`, `trap`, …) are blocked; `timeout`/`time`/`nohup`/`command`/
  `builtin`/`uv run` are unwrapped and the inner command is judged;
- newlines are command separators; `cd` together with a writer, command substitution
  `$(…)`/backticks, variables in paths, `#` comments, and unparseable quoting are blocked or
  treated literally (cannot judge → fail-closed).

Confidential routing (ADR-0011) — in an EXTERNAL session (no `MYELIN_LLM=local`) the shell is also
a *read* channel (Grep/Glob are not in the default tool set on Linux; Claude searches with
`grep`/`find`/`rg` through Bash), so additionally:

- any token mentioning `40_IP` (any case, NFC) is blocked; every non-option token that resolves into
  40_IP/ or to a `classification: confidential` note is blocked (`cat`, `head`, `sed`, `cp` …);
  globs are expanded against cwd/Vault and judged; braces cannot be judged → blocked;
- recursive content searches (`grep -r`, `rg`, `ag`, `ack`, `ugrep`, `git grep`) over the Vault
  root/an ancestor/cwd are blocked while 40_IP/ has files or a confidential note exists beneath
  the root; listings (`find`, `fd`, `tree`, `ls -R`) over such roots are blocked while 40_IP/ has
  files; `git show`/`git diff`/`git log -p` (patch output) need a `-- <path>` outside 40_IP.
"""

from __future__ import annotations

import glob
import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guard_common import (
    ALLOW,
    IP_DIR,
    BlockedError,
    block,
    check_allowed,
    check_read_target,
    check_search_root,
    find_confidential_note,
    find_vault,
    ip_dir_has_files,
    is_local_session,
    read_event,
    resolve_any,
    resolve_inside,
    vault_level,
)

# shlex (punctuation_chars) emits operator runs as single tokens: `>`, `>>`, `>&`, `&>`, `|&`, …
WRITE_REDIRECTS = {">", ">>", ">|", "&>", "&>>", ">&", ">>&", "<>"}
READ_REDIRECTS = {"<", "<<", "<<-", "<<<"}
FD_DUP_RE = re.compile(r"^(\d+|-)$")
SEPARATOR_RE = re.compile(r"^[;&|()]+$")
REDIRECT_TOKEN_RE = re.compile(r"^(\d*)([<>&|]+)$")
GLOB_CHARS = set("*?[{")

WRITERS = {
    "tee",
    "mv",
    "cp",
    "rm",
    "rmdir",
    "touch",
    "truncate",
    "install",
    "ln",
    "chmod",
    "chown",
    "chgrp",
    "chattr",
    "setfacl",
    "mkdir",
    "shred",
    "rsync",
    "unzip",
    "tar",
    "zip",
    "7z",
    "7za",
    "gzip",
    "gunzip",
    "bzip2",
    "bunzip2",
    "xz",
    "unxz",
    "zstd",
    "unzstd",
    "ed",
    "ex",
    "vi",
    "vim",
    "nvim",
    "nano",
}
SED_LIKE = {"sed", "perl"}  # in-place flags
IN_PLACE_RE = re.compile(r"^-[^-]*i|^--in-place")
AWK_LIKE = {"awk", "gawk", "mawk", "nawk"}
INLINE_INTERPRETERS = {
    "python",
    "python3",
    "python3.12",
    "python3.13",
    "node",
    "perl",
    "ruby",
    "bash",
    "sh",
    "dash",
    "zsh",
    "ksh",
    "lua",
    "php",
}
# -c/-e/-E/-r inline code, -s stdin script, -m module from cwd; also clusters: -lc, -pi -e, -c'…'
INLINE_FLAG_RE = re.compile(r"^-[A-Za-z0-9]*[ceErsm]")
INLINE_LONG = {"--eval", "--print", "--command", "-p"}
# programs whose real command cannot be recovered from the argument list → block outright
BLOCKED_PROGS = {
    "sudo",
    "env",
    "doas",
    "su",
    "pkexec",
    "chroot",
    "unshare",
    "systemd-run",
    "setsid",
    "nice",
    "ionice",
    "stdbuf",
    "flock",
    "strace",
    "ltrace",
    "watch",
    "script",
    "expect",
    "xargs",
    "parallel",
    "at",
    "batch",
    "crontab",
    "patch",
    "eval",
    "exec",
    "alias",
    "function",
    "shopt",
    "trap",
    "enable",
    "hash",
}
# wrappers whose remaining args are the real command (after their own options)
UNWRAP = {"nohup", "command", "builtin", "time", "timeout"}
RUNNERS = {"uv", "uvx", "pipx", "npx", "poetry", "pdm", "hatch"}
SHELL_KEYWORDS = {"{", "}", "!", "if", "then", "else", "elif", "while", "until", "do", "coproc"}
ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
FIND_BLOCKED = {"-delete", "-exec", "-execdir", "-ok", "-okdir"}
FIND_WRITE_OPTS = {"-fprint", "-fprint0", "-fprintf", "-fls"}
GIT_READ = {
    "status",
    "diff",
    "log",
    "show",
    "blame",
    "grep",
    "ls-files",
    "ls-tree",
    "rev-parse",
    "rev-list",
    "cat-file",
    "describe",
    "shortlog",
    "name-rev",
    "var",
    "help",
    "version",
    "diff-tree",
    "diff-index",
    "show-ref",
    "for-each-ref",
    "count-objects",
    "check-ignore",
    "check-attr",
}
GIT_GLOBAL_WITH_VALUE = {"-c", "-C", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
GIT_REF_MUTATORS = {
    "-d",
    "-D",
    "-m",
    "-M",
    "-c",
    "-C",
    "-f",
    "-u",
    "--delete",
    "--force",
    "--move",
    "--copy",
    "--set-upstream-to",
    "--unset-upstream",
    "--edit-description",
}
SUBST_RE = re.compile(r"\$\(|`|\$\{?[A-Za-z_]")
OPTION_WITH_VALUE_RE = re.compile(r"^-[a-zA-Z]*$")


def split_commands(tokens: list[str]) -> list[tuple[str, list[str]]]:
    """Split on shell operators; each command carries the operator that preceded it."""
    cmds: list[tuple[str, list[str]]] = [("", [])]
    for t in tokens:
        if SEPARATOR_RE.match(t):
            if cmds[-1][1]:
                cmds.append((t, []))
            else:
                cmds[-1] = (t, cmds[-1][1])
        else:
            cmds[-1][1].append(t)
    return [c for c in cmds if c[1]]


def _check_target(target: str, vault: Path, level: int, saw_cd: bool, what: str) -> None:
    if target in ("-", "/dev/null", "/dev/stdout", "/dev/stderr"):
        return
    if saw_cd:
        raise BlockedError(f"cd 와 함께 쓰는 {what} 는 판단할 수 없습니다 — 차단")
    if GLOB_CHARS & set(target):
        raise BlockedError(f"글로브/중괄호 패턴 대상은 판단할 수 없습니다 → {target}")
    check_allowed(resolve_inside(vault, target), level, target)


def check_command(cmd: list[str], vault: Path, level: int, saw_cd: bool, prev_op: str) -> None:
    """Judge one simple command: redirections first, then the program and its targets."""
    args: list[str] = []
    stdin_redirected = False
    i = 0
    while i < len(cmd):
        t = cmd[i]
        if "<(" in t or ">(" in t:
            raise BlockedError("프로세스 치환 <(…)/>(…) 은 판단할 수 없습니다 — 차단")
        m = REDIRECT_TOKEN_RE.match(t)
        if m is None:
            args.append(t)
            i += 1
            continue
        op = m.group(2)
        if op in READ_REDIRECTS:
            stdin_redirected = True
            i += 2  # skip the source word / heredoc delimiter
            continue
        if op not in WRITE_REDIRECTS:
            raise BlockedError(f"알 수 없는 리다이렉션 {t!r} — 차단")
        i += 1
        if i >= len(cmd):
            raise BlockedError("리다이렉션 대상이 없습니다 — 차단")
        target = cmd[i]
        i += 1
        if op in (">&", ">>&") and FD_DUP_RE.match(target):
            continue  # 2>&1, >&2, >&-
        _check_target(target, vault, level, saw_cd, "리다이렉션")
    while args and ASSIGNMENT_RE.match(args[0]):
        args.pop(0)  # `VAR=value cmd` prefix
    while args and args[0] in SHELL_KEYWORDS:
        args.pop(0)
    _check_args(args, vault, level, saw_cd, stdin_redirected or prev_op in ("|", "|&"))


def _check_args(
    args: list[str], vault: Path, level: int, saw_cd: bool, stdin_fed: bool, depth: int = 0
) -> None:
    if not args:
        return
    if depth > 4:
        raise BlockedError("중첩된 래퍼 명령은 판단할 수 없습니다 — 차단")
    prog = "source" if args[0] in (".", "source") else Path(args[0]).name
    if prog in BLOCKED_PROGS:
        raise BlockedError(f"{prog} 는 허용하지 않습니다 (실제 명령을 판단할 수 없음) — 차단")
    if prog in UNWRAP:
        _check_args(_unwrap(prog, args[1:]), vault, level, saw_cd, stdin_fed, depth + 1)
        return
    if prog in RUNNERS:
        inner = next((k for k, a in enumerate(args[1:], 1) if a in INLINE_INTERPRETERS), None)
        if inner is not None:
            _check_args(args[inner:], vault, level, saw_cd, stdin_fed, depth + 1)
        return
    if prog in INLINE_INTERPRETERS or prog == "source":
        _check_interpreter(prog, args[1:], stdin_fed, vault)
        return
    if prog in AWK_LIKE:
        if any(
            ">" in a or "system(" in a or "inplace" in a or a.startswith("-i") for a in args[1:]
        ):
            raise BlockedError(f"{prog} 프로그램의 파일 쓰기/명령 실행은 검사할 수 없습니다 — 차단")
        return
    if prog == "git":
        _check_git(args[1:])
        return
    if prog == "find":
        _check_find(args[1:], vault, level, saw_cd)
        return
    if prog == "dd":
        for a in args[1:]:
            if a.startswith("of="):
                _check_target(a[3:], vault, level, saw_cd, "dd")
        return
    if prog in ("wget", "curl"):
        _check_downloader(prog, args[1:], vault, level, saw_cd)
        return
    in_place = prog in SED_LIKE and any(IN_PLACE_RE.match(a) for a in args[1:])
    if in_place or prog in WRITERS:
        _check_targets(args[1:], vault, level, saw_cd, prog)


def _unwrap(prog: str, rest: list[str]) -> list[str]:
    if prog == "command" and any(a in ("-v", "-V") for a in rest):
        return []  # `command -v x` only looks a name up
    i = 0
    while i < len(rest) and rest[i].startswith("-"):
        i += 1
    if prog == "timeout":
        if i >= len(rest) or not re.fullmatch(r"[0-9.]+[smhd]?", rest[i]):
            raise BlockedError("timeout 의 시간 인자를 판단할 수 없습니다 — 차단")
        i += 1
    inner = rest[i:]
    if not inner:
        raise BlockedError(f"{prog} 뒤에 실행할 명령이 없습니다 — 차단")
    return inner


def _check_interpreter(prog: str, rest: list[str], stdin_fed: bool, vault: Path) -> None:
    """Interpreters may only run a script file that lives OUTSIDE the Vault (project tooling)."""
    if any(INLINE_FLAG_RE.match(a) or a in INLINE_LONG for a in rest):
        raise BlockedError(
            f"{prog} 인라인 코드/모듈/stdin 실행은 검사할 수 없습니다 — 차단 "
            "(Vault 밖의 스크립트 파일로 실행하세요)"
        )
    positional = [a for a in rest if not a.startswith("-")]
    if stdin_fed or not positional or "-" in rest:
        raise BlockedError(f"{prog} 가 stdin 에서 스크립트를 읽습니다 — 판단 불가, 차단")
    script = positional[0]
    if ".." in Path(script).parts or "~" in script or GLOB_CHARS & set(script):
        raise BlockedError(f"{prog} 스크립트 경로를 판단할 수 없습니다 → {script}")
    try:
        real = (Path(script) if Path(script).is_absolute() else vault / script).resolve()
    except (OSError, RuntimeError) as exc:
        raise BlockedError(f"스크립트 경로를 해석할 수 없습니다 ({exc}) — 차단") from None
    if real == vault or real.is_relative_to(vault):
        raise BlockedError(
            f"{prog} 로 Vault 안의 스크립트를 실행하는 것은 검사할 수 없습니다 → {script}"
        )


def _check_git(rest: list[str]) -> None:
    sub = ""
    i = 0
    while i < len(rest):
        a = rest[i]
        if a in GIT_GLOBAL_WITH_VALUE:
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        sub = a
        break
    tail = rest[i + 1 :]
    if sub in GIT_READ or (not sub and any(a in ("--version", "--help") for a in rest)):
        return
    if sub == "add":
        return
    if sub == "commit":
        if "--amend" in tail:
            raise BlockedError("git commit --amend 는 사람만 수행합니다 — 차단")
        if any(a == "--no-verify" or re.fullmatch(r"-[a-zA-Z]*n[a-zA-Z]*", a) for a in tail):
            # ADR-0011 §5: skipping the Vault pre-commit device is a human-only action
            raise BlockedError(
                "git commit --no-verify 는 사람만 수행합니다 (pre-commit 장치 우회) — 차단"
            )
        return
    if sub in ("branch", "tag"):
        positional = [a for a in tail if not a.startswith("-")]
        listing = any(a in ("-l", "--list") for a in tail)
        if any(a in GIT_REF_MUTATORS for a in tail) or (positional and not listing):
            raise BlockedError(f"git {sub} 변경은 사람만 수행합니다 — 차단")
        return
    if sub == "remote":
        if all(a in ("-v", "--verbose") for a in tail) or tail[:1] in (["show"], ["get-url"]):
            return
        raise BlockedError("git remote 변경은 사람만 수행합니다 — 차단")
    if sub == "config":
        reads = {"--get", "--get-all", "--get-regexp", "--list", "-l"}
        positional = [a for a in tail if not a.startswith("-")]
        if any(a in reads for a in tail) and not any(a.startswith("--unset") for a in tail):
            return
        if len(positional) == 1 and not any(a.startswith("-") for a in tail):
            return
        raise BlockedError("git config 변경은 사람만 수행합니다 — 차단")
    raise BlockedError(f"git {sub or '(없음)'} 는 사람만 수행합니다 — 차단")


def _check_find(rest: list[str], vault: Path, level: int, saw_cd: bool) -> None:
    for k, a in enumerate(rest):
        if a in FIND_BLOCKED:
            raise BlockedError(f"find {a} 는 대상을 판단할 수 없습니다 — 차단")
        if a in FIND_WRITE_OPTS:
            if k + 1 >= len(rest):
                raise BlockedError(f"find {a} 대상이 없습니다 — 차단")
            _check_target(rest[k + 1], vault, level, saw_cd, "find")


DOWNLOADER_OUTPUT_LONG = {
    "wget": ("--output-document", "--directory-prefix"),
    "curl": ("--output", "--output-dir"),
}
DOWNLOADER_OUTPUT_SHORT = {"wget": "OP", "curl": "o"}
CURL_REMOTE_NAME = {"--remote-name", "--remote-header-name", "--remote-name-all"}


def _check_downloader(prog: str, rest: list[str], vault: Path, level: int, saw_cd: bool) -> None:
    """wget/curl write files: every output path must be allowed; server-chosen names are blocked."""
    outputs: list[str] = []
    k = 0
    while k < len(rest):
        a = rest[k]
        long_opts = DOWNLOADER_OUTPUT_LONG[prog]
        if a in long_opts:
            k += 1
            outputs.append(rest[k] if k < len(rest) else "")
        elif a.startswith(long_opts) and "=" in a:
            outputs.append(a.split("=", 1)[1])
        elif prog == "curl" and a in CURL_REMOTE_NAME:
            raise BlockedError("curl 원격 파일명 저장은 대상을 판단할 수 없습니다 — 차단")
        elif re.match(r"^-[a-zA-Z]", a):  # short option cluster, possibly with attached value
            letters = a[1:]
            if prog == "curl" and ("O" in letters or "J" in letters):
                raise BlockedError("curl 원격 파일명 저장은 대상을 판단할 수 없습니다 — 차단")
            flags = DOWNLOADER_OUTPUT_SHORT[prog]
            pos = next((n for n, ch in enumerate(letters) if ch in flags), -1)
            if pos >= 0:
                value = letters[pos + 1 :]
                if not value:
                    k += 1
                    value = rest[k] if k < len(rest) else ""
                outputs.append(value)
        k += 1
    if prog == "wget" and not outputs:
        raise BlockedError(
            "wget 은 현재 디렉터리에 파일을 만듭니다 — `-O <허용 경로>|-` 필요 — 차단"
        )
    for o in outputs:
        if not o:
            raise BlockedError(f"{prog} 출력 대상이 없습니다 — 차단")
        _check_target(o, vault, level, saw_cd, prog)


def _check_targets(rest: list[str], vault: Path, level: int, saw_cd: bool, prog: str) -> None:
    targets: list[str] = []
    for a in rest:
        if a.startswith("--") and "=" in a:
            targets.append(a.split("=", 1)[1])  # --target-directory=DIR, --output=FILE, …
        elif not a.startswith("-") and not OPTION_WITH_VALUE_RE.match(a):
            targets.append(a)
    if prog in SED_LIKE:
        targets = targets[1:]  # first positional is the script
    if not targets:
        raise BlockedError(f"{prog} 대상 경로를 판단할 수 없습니다 — 차단")
    for t in targets:
        _check_target(t, vault, level, saw_cd, prog)


def tokenize(command: str) -> list[str]:
    if "\x00" in command:
        raise BlockedError("command 에 NUL 문자 — 차단")
    text = command.replace("\r\n", "\n").replace("\\\n", " ")
    text = text.replace("\n", " ; ")  # newline = command separator
    try:
        lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        lexer.commenters = ""  # `#` is judged literally (bash comment rules differ from shlex)
        return list(lexer)
    except ValueError as exc:
        raise BlockedError(f"명령을 파싱할 수 없습니다 ({exc}) — 차단") from None


# ------------------------------------------------------ ADR-0011: external-session reads
CONTENT_SEARCHERS = {
    "grep",
    "egrep",
    "fgrep",
    "rgrep",
    "zgrep",
    "rg",
    "ag",
    "ack",
    "ugrep",
    "ug",
    "pt",
    "sift",
}
GREP_RECURSIVE_RE = re.compile(r"^-[a-zA-Z]*[rR]|^--(dereference-)?recursive$|^-d$")
GREP_PATTERN_OPTS = {"-e", "--regexp", "-f", "--file"}
NAME_LISTERS = {"find", "fd", "fdfind", "tree", "du", "locate"}
GIT_PATCH_SUBS = {"show", "diff", "log", "whatchanged", "format-patch", "stash", "reflog"}
GIT_NO_PATCH_FLAGS = {
    "--stat",
    "--name-only",
    "--name-status",
    "--shortstat",
    "--numstat",
    "--summary",
    "--dirstat",
    "-s",
    "--no-patch",
    "--oneline",
    "--raw",
}
GIT_PATCH_FLAGS = {"-p", "-u", "--patch", "--cc", "--full-diff", "--pickaxe-all"}
NFC = "NFC"


def _nfc(text: str) -> str:
    import unicodedata

    return unicodedata.normalize(NFC, text)


def _mentions_ip(token: str) -> bool:
    return IP_DIR.casefold() in _nfc(token).casefold()


def _bases(ev: dict, vault: Path, cmds: list[tuple[str, list[str]]]) -> list[Path]:
    """Directories a relative path resolves against: event cwd, Vault, literal `cd` targets."""
    bases: list[Path] = []
    cwd = ev.get("cwd")
    if isinstance(cwd, str) and cwd and Path(cwd).is_absolute():
        bases.append(resolve_any(cwd, vault))
    bases.append(vault)
    for _op, cmd in cmds:
        if cmd and Path(cmd[0]).name in ("cd", "pushd"):
            for a in cmd[1:]:
                if not a.startswith("-"):
                    for b in list(bases):
                        bases.append(resolve_any(a, b))
                    break
    out: list[Path] = []
    for b in bases:
        if b not in out:
            out.append(b)
    return out


MAX_PATH_TOKEN = 4096  # longer than PATH_MAX: cannot name a file
BRACE_RE = re.compile(r"\{([^{}]*)\}")


def _brace_expand(token: str) -> list[str]:
    """Bash brace expansion for `{a,b}` groups (nested OK). `{a..b}` ranges cannot be judged."""
    m = BRACE_RE.search(token)
    if m is None:
        return [token]
    inner = m.group(1)
    if ".." in inner:
        raise BlockedError(f"중괄호 범위 확장은 판단할 수 없습니다 (외부 LLM 세션) → {token}")
    if "," not in inner:
        # bash leaves `{print}` alone — but the braces may enclose a nested group: recurse on them
        rest = token[: m.start()] + "\x00" + token[m.end() :]
        return [r.replace("\x00", "{" + inner + "}") for r in _brace_expand(rest)]
    out: list[str] = []
    for alt in inner.split(","):
        out.extend(_brace_expand(token[: m.start()] + alt + token[m.end() :]))
    if len(out) > 1000:
        raise BlockedError(f"중괄호 확장이 너무 큽니다 (판단 불가) → {token}")
    return out


def _expand(token: str, bases: list[Path]) -> list[Path]:
    if len(token) > MAX_PATH_TOKEN:
        return []  # cannot be a file name on any POSIX system
    found: list[Path] = []
    for word in _brace_expand(token):
        if not GLOB_CHARS & set(word):
            found.extend(resolve_any(word, b) for b in bases)
            continue
        for b in bases:
            try:
                if Path(word).expanduser().is_absolute():
                    hits = glob.glob(  # noqa: PTH207 — shell semantics (root_dir, hidden files)
                        str(Path(word).expanduser()), recursive=True, include_hidden=True
                    )
                else:
                    hits = glob.glob(  # noqa: PTH207
                        word, root_dir=str(b), recursive=True, include_hidden=True
                    )
            except (OSError, ValueError, RecursionError) as exc:
                raise BlockedError(f"글로브를 확장할 수 없습니다 ({exc}) → {word} — 차단") from None
            found.extend(resolve_any(h, b) for h in hits)
    return found


def _check_read_tokens(cmd: list[str], vault: Path, bases: list[Path]) -> None:
    for t in cmd:
        if _mentions_ip(t):
            raise BlockedError(
                f"외부 LLM 세션에서는 40_IP 를 명령에 쓸 수 없습니다 → {t} "
                "(ADR-0011: MYELIN_LLM=local 로컬 세션에서만)"
            )
        if REDIRECT_TOKEN_RE.match(t) or SEPARATOR_RE.match(t) or t in SHELL_KEYWORDS:
            continue
        if t.startswith("-") or ASSIGNMENT_RE.match(t):
            continue
        for real in _expand(t, bases):
            check_read_target(real, vault, t)
        if ":" in t and "/" in t.split(":", 1)[1]:  # git object spec `REF:path` → judge the path
            for real in _expand(t.split(":", 1)[1], [vault]):
                check_read_target(real, vault, t)


def _positionals(rest: list[str], skip_value_opts: set[str]) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(rest):
        a = rest[i]
        if a == "--":
            out.extend(rest[i + 1 :])
            break
        if a in skip_value_opts:
            i += 2
            continue
        if not a.startswith("-"):
            out.append(a)
        i += 1
    return out


def _check_search_roots(
    roots: list[str], vault: Path, bases: list[Path], *, contents: bool
) -> None:
    if not roots:
        roots = [str(bases[0])]
    for r in roots:
        for real in _expand(r, bases):
            check_search_root(real, vault, r, contents=contents)


def _check_external_reads(
    cmds: list[tuple[str, list[str]]], vault: Path, ev: dict, saw_cd: bool
) -> None:
    bases = _bases(ev, vault, cmds)
    for _op, cmd in cmds:
        _check_read_tokens(cmd, vault, bases)
        args = [t for t in cmd if not REDIRECT_TOKEN_RE.match(t)]
        while args and (ASSIGNMENT_RE.match(args[0]) or args[0] in SHELL_KEYWORDS):
            args.pop(0)
        while args and Path(args[0]).name in UNWRAP | RUNNERS:
            args.pop(0)
        if not args:
            continue
        prog = Path(args[0]).name
        rest = args[1:]
        if prog in CONTENT_SEARCHERS:
            recursive = prog != "grep" or any(GREP_RECURSIVE_RE.match(a) for a in rest)
            pos = _positionals(
                rest, {"-e", "--regexp", "-f", "--file", "-g", "--glob", "-t", "--type"}
            )
            has_pattern_opt = any(a in GREP_PATTERN_OPTS or a.startswith("--regexp=") for a in rest)
            roots = pos if has_pattern_opt else pos[1:]
            if recursive:  # non-recursive grep on named files is judged token by token above
                _check_search_roots(roots, vault, bases, contents=True)
        elif prog in NAME_LISTERS:
            pos = [a for a in rest if not a.startswith(("-", "(", "!"))]
            # find/fd: paths come before the first expression/option; fd: pattern then paths
            if prog in ("fd", "fdfind"):
                pos = pos[1:]
            if prog == "find":
                pos = []
                for a in rest:
                    if a.startswith(("-", "(", "!")):
                        break
                    pos.append(a)
            _check_search_roots(pos, vault, bases, contents=False)
        elif prog == "ls" and any(a.startswith("-") and "R" in a for a in rest):
            _check_search_roots(
                [a for a in rest if not a.startswith("-")], vault, bases, contents=False
            )
        elif prog == "git":
            _check_git_reads(rest, vault, bases)


def _check_git_reads(rest: list[str], vault: Path, bases: list[Path]) -> None:
    i = 0
    while i < len(rest) and rest[i].startswith("-"):
        i += 2 if rest[i] in GIT_GLOBAL_WITH_VALUE else 1
    sub = rest[i] if i < len(rest) else ""
    tail = rest[i + 1 :]
    pathspecs = tail[tail.index("--") + 1 :] if "--" in tail else []
    if sub == "grep":
        if not pathspecs:
            _check_search_roots([], vault, [vault], contents=True)
        for ps in pathspecs:
            _check_search_roots([ps], vault, [vault], contents=True)
        return
    if sub not in GIT_PATCH_SUBS:
        return
    if sub == "log" and not any(a in GIT_PATCH_FLAGS or a.startswith("-U") for a in tail):
        return  # messages only
    if sub == "stash" and "show" not in tail:
        return
    if sub == "reflog" and not any(a in GIT_PATCH_FLAGS for a in tail):
        return
    if any(a in GIT_NO_PATCH_FLAGS for a in tail) and not any(a in GIT_PATCH_FLAGS for a in tail):
        return  # names/stats only
    if not ip_dir_has_files(vault) and find_confidential_note(vault, vault) is None:
        return
    if not pathspecs:
        raise BlockedError(
            f"외부 LLM 세션에서 git {sub} 의 patch 출력은 기밀을 드러낼 수 있습니다 — "
            "`-- <40_IP 밖 경로>` 로 범위를 제한하세요 (ADR-0011)"
        )
    for ps in pathspecs:
        for real in _expand(ps, [vault]):
            check_search_root(real, vault, ps, contents=True)


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
    tokens = tokenize(command)
    vault = find_vault(ev)
    level = vault_level(vault)
    cmds = split_commands(tokens)
    saw_cd = any(c and Path(c[0]).name in ("cd", "pushd", "popd") for _, c in cmds)
    if not is_local_session():
        _check_external_reads(cmds, vault, ev, saw_cd)
    for op, cmd in cmds:
        check_command(cmd, vault, level, saw_cd, op)
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
