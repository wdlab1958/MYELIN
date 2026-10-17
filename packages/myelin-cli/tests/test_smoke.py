import pytest
from myelin_cli.main import main


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--version"]) == 0
    assert "myelin 0.0.1" in capsys.readouterr().out


def test_unimplemented_command_fails_closed() -> None:
    # 미구현 명령은 성공처럼 보이지 않고 0이 아닌 코드로 끝나야 한다 (fail-closed).
    assert main(["init"]) == 2
