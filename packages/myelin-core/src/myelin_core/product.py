"""Product display name — one constant (WBS 1.6: the name is provisional, the trademark check
is not done).

Only the *display* name is configurable. Identifiers are a protocol and stay `myelin`: the
package and module names, the `myelin` / `myelin-hub` / `myelin-mcp` commands, `myelin.yaml`,
the `.myelin/` runtime directory, `MYELIN_*` environment variables, the `X-Myelin-Intent`
header, `[myelin:<skill>]` commit prefixes, the `myelin.core` pack and the `/myelin:*` plugin
namespace. Renaming those is a breaking change for every existing Vault and needs a migration.

`MYELIN_PRODUCT_NAME` overrides the display name at start-up (CLI help, Hub title and banner,
MCP server instructions, assistant name). Text written *into* a Vault (CLAUDE.md, myelin.yaml
header comments, the welcome note) keeps the built-in name so that generated files stay
reproducible.
"""

from __future__ import annotations

import os
import re

DEFAULT_PRODUCT_NAME = "MYELIN"
PRODUCT_NAME_ENV = "MYELIN_PRODUCT_NAME"
PRODUCT_TAGLINE = "Personal Knowledge OS"
_SAFE = re.compile(r"^[^\x00-\x1f\x7f<>\"'`\\]{1,40}$")


def _resolve(raw: str | None) -> str:
    name = (raw or "").strip()
    return name if name and _SAFE.match(name) else DEFAULT_PRODUCT_NAME


PRODUCT_NAME = _resolve(os.environ.get(PRODUCT_NAME_ENV))
