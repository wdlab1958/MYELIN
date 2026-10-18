"""HubService — the write-side policy layer behind the Hub API (정본 §4.2 Review Gate, ADR-0009).

Every Vault mutation goes through one of five explicit user actions and ends in a git commit:
promote · reject · apply_patch · reject_patch · save_settings (+ onboarding init, save_pack).
Reads never write (audited by tests).
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedSeq

from myelin_core.commons import CommonsError, DeidRule, candidates, publish_note
from myelin_core.config import MyelinConfig, dump_config
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
from myelin_core.patches import PatchError, read_patch
from myelin_core.render import make_note_id, render_claude_md
from myelin_core.scaffold import ScaffoldError, VaultExistsError, init_vault
from myelin_core.schema.frontmatter import Origin, Status
from myelin_core.schema.pack import Pack
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


class HubError(ValueError):
    def __init__(self, message: str, status: int = 400) -> None:
        self.status = status
        super().__init__(message)


@dataclass
class HubService:
    root: Path
    vault: Vault | None = None
    index: VaultIndex | None = None

    # ------------------------------------------------------------------ lifecycle
    @classmethod
    def open(cls, root: Path) -> HubService:
        svc = cls(root=Path(root).resolve())
        svc.reload()
        return svc

    def reload(self) -> None:
        if Vault.is_vault(self.root):
            self.vault = Vault.open(self.root)
            if self.index is not None:
                self.index.close()
            self.index = open_index(self.vault)
        else:
            self.vault = None
            self.index = None

    @property
    def ready(self) -> bool:
        return self.vault is not None

    def _v(self) -> Vault:
        if self.vault is None:
            raise HubError("Vault not initialised — complete onboarding first", 409)
        return self.vault

    def _idx(self) -> VaultIndex:
        if self.index is None:
            raise HubError("Vault not initialised — complete onboarding first", 409)
        self.index.refresh()
        return self.index

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
        proc = subprocess.run(["git", *args], cwd=v.root, capture_output=True, text=True)
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
        proc = self._git("status", "--porcelain", check=False)
        changes = [ln for ln in proc.stdout.splitlines() if ln.strip()]
        return {"repo": True, "clean": not changes, "changes": changes}

    # ------------------------------------------------------------------ reads
    def summary(self) -> dict[str, Any]:
        if self.vault is None:
            return {"ready": False, "root": str(self.root)}
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
        }

    def stats(self, today: date | None = None) -> dict[str, Any]:
        st = self._idx().stats(today or date.today())
        d = st.to_dict()
        d["kpi"] = [{"kpi": k, "value": v, "target": t} for k, v, t in st.kpi_rows()]
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
            out.append(
                {
                    "id": did,
                    "role": role,
                    "notes": counts.get(did, 0),
                    "verified": verified.get(did, 0),
                    "moc": moc if (v.root / moc).exists() else None,
                    **declared.get(did, {}),
                }
            )
        return out

    def notes(self, **filters: Any) -> list[dict[str, Any]]:
        limit = int(filters.pop("limit", 200))
        clean = {k: v for k, v in filters.items() if v is not None}
        try:
            return [n.to_dict() for n in self._idx().query(limit=limit, **clean)]
        except (TypeError, ValueError) as exc:
            raise HubError(f"bad filter: {exc}") from None

    def search(self, q: str, limit: int = 20) -> list[dict[str, Any]]:
        try:
            return [h.to_dict() for h in self._idx().search(q, limit=limit)]
        except ValueError as exc:
            raise HubError(str(exc)) from None

    def note(self, ref: str) -> dict[str, Any]:
        idx = self._idx()
        n = idx.get(ref) or idx.get(self._rel(ref))
        if n is None:
            raise HubError(f"note not found: {ref}", 404)
        d = n.to_dict()
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
        patches = []
        for p in sorted((v.root / PATCHES).glob("*.patch.md")):
            try:
                patch = read_patch(p)
                patches.append(
                    patch.model_dump(mode="json") | {"file": p.name, "sections": patch.sections}
                )
            except PatchError as exc:
                patches.append({"file": p.name, "error": str(exc), "status": "invalid"})
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
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name
        if dest.exists():
            raise HubError(f"{self._rel(str(dest))} already exists — rename the draft first", 409)
        dest.write_text(dump_note(note), encoding="utf-8")
        src.unlink()
        commit = self._commit(
            [rel, self._rel(str(dest))], f"[myelin:review] promote {src.stem} → {target_domain}"
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

    def reject(self, ref: str, reason: str = "") -> dict[str, Any]:
        v = self._v()
        rel = self._rel(ref)
        if not rel.startswith(AI_DRAFTS + "/"):
            raise HubError("only notes in 00_Inbox/ai-drafts can be rejected", 400)
        src = v.root / rel
        if not src.is_file():
            raise HubError(f"draft not found: {rel}", 404)
        dest_dir = v.root / ARCHIVE / "rejected"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name
        if dest.exists():
            dest = dest_dir / f"{src.stem} ({datetime.now():%Y%m%d-%H%M%S}).md"
        try:
            note = read_note(src)
            note.raw_frontmatter["status"] = Status.DEPRECATED.value
            text = dump_note(note)
        except NoteParseError:
            text = src.read_text(encoding="utf-8")
        dest.write_text(text, encoding="utf-8")
        src.unlink()
        msg = f"[myelin:review] reject {src.stem}" + (f" — {reason[:80]}" if reason else "")
        commit = self._commit([rel, self._rel(str(dest))], msg)
        self._idx()
        return {"path": self._rel(str(dest)), "commit": commit, "status": "deprecated"}

    def apply_patch(self, name: str) -> dict[str, Any]:
        v = self._v()
        p = v.root / PATCHES / name
        if not p.is_file() or not name.endswith(".patch.md") or "/" in name:
            raise HubError(f"patch not found: {name}", 404)
        try:
            patch = read_patch(p)
        except PatchError as exc:
            raise HubError(str(exc), 422) from None
        if patch.status in ("applied", "rejected"):
            raise HubError(f"patch already {patch.status}", 409)
        target = v.root / self._rel(patch.target)
        if not target.is_file():
            raise HubError(f"patch target missing: {patch.target}", 422)
        text = target.read_text(encoding="utf-8")
        if patch.kind == "append":
            new = text.rstrip("\n") + "\n" + patch.sections["append"].rstrip("\n") + "\n"
        elif patch.kind == "replace":
            before = patch.sections["before"]
            if text.count(before) != 1:
                raise HubError("patch `before` must occur exactly once in the target", 422)
            new = text.replace(before, patch.sections["after"], 1)
        else:
            note = read_note(target)
            for line in patch.sections["set"].splitlines():
                if ":" not in line:
                    raise HubError(f"bad frontmatter line in patch: {line!r}", 422)
                k, val = line.split(":", 1)
                note.raw_frontmatter[k.strip()] = YAML(typ="safe").load(io.StringIO(val.strip()))
            new = dump_note(note)
        target.write_text(new, encoding="utf-8")
        try:
            read_note(target)
        except NoteParseError as exc:
            target.write_text(text, encoding="utf-8")
            raise HubError(
                f"patch would break the target's frontmatter — reverted: {exc}", 422
            ) from None
        self._set_patch_status(p, "applied")
        commit = self._commit(
            [patch.target, self._rel(str(p))], f"[myelin:{patch.skill}] apply patch {name}"
        )
        self._idx()
        return {"target": patch.target, "commit": commit, "status": "applied"}

    def reject_patch(self, name: str) -> dict[str, Any]:
        v = self._v()
        p = v.root / PATCHES / name
        if not p.is_file() or "/" in name:
            raise HubError(f"patch not found: {name}", 404)
        self._set_patch_status(p, "rejected")
        commit = self._commit([self._rel(str(p))], f"[myelin:review] reject patch {name}")
        return {"commit": commit, "status": "rejected"}

    @staticmethod
    def _set_patch_status(p: Path, status: str) -> None:
        text = p.read_text(encoding="utf-8")
        new, n = re.subn(r"^status:\s*\w+\s*$", f"status: {status}", text, count=1, flags=re.M)
        if n == 0:
            new = text.replace("\n---\n", f"\nstatus: {status}\n---\n", 1)
        p.write_text(new, encoding="utf-8")

    def settings(self) -> dict[str, Any]:
        v = self._v()
        return v.config.model_dump(mode="json")

    def save_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        v = self._v()
        try:
            cfg = MyelinConfig.model_validate(data)
        except ValueError as exc:
            raise HubError(f"invalid settings: {exc}", 422) from None
        (v.root / "myelin.yaml").write_text(dump_config(cfg), encoding="utf-8")
        touched = ["myelin.yaml"]
        claude = v.root / "CLAUDE.md"
        try:
            packs = Vault(v.root, cfg).packs()
            prev = claude.read_text(encoding="utf-8") if claude.exists() else None
            claude.write_text(render_claude_md(cfg, packs, datetime.now(), prev), encoding="utf-8")
            touched.append("CLAUDE.md")
        except PackError:
            pass
        commit = self._commit(touched, "[myelin:settings] update myelin.yaml")
        self.reload()
        return {"commit": commit, "settings": cfg.model_dump(mode="json")}

    # ------------------------------------------------------------------ packs
    def pack_roots(self) -> list[Path]:
        return default_pack_roots(self.root)

    def packs(self) -> list[dict[str, Any]]:
        reg = discover_packs(self.pack_roots(), strict=False)
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
        reg = discover_packs(self.pack_roots(), strict=False)
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

    def save_pack(self, name: str, text: str) -> dict[str, Any]:
        """Personal packs only: written to <Vault>/packs/<name>/pack.yaml and loader-validated."""
        check = self.validate_pack_yaml(text)
        if not check["ok"]:
            raise HubError(check["error"], 422)
        if check["pack"] != name:
            raise HubError(f"pack name in YAML ({check['pack']}) must equal {name}", 422)
        if not name.startswith("me."):
            raise HubError(
                "only personal packs (me.*) are editable in the Hub; "
                "org/reference packs come from the registry",
                403,
            )
        pdir = self.root / "packs" / name
        pdir.mkdir(parents=True, exist_ok=True)
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
            self._commit([f"packs/{name}/pack.yaml"], f"[myelin:packs] save {name}")
            if self.vault
            else ""
        )
        return {"name": name, "commit": commit}

    # ------------------------------------------------------------------ onboarding
    def onboard(self, data: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
        if self.vault is not None:
            raise HubError("Vault already initialised", 409)
        now = now or datetime.now()
        try:
            cfg = MyelinConfig.model_validate(
                {
                    "owner": {
                        "name": data.get("name", ""),
                        "team": data.get("team", ""),
                        "email": data.get("email", ""),
                    },
                    "language": data.get("language", "ko"),
                    "packs": list(dict.fromkeys(["myelin.core", *data.get("packs", [])])),
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
        """share:true notes with their publish check (read-only)."""
        return [c.to_dict() for c in candidates(self._v(), self._deid_rule())]

    def commons_publish(self, ref: str, confirmed: bool, push: bool = False) -> dict[str, Any]:
        v = self._v()
        if not confirmed:
            raise HubError("publish requires the human confirmation flag (비식별 확인)", 422)
        rel = self._rel(ref)
        try:
            res = publish_note(
                v, rel, self._commons_path(), confirmed=True, rule=self._deid_rule(), push=push
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
