"""P0 smoke test: the package imports and exposes a version (Gate P=0: 빈 패키지 테스트 green)."""

import myelin_hub_api


def test_version() -> None:
    assert myelin_hub_api.__version__.startswith("0.")
