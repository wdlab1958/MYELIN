"""Pack loader.

- `load_pack(dir)`      : parse+validate `pack.yaml` and every side file it references.
- `discover_packs(roots)`: scan `<root>/*/pack.yaml` into a `PackRegistry` (name → LoadedPack).
- `resolve_packs(names, registry)`: dependency resolution (requires + version specs),
  cycle detection, cross-pack Domain-ID uniqueness; returns packs in install order.

Every failure is a `PackError` with the offending path and a human-readable message
(P1 Gate: 잘못된 Pack 10종 fixture 모두 명확한 오류 메시지).
"""

from __future__ import annotations

import io
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from myelin_core.schema.pack import InterviewBank, Pack, Requirement, Taxonomy

PACK_FILE = "pack.yaml"


class PackError(ValueError):
    def __init__(self, path: Path | str, message: str) -> None:
        self.path = Path(path)
        self.message = message
        super().__init__(f"{self.path}: {message}")


@dataclass
class LoadedPack:
    pack: Pack
    root: Path
    taxonomies: dict[str, Taxonomy] = field(default_factory=dict)  # rel path → parsed
    interview_banks: dict[str, InterviewBank] = field(default_factory=dict)
    template_files: dict[str, list[Path]] = field(default_factory=dict)  # rel dir → *.md

    @property
    def name(self) -> str:
        return self.pack.pack

    def taxonomy_for(self, domain_id: str) -> Taxonomy | None:
        d = next((d for d in self.pack.domains if d.id == domain_id), None)
        return self.taxonomies.get(d.taxonomy_seed) if d and d.taxonomy_seed else None

    def interview_bank_for(self, domain_id: str) -> InterviewBank | None:
        d = next((d for d in self.pack.domains if d.id == domain_id), None)
        return self.interview_banks.get(d.interview_bank) if d and d.interview_bank else None


PackRegistry = dict[str, LoadedPack]


def _format_validation_error(exc: ValidationError) -> str:
    lines = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"]) or "<root>"
        msg = err["msg"]
        if err["type"] == "extra_forbidden":
            msg = "unknown field (typo? unknown fields are rejected in packs)"
        lines.append(f"  - {loc}: {msg}")
    return "\n".join(lines)


def _load_yaml(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise PackError(path, "file not found") from None
    except UnicodeDecodeError as exc:
        raise PackError(path, f"not UTF-8: {exc}") from None
    try:
        data = YAML(typ="safe").load(io.StringIO(text))
    except YAMLError as exc:
        raise PackError(path, f"invalid YAML: {exc}") from None
    if data is None:
        raise PackError(path, "file is empty")
    if not isinstance(data, dict):
        raise PackError(path, "top level must be a mapping")
    return data


def _resolve_inside(root: Path, rel: str, label: str) -> Path:
    target = (root / rel).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError:
        raise PackError(root / PACK_FILE, f"{label}: {rel!r} escapes the pack directory") from None
    if not target.exists():
        raise PackError(root / PACK_FILE, f"{label}: referenced path {rel!r} does not exist")
    return target


def load_pack(pack_dir: Path) -> LoadedPack:
    """Validate `pack.yaml` and all referenced side files. Raises PackError."""
    root = Path(pack_dir)
    pack_file = root / PACK_FILE
    if not root.is_dir():
        raise PackError(root, "pack directory does not exist")
    if not pack_file.is_file():
        raise PackError(pack_file, "pack.yaml not found")
    data = _load_yaml(pack_file)
    try:
        pack = Pack.model_validate(data)
    except ValidationError as exc:
        raise PackError(
            pack_file, f"pack.yaml schema violation:\n{_format_validation_error(exc)}"
        ) from None
    if pack.pack != root.name:
        raise PackError(
            pack_file, f"pack name {pack.pack!r} must match its directory name {root.name!r}"
        )

    loaded = LoadedPack(pack=pack, root=root)
    for rel, label in pack.referenced_paths().items():
        target = _resolve_inside(root, rel, label)
        if label.endswith("templates"):
            if not target.is_dir():
                raise PackError(pack_file, f"{label}: {rel!r} must be a directory")
            files = sorted(target.glob("*.md"))
            if not files:
                raise PackError(pack_file, f"{label}: {rel!r} contains no *.md templates")
            loaded.template_files[rel] = files
        elif label.endswith("taxonomy_seed"):
            if rel not in loaded.taxonomies:
                loaded.taxonomies[rel] = _load_side(target, Taxonomy)
        elif label.endswith("interview_bank"):
            if rel not in loaded.interview_banks:
                bank = _load_side(target, InterviewBank)
                _check_bank_domains(target, bank, pack)
                loaded.interview_banks[rel] = bank
    return loaded


def _load_side[T: (Taxonomy, InterviewBank)](path: Path, model: type[T]) -> T:
    data = _load_yaml(path)
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise PackError(
            path, f"{model.__name__} schema violation:\n{_format_validation_error(exc)}"
        ) from None


def _check_bank_domains(path: Path, bank: InterviewBank, pack: Pack) -> None:
    known = set(pack.domain_ids)
    for q in bank.questions:
        if q.domain is not None and q.domain not in known:
            raise PackError(
                path,
                f"question {q.id!r} references domain {q.domain!r} not declared in {pack.pack}",
            )
        if q.sub_moc is not None and q.domain is not None:
            dom = next(d for d in pack.domains if d.id == q.domain)
            if q.sub_moc not in dom.sub_mocs:
                raise PackError(
                    path, f"question {q.id!r}: sub_moc {q.sub_moc!r} is not in {q.domain}.sub_mocs"
                )


def discover_packs(roots: Iterable[Path], *, strict: bool = True) -> PackRegistry:
    """Load every `<root>/*/pack.yaml`. With strict=True the first invalid pack raises."""
    registry: PackRegistry = {}
    for root in roots:
        root = Path(root)
        if not root.is_dir():
            continue
        for pack_file in sorted(root.glob(f"*/{PACK_FILE}")):
            try:
                loaded = load_pack(pack_file.parent)
            except PackError:
                if strict:
                    raise
                continue
            if loaded.name in registry:
                raise PackError(
                    pack_file,
                    f"pack {loaded.name!r} already loaded from {registry[loaded.name].root}",
                )
            registry[loaded.name] = loaded
    return registry


def resolve_packs(requested: Sequence[str], registry: PackRegistry) -> list[LoadedPack]:
    """Return requested packs plus their transitive requirements, dependencies first.

    Errors: unknown pack, version spec not satisfied, circular requires, duplicate Domain IDs.
    """
    order: list[LoadedPack] = []
    state: dict[str, str] = {}  # name → "visiting" | "done"
    stack: list[str] = []

    def visit(req: Requirement, requested_by: str | None) -> None:
        name = req.name
        if name not in registry:
            who = f" (required by {requested_by})" if requested_by else ""
            raise PackError(
                requested_by or "<request>", f"pack {name!r} not found in registry{who}"
            )
        lp = registry[name]
        if not req.satisfied_by(lp.pack.semver):
            raise PackError(
                lp.root / PACK_FILE,
                f"{requested_by or '<request>'} requires {req}, "
                f"but {name} is version {lp.pack.version}",
            )
        if state.get(name) == "done":
            return
        if state.get(name) == "visiting":
            cycle = " -> ".join([*stack[stack.index(name) :], name])
            raise PackError(lp.root / PACK_FILE, f"circular requires: {cycle}")
        state[name] = "visiting"
        stack.append(name)
        for sub in lp.pack.requirements:
            visit(sub, name)
        stack.pop()
        state[name] = "done"
        order.append(lp)

    for r in requested:
        visit(Requirement(r), None)

    seen: dict[str, str] = {}
    for lp in order:
        for did in lp.pack.domain_ids:
            if did in seen:
                raise PackError(
                    lp.root / PACK_FILE,
                    f"domain id {did!r} is declared by both {seen[did]} and {lp.name}",
                )
            seen[did] = lp.name
    return order
