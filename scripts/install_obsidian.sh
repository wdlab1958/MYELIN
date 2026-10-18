#!/usr/bin/env bash
# Install Obsidian on Debian/Ubuntu from the official GitHub release (.deb, amd64) and register a Vault.
#
#   scripts/install_obsidian.sh [--vault <path>] [--version v1.14.4] [--no-launch]
#
# - Downloads obsidian_<ver>_amd64.deb from github.com/obsidianmd/obsidian-releases (size is verified
#   against the release API), installs it with sudo apt-get, and — with --vault — applies the MYELIN
#   Emboss theme (via scripts/install.sh) and opens the Vault once so Obsidian registers it.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VAULT=""; VER=""; LAUNCH=1
while [[ $# -gt 0 ]]; do case "$1" in
  --vault) VAULT="$2"; shift 2;; --version) VER="$2"; shift 2;; --no-launch) LAUNCH=0; shift;;
  -h|--help) sed -n '2,8p' "$0"; exit 0;; *) echo "unknown option: $1" >&2; exit 2;; esac; done
say() { echo "▸ $*"; }
[[ "$(uname -m)" == "x86_64" ]] || { echo "✗ amd64 only (got $(uname -m)); use the AppImage/flatpak manually" >&2; exit 1; }
command -v gh >/dev/null || { echo "✗ gh CLI required for release download" >&2; exit 1; }

if command -v obsidian >/dev/null; then
  say "obsidian already installed: $(dpkg -s obsidian 2>/dev/null | awk '/^Version/{print $2}')"
else
  [[ -n "$VER" ]] || VER="$(gh api repos/obsidianmd/obsidian-releases/releases/latest --jq .tag_name)"
  ASSET="obsidian_${VER#v}_amd64.deb"
  SIZE="$(gh api "repos/obsidianmd/obsidian-releases/releases/tags/$VER" --jq ".assets[] | select(.name==\"$ASSET\") | .size")"
  [[ -n "$SIZE" ]] || { echo "✗ asset $ASSET not found in release $VER" >&2; exit 1; }
  TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
  say "downloading $ASSET ($SIZE bytes) from github.com/obsidianmd/obsidian-releases $VER"
  gh release download "$VER" --repo obsidianmd/obsidian-releases --pattern "$ASSET" --dir "$TMP"
  ACTUAL="$(stat -c %s "$TMP/$ASSET")"
  [[ "$ACTUAL" == "$SIZE" ]] || { echo "✗ size mismatch: expected $SIZE got $ACTUAL" >&2; exit 1; }
  say "installing (sudo apt-get install)"
  sudo apt-get install -y "$TMP/$ASSET" >/dev/null
  say "installed: obsidian $(dpkg -s obsidian | awk '/^Version/{print $2}')"  # never run the obsidian binary here: it opens the GUI
fi

if [[ -n "$VAULT" ]]; then
  "$REPO/scripts/install.sh" --vault "$VAULT" --no-web --no-plugin --no-mcp >/dev/null
  APP="$VAULT/.obsidian/appearance.json"
  if [[ ! -f "$APP" ]]; then
    mkdir -p "$VAULT/.obsidian"
    printf '{\n  "cssTheme": "MYELIN Emboss",\n  "theme": "moonstone",\n  "baseFontSize": 16\n}\n' > "$APP"
    say "theme preselected in $APP (light / MYELIN Emboss)"
  else
    say "$APP exists — leaving it; choose MYELIN Emboss in Settings › Appearance"
  fi
  if [[ $LAUNCH -eq 1 ]]; then
    say "opening vault in Obsidian"
    (setsid nohup obsidian "obsidian://open?path=$(python3 -c 'import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))' "$VAULT")" >/dev/null 2>&1 &)
  fi
fi
say "done"
