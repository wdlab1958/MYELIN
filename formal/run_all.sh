#!/usr/bin/env bash
# formal/run_all.sh — WDLAB-STD-VERIFY-001 three-config gate (§6.1, §13) for every concern under formal/.
#   MC.cfg (fix ON)                 must PASS  (exit 0)
#   MC_bug*.cfg (fix OFF)           must FAIL  (exit 12 = invariant violated)
#   MC_partial.cfg (F1 on, F2 off)  must FAIL  (exit 12)  — mutation of the F2 fix
#   MC_sanity*.cfg (reachability)   must FAIL  (exit 12)
# FORMAL_NIGHTLY=1 adds the larger bounds (review-gate MC_3: 105,648 states, ~10 s).
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
  local states; states="$(grep -oE '[0-9]+ distinct states found' "$out/tlc.log" | tail -1 | sed 's/ found//')"
  if [ "$rc" = "$want" ]; then
    printf '  ok    %-26s %-12s exit %-3s expected %-3s %s\n' "$c" "$cfg" "$rc" "$want" "$states"
  else
    printf '  FAIL  %-26s %-12s exit %-3s expected %-3s -> %s\n' "$c" "$cfg" "$rc" "$want" "$out/tlc.log"; fail=1
  fi
  [ "$SAVE" = 1 ] && cp "$out/tlc.log" "$HERE/$c/evidence/$name"
}

echo "formal/run_all.sh — TLC $(java -cp "$JAR" tlc2.TLC -h 2>&1 | grep -oE 'Version [0-9.]+' | head -1) · workers=$WORKERS"
C=hub-config-stale-cache            # P1 stale decision · P2 lost Domain (F1, F2, F8)
check "$C" MC         0  tlc_fixed.log
check "$C" MC_3       0  tlc_fixed_doms3.log
check "$C" MC_bug     12 tlc_bug.log
check "$C" MC_bug_p2  12 tlc_bug_p2.log
check "$C" MC_partial 12 tlc_partial.log        # mutation: If-Match check removed
check "$C" MC_sanity  12 tlc_sanity.log

C=review-gate-promote-toctou        # P3 verified == what the human read (F4)
check "$C" MC                0  tlc_fixed.log
check "$C" MC_bug            12 tlc_bug.log
check "$C" MC_sanity         12 tlc_sanity.log
check "$C" MC_sanity_refused 12 tlc_sanity_refused.log
check "$C" MC_sanity_reread  12 tlc_sanity_reread.log
[ "${FORMAL_NIGHTLY:-0}" = 1 ] && check "$C" MC_3 0 tlc_fixed_notes3.log   # 105,648 states

C=hub-pack-save-atomicity           # P4 loadable · P5 ok==saved · P6 all-or-nothing · P7 no race (F5, F6)
check "$C" MC                 0  tlc_fixed.log
check "$C" MC_bug             12 tlc_bug.log
check "$C" MC_bug_p4          12 tlc_bug_p4.log
check "$C" MC_bug_p5          12 tlc_bug_p5.log
check "$C" MC_bug_p6          12 tlc_bug_p6.log
check "$C" MC_sanity          12 tlc_sanity.log
check "$C" MC_sanity_rejected 12 tlc_sanity_rejected.log
check "$C" MC_sanity_both     12 tlc_sanity_both.log

C=hub-onboard-atomicity             # P8 failed leaves nothing · P9 config has its pack · P10 committed (F7)
check "$C" MC              0  tlc_fixed.log
check "$C" MC_nocustom     0  tlc_fixed_nocustom.log
check "$C" MC_bug          12 tlc_bug.log
check "$C" MC_bug_p9       12 tlc_bug_p9.log
check "$C" MC_bug_p10      12 tlc_bug_p10.log
check "$C" MC_sanity       12 tlc_sanity.log
check "$C" MC_sanity_retry 12 tlc_sanity_retry.log

if [ "$fail" = 0 ]; then echo "GATE: all configs behaved as expected"; else echo "GATE: FAILED" >&2; exit 1; fi
