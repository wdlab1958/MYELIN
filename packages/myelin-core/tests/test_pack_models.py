from typing import Any

import pytest
from pydantic import ValidationError

from myelin_core.errors import issues_from_validation
from myelin_core.pack import (
    Accent,
    InterviewBank,
    PackKind,
    PackManifest,
    TaxonomyFile,
)


def manifest(**over: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "pack": "me.side-research",
        "version": "1.0.0",
        "kind": "personal",
        "maintainer": "tester",
        "requires": ["myelin.core>=1.0"],
        "domains": [
            {"id": "LLM-SEC", "label": "R1", "name": "LLM 보안", "sub_mocs": ["공격", "방어"]}
        ],
    }
    data.update(over)
    return data


def locs(data: dict[str, Any]) -> list[str]:
    with pytest.raises(ValidationError) as info:
        PackManifest.model_validate(data)
    return [issue.loc for issue in issues_from_validation(info.value)]


def test_valid_manifest_defaults() -> None:
    m = PackManifest.model_validate(manifest())
    assert m.kind is PackKind.PERSONAL
    assert m.version_tuple == (1, 0, 0)
    (d,) = m.domains
    assert d.accent is Accent.VIOLET
    assert [t.value for t in d.note_types] == ["evergreen", "lesson"]
    assert d.classification_default.value == "internal"


def test_core_pack_may_have_no_domains() -> None:
    m = PackManifest.model_validate(
        manifest(kind="core", pack="myelin.core", requires=[], domains=[])
    )
    assert m.domains == []


@pytest.mark.parametrize(
    ("over", "loc"),
    [
        ({"pack": "Side Research"}, "pack"),
        ({"pack": "single"}, "pack"),
        ({"version": "1.0"}, "version"),
        ({"kind": "team"}, "kind"),
        ({"maintainer": "  "}, "maintainer"),
        ({"requires": ["bad req"]}, "requires"),
        ({"requires": ["myelin.core", "myelin.core>=1"]}, "requires"),
        ({"requires": ["me.side-research"]}, "requires"),
        ({"domains": []}, "domains"),
        ({"templates": "../tpl"}, "templates"),
        ({"templates": "/abs"}, "templates"),
        ({"author": "x"}, "author"),
    ],
)
def test_manifest_errors_have_field_locs(over: dict[str, Any], loc: str) -> None:
    assert loc in locs(manifest(**over))


def test_omitted_domains_rejected_for_non_core() -> None:
    data = manifest()
    del data["domains"]
    assert "domains" in locs(data)


@pytest.mark.parametrize(
    ("domain_over", "loc"),
    [
        ({"id": "llm sec"}, "domains[0].id"),
        ({"label": "TOO-LONG"}, "domains[0].label"),
        ({"sub_mocs": []}, "domains[0].sub_mocs"),
        ({"sub_mocs": ["a", "a"]}, "domains[0].sub_mocs"),
        ({"note_types": ["essay"]}, "domains[0].note_types[0]"),
        ({"note_types": []}, "domains[0].note_types"),
        ({"accent": "gold"}, "domains[0].accent"),
        ({"interview_bank": "..\\x.yaml"}, "domains[0].interview_bank"),
        ({"unknown": 1}, "domains[0].unknown"),
    ],
)
def test_domain_errors_have_field_locs(domain_over: dict[str, Any], loc: str) -> None:
    domain = {"id": "LLM-SEC", "name": "x", "sub_mocs": ["a"], **domain_over}
    assert loc in locs(manifest(domains=[domain]))


def test_duplicate_domain_ids() -> None:
    d = {"id": "X", "name": "x", "sub_mocs": ["a"]}
    assert "domains" in locs(manifest(domains=[d, dict(d)]))


def test_taxonomy_and_interview_models() -> None:
    tax = TaxonomyFile.model_validate({"terms": [{"term": "WCET", "aliases": ["최악 실행 시간"]}]})
    assert tax.terms[0].domain is None
    bank = InterviewBank.model_validate({"domains": {"X": [{"id": "q-1", "q": "왜?"}]}})
    assert bank.domains["X"][0].follow_ups == []
    for bad in [{"terms": []}, {"domains": {}}, {"domains": {"X": []}}]:
        with pytest.raises(ValidationError):
            (TaxonomyFile if "terms" in bad else InterviewBank).model_validate(bad)
