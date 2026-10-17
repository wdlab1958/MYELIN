import pytest

from myelin_core.versioning import parse_requirement, parse_version


def test_parse_version() -> None:
    assert parse_version("1.2.3") == (1, 2, 3)
    for bad in ["1.0", "v1.0.0", "1.0.0-beta", ""]:
        with pytest.raises(ValueError):
            parse_version(bad)


@pytest.mark.parametrize(
    ("req", "version", "ok"),
    [
        ("myelin.core", (0, 0, 1), True),
        ("myelin.core>=1.0", (1, 0, 0), True),
        ("myelin.core>=1.0", (0, 9, 9), False),
        ("myelin.core>=1.0,<2", (1, 9, 0), True),
        ("myelin.core>=1.0,<2", (2, 0, 0), False),
        ("myelin.core==1.2.3", (1, 2, 3), True),
        ("myelin.core!=1.2.3", (1, 2, 3), False),
        ("myelin.core>1", (1, 0, 1), True),
        ("myelin.core<=1.1", (1, 1, 0), True),
    ],
)
def test_requirement_satisfaction(req: str, version: tuple[int, int, int], ok: bool) -> None:
    assert parse_requirement(req).satisfied_by(version) is ok


def test_requirement_str_roundtrip() -> None:
    assert str(parse_requirement("org.x >= 1 , < 2.1")) == "org.x>=1.0.0,<2.1.0"


@pytest.mark.parametrize(
    "bad", ["", "core>=1", "myelin.core>=", "myelin.core~=1.0", "myelin.core>=a"]
)
def test_invalid_requirements(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_requirement(bad)
