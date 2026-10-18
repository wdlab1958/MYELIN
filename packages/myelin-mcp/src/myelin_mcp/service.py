"""VaultService — the policy layer the MCP tools call (정본 §7.3, ADR-0007).

- Every path a client passes is resolved and must stay inside the Vault root (symlinks
  resolved, `..`/absolute rejected) — fail-closed.
- Confidential notes (classification: confidential, or anything under 40_IP/) are hidden from
  search results and returned body-less by get_note unless `mcp.expose_confidential: true`.
- write_draft exists only when `mcp.write_draft: true` AND `level >= 1`; it creates new files
  in 00_Inbox/ai-drafts only, never overwrites, origin claude / status draft.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from myelin_core.index import VaultIndex, open_index
from myelin_core.render import make_note_id, render_template
from myelin_core.schema.frontmatter import Classification, NoteType
from myelin_core.vault import AI_DRAFTS, IP, TEMPLATES, Vault

REDACTED = "[confidential — body withheld by MYELIN MCP policy (mcp.expose_confidential: false)]"


class MCPError(ValueError):
    """Raised for client-facing errors (bad path, policy, bad argument)."""


@dataclass
class VaultService:
    vault: Vault
    index: VaultIndex

    @classmethod
    def open(cls, root: Path, *, refresh: bool = True) -> VaultService:
        vault = Vault.open(root)
        return cls(vault=vault, index=open_index(vault, refresh=refresh))

    # ------------------------------------------------------------------ policy helpers
    @property
    def expose_confidential(self) -> bool:
        return self.vault.config.mcp.expose_confidential

    @property
    def write_enabled(self) -> bool:
        return self.vault.config.mcp.write_draft and self.vault.config.level >= 1

    def _hidden(self, path: str, classification: str) -> bool:
        if self.expose_confidential:
            return False
        return classification == Classification.CONFIDENTIAL.value or path.startswith(IP + "/")

    def safe_rel(self, ref: str) -> str:
        """Resolve a client-supplied path to a Vault-relative posix path or raise MCPError."""
        if not ref or "\x00" in ref:
            raise MCPError("path is empty")
        p = Path(ref)
        if p.is_absolute() or ".." in p.parts or ref.startswith("~"):
            raise MCPError(f"path must be Vault-relative without '..': {ref!r}")
        real = (self.vault.root / p).resolve(strict=False)
        try:
            return real.relative_to(self.vault.root).as_posix()
        except ValueError:
            raise MCPError(f"path escapes the Vault: {ref!r}") from None

    # ------------------------------------------------------------------ tools
    def refresh(self) -> dict[str, int]:
        r = self.index.refresh()
        return {
            "added": r.added,
            "updated": r.updated,
            "removed": r.removed,
            "unchanged": r.unchanged,
            "errors": r.errors,
        }

    def search_notes(
        self,
        query: str,
        *,
        domain: str | None = None,
        status: str | None = None,
        type: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        self.index.refresh()
        try:
            hits = self.index.search(
                query,
                limit=limit,
                domain=domain,
                status=status,
                type_=type,
                exclude_confidential=not self.expose_confidential,
            )
        except ValueError as exc:
            raise MCPError(str(exc)) from None
        return [h.to_dict() for h in hits if not self._hidden(h.note.path, h.note.classification)]

    def get_note(self, ref: str) -> dict[str, Any]:
        self.index.refresh()
        note = self.index.get(ref)
        if note is None:
            # maybe a path: check the boundary before "not found" (never leak outside existence)
            rel = self.safe_rel(ref) if ("/" in ref or ref.endswith(".md")) else ref
            note = self.index.get(rel)
            if note is None:
                raise MCPError(f"note not found: {ref!r}")
        d = note.to_dict()
        if self._hidden(note.path, note.classification):
            d["body"] = REDACTED
            d["redacted"] = True
        else:
            d["body"] = self.index.body(note.path) or ""
            d["redacted"] = False
        d["backlinks"] = self.index.backlinks(Path(note.path).stem)
        return d

    def query_frontmatter(self, **filters: Any) -> list[dict[str, Any]]:
        self.index.refresh()
        limit = int(filters.pop("limit", 100))
        order = str(filters.pop("order", "created"))
        clean = {k: v for k, v in filters.items() if v is not None}
        if not self.expose_confidential:
            clean["exclude_confidential"] = True
        try:
            rows = self.index.query(limit=limit, order=order, **clean)
        except (TypeError, ValueError) as exc:
            raise MCPError(f"bad filter: {exc}") from None
        return [n.to_dict() for n in rows if not self._hidden(n.path, n.classification)]

    def list_domains(self) -> dict[str, Any]:
        counts = self.index.domains()
        cfg = self.vault.config
        declared: dict[str, dict[str, Any]] = {}
        try:
            for lp in self.vault.packs():
                for d in lp.pack.domains:
                    declared[d.id] = {
                        "name": d.name,
                        "accent": d.accent,
                        "pack": lp.name,
                        "sub_mocs": list(d.sub_mocs),
                        "note_types": [t.value for t in d.note_types],
                    }
        except Exception as exc:
            declared = {"_error": {"message": f"packs unavailable: {exc}"}}
        return {
            "level": cfg.level,
            "configured": [
                {"id": did, "role": role, "notes": counts.get(did, 0), **declared.get(did, {})}
                for did, role in cfg.domains.roles.items()
            ],
            "packs": cfg.pack_names,
            "declared_but_inactive": sorted(
                d for d in declared if d not in cfg.domains.all_ids and d != "_error"
            ),
        }

    def vault_stats(self, today: date | None = None) -> dict[str, Any]:
        self.index.refresh()
        st = self.index.stats(today or date.today())
        d = st.to_dict()
        d["kpi"] = [{"kpi": k, "value": v, "target": t} for k, v, t in st.kpi_rows()]
        return d

    def write_draft(
        self,
        title: str,
        body: str,
        *,
        type: str = "fleeting",
        domain: list[str] | None = None,
        tags: list[str] | None = None,
        source: list[str] | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        if not self.write_enabled:
            raise MCPError(
                "write_draft is disabled (myelin.yaml mcp.write_draft: false or level 0)"
            )
        try:
            ntype = NoteType(type)
        except ValueError:
            raise MCPError(f"unknown note type {type!r}") from None
        title = title.strip()
        if not title or "/" in title or title.startswith(".") or len(title) > 120:
            raise MCPError("title must be 1-120 chars, no '/' and not hidden")
        for d in domain or []:
            if d not in self.vault.config.domains.all_ids:
                raise MCPError(f"domain {d!r} is not configured in this Vault")
        now = now or datetime.now()
        template = self.vault.root / TEMPLATES / f"{ntype.value}.md"
        if not template.is_file():
            raise MCPError(
                f"template missing: {TEMPLATES}/{ntype.value}.md (run myelin init/add-domain)"
            )
        text = render_template(
            template.read_text(encoding="utf-8"),
            {
                "id": make_note_id(now, title),
                "domain": domain or [],
                "origin": "claude",
                "date": now.date(),
                "classification": "internal",
                "title": title,
                "source": (source or [""])[0],
                "description": "",
                "sub_mocs": "",
            },
        )
        # ensure tags/source land in frontmatter even when the template keeps defaults
        if tags:
            text = text.replace("tags: []", f"tags: [{', '.join(tags)}]", 1)
        if source and "source: []" in text:
            text = text.replace(
                "source: []", "source: [" + ", ".join(f'"{s}"' for s in source) + "]", 1
            )
        text = text.rstrip("\n") + "\n\n" + body.strip() + "\n"
        target_dir = self.vault.root / AI_DRAFTS
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{title}.md"
        rel = self.safe_rel(f"{AI_DRAFTS}/{title}.md")
        if not rel.startswith(AI_DRAFTS + "/"):
            raise MCPError("write_draft may only create files under 00_Inbox/ai-drafts")
        try:
            with target.open("x", encoding="utf-8") as fh:  # never overwrite
                fh.write(text)
        except FileExistsError:
            raise MCPError(f"{rel} already exists — choose another title") from None
        self.index.refresh()
        errs = dict(self.index.parse_errors())
        if rel in errs:
            target.unlink()
            self.index.refresh()
            raise MCPError(f"draft failed frontmatter validation and was removed: {errs[rel]}")
        return {"path": rel, "id": make_note_id(now, title), "status": "draft", "origin": "claude"}
