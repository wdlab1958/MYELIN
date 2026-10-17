"""T3/T4 — Pack · Domain · Version · Requirement · side-file schemas (정본 §5.2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from myelin_core.schema import (
    ACCENTS,
    Domain,
    InterviewBank,
    Pack,
    PackKind,
    Requirement,
    Taxonomy,
    Version,
)

SPEC_PACK = {
    "pack": "a3.security-consulting",
    "version": "1.0.0",
    "kind": "org",
    "maintainer": "A3-AI WG",
    "requires": ["myelin.core>=1.0"],
    "domains": [
        {
            "id": "SEC-CONSULT",
            "name": "보안 컨설팅",
            "accent": "violet",
            "description": "진단·컨설팅 업무 지식 — 방법론, 산출물, 고객 유형별 교훈",
            "sub_mocs": [
                "진단 방법론",
                "컴플라이언스(ISMS-P 등)",
                "위협 모델링",
                "보고서 작성",
                "고객 커뮤니케이션",
            ],
            "note_types": ["evergreen", "lesson", "checklist", "adr"],
            "taxonomy_seed": "taxonomy.yaml",
            "templates": "templates/",
            "interview_bank": "interviews.yaml",
            "classification_default": "internal",
            "compose_targets": ["진단 보고서 초안", "제안서 섹션", "교육자료"],
        }
    ],
}


def test_spec_example_pack() -> None:
    p = Pack.model_validate(SPEC_PACK)
    assert p.kind is PackKind.ORG
    assert p.domain_ids == ["SEC-CONSULT"]
    assert p.domains[0].templates == "templates"  # trailing slash normalised
    assert str(p.requirements[0]) == "myelin.core>=1.0.0"
    assert p.referenced_paths() == {
        "taxonomy.yaml": "domains[SEC-CONSULT].taxonomy_seed",
        "templates": "domains[SEC-CONSULT].templates",
        "interviews.yaml": "domains[SEC-CONSULT].interview_bank",
    }


def test_core_pack_rules() -> None:
    core = Pack.model_validate(
        {"pack": "myelin.core", "kind": "core", "maintainer": "MYELIN", "templates": "templates"}
    )
    assert core.domains == [] and core.referenced_paths() == {"templates": "templates"}
    with pytest.raises(ValidationError, match="must not declare domains"):
        Pack.model_validate({**SPEC_PACK, "pack": "myelin.core", "kind": "core", "requires": []})
    with pytest.raises(ValidationError, match="must have kind: core"):
        Pack.model_validate({**SPEC_PACK, "pack": "myelin.core"})


def test_non_core_needs_domain_and_core_requirement() -> None:
    with pytest.raises(ValidationError, match="at least one domain"):
        Pack.model_validate({**SPEC_PACK, "domains": []})
    with pytest.raises(ValidationError, match=r"must require myelin\.core"):
        Pack.model_validate({**SPEC_PACK, "requires": []})


def test_duplicate_domain_ids_in_pack() -> None:
    d = SPEC_PACK["domains"][0]
    with pytest.raises(ValidationError, match="duplicate domain id"):
        Pack.model_validate({**SPEC_PACK, "domains": [d, d]})


def test_unknown_field_forbidden() -> None:
    with pytest.raises(ValidationError, match="sub_moc"):
        Pack.model_validate({**SPEC_PACK, "domains": [{**SPEC_PACK["domains"][0], "sub_moc": []}]})
    with pytest.raises(ValidationError, match="extra"):
        Pack.model_validate({**SPEC_PACK, "extra": 1})


@pytest.mark.parametrize("name", ["Myelin.core", "core", "a3..x", "a3.", "-a.b", "a3.Sec"])
def test_pack_name_pattern(name: str) -> None:
    with pytest.raises(ValidationError):
        Pack.model_validate({**SPEC_PACK, "pack": name})


def test_version_normalised_and_invalid() -> None:
    assert Pack.model_validate({**SPEC_PACK, "version": "1.2"}).version == "1.2.0"
    with pytest.raises(ValidationError, match="invalid version"):
        Pack.model_validate({**SPEC_PACK, "version": "v1"})


def test_version_ordering() -> None:
    assert Version("1.0") == Version("1.0.0")
    assert Version("1.0.1") > Version("1.0") and Version("0.9.9") < Version("1.0")
    assert sorted([Version("2.0"), Version("1.10.0"), Version("1.9.9")])[-1] == Version("2.0")
    assert repr(Version("1.2.3")) == "Version('1.2.3')"
    assert len({Version("1.0"), Version("1.0.0")}) == 1
    with pytest.raises(ValueError, match="invalid version"):
        Version("1")


@pytest.mark.parametrize(
    "req,ver,ok",
    [
        ("myelin.core", "0.1.0", True),
        ("myelin.core>=1.0", "1.0.0", True),
        ("myelin.core>=1.0", "0.9.9", False),
        ("myelin.core>1.0", "1.0.0", False),
        ("myelin.core<=1.0", "1.0.0", True),
        ("myelin.core<1.0", "1.0.0", False),
        ("myelin.core==1.0", "1.0.0", True),
        ("myelin.core==1.0", "1.0.1", False),
        ("myelin.core~=1.2", "1.9.0", True),
        ("myelin.core~=1.2", "2.0.0", False),
        ("myelin.core~=1.2", "1.1.0", False),
    ],
)
def test_requirement_specs(req: str, ver: str, ok: bool) -> None:
    r = Requirement(req)
    assert r.satisfied_by(Version(ver)) is ok
    assert repr(r).startswith("Requirement(")


def test_requirement_invalid() -> None:
    with pytest.raises(ValueError, match="invalid requirement"):
        Requirement("myelin.core >>= 1")
    with pytest.raises(ValueError, match="invalid pack name"):
        Requirement("core")
    with pytest.raises(ValidationError, match="more than once"):
        Pack.model_validate({**SPEC_PACK, "requires": ["myelin.core>=1.0", "myelin.core<2.0"]})


def test_domain_validators() -> None:
    base = SPEC_PACK["domains"][0]
    with pytest.raises(ValidationError, match="accent"):
        Domain.model_validate({**base, "accent": "amber"})
    with pytest.raises(ValidationError, match="unique"):
        Domain.model_validate({**base, "sub_mocs": ["a", "a"]})
    with pytest.raises(ValidationError, match="non-empty"):
        Domain.model_validate({**base, "compose_targets": [" "]})
    with pytest.raises(ValidationError, match="at least one note type"):
        Domain.model_validate({**base, "note_types": []})
    with pytest.raises(ValidationError, match="unique"):
        Domain.model_validate({**base, "note_types": ["lesson", "lesson"]})
    with pytest.raises(ValidationError, match="inside the pack"):
        Domain.model_validate({**base, "templates": "../other"})
    with pytest.raises(ValidationError, match="inside the pack"):
        Domain.model_validate({**base, "taxonomy_seed": "/etc/passwd"})
    with pytest.raises(ValidationError):
        Domain.model_validate({**base, "id": "sec"})
    d = Domain.model_validate({"id": "X", "name": "x"})
    assert d.accent == "violet" and d.taxonomy_seed is None


def test_accents_match_design_tokens(repo_root: Path) -> None:
    tokens = json.loads((repo_root / "design/tokens.json").read_text(encoding="utf-8"))["color"]
    for accent in ACCENTS:
        assert (accent == "violet" and "violet-600" in tokens) or f"neon-{accent}" in tokens, accent


def test_taxonomy_schema() -> None:
    t = Taxonomy.model_validate(
        {"terms": [{"term": "WCET", "aliases": "worst-case execution time", "domain": "D2"}]}
    )
    assert t.terms[0].aliases == ["worst-case execution time"] and t.terms[0].domain == ["D2"]
    with pytest.raises(ValidationError, match="claimed by both"):
        Taxonomy.model_validate(
            {"terms": [{"term": "A", "aliases": ["x"]}, {"term": "B", "aliases": ["X"]}]}
        )
    # same alias on the same term twice is not a conflict
    Taxonomy.model_validate({"terms": [{"term": "A", "aliases": ["a"]}]})


def test_interview_bank_schema() -> None:
    bank = InterviewBank.model_validate({"questions": [{"id": "q1", "prompt": "왜?"}]})
    assert bank.questions[0].yields.value == "lesson"
    with pytest.raises(ValidationError, match="at least 1"):
        InterviewBank.model_validate({"questions": []})
    with pytest.raises(ValidationError, match="duplicate question id"):
        InterviewBank.model_validate(
            {"questions": [{"id": "q1", "prompt": "a"}, {"id": "q1", "prompt": "b"}]}
        )
    with pytest.raises(ValidationError):
        InterviewBank.model_validate({"questions": [{"id": "Q 1", "prompt": "a"}]})
