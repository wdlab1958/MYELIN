#!/usr/bin/env bash
# Source: WDLAB proof-skills v0.1.1 (MIT) — skills/formal-verify CI kit, vendored 2026-11-16
# formal/ci/setup_tla.sh — fetch the pinned TLA+ toolchain into $PROOF_SKILLS_TOOLS (default ~/.cache/proof-skills).
# Pinned per formal/TOOLCHAIN.lock: tla2tools v1.8.0 (TLC 2026.10.28) + CommunityModules-deps.jar. Idempotent.
set -euo pipefail
TOOLS="${PROOF_SKILLS_TOOLS:-$HOME/.cache/proof-skills}"
TLA_VERSION="${TLA_VERSION:-v1.8.0}"
mkdir -p "$TOOLS"
if [ ! -f "$TOOLS/tla2tools.jar" ]; then
  curl -fsSL "https://github.com/tlaplus/tlaplus/releases/download/$TLA_VERSION/tla2tools.jar" -o "$TOOLS/tla2tools.jar.tmp"
  mv "$TOOLS/tla2tools.jar.tmp" "$TOOLS/tla2tools.jar"
fi
if [ ! -f "$TOOLS/CommunityModules-deps.jar" ]; then
  curl -fsSL "https://github.com/tlaplus/CommunityModules/releases/latest/download/CommunityModules-deps.jar" -o "$TOOLS/CommunityModules-deps.jar.tmp"
  mv "$TOOLS/CommunityModules-deps.jar.tmp" "$TOOLS/CommunityModules-deps.jar"
fi
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for f in tlc.sh parse_tlc_trace.py check_trust.sh; do
  [ -f "$HERE/../tools/$f" ] && cp -n "$HERE/../tools/$f" "$TOOLS/$f" 2>/dev/null || true
done
java -cp "$TOOLS/tla2tools.jar" tlc2.TLC -h 2>&1 | grep -m1 -i version || true
echo "tla2tools.jar sha256: $(sha256sum "$TOOLS/tla2tools.jar" | cut -c1-16)…  (note: the v1.8.0 GitHub release is a rolling pre-release; the CI log records the actual TLC build)"
echo "TLA+ tools ready in $TOOLS"
