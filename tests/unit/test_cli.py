import pytest

from budget_cli.main import main
from budget_core import APP_NAME, __version__


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"{APP_NAME} {__version__}"


def test_no_args_succeeds() -> None:
    assert main([]) == 0
