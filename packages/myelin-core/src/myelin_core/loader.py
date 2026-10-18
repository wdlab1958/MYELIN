"""Pack 로더 · 해석기.

- `load_pack(dir)`      : 매니페스트·참조 파일을 모두 검증하고 문제를 한 번에 보고한다.
- `discover_packs(root)`: 하위 디렉터리의 Pack을 모두 읽는다. 하나라도 잘못되면 전체 실패.
- `resolve(names, ...)` : 의존성 순서로 정렬하고 누락·버전·순환·Domain ID 충돌을 검사한다.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from myelin_core.errors import Issue, PackError, issues_from_validation
from myelin_core.pack import Domain, InterviewBank, PackManifest, TaxonomyFile
from myelin_core.versioning import parse_requirement
from myelin_core.yamlio import load_yaml

MANIFEST = "pack.yaml"
CORE_PACK = "myelin.core"


@dataclass(frozen=True)
class LoadedPack:
    manifest: PackManifest
    root: Path
    taxonomies: dict[str, TaxonomyFile] = field(default_factory=dict)
    interview_banks: dict[str, InterviewBank] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.manifest.pack

    @property
    def domains(self) -> list[Domain]:
        return self.manifest.domains


def _read_yaml_file(path: Path, rel: str) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise PackError(
            f"UTF-8로 읽을 수 없습니다: {rel}", [Issue(rel, "UTF-8 디코딩 실패")]
        ) from exc
    return load_yaml(text, rel, PackError)


def _validate[M: BaseModel](model: type[M], data: Any, prefix: str) -> M:
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise PackError(f"검증 실패: {prefix}", issues_from_validation(exc, prefix)) from exc


def _inside(root: Path, rel: str) -> Path | None:
    """rel 이 실제로 Pack 안에 있으면 절대경로, 아니면(심볼릭 링크 탈출 등) None."""
    target = (root / rel).resolve()
    return target if target.is_relative_to(root.resolve()) else None


# Pack 템플릿은 Obsidian Templater가 실행한다. `<%* … %>`(JS 실행), tp.user·tp.system·tp.web·
# tp.file.include 등은 임의 코드 실행·외부 호출이 될 수 있다. 남의 Pack이 이를 Vault에
# 심지 못하게 아래 허용 목록의 표현식만 받는다 (STRIDE T3/E3, P8).
_TEMPLATER_TAG = re.compile(r"<%.*?%>", re.DOTALL)
_SAFE_TAG = re.compile(
    r"""<%\s*tp\.(?:date\.now\(\s*(?:"[^"\\]*"|'[^'\\]*')?\s*\)|file\.title|date\.today\(\s*(?:"[^"\\]*"|'[^'\\]*')?\s*\))\s*%>"""
)


def _template_issues(root: Path, rel: str, loc: str) -> list[Issue]:
    target = _inside(root, rel)
    if target is None or not target.is_dir():
        return []
    out: list[Issue] = []
    root = root.resolve()
    for f in sorted(target.rglob("*")):
        if f.is_symlink():
            out.append(Issue(loc, f"symlink in templates: {f.relative_to(root)}", "symlink"))
            continue
        if not f.is_file():
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            out.append(Issue(loc, f"not UTF-8: {f.relative_to(root)}", "encoding"))
            continue
        for m in _TEMPLATER_TAG.finditer(text):
            if not _SAFE_TAG.fullmatch(m.group(0)):
                line = text.count("\n", 0, m.start()) + 1
                out.append(
                    Issue(
                        f"{f.relative_to(root).as_posix()}:{line}",
                        f"허용되지 않은 Templater 표현식: {m.group(0)[:60]}",
                        "unsafe_template",
                    )
                )
    return out


def load_pack(path: Path) -> LoadedPack:
    manifest_path = path / MANIFEST
    if not manifest_path.is_file():
        raise PackError(
            f"{MANIFEST} 가 없습니다: {path}", [Issue(MANIFEST, "file not found", "missing_file")]
        )

    data = _read_yaml_file(manifest_path, MANIFEST)
    if not isinstance(data, dict):
        raise PackError(
            f"{MANIFEST} 최상위는 mapping이어야 합니다",
            [Issue(MANIFEST, "top-level must be a mapping", "not_mapping")],
        )
    manifest = _validate(PackManifest, data, "")

    issues: list[Issue] = []
    taxonomies: dict[str, TaxonomyFile] = {}
    banks: dict[str, InterviewBank] = {}

    def check_dir(rel: str | None, loc: str) -> None:
        if rel is None:
            return
        target = _inside(path, rel)
        if target is None:
            issues.append(Issue(loc, f"{rel!r} escapes the pack directory", "path_escape"))
        elif not target.is_dir():
            issues.append(Issue(loc, f"directory not found: {rel}", "missing_file"))

    def load_ref[M: BaseModel](rel: str, loc: str, model: type[M]) -> M | None:
        target = _inside(path, rel)
        if target is None:
            issues.append(Issue(loc, f"{rel!r} escapes the pack directory", "path_escape"))
            return None
        if not target.is_file():
            issues.append(Issue(loc, f"file not found: {rel}", "missing_file"))
            return None
        try:
            return _validate(model, _read_yaml_file(target, rel), rel)
        except PackError as err:
            issues.extend(err.issues)
            return None

    check_dir(manifest.templates, "templates")
    if manifest.templates:
        issues.extend(_template_issues(path, manifest.templates, "templates"))
    for idx, domain in enumerate(manifest.domains):
        loc = f"domains[{idx}]"
        check_dir(domain.templates, f"{loc}.templates")
        if domain.templates and domain.templates != manifest.templates:
            issues.extend(_template_issues(path, domain.templates, f"{loc}.templates"))
        if domain.taxonomy_seed:
            tax = taxonomies.get(domain.taxonomy_seed) or load_ref(
                domain.taxonomy_seed, f"{loc}.taxonomy_seed", TaxonomyFile
            )
            if tax is not None:
                taxonomies[domain.taxonomy_seed] = tax
        if domain.interview_bank:
            bank = banks.get(domain.interview_bank) or load_ref(
                domain.interview_bank, f"{loc}.interview_bank", InterviewBank
            )
            if bank is not None:
                banks[domain.interview_bank] = bank
                if domain.id not in bank.domains:
                    issues.append(
                        Issue(
                            f"{loc}.interview_bank",
                            f"{domain.interview_bank} has no questions for {domain.id}",
                            "missing_questions",
                        )
                    )

    if issues:
        raise PackError(f"Pack 검증 실패: {manifest.pack}", issues)
    return LoadedPack(manifest=manifest, root=path, taxonomies=taxonomies, interview_banks=banks)


def discover_packs(root: Path) -> dict[str, LoadedPack]:
    found: dict[str, LoadedPack] = {}
    issues: list[Issue] = []
    for child in sorted(p for p in root.iterdir() if p.is_dir()):
        if not (child / MANIFEST).exists():
            continue
        try:
            pack = load_pack(child)
        except PackError as err:
            issues.extend(Issue(f"{child.name}/{i.loc}", i.msg, i.code) for i in err.issues)
            continue
        if pack.name != child.name:
            issues.append(
                Issue(
                    f"{child.name}/{MANIFEST}.pack",
                    f"directory name must equal pack name ({pack.name!r})",
                    "name_mismatch",
                )
            )
            continue
        found[pack.name] = pack
    if issues:
        raise PackError(f"Pack 탐색 실패: {root}", issues)
    return found


def resolve(
    selected: Sequence[str],
    available: Mapping[str, LoadedPack],
    require_core: bool = True,
) -> list[LoadedPack]:
    """의존성이 먼저 오도록 정렬한 Pack 목록을 돌려준다."""
    order: list[LoadedPack] = []
    state: dict[str, str] = {}  # visiting | done
    issues: list[Issue] = []

    def visit(name: str, chain: list[str], required_by: str | None) -> None:
        if state.get(name) == "done":
            return
        if state.get(name) == "visiting":
            cycle = " -> ".join([*chain[chain.index(name) :], name])
            issues.append(Issue(f"{name}.requires", f"dependency cycle: {cycle}", "cycle"))
            return
        pack = available.get(name)
        if pack is None:
            where = f"{required_by}.requires" if required_by else name
            issues.append(Issue(where, f"pack not found: {name}", "missing_pack"))
            return
        state[name] = "visiting"
        for raw in pack.manifest.requires:
            req = parse_requirement(raw)
            dep = available.get(req.name)
            if dep is not None and not req.satisfied_by(dep.manifest.version_tuple):
                issues.append(
                    Issue(
                        f"{name}.requires",
                        f"{req} not satisfied by {dep.name} {dep.manifest.version}",
                        "version_unsatisfied",
                    )
                )
            visit(req.name, [*chain, name], name)
        state[name] = "done"
        order.append(pack)

    for name in selected:
        visit(name, [], None)

    if require_core and not issues and CORE_PACK not in {p.name for p in order}:
        issues.append(Issue("packs", f"{CORE_PACK} is required", "missing_core"))

    owner: dict[str, str] = {}
    for pack in order:
        for domain in pack.domains:
            if domain.id in owner:
                issues.append(
                    Issue(
                        f"{pack.name}.domains",
                        f"domain id {domain.id!r} is also defined by {owner[domain.id]}",
                        "domain_conflict",
                    )
                )
            else:
                owner[domain.id] = pack.name

    if issues:
        raise PackError("Pack 해석 실패", issues)
    return order
