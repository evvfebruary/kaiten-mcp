import json

import pytest

from kaiten_mcp.checks.cli import main


def test_explicit_live_without_configuration_fails(tmp_path):
    with pytest.raises(SystemExit) as error:
        main(["live", "--output", str(tmp_path)])
    assert error.value.code == 1
    result = json.loads((tmp_path / "report.json").read_text())
    assert result["live"]["status"] == "not_configured"
    assert (tmp_path / "checks.xml").is_file()


def test_docs_source_failure_does_not_overwrite_baseline(tmp_path, monkeypatch):
    baseline = tmp_path / "baseline.json"
    baseline.write_text('{"original": true}')

    def fail():
        raise ValueError("markup changed")

    monkeypatch.setattr("kaiten_mcp.checks.cli.fetch_snapshot", fail)
    with pytest.raises(SystemExit) as error:
        main(["docs", "--baseline", str(baseline), "--output", str(tmp_path / "reports")])
    assert error.value.code == 1
    assert baseline.read_text() == '{"original": true}'
    result = json.loads((tmp_path / "reports/report.json").read_text())
    assert result["docs"]["status"] == "source_error"
