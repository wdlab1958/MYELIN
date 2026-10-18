#!/usr/bin/env bash
# MYELIN 설치 스크립트 — macOS · Linux · WSL2
#
#   curl 로 받아 바로 실행하지 말고, 내용을 확인한 뒤 실행하세요:
#     git clone https://github.com/wdlab1958/MYELIN.git && bash MYELIN/scripts/install.sh
#
# 하는 일 (사용자 홈 아래에서만):
#   1) MYELIN 소스를 $MYELIN_HOME (기본 ~/.local/share/myelin) 에 clone/갱신
#   2) uv 로 고정된 의존성 설치 (uv.lock, --frozen)
#   3) Node 18+ 가 있으면 Hub 웹 화면 빌드 (package-lock, npm ci)
#   4) ~/.local/bin 에 myelin · myelin-hub · myelin-mcp 실행 파일(shim)
#   5) (선택, 플래그를 줄 때만)
#      --vault <경로>  Obsidian Emboss 테마를 <Vault>/.obsidian/themes/ 에 복사 (기존 파일이 다르면 건너뜀)
#      --claude        Claude Code 플러그인 등록, --vault 와 함께면 MCP 서버(읽기 전용)도 등록
# 하지 않는 일: sudo, 시스템 파일 수정, Vault 노트 생성·수정, 네트워크로 노트 전송.
set -euo pipefail

REPO="${MYELIN_REPO:-https://github.com/wdlab1958/MYELIN.git}"
PREFIX="${MYELIN_HOME:-$HOME/.local/share/myelin}"
BIN="${MYELIN_BIN:-$HOME/.local/bin}"
REF="${MYELIN_REF:-main}"
WEB=1
VAULT=""
CLAUDE=0

usage() {
  cat <<USAGE
사용: install.sh [--source <git URL|경로>] [--ref <브랜치|태그|커밋>] [--prefix <설치 폴더>] [--bin <shim 폴더>] [--no-web]
                  [--vault <Vault 경로>] [--claude]
  기본: --source $REPO --ref $REF --prefix $PREFIX --bin $BIN
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --source) REPO="$2"; shift 2 ;;
    --ref) REF="$2"; shift 2 ;;
    --prefix) PREFIX="$2"; shift 2 ;;
    --bin) BIN="$2"; shift 2 ;;
    --no-web) WEB=0; shift ;;
    --vault) VAULT="$2"; shift 2 ;;
    --claude) CLAUDE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "✗ 알 수 없는 옵션: $1" >&2; usage >&2; exit 2 ;;
  esac
done

say() { printf '\033[1m▸ %s\033[0m\n' "$*"; }
fail() { printf '✗ %s\n' "$*" >&2; exit 1; }

# ── 0. 필요한 도구 ─────────────────────────────────────────────────────
command -v git >/dev/null 2>&1 || fail "git 이 필요합니다 (https://git-scm.com)"
command -v uv >/dev/null 2>&1 || fail "uv 가 필요합니다 — 설치 안내: https://docs.astral.sh/uv/getting-started/installation/"
if [ "$WEB" = 1 ]; then
  if command -v npm >/dev/null 2>&1 && command -v node >/dev/null 2>&1; then
    NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
    if [ "$NODE_MAJOR" -lt 18 ]; then
      echo "! Node $NODE_MAJOR — Hub 웹 화면에는 Node 18+ 가 필요합니다. 웹 빌드를 건너뜁니다."
      WEB=0
    fi
  else
    echo "! Node/npm 이 없습니다 — CLI·MCP는 설치하고 Hub 웹 화면 빌드는 건너뜁니다 (https://nodejs.org)."
    WEB=0
  fi
fi

# ── 1. 소스 ────────────────────────────────────────────────────────────
case "$PREFIX" in
  "$HOME"/*|/tmp/*|/var/folders/*) ;;
  *) [ -n "${MYELIN_ALLOW_PREFIX:-}" ] || fail "설치 폴더는 홈 아래여야 합니다: $PREFIX (MYELIN_ALLOW_PREFIX=1 로 무시)" ;;
esac
if [ -d "$PREFIX/.git" ]; then
  say "기존 설치 갱신: $PREFIX"
  [ -z "$(git -C "$PREFIX" status --porcelain)" ] || fail "$PREFIX 에 수정된 파일이 있습니다 — 확인 후 다시 실행하세요"
  git -C "$PREFIX" fetch --quiet --tags origin
  git -C "$PREFIX" checkout --quiet "$REF"
  git -C "$PREFIX" pull --quiet --ff-only origin "$REF" 2>/dev/null || true
elif [ -e "$PREFIX" ] && [ -n "$(ls -A "$PREFIX" 2>/dev/null)" ]; then
  fail "$PREFIX 가 비어 있지 않고 MYELIN 설치도 아닙니다"
else
  say "소스 받기: $REPO ($REF) → $PREFIX"
  mkdir -p "$(dirname "$PREFIX")"
  git clone --quiet "$REPO" "$PREFIX"
  git -C "$PREFIX" checkout --quiet "$REF"
fi
[ -f "$PREFIX/packs/myelin.core/pack.yaml" ] || fail "MYELIN 소스가 아닙니다: $PREFIX"

# ── 2. Python 의존성 (고정) ────────────────────────────────────────────
say "의존성 설치 (uv.lock 고정)"
uv sync --frozen --no-dev --quiet --project "$PREFIX"

# ── 3. Hub 웹 ──────────────────────────────────────────────────────────
if [ "$WEB" = 1 ]; then
  say "Hub 웹 화면 빌드 (package-lock 고정)"
  ( cd "$PREFIX/packages/myelin-hub/web" && npm ci --no-audit --no-fund --loglevel=error && npm run --silent build >/dev/null )
fi

# ── 4. 실행 파일 ───────────────────────────────────────────────────────
mkdir -p "$BIN"
for cmd in myelin myelin-hub myelin-mcp; do
  target="$PREFIX/.venv/bin/$cmd"
  [ -x "$target" ] || fail "$target 가 없습니다"
  printf '#!/bin/sh\nexec "%s" "$@"\n' "$target" > "$BIN/$cmd"
  chmod 0755 "$BIN/$cmd"
done

# ── 5. 선택 설정 (플래그를 줄 때만) ────────────────────────────────────
if [ -n "$VAULT" ]; then
  [ -f "$VAULT/myelin.yaml" ] || fail "$VAULT 는 MYELIN Vault가 아닙니다 (myelin.yaml 없음) — 먼저 온보딩하세요"
  theme_dir="$VAULT/.obsidian/themes/MYELIN Emboss"
  mkdir -p "$theme_dir"
  for f in manifest.json theme.css; do
    src="$PREFIX/theme/obsidian-myelin-emboss/$f"
    dst="$theme_dir/$f"
    if [ -e "$dst" ] && ! cmp -s "$src" "$dst"; then
      echo "! $dst 가 이미 있고 내용이 다릅니다 — 덮어쓰지 않습니다 (직접 고친 테마일 수 있음)"
    else
      cp "$src" "$dst"
    fi
  done
  say "Obsidian 테마 → $theme_dir (설정 › 모양 › 테마 › MYELIN Emboss)"
fi
if [ "$CLAUDE" = 1 ]; then
  if command -v claude >/dev/null 2>&1; then
    say "Claude Code 플러그인 등록"
    claude plugin marketplace add "$PREFIX" || echo "! marketplace 등록 실패 — 수동: /plugin marketplace add wdlab1958/MYELIN"
    claude plugin install myelin@myelin || echo "! 플러그인 설치 실패 — 수동: /plugin install myelin@myelin"
    if [ -n "$VAULT" ]; then
      say "MCP 서버 등록 (읽기 전용 기본)"
      claude mcp add myelin -- "$BIN/myelin-mcp" --vault "$VAULT" || echo "! MCP 등록 실패(이미 있음?) — docs/guides/mcp.md"
    fi
  else
    echo "! claude CLI가 없습니다 — Claude Code 설치 후 install.sh --claude 를 다시 실행하세요"
  fi
fi

say "완료 — $("$BIN/myelin" --version)"
case ":$PATH:" in
  *":$BIN:"*) ;;
  *) echo "! PATH에 $BIN 을 추가하세요:  export PATH=\"$BIN:\$PATH\"" ;;
esac
cat <<NEXT

다음 단계 (15분):
  1) myelin-hub --vault ~/MyVault --open      # 온보딩 마법사 — 이름 · Pack · 3+1 Domain · Level
  2) Vault 폴더에서 Claude Code:  /plugin marketplace add wdlab1958/MYELIN  →  /plugin install myelin@myelin
  3) /myelin:ingest <자료>  →  Hub Review Gate 에서 원문 확인 후 Promote
가이드: $PREFIX/docs/guides/user.md
NEXT
