import pytest

from budget_cli.main import main
from budget_core.selftest import run_selftest


def test_selftest_passes_in_a_working_install() -> None:
    assert run_selftest() == []


def test_cli_selftest(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["self-test"]) == 0
    assert "Self-test passed." in capsys.readouterr().out


def test_selftest_reports_failures_without_content(monkeypatch: pytest.MonkeyPatch) -> None:
    import budget_core.selftest as st

    def boom(_text: str, _field: str) -> float:
        raise RuntimeError("SECRETVALUE")

    monkeypatch.setattr(st, "parse_quantity", boom)
    failures = st.run_selftest()
    assert failures == ["RuntimeError during the self-test"]
