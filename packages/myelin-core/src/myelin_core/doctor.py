"""`myelin doctor` — Vault integrity rules (정본 §6.2 doctor, P2-T8: 8 rules).

| rule | severity | what |
|---|---|---|
| schema            | error | frontmatter missing / invalid YAML / schema violation (unparseable) |
| fail-closed       | error | verified note links to an unverified `origin: claude` note;
|                   |       | or a claude draft lives outside 00_Inbox/ai-drafts |
| orphan            | warning | no inbound and no outbound links (Inbox, Archive, MOC excluded) |
| confidential-share| error | classification: confidential + share: true |
| broken-link       | warning | wikilink target that matches no note (non-.md embeds ignored) |
| duplicate-id      | error | same frontmatter id in two files |
| domain            | error | domain id not configured/declared; moc without domain |
| temporal          | error | reviewed < created; verified without reviewed |
| extra-field       | info  | unknown frontmatter keys (ADR-0003 §2) |
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from myelin_core.note import Note
from myelin_core.packs.loader import PackError
from myelin_core.schema.frontmatter import Classification, NoteType, Origin, Status
from myelin_core.vault import AI_DRAFTS, ARCHIVE, INBOX, Vault

Severity = Literal["error", "warning", "info"]
RULES: tuple[str, ...] = (
    "schema",
    "fail-closed",
    "orphan",
    "confidential-share",
    "broken-link",
    "duplicate-id",
    "domain",
    "temporal",
)


@dataclass(frozen=True, order=True)
class Finding:
    rule: str
    severity: Severity
    path: str
    message: str


@dataclass
class DoctorReport:
    findings: list[Finding] = field(default_factory=list)
    notes_scanned: int = 0

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors and not self.warnings

    def by_rule(self) -> dict[str, int]:
        out: dict[str, int] = defaultdict(int)
        for f in self.findings:
            out[f.rule] += 1
        return dict(sorted(out.items()))

    def to_dict(self) -> dict[str, object]:
        return {
            "notes_scanned": self.notes_scanned,
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "by_rule": self.by_rule(),
            "findings": [f.__dict__ for f in sorted(self.findings)],
        }


def _resolve_targets(notes: list[Note], vault: Vault) -> dict[str, list[Note]]:
    """Obsidian-style resolution: file stem, relative path without .md, and aliases."""
    index: dict[str, list[Note]] = defaultdict(list)
    for n in notes:
        assert n.path is not None
        rel = vault.rel(n.path)
        index[n.path.stem].append(n)
        index[rel[:-3]].append(n)
        for alias in n.frontmatter.extra_fields.get("aliases", []) or []:
            if isinstance(alias, str):
                index[alias].append(n)
    return index


def known_domains(vault: Vault, pack_roots: list[Path] | None = None) -> set[str]:
    """Configured 3+1 domains plus every domain declared by the configured packs.

    A note may use a pack domain that is not (yet) activated; that is not a typo. If packs
    cannot be resolved (offline, missing packs dir) only the configured ids are known.
    """
    ids = set(vault.config.domains.all_ids)
    try:
        for lp in vault.packs(pack_roots):
            ids.update(lp.pack.domain_ids)
    except PackError:
        pass
    return ids


def run_doctor(
    vault: Vault, *, declared_domains: set[str] | None = None, pack_roots: list[Path] | None = None
) -> DoctorReport:
    report = DoctorReport()
    notes, parse_errors = vault.read_all()
    report.notes_scanned = len(notes) + len(parse_errors)
    for exc in parse_errors:
        assert exc.path is not None
        msg = str(exc).split(": ", 1)[-1]
        report.findings.append(Finding("schema", "error", vault.rel(exc.path), msg))

    known = declared_domains if declared_domains is not None else known_domains(vault, pack_roots)
    index = _resolve_targets(notes, vault)
    by_id: dict[str, list[Note]] = defaultdict(list)
    inbound: dict[int, int] = defaultdict(int)  # id(note) → inbound count

    # pass 1: per-note rules + link graph
    for n in notes:
        assert n.path is not None
        rel = vault.rel(n.path)
        fm = n.frontmatter
        by_id[fm.id].append(n)

        if fm.classification is Classification.CONFIDENTIAL and fm.share:
            report.findings.append(
                Finding(
                    "confidential-share",
                    "error",
                    rel,
                    "classification: confidential 노트는 share: true 일 수 없다",
                )
            )
        if fm.reviewed is not None and fm.reviewed < fm.created:
            report.findings.append(
                Finding(
                    "temporal",
                    "error",
                    rel,
                    f"reviewed({fm.reviewed}) 가 created({fm.created}) 보다 앞선다",
                )
            )
        if fm.status is Status.VERIFIED and fm.reviewed is None:
            report.findings.append(
                Finding(
                    "temporal", "error", rel, "status: verified 노트는 reviewed 날짜가 필요하다"
                )
            )
        for did in fm.domain:
            if did not in known:
                report.findings.append(
                    Finding(
                        "domain",
                        "error",
                        rel,
                        f"domain {did!r} 는 myelin.yaml/Pack에 선언되지 않았다",
                    )
                )
        if fm.type is NoteType.MOC and not fm.domain:
            report.findings.append(
                Finding("domain", "error", rel, "type: moc 노트는 domain 이 최소 1개 필요하다")
            )
        if (
            fm.origin is Origin.CLAUDE
            and fm.status is Status.DRAFT
            and not rel.startswith(AI_DRAFTS + "/")
        ):
            report.findings.append(
                Finding(
                    "fail-closed",
                    "error",
                    rel,
                    f"origin: claude 초안은 {AI_DRAFTS}/ 에만 있어야 한다",
                )
            )
        for key in fm.extra_fields:
            report.findings.append(
                Finding("extra-field", "info", rel, f"알 수 없는 frontmatter 필드 {key!r} (보존됨)")
            )

        for link in n.links:
            targets = index.get(link.target)
            if not targets:
                if link.embed and "." in link.target.rsplit("/", 1)[-1]:
                    continue  # image/pdf embed — not a note
                report.findings.append(
                    Finding(
                        "broken-link", "warning", rel, f"[[{link.target}]] 에 해당하는 노트가 없다"
                    )
                )
                continue
            for t in targets:
                inbound[id(t)] += 1
                if (
                    fm.status is Status.VERIFIED
                    and t.frontmatter.origin is Origin.CLAUDE
                    and t.frontmatter.status is not Status.VERIFIED
                ):
                    assert t.path is not None
                    report.findings.append(
                        Finding(
                            "fail-closed",
                            "error",
                            rel,
                            f"verified 노트가 미검증 AI 노트 [[{link.target}]] "
                            f"({vault.rel(t.path)}) 를 링크한다",
                        )
                    )

    # pass 2: duplicates + orphans
    for nid, group in by_id.items():
        if len(group) > 1:
            paths = sorted(vault.rel(g.path) for g in group if g.path)
            for p in paths:
                report.findings.append(
                    Finding(
                        "duplicate-id",
                        "error",
                        p,
                        f"id {nid!r} 가 {len(group)}개 파일에 있다: {paths}",
                    )
                )
    for n in notes:
        assert n.path is not None
        rel = vault.rel(n.path)
        top = rel.split("/", 1)[0]
        if top in (INBOX, ARCHIVE) or n.frontmatter.type is NoteType.MOC:
            continue
        if not n.links and inbound[id(n)] == 0:
            report.findings.append(
                Finding("orphan", "warning", rel, "들어오는 링크도 나가는 링크도 없다 (고아 노트)")
            )

    report.findings.sort()
    return report
