"""T1 — Frontmatter v2 (정본 §6.2)."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from myelin_core.schema import Classification, Frontmatter, NoteType, Origin, Status

BASE = {
    "id": "20261018-0712-wcet-budget",
    "type": "evergreen",
    "domain": ["D2", "D3"],
    "status": "verified",
    "origin": "mixed",
    "confidence": "high",
    "classification": "internal",
    "share": False,
    "source": ["[[Lit - ROS2 Executor]]"],
    "created": "2026-10-18",
    "reviewed": "2026-10-18",
    "tags": ["rtos", "control-loop"],
}


def test_spec_example_validates() -> None:
    fm = Frontmatter.model_validate(BASE)
    assert fm.type is NoteType.EVERGREEN
    assert fm.status is Status.VERIFIED
    assert fm.origin is Origin.MIXED
    assert fm.classification is Classification.INTERNAL
    assert fm.created == date(2026, 10, 18)
    assert fm.domain == ["D2", "D3"]
    assert fm.consistency_issues() == []
    assert fm.extra_fields == {}


def test_defaults_minimal() -> None:
    fm = Frontmatter.model_validate(
        {"id": "20261018-0001-x", "type": "fleeting", "created": "2026-10-18"}
    )
    assert fm.status is Status.DRAFT
    assert fm.origin is Origin.HUMAN
    assert fm.classification is Classification.INTERNAL
    assert fm.share is False
    assert fm.domain == [] and fm.tags == [] and fm.source == []
    assert fm.reviewed is None


@pytest.mark.parametrize(
    "bad_id",
    [
        "wcet-budget",  # no date/time
        "2026101-0712-x",  # 7-digit date
        "20261018-0712-",  # empty slug
        "20261018-0712-Upper",  # uppercase slug
        "20261332-0712-x",  # month 13
        "20261018-2460-x",  # hour 24
        "20261018-0760-x",  # minute 60
    ],
)
def test_invalid_ids_rejected(bad_id: str) -> None:
    with pytest.raises(ValidationError):
        Frontmatter.model_validate({**BASE, "id": bad_id})


@pytest.mark.parametrize(
    "field,value",
    [
        ("type", "note"),
        ("status", "approved"),
        ("origin", "gpt"),
        ("confidence", "sure"),
        ("classification", "secret"),
    ],
)
def test_enum_fields_rejected(field: str, value: str) -> None:
    with pytest.raises(ValidationError) as ei:
        Frontmatter.model_validate({**BASE, field: value})
    assert field in str(ei.value)


def test_domain_id_pattern() -> None:
    with pytest.raises(ValidationError):
        Frontmatter.model_validate({**BASE, "domain": ["d2"]})
    with pytest.raises(ValidationError):
        Frontmatter.model_validate({**BASE, "domain": ["D2", "D2"]})


def test_scalar_promoted_to_list() -> None:
    fm = Frontmatter.model_validate({**BASE, "domain": "D1", "tags": "rtos", "source": "x"})
    assert fm.domain == ["D1"] and fm.tags == ["rtos"] and fm.source == ["x"]


def test_tag_pattern() -> None:
    with pytest.raises(ValidationError):
        Frontmatter.model_validate({**BASE, "tags": ["Has Space"]})
    assert Frontmatter.model_validate({**BASE, "tags": ["a/b_c-1"]}).tags == ["a/b_c-1"]


def test_extra_fields_allowed_and_preserved() -> None:
    fm = Frontmatter.model_validate({**BASE, "aliases": ["WCET"], "cssclasses": "wide"})
    assert fm.extra_fields == {"aliases": ["WCET"], "cssclasses": "wide"}


def test_missing_required() -> None:
    with pytest.raises(ValidationError) as ei:
        Frontmatter.model_validate({"type": "evergreen"})
    msg = str(ei.value)
    assert "id" in msg and "created" in msg


def test_consistency_issues_are_not_parse_errors() -> None:
    fm = Frontmatter.model_validate(
        {**BASE, "classification": "confidential", "share": True, "reviewed": "2026-01-01"}
    )
    issues = fm.consistency_issues()
    assert any("confidential" in i for i in issues)
    assert any("reviewed" in i for i in issues)
    assert len(issues) == 2


def test_verified_requires_reviewed_and_moc_requires_domain() -> None:
    fm = Frontmatter.model_validate({**BASE, "reviewed": None})
    assert fm.consistency_issues() == ["status: verified 노트는 reviewed 날짜가 필요하다"]
    moc = Frontmatter.model_validate({**BASE, "type": "moc", "domain": []})
    assert any("moc" in i for i in moc.consistency_issues())


def test_publishable_rule() -> None:
    assert not Frontmatter.model_validate(BASE).is_publishable
    assert Frontmatter.model_validate({**BASE, "share": True}).is_publishable
    assert not Frontmatter.model_validate({**BASE, "share": True, "status": "draft"}).is_publishable
    assert not Frontmatter.model_validate(
        {**BASE, "share": True, "classification": "confidential"}
    ).is_publishable
    assert Frontmatter.model_validate({**BASE, "origin": "claude"}).is_ai_origin
