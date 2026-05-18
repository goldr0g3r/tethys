"""End-to-end tests for ``tethys-master demo --dry-run``.

Exercises the full F2 path without opening a transport:

* scenario JSON is loaded + validated by the Pydantic model,
* the CSV bridge files are created with the canonical headers,
* the Jinja2 HTML report is rendered + written to the scenario's
  ``report_html`` path,
* the CLI exits 0.

The tests seed a throwaway repo root with shortened scenario JSONs
(``duration_s=0.05``) so the CSV-bridge loop runs in well under one
second; the production JSONs (``duration_s=5.0``) are unchanged.

Cite: parent plan §8 (Phase 9 — HIL + MATLAB integration).
"""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from tethys_master.cli import cli

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIOS_DIR = REPO_ROOT / "hil" / "scenarios"


def _seed_repo(tmp_root: Path, *, duration_s: float = 0.05) -> None:
    """Copy + shrink the scenario JSONs into a throwaway repo root."""
    target_scenarios = tmp_root / "hil" / "scenarios"
    target_scenarios.mkdir(parents=True, exist_ok=True)
    for name in ("marine-common-rail-injector.json", "space-reaction-wheel.json"):
        payload = json.loads((SCENARIOS_DIR / name).read_text(encoding="utf-8"))
        payload["duration_s"] = duration_s
        (target_scenarios / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_dry_run_marine_writes_report(tmp_path: Path) -> None:
    """``tethys-master demo marine-common-rail-injector --dry-run`` exits 0 + writes report."""
    _seed_repo(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "demo",
            "marine-common-rail-injector",
            "--dry-run",
            "--repo-root",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    report_path = tmp_path / "hil" / "reports" / "marine-common-rail-injector-latest.html"
    assert report_path.is_file(), f"report missing at {report_path}; output={result.output}"
    html = report_path.read_text(encoding="utf-8")
    assert "marine-common-rail-injector" in html
    assert "Tethys demo report" in html
    assert "Standards trace" in html

    master_csv = tmp_path / "hil" / "master_out.csv"
    assert master_csv.is_file()
    lines = master_csv.read_text(encoding="ascii").splitlines()
    assert lines[0] == "sample_index,timestamp_us,command,setpoint,gain,enable,checksum"
    assert len(lines) >= 2


def test_dry_run_space_writes_report(tmp_path: Path) -> None:
    """The space-profile scenario also runs end-to-end in dry-run."""
    _seed_repo(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "demo",
            "space-reaction-wheel",
            "--dry-run",
            "--repo-root",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    report_path = tmp_path / "hil" / "reports" / "space-reaction-wheel-latest.html"
    assert report_path.is_file()
    html = report_path.read_text(encoding="utf-8")
    assert "space-reaction-wheel" in html
    assert "NIST FIPS-197" in html


def test_unknown_scenario_exits_nonzero(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "demo",
            "no-such-scenario",
            "--dry-run",
            "--repo-root",
            str(tmp_path),
        ],
    )
    assert result.exit_code != 0
    assert "no-such-scenario" in result.output or "not found" in result.output
