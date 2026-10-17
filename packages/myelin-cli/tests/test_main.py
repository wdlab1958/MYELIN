from myelin_cli.__main__ import main


def test_version_flag(capsys) -> None:
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.startswith("myelin ")


def test_unimplemented_is_fail_closed() -> None:
    assert main(["init"]) == 2
