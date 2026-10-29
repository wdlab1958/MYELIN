#!/usr/bin/env bash
# formal/run_all.sh — WDLAB-STD-VERIFY-001 three-config gate (§6.1, §13) for every concern under formal/.
#   MC.cfg (fix ON)                 must PASS  (exit 0)
#   MC_bug*.cfg (fix OFF)           must FAIL  (exit 12 = invariant violated)
#   MC_partial.cfg (F1 on, F2 off)  must FAIL  (exit 12)  — documents the still-open finding F2
#   MC_sanity.cfg (reachability)    must FAIL  (exit 12)
# Honours TLC_WORKERS (default 4). SAVE_EVIDENCE=1 copies each tlc.log into <concern>/evidence/.
# Needs Java 21+ and tla2tools.jar (proof-skills: skills/tlaplus-model/scripts/setup_tla.sh),
# found via $TLA2TOOLS or $PROOF_SKILLS_TOOLS (default ~/.cache/proof-skills).
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS="${PROOF_SKILLS_TOOLS:-$HOME/.cache/proof-skills}"
JAR="${TLA2TOOLS:-$TOOLS/tla2tools.jar}"
[ -f "$JAR" ] || { echo "tla2tools.jar not found at $JAR" >&2; exit 2; }
command -v java >/dev/null || { echo "java not found" >&2; exit 2; }
WORKERS="${TLC_WORKERS:-4}"
SAVE="${SAVE_EVIDENCE:-0}"
fail=0

check() {  # check <concern> <cfg-name> <expected-exit> <evidence-file>
  local c="$1" cfg="$2" want="$3" name="$4" dir="$HERE/$1/tla" out rc
  out="$dir/.tlc-out/$cfg"; mkdir -p "$out"
  ( cd "$dir" && java -XX:+UseParallelGC -cp "$JAR" tlc2.TLC -workers "$WORKERS" -config "$cfg.cfg" \
      -metadir "$out/states" Properties.tla > "$out/tlc.log" 2>&1 )
  rc=$?
  rm -rf "$out/states"; rm -f "$dir"/Properties_TTrace_* "$dir"/Spec_TTrace_* 2>/dev/null
  local states; states="$(grep -oE '[0-9]+ distinct states' "$out/tlc.log" | head -1)"
  if [ "$rc" = "$want" ]; then
    printf '  ok    %-26s %-12s exit %-3s expected %-3s %s\n' "$c" "$cfg" "$rc" "$want" "$states"
  else
    printf '  FAIL  %-26s %-12s exit %-3s expected %-3s -> %s\n' "$c" "$cfg" "$rc" "$want" "$out/tlc.log"; fail=1
  fi
  [ "$SAVE" = 1 ] && cp "$out/tlc.log" "$HERE/$c/evidence/$name"
}

echo "formal/run_all.sh — TLC $(java -cp "$JAR" tlc2.TLC -h 2>&1 | grep -oE 'Version [0-9.]+' | head -1) · workers=$WORKERS"
C=hub-config-stale-cache
check "$C" MC         0  tlc_fixed.log
check "$C" MC_3       0  tlc_fixed_doms3.log
check "$C" MC_bug     12 tlc_bug.log
check "$C" MC_bug_p2  12 tlc_bug_p2.log
check "$C" MC_partial 12 tlc_partial.log
check "$C" MC_sanity  12 tlc_sanity.log

if [ "$fail" = 0 ]; then echo "GATE: all configs behaved as expected"; else echo "GATE: FAILED" >&2; exit 1; fi
