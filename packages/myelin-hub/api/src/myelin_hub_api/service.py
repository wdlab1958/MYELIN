"""HubService — the write-side policy layer behind the Hub API (정본 §4.2 Review Gate, ADR-0009).

Every Vault mutation goes through one of five explicit user actions and ends in a git commit:
promote · reject · apply_patch · reject_patch · save_settings (+ onboarding init, save_pack).
Reads never write (audited by tests).
"""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import shutil
import subprocess
import sys
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Concatenate

from pydantic import ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedSeq

from myelin_core.commons import (
    CommonsError,
    DeidRule,
    candidates,
    commons_notes,
    commons_reuse,
    manual_next_step,
    owner_hash,
    publish_note,
)
from myelin_core.config import ConfigError, MyelinConfig, dump_config
from myelin_core.doctor import run_doctor
from myelin_core.index import VaultIndex, open_index
from myelin_core.levels import skill_table
from myelin_core.metrics import (
    events,
    onboarding_minutes,
    org_metrics,
    payload_is_anonymous,
    record_event,
)
from myelin_core.note import NoteParseError, dump_note, read_note
from myelin_core.packs.loader import PackError, discover_packs, load_pack
from myelin_core.patches import (
    APPLIED_DIR,
    REJECTED_DIR,
    PatchError,
    apply_plan,
    check_patch_name,
    history_dest,
    list_patches,
    plan_patch,
    reject_patch,
)
from myelin_core.render import make_note_id, render_claude_md
from myelin_core.scaffold import ScaffoldError, VaultExistsError, init_vault, install_git_hook
from myelin_core.schema.frontmatter import Origin, Status
from myelin_core.schema.pack import Pack
from myelin_core.stats import kpi_status
from myelin_core.vault import (
    AI_DRAFTS,
    ARCHIVE,
    DOMAINS,
    PATCHES,
    RUNTIME,
    Vault,
    default_pack_roots,
)

GUARD_LOG = f"{RUNTIME}/guard.log"
WELCOME_TITLE = "MYELIN 시작하기"
PERSONAL_PACK = "me.my-domains"  # personal pack written by the onboarding wizard's custom domains


def _explain_validation(exc: ValidationError) -> str:
    """Pydantic errors → one readable line per field (no type codes, no doc URLs)."""
    parts = []
    for e in exc.errors(include_url=False):
        loc = ".".join(str(x) for x in e["loc"]) or "settings"
        msg = str(e["msg"]).removeprefix("Value error, ")
        parts.append(f"{loc}: {msg}" if loc != "settings" else msg)
    return "; ".join(parts)


class HubError(ValueError):
    def __init__(self, message: str, status: int = 400) -> None:
        self.status = status
        super().__init__(message)


def _serialised[**P, R](
    fn: Callable[Concatenate[HubService, P], R],
) -> Callable[Concatenate[HubService, P], R]:
    """Vault writes run one at a time: a double click or two tabs must not race each other
    (one would hit a half-moved file or git's index.lock and surface as a 500)."""

    def wrapper(self: HubService, /, *args: P.args, **kwargs: P.kwargs) -> R:
        with self._write_lock:
            return fn(self, *args, **kwargs)

    wrapper.__name__, wrapper.__doc__ = fn.__name__, fn.__doc__
    return wrapper


@dataclass
class HubService:
    root: Path
    vault: Vault | None = None
    index: VaultIndex | None = None
    config_error: str | None = None  # myelin.yaml present but unreadable (reported, not fatal)
    _write_lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    # ------------------------------------------------------------------ lifecycle
    @classmethod
    def open(cls, root: Path) -> HubService:
        svc = cls(root=Path(root).resolve())
        svc.reload()
        return svc

    def reload(self) -> None:
        self.config_error = None
        if not Vault.is_vault(self.root):
            self.vault = None
            self._drop_index()
            return
        try:
            vault = Vault.open(self.root)
        except ConfigError as exc:
            # A corrupt myelin.yaml must not take the Hub down: report it and stay not-ready.
            self.config_error = str(exc)
            self.vault = None
            self._drop_index()
            return
        self.vault = vault
        if self.index is None:
            self.index = open_index(vault)
        else:
            # Keep the shared connection: readers on other threads may be mid-query.
            self.index.vault = vault
            self.index.refresh()

    def _drop_index(self) -> None:
        if self.index is not None:
            self.index.close()
            self.index = None

    @property
    def ready(self) -> bool:
        return self.vault is not None

    def _not_ready(self) -> HubError:
        if self.config_error:
            return HubError(f"Vault config is invalid — fix it first: {self.config_error}", 409)
        return HubError("Vault not initialised — complete onboarding first", 409)

    def _v(self) -> Vault:
        if self.vault is None:
            raise self._not_ready()
        return self.vault

    def _idx(self) -> VaultIndex:
        if self.index is None:
            raise self._not_ready()
        self.index.refresh()
        return self.index

    @contextmanager
    def _mutation(self, rels: list[str]) -> Iterator[None]:
        """All-or-nothing Vault write: snapshot `rels`, run the body, and on any failure (git
        index.lock, missing identity, read-only disk, race) restore the files and unstage them.

        ADR-0009: every mutation is exactly one commit — the Vault is left either untouched or
        fully committed, never half-moved.
        """
        v = self._v()
        rels = [*rels, ".gitignore"]  # ensure_git() may create it on the first write
        with self._write_lock:
            snapshot: dict[str, bytes | None] = {}
            for rel in rels:
                p = v.root / rel
                snapshot[rel] = p.read_bytes() if p.is_file() else None
            try:
                yield
            except BaseException:
                for rel, data in snapshot.items():
                    p = v.root / rel
                    try:
                        if data is None:
                            if p.is_file():
                                p.unlink()
                        else:
                            p.parent.mkdir(parents=True, exist_ok=True)
                            p.write_bytes(data)
                    except OSError:
                        pass  # best effort (e.g. read-only disk — then nothing was written)
                if (v.root / ".git").exists():
                    for rel in rels:
                        subprocess.run(
                            ["git", "reset", "-q", "--", rel], cwd=v.root, capture_output=True
                        )
                raise

    def _rel(self, ref: str) -> str:
        """Vault-relative posix path for a client ref (relative) or an internal absolute path."""
        v = self._v()
        p = Path(ref)
        if not ref or ".." in p.parts or "\x00" in ref:
            raise HubError(f"bad path {ref!r}", 400)
        real = p.resolve(strict=False) if p.is_absolute() else (v.root / p).resolve(strict=False)
        try:
            return real.relative_to(v.root).as_posix()
        except ValueError:
            raise HubError(f"path escapes the Vault: {ref!r}", 400) from None

    # ------------------------------------------------------------------ git
    def _git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        v = self._v()
        # the Vault pre-commit device (ADR-0011 §5) invokes this interpreter's CLI
        env = {**os.environ, "MYELIN_BIN": f"{sys.executable} -m myelin_cli"}
        proc = subprocess.run(["git", *args], cwd=v.root, capture_output=True, text=True, env=env)
        if check and proc.returncode != 0:
            raise HubError(f"git {' '.join(args)} failed: {proc.stderr.strip()}", 500)
        return proc

    def ensure_git(self) -> None:
        """Make the Vault a git repo (first write) and keep runtime files out of commits."""
        v = self._v()
        gi = v.root / ".gitignore"
        existing = gi.read_text(encoding="utf-8") if gi.exists() else ""
        if ".myelin/" not in existing.splitlines():
            gi.write_text(
                existing.rstrip("\n") + ("\n" if existing else "") + "# MYELIN runtime\n.myelin/\n",
                encoding="utf-8",
            )
        if not (v.root / ".git").exists():
            subprocess.run(["git", "init", "-q", "-b", "main"], cwd=v.root, check=True)
            for k, val in (("user.name", "MYELIN Hub"), ("user.email", "hub@myelin.local")):
                if (
                    subprocess.run(
                        ["git", "config", "--get", k], cwd=v.root, capture_output=True
                    ).returncode
                    != 0
                ):
                    subprocess.run(["git", "config", k, val], cwd=v.root, check=True)
            try:
                install_git_hook(v.root)  # Claude Code 밖의 커밋도 같은 정책을 거친다
            except ScaffoldError as exc:
                raise HubError(f"pre-commit hook not installed: {exc}", 500) from None
            self._git("add", "-A")
            self._git("commit", "-q", "-m", "[myelin:init] vault created", "--allow-empty")

    def _commit(self, paths: list[str], message: str) -> str:
        self.ensure_git()
        self._stage([*paths, ".gitignore"])
        self._git("commit", "-q", "-m", message, "--allow-empty")
        return self._git("rev-parse", "HEAD").stdout.strip()

    def _stage(self, paths: list[str]) -> None:
        """Stage exactly the touched paths: adds, modifications and deletions of tracked files.

        An untracked file that was deleted (e.g. a draft never committed) is simply skipped.
        """
        v = self._v()
        for rel in paths:
            if (v.root / rel).exists():
                self._git("add", "--", rel)
            elif self._git("ls-files", "--error-unmatch", "--", rel, check=False).returncode == 0:
                self._git("rm", "-q", "--cached", "--", rel)

    def git_log(self, limit: int = 20) -> list[dict[str, str]]:
        v = self._v()
        if not (v.root / ".git").exists():
            return []
        proc = self._git(
            "log", f"-{limit}", "--pretty=format:%H%x1f%ad%x1f%s", "--date=iso-strict", check=False
        )
        out = []
        for line in proc.stdout.splitlines():
            if "\x1f" in line:
                h, d, s = line.split("\x1f", 2)
                out.append({"hash": h, "date": d, "subject": s})
        return out

    def git_status(self) -> dict[str, Any]:
        v = self._v()
        if not (v.root / ".git").exists():
            return {"repo": False, "clean": True, "changes": []}
        # --no-optional-locks: a read must never take .git/index.lock (it would race a concurrent
        # promote/save commit into a spurious "index.lock exists" failure).
        proc = self._git("--no-optional-locks", "status", "--porcelain", check=False)
        changes = [ln for ln in proc.stdout.splitlines() if ln.strip()]
        return {"repo": True, "clean": not changes, "changes": changes}

    # ------------------------------------------------------------------ reads
    def summary(self) -> dict[str, Any]:
        if self.vault is None:
            return {"ready": False, "error": self.config_error, "root": str(self.root)}
        cfg = self.vault.config
        return {
            "ready": True,
            "root": str(self.vault.root),
            "owner": cfg.owner.model_dump(),
            "level": cfg.level,
            "level_name": cfg.level_name,
            "domains": cfg.domains.roles,
            "packs": cfg.pack_names,
            "mcp": cfg.mcp.model_dump(),
            "skills": skill_table(cfg.level),
            "git": self.git_status(),
            "commons": self._commons_status(),
        }

    def _commons_status(self) -> dict[str, Any]:
        """Whether 'Commons 제안' can work right now — shown in the Hub before the user clicks."""
        cfg = self._v().config.commons
        try:
            self._commons_path()
            error: str | None = None
        except HubError as exc:
            error = str(exc)
        published_count = cited_total = 0
        if error is None:
            published_count = len(self._published_ids())
            cited_total = sum(self._commons_cited().values())
        return {
            "configured": error is None,
            "error": error,
            "local": cfg.local,
            "enabled": cfg.enabled,
            "remote": cfg.remote,
            "metrics_opt_in": cfg.metrics_opt_in,
            "published_count": published_count,
            "cited_total": cited_total,
        }

    def _commons_cited(self) -> dict[str, int]:
        """original note id → citations of its Commons copy by others (ADR-0012); {} w/o clone."""
        try:
            clone = self._commons_path()
        except HubError:
            return {}
        try:
            return commons_reuse(clone, exclude_owner=owner_hash(self._v()))
        except (OSError, CommonsError):
            return {}

    def _published_ids(self) -> set[str]:
        try:
            clone = self._commons_path()
        except HubError:
            return set()
        try:
            return {cn.published_from for cn in commons_notes(clone)}
        except OSError:
            return set()

    def _with_reuse(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Attach inbound / output_uses / commons_cited / strength to note rows (ADR-0012)."""
        if not rows:
            return rows
        reuse = self._idx().reuse(self._commons_cited())
        for d in rows:
            r = reuse.get(d["path"])
            d.update(
                r.to_dict()
                if r is not None
                else {"inbound": 0, "output_uses": 0, "commons_cited": 0, "strength": 0}
            )
        return rows

    def stats(self, today: date | None = None) -> dict[str, Any]:
        st = self._idx().stats(today or date.today(), commons_cited=self._commons_cited())
        d = st.to_dict()
        d["kpi"] = [
            {"kpi": k, "value": v, "target": t, "status": kpi_status(k, getattr(st, k))}
            for k, v, t in st.kpi_rows()
        ]
        d["guard_blocks_7d"] = len(self.guard_events(days=7))
        d["review_queue"] = len(self.review_queue()["drafts"]) + len(self.review_queue()["patches"])
        return d

    def doctor(self) -> dict[str, Any]:
        return run_doctor(self._v()).to_dict()

    def domains(self) -> list[dict[str, Any]]:
        v = self._v()
        idx = self._idx()
        counts = idx.domains()
        verified = {d: len(idx.query(domain=d, status="verified", limit=1000)) for d in counts}
        declared: dict[str, dict[str, Any]] = {}
        try:
            for lp in v.packs():
                for d in lp.pack.domains:
                    declared[d.id] = {
                        "name": d.name,
                        "accent": d.accent,
                        "description": d.description,
                        "pack": lp.name,
                        "sub_mocs": list(d.sub_mocs),
                        "compose_targets": list(d.compose_targets),
                    }
        except PackError as exc:
            declared = {"_error": {"message": str(exc)}}
        out = []
        for did, role in v.config.domains.roles.items():
            moc = f"{DOMAINS}/{did}/_MOC.md"
            info = declared.get(did, {})
            subs = []
            for name in info.get("sub_mocs", []):
                rel = f"{DOMAINS}/{did}/{did} - {name}.md"
                subs.append(
                    {"name": name, "path": rel, "note": rel if (v.root / rel).exists() else None}
                )
            out.append(
                {
                    "id": did,
                    "role": role,
                    "notes": counts.get(did, 0),
                    "verified": verified.get(did, 0),
                    "moc": moc if (v.root / moc).exists() else None,
                    "sub_moc_notes": subs,
                    **info,
                }
            )
        return out

    def notes(self, **filters: Any) -> list[dict[str, Any]]:
        limit = int(filters.pop("limit", 200))
        clean = {k: v for k, v in filters.items() if v is not None}
        try:
            rows = [n.to_dict() for n in self._idx().query(limit=limit, **clean)]
        except (TypeError, ValueError) as exc:
            raise HubError(f"bad filter: {exc}") from None
        return self._with_reuse(rows)

    def search(self, q: str, limit: int = 20) -> list[dict[str, Any]]:
        try:
            rows = [h.to_dict() for h in self._idx().search(q, limit=limit)]
        except ValueError as exc:
            raise HubError(str(exc)) from None
        return self._with_reuse(rows)

    def note(self, ref: str) -> dict[str, Any]:
        idx = self._idx()
        n = idx.get(ref) or idx.get(self._rel(ref))
        if n is None:
            raise HubError(f"note not found: {ref}", 404)
        d = self._with_reuse([n.to_dict()])[0]
        d["body"] = idx.body(n.path) or ""
        d["backlinks"] = idx.backlinks(Path(n.path).stem)
        return d

    def review_queue(self) -> dict[str, list[dict[str, Any]]]:
        v = self._v()
        idx = self._idx()
        drafts = [
            n.to_dict() | {"doctor_ok": True}
            for n in idx.query(limit=500, order="created")
            if n.path.startswith(AI_DRAFTS + "/")
        ]
        errors = dict(idx.parse_errors())
        for rel, msg in errors.items():
            if rel.startswith(AI_DRAFTS + "/"):
                drafts.append(
                    {
                        "path": rel,
                        "title": Path(rel).stem,
                        "status": "draft",
                        "origin": "claude",
                        "doctor_ok": False,
                        "error": msg,
                        "domains": [],
                        "type": "?",
                        "id": "?",
                        "created": "",
                        "tags": [],
                    }
                )
        patches = [p for p in list_patches(v.root) if p.get("group") == "proposed"]
        return {"drafts": drafts, "patches": patches}

    def guard_events(self, days: int = 7) -> list[dict[str, Any]]:
        v = self._v()
        log = v.root / GUARD_LOG
        if not log.exists():
            return []
        cutoff = datetime.now().timestamp() - days * 86400
        out = []
        for line in log.read_text(encoding="utf-8").splitlines():
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if float(ev.get("ts", 0)) >= cutoff:
                out.append(ev)
        return out[-200:]

    # ------------------------------------------------------------------ writes (user actions only)
    @_serialised
    def promote(
        self, ref: str, domain: str | None = None, today: date | None = None
    ) -> dict[str, Any]:
        v = self._v()
        rel = self._rel(ref)
        if not rel.startswith(AI_DRAFTS + "/"):
            raise HubError("only notes in 00_Inbox/ai-drafts can be promoted", 400)
        src = v.root / rel
        if not src.is_file():
            raise HubError(f"draft not found: {rel}", 404)
        try:
            note = read_note(src)
        except NoteParseError as exc:
            raise HubError(
                f"draft fails frontmatter validation — fix it first: {exc}", 422
            ) from None
        fm = note.frontmatter
        target_domain = domain or (fm.domain[0] if fm.domain else None)
        if target_domain is None:
            raise HubError("draft has no domain — choose one to promote into", 422)
        if target_domain not in v.config.domains.all_ids:
            raise HubError(f"domain {target_domain!r} is not configured", 422)
        issues = fm.consistency_issues()
        issues = [i for i in issues if "reviewed" not in i]  # we set reviewed now
        if issues:
            raise HubError("draft has consistency issues: " + "; ".join(issues), 422)
        today = today or date.today()
        raw = note.raw_frontmatter
        raw["status"] = Status.VERIFIED.value
        raw["reviewed"] = today  # date object → unquoted YAML date
        if fm.origin is Origin.CLAUDE:
            raw["origin"] = Origin.MIXED.value  # human review makes it mixed (정본 origin 추적)
        if target_domain not in fm.domain:
            seq = CommentedSeq([*fm.domain, target_domain])
            seq.fa.set_flow_style()  # keep `domain: [D3, D1]` on one line like the templates
            raw["domain"] = seq
        dest_dir = v.root / DOMAINS / target_domain
        dest = dest_dir / src.name
        dest_rel = f"{DOMAINS}/{target_domain}/{src.name}"
        if dest.exists():
            raise HubError(f"{dest_rel} already exists — rename the draft first", 409)
        with self._mutation([rel, dest_rel]):
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest.write_text(dump_note(note), encoding="utf-8")
            src.unlink()
            commit = self._commit(
                [rel, dest_rel], f"[myelin:review] promote {src.stem} → {target_domain}"
            )
        if not any(e.get("event") == "first_promote" for e in events(v.root)):
            record_event(v.root, "first_promote", via="hub")
        self._idx()
        return {
            "path": self._rel(str(dest)),
            "domain": target_domain,
            "commit": commit,
            "status": "verified",
        }

    @_serialised
    def reject(self, ref: str, reason: str = "") -> dict[str, Any]:
        v = self._v()
        rel = self._rel(ref)
        if not rel.startswith(AI_DRAFTS + "/"):
            raise HubError("only notes in 00_Inbox/ai-drafts can be rejected", 400)
        src = v.root / rel
        if not src.is_file():
            raise HubError(f"draft not found: {rel}", 404)
        dest_dir = v.root / ARCHIVE / "rejected"
        dest = dest_dir / src.name
        if dest.exists():
            dest = dest_dir / f"{src.stem} ({datetime.now():%Y%m%d-%H%M%S}).md"
        dest_rel = f"{ARCHIVE}/rejected/{dest.name}"
        try:
            note = read_note(src)
            note.raw_frontmatter["status"] = Status.DEPRECATED.value
            payload = dump_note(note).encode("utf-8")
        except NoteParseError:
            payload = src.read_bytes()  # unparseable (even binary) drafts are archived verbatim
        msg = f"[myelin:review] reject {src.stem}" + (f" — {reason[:80]}" if reason else "")
        with self._mutation([rel, dest_rel]):
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(payload)
            src.unlink()
            commit = self._commit([rel, dest_rel], msg)
        self._idx()
        return {"path": dest_rel, "commit": commit, "status": "deprecated"}

    def patch_preview(self, name: str) -> dict[str, Any]:
        """Dry-run plan: diff, fail-closed issues and the digest the Apply call must echo back."""
        v = self._v()
        try:
            return plan_patch(v.root, name).to_dict()
        except PatchError as exc:
            raise HubError(str(exc), 404 if "not found" in str(exc) else 422) from None

    @_serialised
    def apply_patch(self, name: str, digest: str | None = None) -> dict[str, Any]:
        v = self._v()
        try:
            plan = plan_patch(v.root, name)
        except PatchError as exc:
            raise HubError(str(exc), 404 if "not found" in str(exc) else 422) from None
        if not plan.ok:
            raise HubError("patch cannot be applied: " + "; ".join(plan.issues), 422)
        if digest is not None and not hmac.compare_digest(plan.digest, digest):
            raise HubError(
                "화면의 patch 와 파일이 다릅니다 — 새로고침 후 다시 확인하세요 (digest mismatch)",
                409,
            )
        history = history_dest(v.root, APPLIED_DIR, name).relative_to(v.root).as_posix()
        with self._mutation([plan.target, f"{PATCHES}/{name}", history]):
            touched = apply_plan(v.root, plan)
            commit = self._commit(
                touched, f"[myelin:{plan.patch.skill}] apply patch {name} → {plan.target}"
            )
        self._idx()
        return {"target": plan.target, "commit": commit, "status": "applied", "digest": plan.digest}

    @_serialised
    def reject_patch(self, name: str) -> dict[str, Any]:
        v = self._v()
        try:
            check_patch_name(name)
        except PatchError as exc:
            raise HubError(str(exc), 422) from None
        history = history_dest(v.root, REJECTED_DIR, name).relative_to(v.root).as_posix()
        with self._mutation([f"{PATCHES}/{name}", history]):
            try:
                touched = reject_patch(v.root, name)
            except PatchError as exc:
                raise HubError(str(exc), 404 if "not found" in str(exc) else 422) from None
            commit = self._commit(touched, f"[myelin:review] reject patch {name}")
        return {"commit": commit, "status": "rejected"}

    def patches(self) -> list[dict[str, Any]]:
        """Proposed + applied + rejected (history) for the Hub patch list."""
        return list_patches(self._v().root)

    def settings(self) -> dict[str, Any]:
        v = self._v()
        return v.config.model_dump(mode="json")

    @_serialised
    def save_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        v = self._v()
        try:
            cfg = MyelinConfig.model_validate(data)
        except ValidationError as exc:
            raise HubError("설정이 유효하지 않다: " + _explain_validation(exc), 422) from None
        except ValueError as exc:
            raise HubError(f"설정이 유효하지 않다: {exc}", 422) from None
        with self._mutation(["myelin.yaml", "CLAUDE.md"]):
            (v.root / "myelin.yaml").write_text(dump_config(cfg), encoding="utf-8")
            touched = ["myelin.yaml"]
            claude = v.root / "CLAUDE.md"
            try:
                packs = Vault(v.root, cfg).packs()
                prev = claude.read_text(encoding="utf-8") if claude.exists() else None
                claude.write_text(
                    render_claude_md(cfg, packs, datetime.now(), prev), encoding="utf-8"
                )
                touched.append("CLAUDE.md")
            except PackError:
                pass
            commit = self._commit(touched, "[myelin:settings] update myelin.yaml")
        self.reload()
        return {"commit": commit, "settings": cfg.model_dump(mode="json")}

    # ------------------------------------------------------------------ packs
    def pack_roots(self) -> list[Path]:
        return default_pack_roots(self.root)

    def _registry(self) -> dict[str, Any]:
        try:
            return discover_packs(self.pack_roots(), strict=False)
        except PackError as exc:  # e.g. the same pack in <Vault>/packs and the registry
            raise HubError(f"pack registry is inconsistent: {exc}", 422) from None

    def packs(self) -> list[dict[str, Any]]:
        reg = self._registry()
        active = set(self.vault.config.pack_names) if self.vault else set()
        out = []
        for name, lp in sorted(reg.items()):
            editable = lp.root.is_relative_to(self.root / "packs")
            out.append(
                {
                    "name": name,
                    "version": lp.pack.version,
                    "kind": lp.pack.kind.value,
                    "maintainer": lp.pack.maintainer,
                    "description": lp.pack.description,
                    "active": name in active,
                    "editable": editable,
                    "root": str(lp.root),
                    "domains": [
                        {
                            "id": d.id,
                            "name": d.name,
                            "accent": d.accent,
                            "sub_mocs": list(d.sub_mocs),
                        }
                        for d in lp.pack.domains
                    ],
                }
            )
        return out

    def pack_source(self, name: str) -> dict[str, Any]:
        reg = self._registry()
        if name not in reg:
            raise HubError(f"pack not found: {name}", 404)
        lp = reg[name]
        return {
            "name": name,
            "editable": lp.root.is_relative_to(self.root / "packs"),
            "pack_yaml": (lp.root / "pack.yaml").read_text(encoding="utf-8"),
        }

    def validate_pack_yaml(self, text: str) -> dict[str, Any]:
        try:
            data = YAML(typ="safe").load(io.StringIO(text))
            pack = Pack.model_validate(data)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "pack": pack.pack, "domains": pack.domain_ids}

    def save_pack(self, name: str, text: str, copy_from: str | None = None) -> dict[str, Any]:
        """Personal packs only: written to <Vault>/packs/<name>/pack.yaml and loader-validated.

        `copy_from` names a registry pack whose sidecar files (taxonomy.yaml, interviews.yaml,
        templates/ …) are copied next to the new pack.yaml — the Hub's "개인 Pack 으로 복사" — so a
        YAML that references them loads. Existing files in the target are never overwritten.
        """
        check = self.validate_pack_yaml(text)
        if not check["ok"]:
            raise HubError(check["error"], 422)
        if check["pack"] != name:
            raise HubError(f"pack name in YAML ({check['pack']}) must equal {name}", 422)
        if not name.startswith("me.") or "/" in name or "\\" in name or ".." in name:
            raise HubError(
                "only personal packs (me.*) are editable in the Hub; "
                "org/reference packs come from the registry",
                403,
            )
        pdir = self.root / "packs" / name
        pdir.mkdir(parents=True, exist_ok=True)
        if copy_from:
            self._copy_pack_sidecars(copy_from, pdir)
        tmp = pdir / "pack.yaml.tmp"
        tmp.write_text(text, encoding="utf-8")
        final = pdir / "pack.yaml"
        backup = final.read_text(encoding="utf-8") if final.exists() else None
        shutil.move(tmp, final)
        try:
            load_pack(pdir)
        except PackError as exc:
            if backup is None:
                final.unlink()
            else:
                final.write_text(backup, encoding="utf-8")
            raise HubError(f"pack rejected by loader: {exc}", 422) from None
        commit = (
            self._commit([f"packs/{name}"], f"[myelin:packs] save {name}")  # yaml + sidecars
            if self.vault
            else ""
        )
        return {"name": name, "commit": commit}

    def _copy_pack_sidecars(self, source: str, dest: Path) -> None:
        reg = discover_packs(self.pack_roots(), strict=False)
        if source not in reg:
            raise HubError(f"copy_from pack not found: {source}", 404)
        src_root = reg[source].root.resolve()
        for f in sorted(src_root.rglob("*")):
            if f.is_symlink() or not f.is_file() or f.name == "pack.yaml":
                continue
            rel = f.relative_to(src_root)
            target = dest / rel
            if target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(f, target)

    # ------------------------------------------------------------------ onboarding
    @_serialised
    def onboard(self, data: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
        if self.vault is not None or Vault.is_vault(self.root):
            # also a *corrupt* myelin.yaml: onboarding never overwrites an existing Vault
            why = f" (myelin.yaml unreadable: {self.config_error})" if self.config_error else ""
            raise HubError("Vault already initialised" + why, 409)
        now = now or datetime.now()
        custom = list(data.get("custom_domains") or [])
        packs_wanted = list(data.get("packs", []))
        personal = self.root / "packs" / PERSONAL_PACK
        created_personal = bool(custom) and not personal.exists()
        if custom:
            self._write_personal_pack(custom)
            packs_wanted.append(PERSONAL_PACK)
        try:
            return self._onboard(data, packs_wanted, now)
        except BaseException:
            if created_personal:  # no half-initialised directory left behind
                shutil.rmtree(personal, ignore_errors=True)
                if personal.parent.is_dir() and not any(personal.parent.iterdir()):
                    personal.parent.rmdir()
            raise

    def _onboard(
        self, data: dict[str, Any], packs_wanted: list[str], now: datetime
    ) -> dict[str, Any]:
        try:
            cfg = MyelinConfig.model_validate(
                {
                    "owner": {
                        "name": data.get("name", ""),
                        "team": data.get("team", ""),
                        "email": data.get("email", ""),
                    },
                    "language": data.get("language", "ko"),
                    "packs": list(dict.fromkeys(["myelin.core", *packs_wanted])),
                    "domains": {
                        k: data.get(k) for k in ("primary", "research", "growth") if data.get(k)
                    },
                    "level": int(data.get("level", 1)),
                }
            )
        except ValueError as exc:
            raise HubError(f"invalid onboarding data: {exc}", 422) from None
        try:
            plan = init_vault(self.root, cfg, now, pack_roots=self.pack_roots())
        except VaultExistsError as exc:
            raise HubError(str(exc), 409) from None
        except (ScaffoldError, PackError) as exc:
            raise HubError(str(exc), 422) from None
        self.reload()
        record_event(self.root, "onboard_start", via="hub")
        welcome = self._write_welcome(cfg, now)
        self.ensure_git()
        return {"root": str(self.root), "files": len(plan.files), "welcome": welcome}

    def _write_welcome(self, cfg: MyelinConfig, now: datetime) -> str:
        """First ai-draft so the first Review Gate promotion is possible on Day 1 (부록 D)."""
        v = self._v()
        primary = cfg.domains.primary
        path = v.root / AI_DRAFTS / f"{WELCOME_TITLE}.md"
        text = (
            "---\n"
            f"id: {make_note_id(now, 'welcome')}\n"
            "type: evergreen\n"
            f"domain: [{primary}]\n"
            "status: draft\n"
            "origin: claude\n"
            "confidence: high\n"
            "classification: internal\n"
            "share: false\n"
            "source: []\n"
            f"created: {now:%Y-%m-%d}\n"
            "tags: [welcome]\n"
            "---\n"
            f"# {WELCOME_TITLE}\n\n"
            "> 이 노트는 MYELIN 이 만든 첫 AI 초안입니다. Review Gate 에서 **Promote** 를 누르면 "
            f"`10_Domains/{primary}/` 로 옮겨지고 verified(myelinated) 가 됩니다 — "
            "모든 승격은 사람의 클릭으로만 일어나고 git commit 으로 기록됩니다.\n\n"
            "## 매일 하는 일\n"
            "1. 메모는 `00_Inbox/` 에. 7일 안에 `/distill`.\n"
            "2. 외부 자료는 `/ingest` → literature 초안.\n"
            "3. 주 1회 `/review` 로 지표와 doctor 결과를 본다.\n\n"
            "## 연결\n"
            "- 상위: [[_MOC]]\n"
        )
        path.write_text(text, encoding="utf-8")
        return self._rel(str(path))

    # ------------------------------------------------------------------ commons (ADR-0010)
    def _commons_path(self) -> Path:
        v = self._v()
        local = v.config.commons.local
        if not local:
            raise HubError("Commons clone not configured (myelin.yaml commons.local)", 409)
        p = Path(local).expanduser()
        if not (p / ".git").exists():
            raise HubError(f"Commons clone missing at {p} — run `myelin commons init`", 409)
        return p

    def _deid_rule(self) -> DeidRule:
        v = self._v()
        files = [v.root / "90_System" / "deid.yaml"]
        local = v.config.commons.local
        if local:
            files.insert(0, Path(local).expanduser() / "deid.yaml")
        return DeidRule.load(*files)

    def commons_candidates(self) -> list[dict[str, Any]]:
        """share:true notes with their publish check (read-only). `cited` = citations of the
        already-published copy (ADR-0012), 0 for notes not yet in Commons."""
        published = self._published_ids()
        cited = self._commons_cited() if published else {}
        out = []
        for c in candidates(self._v(), self._deid_rule()):
            d = c.to_dict()
            nid = c.note.id if c.note is not None else None
            d["published"] = nid in published
            d["cited"] = cited.get(nid, 0) if nid in published else 0
            out.append(d)
        return out

    def commons_publish(
        self, ref: str, confirmed: bool, push: bool = False, pr: bool = False
    ) -> dict[str, Any]:
        """Commons 제안 all the way to a PR (정본 §9.1): commit → (push) → (gh pr create).

        push / PR are best effort: a missing `origin` is added from myelin.yaml commons.remote;
        a failed push or missing `gh` still returns 200 with `pushed: false` / `pr_url: null`
        and `next_step` telling the human the exact commands. The commit is never lost.
        """
        v = self._v()
        if not confirmed:
            raise HubError("publish requires the human confirmation flag (비식별 확인)", 422)
        rel = self._rel(ref)
        clone = self._commons_path()
        try:
            res = publish_note(
                v,
                rel,
                clone,
                confirmed=True,
                rule=self._deid_rule(),
                push=push,
                open_pr=pr,
                remote=v.config.commons.remote,
            )
        except CommonsError as exc:
            raise HubError(str(exc), 422) from None
        record_event(v.root, "publish", path_hash=hashlib.sha256(rel.encode()).hexdigest()[:8])
        return {
            "branch": res.branch,
            "commit": res.commit,
            "dest": res.dest,
            "pushed": res.pushed,
            "pr_url": res.pr_url,
            "push_error": res.push_error,
            "pr_error": res.pr_error,
            "next_step": manual_next_step(clone, res),
        }

    def metrics(self) -> dict[str, Any]:
        v = self._v()
        payload = org_metrics(v)
        return {
            "payload": payload,
            "anonymous": not payload_is_anonymous(payload, v),
            "opt_in": v.config.commons.metrics_opt_in,
            "onboarding_minutes": onboarding_minutes(v.root),
            "events": [{"event": e.get("event"), "ts": e.get("ts")} for e in events(v.root)][-20:],
        }

    # ------------------------------------------------------------------ onboarding: custom domains
    def _write_personal_pack(self, custom: list[dict[str, Any]]) -> Path:
        """Create <vault>/packs/me.my-domains/pack.yaml from the wizard's '직접 정의' domains.

        The user's own domains are a Personal Pack (정본 §5.1) — Brian's reference pack is only
        a starting point others may or may not pick. Validated with the Pack model before writing.
        """
        domains = []
        for c in custom:
            did = str(c.get("id", "")).strip().upper().replace(" ", "-")
            domains.append(
                {
                    "id": did,
                    "name": str(c.get("name", "")).strip() or did,
                    "accent": str(c.get("accent", "violet")).strip() or "violet",
                    "description": str(c.get("description", "")).strip(),
                    "sub_mocs": [str(x).strip() for x in c.get("sub_mocs", []) if str(x).strip()],
                    "note_types": ["evergreen", "lesson", "literature", "checklist", "adr"],
                    "classification_default": "internal",
                }
            )
        data = {
            "pack": PERSONAL_PACK,
            "version": "1.0.0",
            "kind": "personal",
            "maintainer": "me",
            "requires": ["myelin.core>=1.0"],
            "description": "온보딩 마법사에서 직접 정의한 내 Domain",
            "domains": domains,
        }
        try:
            Pack.model_validate(data)
        except ValueError as exc:
            raise HubError(f"invalid custom domain: {exc}", 422) from None
        pdir = self.root / "packs" / PERSONAL_PACK
        pdir.mkdir(parents=True, exist_ok=True)
        y = YAML()
        y.default_flow_style = False
        buf = io.StringIO()
        buf.write("# 온보딩 마법사가 만든 개인 Pack — Domain Packs 화면에서 편집한다\n")
        y.dump(data, buf)
        (pdir / "pack.yaml").write_text(buf.getvalue(), encoding="utf-8")
        return pdir
