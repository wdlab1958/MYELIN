"""P0 smoke test: the package imports and exposes a version (Gate P=0: 빈 패키지 테스트 green)."""

import myelin_mcp


def test_version() -> None:
    assert myelin_mcp.__version__.startswith("0.")
