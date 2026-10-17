from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from myelin_core.frontmatter import (
    Classification,
    Confidence,
    Frontmatter,
    NoteType,
    Origin,
    Status,
    id_change_issue,
)


def base(**over: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": "20261018-0712-wcet-budget",
        "type": "evergreen",
        "status": "draft",
        "origin": "human",
        "created": "2026-10-18",
    }
    data.update(over)
    return data


def test_minimal_valid_and_defaults() -> None:
    fm = Frontmatter.model_validate(base())
    assert fm.type is NoteType.EVERGREEN
    assert fm.status is Status.DRAFT
    assert fm.origin is Origin.HUMAN
    assert fm.confidence is Confidence.MEDIUM
    assert fm.classification is Classification.INTERNAL
    assert fm.share is False
    assert fm.domain == [] and fm.tags == [] and fm.source == []
    assert fm.created == date(2026, 10, 18)


def test_scalar_fields_become_lists() -> None:
    fm = Frontmatter.model_validate(base(domain="D2", source="[[Lit - X]]", tags=None))
    assert fm.domain == ["D2"]
    assert fm.source == ["[[Lit - X]]"]
    assert fm.tags == []


def test_tags_strip_hash_and_drop_empty() -> None:
    fm = Frontmatter.model_validate(base(tags=["#rtos", "control-loop", "#", " "]))
    assert fm.tags == ["rtos", "control-loop"]


def test_extra_fields_preserved() -> None:
    fm = Frontmatter.model_validate(base(type="lesson", era="1980s"))
    assert fm.model_extra == {"era": "1980s"}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", "wcet-budget"),
        ("id", "20261018-0712-WCET"),
        ("type", "essay"),
        ("status", "done"),
        ("origin", "gpt"),
        ("classification", "secret"),
        ("domain", ["d2"]),
        ("domain", ["D2", "D2"]),
        ("created", "yesterday"),
    ],
)
def test_invalid_values_rejected(field: str, value: Any) -> None:
    with pytest.raises(ValidationError):
        Frontmatter.model_validate(base(**{field: value}))


@pytest.mark.parametrize("missing", ["id", "type", "status", "origin", "created"])
def test_required_fields(missing: str) -> None:
    data = base()
    del data[missing]
    with pytest.raises(ValidationError):
        Frontmatter.model_validate(data)


def test_reviewed_before_created_rejected() -> None:
    with pytest.raises(ValidationError):
        Frontmatter.model_validate(base(reviewed="2026-10-01"))


def test_policy_share_confidential() -> None:
    ok = Frontmatter.model_validate(base(share=True, classification="internal"))
    assert ok.policy_issues() == []
    bad = Frontmatter.model_validate(base(share=True, classification="confidential"))
    (issue,) = bad.policy_issues()
    assert issue.loc == "share" and issue.code == "share_confidential"


def test_id_is_immutable() -> None:
    a = Frontmatter.model_validate(base())
    b = Frontmatter.model_validate(base(id="20261018-0712-other"))
    assert id_change_issue(a, a) is None
    issue = id_change_issue(a, b)
    assert issue is not None and issue.code == "id_changed"
