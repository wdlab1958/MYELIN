"""MYELIN Fail-closed Guard (PreToolUse). Standard library only.

P0 STATUS: placeholder. Until P3 implements the allow-list logic and its test suite,
this guard BLOCKS every Write/Edit (fail-closed) so an accidentally loaded plugin can
never widen write access.
Spec: docs/spec/MYELIN_Rev2.0.md §7.2 · layout: docs/adr/0002-plugin-spec.md
"""

import sys

if __name__ == "__main__":
    print(
        "MYELIN guard: write guard not yet implemented (P3) — blocking by default (fail-closed).",
        file=sys.stderr,
    )
    sys.exit(2)
