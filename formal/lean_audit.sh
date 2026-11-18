#!/usr/bin/env bash
# formal/lean_audit.sh — WDLAB-STD-VERIFY-001 §6.5 Lean trust audit for every formal/<concern>/lean project.
#   * source scan: no `sorry` / `admit` / user `axiom` / `native_decide` / `unsafe` / `implemented_by`
#   * `lake build` succeeds without warnings about sorry
#   * `#print axioms` of every theorem listed in <project>/AUDIT_THEOREMS uses only the standard
#     axioms (propext, Classical.choice, Quot.sound)
# Needs `lake`/`lean` on PATH (elan; toolchain pinned by each project's lean-toolchain).
# SAVE_EVIDENCE=1 copies the audit log to <concern>/evidence/lean_audit.log. Exit 0 clean, 1 problem.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
command -v lake >/dev/null || { echo "lake not found (install elan; see formal/README.md)" >&2; exit 2; }
fail=0
for proj in "$HERE"/*/lean; do
  [ -f "$proj/lakefile.toml" ] || continue
  concern="$(basename "$(dirname "$proj")")"
  log="$(mktemp)"
  {
    echo "== lean trust audit: $concern  ($(lean --version 2>/dev/null))"
    src=$(find "$proj" -name '*.lean' -not -path '*/.lake/*' -not -name '_audit.lean')
    bad=$(grep -nE '(^|[^A-Za-z_])(sorry|admit|native_decide)([^A-Za-z_]|$)|^\s*(axiom|unsafe)\s|implemented_by|@\[extern' $src | grep -vE ':[0-9]+:\s*--' || true)
    if [ -n "$bad" ]; then echo "FORBIDDEN constructs:"; echo "$bad"; fail=1; else echo "source scan: 0 sorry · 0 admit · 0 user axioms · 0 native_decide · 0 unsafe/implemented_by"; fi
    if ( cd "$proj" && lake build 2>&1 ); then echo "lake build: ok"; else echo "lake build: FAILED"; fail=1; fi
    mod=$(awk '/^\[\[lean_lib\]\]/{f=1;next} f&&/^name *=/{gsub(/.*= *"|".*/,"");print;exit}' "$proj/lakefile.toml")
    { echo "import $mod"; while read -r t; do [ -n "$t" ] && echo "#print axioms $t"; done < "$proj/AUDIT_THEOREMS"; } > "$proj/_audit.lean"
    out=$( cd "$proj" && lake env lean _audit.lean 2>&1 ); rm -f "$proj/_audit.lean"
    echo "$out"
    n=$(grep -c . "$proj/AUDIT_THEOREMS")
    seen=$(echo "$out" | grep -cE "does not depend on any axioms|depends on axioms")
    [ "$seen" = "$n" ] || { echo "axiom audit: expected $n theorems, saw $seen"; fail=1; }
    nonstd=$(echo "$out" | grep -E "depends on axioms" | sed -E 's/.*depends on axioms: \[(.*)\]/\1/' | tr ',' '\n' | sed 's/ //g' | grep -vE '^(propext|Classical\.choice|Quot\.sound)$' | grep . || true)
    if [ -n "$nonstd" ] || echo "$out" | grep -q sorryAx; then echo "NON-STANDARD axioms: $nonstd"; fail=1; else echo "axioms: standard only ($n theorems audited)"; fi
  } > "$log" 2>&1
  cat "$log"
  [ "${SAVE_EVIDENCE:-0}" = 1 ] && cp "$log" "$HERE/$concern/evidence/lean_audit.log"
  rm -f "$log"
done
if [ "$fail" = 0 ]; then echo "LEAN AUDIT: clean"; else echo "LEAN AUDIT: FAILED" >&2; exit 1; fi
