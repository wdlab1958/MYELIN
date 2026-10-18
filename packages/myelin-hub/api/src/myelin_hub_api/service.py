"""Hub 서비스 — HTTP를 모르는 얇은 계층. 판단은 모두 myelin_core가 한다 (ADR-0001).

읽기 메서드는 파일을 쓰지 않는다. 쓰기 메서드(`do_*`)는 사람의 클릭으로만 불린다 (ADR-0008):
HTTP 계층이 POST + 의도 헤더 + 같은 출처를 확인한 뒤에만 호출한다.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from myelin_core import gitops
from myelin_core.config import (
    CONFIG_FILE,
    LEVEL_DESCRIPTIONS,
    VaultConfig,
    load_config,
    update_config,
)
from myelin_core.doctor import run_doctor
from myelin_core.errors import Issue, MyelinError, PackError, issues_from_validation
from myelin_core.gitops import Author
from myelin_core.loader import CORE_PACK, LoadedPack
from myelin_core.lock import load_lock
from myelin_core.onboarding import (
    ROLES_ADDABLE,
    InitRequest,
    load_packs,
    prepare_add_domain,
    prepare_init,
)
from myelin_core.pack import PackManifest
from myelin_core.review import (
    Change,
    apply_change,
    commit_message,
    plan_promote,
    plan_reject,
    read_note,
    revert_change,
    review_queue,
)
from myelin_core.safety import init_target_issues
from myelin_core.scaffold import apply_plan
from myelin_core.stats import compute_stats
from myelin_core.vault import scan_vault
from myelin_core.yamlio import load_yaml

MAX_PACK_TEXT = 200_000


class NotInitialized(MyelinError):
    """Vault가 아직 없다 — 온보딩 마법사로."""


def _jsonable(value: Any) -> Any:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    if hasattr(value, "value") and not isinstance(value, str | int | float | bool):
        return value.value
    return value


class HubService:
    def __init__(
        self, vault: Path, packs_dir: Path, today: Callable[[], date] = date.today
    ) -> None:
        self.vault = vault
        self.packs_dir = packs_dir
        self.today = today
        self._lock = threading.Lock()  # 쓰기는 한 번에 하나

    # ── 공통 ────────────────────────────────────────────────────────────
    @property
    def initialized(self) -> bool:
        return (self.vault / CONFIG_FILE).is_file()

    def _cfg(self) -> VaultConfig:
        if not self.initialized:
            raise NotInitialized(
                "Vault가 아직 없습니다",
                [Issue(CONFIG_FILE, "온보딩을 진행하세요", "not_initialized")],
            )
        return load_config(self.vault)

    def _author(self, cfg: VaultConfig) -> Author:
        return Author(cfg.owner.name, cfg.owner.email or "myelin@localhost")

    def _packs(self) -> dict[str, LoadedPack]:
        return load_packs(self.packs_dir)

    def _commit_or_revert(self, paths: list[str], message: str, undo: Callable[[], object]) -> str:
        """파일 변경을 commit 한다. 실패하면 되돌리고 오류를 다시 던진다."""
        cfg = self._cfg()
        try:
            return gitops.commit_paths(self.vault, paths, message, self._author(cfg))
        except Exception:
            undo()
            raise

    # ── 읽기 ────────────────────────────────────────────────────────────
    def state(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "vault": str(self.vault),
            "initialized": self.initialized,
            "git": gitops.is_repo(self.vault),
            "git_available": gitops.git_available(),
        }
        if self.initialized:
            cfg = self._cfg()
            out["owner"] = cfg.owner.name
            out["level"] = cfg.level
        return out

    def dashboard(self) -> dict[str, Any]:
        cfg = self._cfg()
        today = self.today()
        findings = run_doctor(self.vault, today=today)
        return {
            "owner": cfg.owner.name,
            "stats": compute_stats(self.vault, today).as_dict(),
            "review_count": len(review_queue(self.vault)),
            "findings": [asdict(f) for f in findings],
            "commits": [asdict(c) for c in gitops.recent_commits(self.vault, 5)],
        }

    def domains(self) -> dict[str, Any]:
        cfg = self._cfg()
        lock = load_lock(self.vault)
        notes = scan_vault(self.vault).notes
        rows = []
        for d_id in cfg.domains.all():
            locked = lock.domain(d_id)
            mine = [n for n in notes if d_id in n.frontmatter.domain]
            rows.append(
                {
                    "id": d_id,
                    "label": locked.label if locked else None,
                    "name": locked.name if locked else d_id,
                    "accent": locked.accent.value if locked else "violet",
                    "role": cfg.domains.role_of(d_id),
                    "notes": len(mine),
                    "verified": sum(1 for n in mine if n.frontmatter.status.value == "verified"),
                    "moc": f"10_Domains/{d_id}/_MOC.md",
                }
            )
        open_roles = [r for r in ROLES_ADDABLE if not getattr(cfg.domains, r)]
        addable = [
            {
                "id": d.id,
                "label": d.label,
                "name": d.name,
                "accent": d.accent.value,
                "pack": p.name,
            }
            for p in self._packs().values()
            for d in p.domains
            if d.id not in cfg.domains.all()
        ]
        return {"domains": rows, "open_roles": open_roles, "addable": addable}

    def review(self) -> list[dict[str, Any]]:
        self._cfg()
        return [asdict(i) for i in review_queue(self.vault)]

    def note(self, rel: str) -> dict[str, Any]:
        self._cfg()
        note, _ = read_note(self.vault, rel)
        fm = note.frontmatter.model_dump(mode="json")
        return {"path": rel, "title": note.title, "frontmatter": fm, "body": note.body}

    def packs(self) -> list[dict[str, Any]]:
        installed = set(self._cfg().packs) if self.initialized else set()
        out = []
        for p in self._packs().values():
            m = p.manifest
            out.append(
                {
                    "name": m.pack,
                    "version": m.version,
                    "kind": m.kind.value,
                    "maintainer": m.maintainer,
                    "description": m.description,
                    "installed": m.pack in installed,
                    "terms": sum(len(t.terms) for t in p.taxonomies.values()),
                    "questions": sum(
                        len(qs) for b in p.interview_banks.values() for qs in b.domains.values()
                    ),
                    "domains": [
                        {
                            "id": d.id,
                            "label": d.label,
                            "name": d.name,
                            "accent": d.accent.value,
                            "description": d.description,
                            "sub_mocs": d.sub_mocs,
                        }
                        for d in m.domains
                    ],
                }
            )
        return out

    def pack_source(self, name: str) -> dict[str, Any]:
        packs = self._packs()
        if name not in packs:
            raise PackError("Pack을 찾을 수 없습니다", [Issue("pack", name, "not_found")])
        text = (packs[name].root / "pack.yaml").read_text(encoding="utf-8")
        return {"name": name, "yaml": text}

    @staticmethod
    def validate_pack(text: str) -> dict[str, Any]:
        """Pack 편집기의 검증 — 순수 함수, 저장하지 않는다 (Pack은 Pack 저장소에서 git으로)."""
        if len(text) > MAX_PACK_TEXT:
            return {"ok": False, "issues": [{"loc": "pack.yaml", "msg": "너무 큽니다"}]}
        try:
            data = load_yaml(text, "pack.yaml", PackError)
            m = PackManifest.model_validate(data)
        except PackError as err:
            return {"ok": False, "issues": [asdict(i) for i in err.issues]}
        except ValidationError as exc:
            return {
                "ok": False,
                "issues": [asdict(i) for i in issues_from_validation(exc, prefix="pack.yaml")],
            }
        return {"ok": True, "issues": [], "pack": m.pack, "domains": [d.id for d in m.domains]}

    def settings(self) -> dict[str, Any]:
        cfg = self._cfg()
        location = [
            asdict(f) for f in run_doctor(self.vault, today=self.today()) if f.rule == "location"
        ]
        return {
            "vault": str(self.vault),
            "owner": cfg.owner.model_dump(),
            "language": cfg.language,
            "level": cfg.level,
            "levels": {str(k): v for k, v in LEVEL_DESCRIPTIONS.items()},
            "mcp_write_drafts": cfg.mcp.write_drafts,
            "llm": cfg.llm.model_dump(),
            "git": gitops.is_repo(self.vault),
            "git_available": gitops.git_available(),
            "location": location,
        }

    def onboarding(self) -> dict[str, Any]:
        packs = [p for p in self.packs() if p["name"] != CORE_PACK]
        issues = [] if self.initialized else init_target_issues(self.vault)
        return {
            "target": str(self.vault),
            "initialized": self.initialized,
            "target_issues": [asdict(i) for i in issues],
            "packs": packs,
            "levels": {str(k): v for k, v in LEVEL_DESCRIPTIONS.items()},
            "git_available": gitops.git_available(),
        }

    def onboarding_preview(self, req: InitRequest) -> dict[str, Any]:
        prepared = prepare_init(self.vault, req, self._packs(), self.today())
        files = sorted(prepared.plan.files)
        return {
            "files": len(files),
            "domains": prepared.config.domains.all(),
            "packs": prepared.config.packs,
            "level": prepared.config.level,
            "sample": [f for f in files if not f.endswith(".gitkeep")][:40],
        }

    # ── 쓰기 (사람의 클릭만) ────────────────────────────────────────────
    def do_onboarding(self, req: InitRequest, start_git: bool) -> dict[str, Any]:
        with self._lock:
            prepared = prepare_init(self.vault, req, self._packs(), self.today())
            apply_plan(self.vault, prepared.plan)
            sha = None
            if start_git and gitops.git_available():
                sha = gitops.init_repo(self.vault, self._author(prepared.config))
            return {**self.state(), "commit": sha}

    def do_git_init(self) -> dict[str, Any]:
        with self._lock:
            sha = gitops.init_repo(self.vault, self._author(self._cfg()))
            return {"commit": sha}

    def _do_review(self, change: Change) -> dict[str, Any]:
        apply_change(self.vault, change)
        sha = self._commit_or_revert(
            change.paths, commit_message(change), lambda: revert_change(self.vault, change)
        )
        return {"action": change.action, "id": change.note_id, "path": change.dst, "commit": sha}

    def _require_repo(self) -> None:
        if not gitops.is_repo(self.vault):
            raise gitops.GitError(
                "승격·반려는 git commit으로 남깁니다 — 먼저 로컬 git을 시작하세요",
                [Issue(".git", "Settings → 로컬 git 시작", "no_repo")],
            )

    def do_promote(self, rel: str, note_id: str) -> dict[str, Any]:
        with self._lock:
            self._cfg()
            self._require_repo()
            return self._do_review(plan_promote(self.vault, rel, note_id, self.today()))

    def do_reject(self, rel: str, note_id: str) -> dict[str, Any]:
        with self._lock:
            self._cfg()
            self._require_repo()
            return self._do_review(plan_reject(self.vault, rel, note_id, self.today()))

    def do_update_settings(
        self, level: int | None = None, write_drafts: bool | None = None
    ) -> dict[str, Any]:
        """Level·MCP 초안 쓰기만 바꾼다. LLM 라우팅(기밀 경계)은 Hub에서 바꾸지 않는다."""
        with self._lock:
            self._cfg()

            def mutate(data: Any) -> None:
                if level is not None:
                    data["level"] = level
                if write_drafts is not None:
                    if "mcp" not in data or data["mcp"] is None:
                        data["mcp"] = {}
                    data["mcp"]["write_drafts"] = write_drafts

            _, text = update_config(self.vault, mutate)
            path = self.vault / CONFIG_FILE
            before = path.read_text(encoding="utf-8")
            if text == before:
                return {**self.settings(), "commit": None}
            path.write_text(text, encoding="utf-8")
            sha = None
            if gitops.is_repo(self.vault):
                sha = self._commit_or_revert(
                    [CONFIG_FILE],
                    "myelin: update settings via Hub",
                    lambda: path.write_text(before, encoding="utf-8"),
                )
            return {**self.settings(), "commit": sha}

    def do_add_domain(self, domain: str, role: str, pack: str | None) -> dict[str, Any]:
        with self._lock:
            self._cfg()
            prepared = prepare_add_domain(
                self.vault, domain, role, pack, self._packs(), self.today()
            )
            originals = {
                rel: (self.vault / rel).read_text(encoding="utf-8")
                if (self.vault / rel).is_file()
                else None
                for rel in prepared.plan.updates
            }
            written = apply_plan(self.vault, prepared.plan)
            sha = None
            if gitops.is_repo(self.vault):

                def undo() -> None:
                    for rel in prepared.plan.files:
                        (self.vault / rel).unlink(missing_ok=True)
                    for rel, text in originals.items():
                        if text is None:
                            (self.vault / rel).unlink(missing_ok=True)
                        else:
                            (self.vault / rel).write_text(text, encoding="utf-8")

                sha = self._commit_or_revert(written, f"myelin: add domain {domain} ({role})", undo)
            return {"domain": domain, "role": role, "commit": sha}
