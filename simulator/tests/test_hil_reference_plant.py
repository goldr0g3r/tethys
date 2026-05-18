"""Unit tests for the pure-Python reference plant (F3).

Covers the acceptance criteria listed in
``.cursor/plans/implement-pending-followups.plan.md`` §AC-F3-*:

* header validation + schema-mismatch refusal,
* watchdog timeout zero-order-hold,
* idempotency of repeat reads,
* marine first-order step-response monotonicity,
* space second-order non-zero state after one tick.

The tests drive synthetic ``master_out.csv`` files in temporary
directories so the live ``hil/master_out.csv`` is never touched.
"""

from __future__ import annotations

import json
import zlib
from itertools import pairwise
from pathlib import Path

import pytest

from tethys_sim.hil.reference_plant import (
    MASTER_OUT_HEADER,
    PLANT_OUT_HEADER,
    BridgeSchemaError,
    PlantScenario,
    ReferencePlant,
    _row_checksum,
)

_BRIDGE_REL = Path("hil")


def _scenario_json(
    repo_root: Path,
    *,
    kind: str,
    sample_time_s: float = 0.001,
    watchdog_timeout_s: float = 0.5,
) -> Path:
    """Write a minimal scenario JSON the reference plant can parse."""
    scenarios_dir = repo_root / "hil" / "scenarios"
    scenarios_dir.mkdir(parents=True, exist_ok=True)
    name = "test-" + kind
    payload = {
        "name": name,
        "profile": "marine" if "marine" in kind else "space",
        "duration_s": 0.01,
        "plant": {
            "kind": kind,
            "bridge": {
                "sample_time_s": sample_time_s,
                "watchdog_timeout_s": watchdog_timeout_s,
                "master_out": str(_BRIDGE_REL / "master_out.csv"),
                "plant_out": str(_BRIDGE_REL / "plant_out.csv"),
            },
        },
    }
    path = scenarios_dir / f"{name}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_master_rows(repo_root: Path, rows: list[tuple[int, int, float, float, float, int]]) -> Path:
    """Write a master_out.csv with valid checksums; return the path."""
    master_path = repo_root / "hil" / "master_out.csv"
    master_path.parent.mkdir(parents=True, exist_ok=True)
    with master_path.open("w", encoding="ascii", newline="\n") as fh:
        fh.write(",".join(MASTER_OUT_HEADER) + "\n")
        for idx, ts_us, command, setpoint, gain, enable in rows:
            fields = (
                str(idx),
                str(ts_us),
                f"{command:.6f}",
                f"{setpoint:.6f}",
                f"{gain:.6f}",
                str(enable),
            )
            checksum = _row_checksum(fields)
            fh.write(",".join((*fields, str(checksum))) + "\n")
    return master_path


def _read_plant_rows(repo_root: Path) -> list[list[str]]:
    plant_path = repo_root / "hil" / "plant_out.csv"
    if not plant_path.exists():
        return []
    return [line.split(",") for line in plant_path.read_text(encoding="ascii").splitlines()]


class TestPlantScenarioLoader:
    def test_loads_marine_scenario(self, tmp_path: Path) -> None:
        scenario_path = _scenario_json(tmp_path, kind="marine-common-rail-injector")
        scenario = PlantScenario.from_json_file(scenario_path)
        assert scenario.name.endswith("marine-common-rail-injector")
        assert scenario.kind == "marine-common-rail-injector"
        assert scenario.sample_time_s == pytest.approx(0.001)
        assert scenario.watchdog_timeout_s == pytest.approx(0.5)

    def test_loads_space_scenario(self, tmp_path: Path) -> None:
        scenario_path = _scenario_json(tmp_path, kind="space-reaction-wheel")
        scenario = PlantScenario.from_json_file(scenario_path)
        assert scenario.kind == "space-reaction-wheel"

    def test_rejects_unknown_kind(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text(
            json.dumps(
                {
                    "name": "bad",
                    "profile": "marine",
                    "plant": {
                        "kind": "no-such-plant",
                        "bridge": {
                            "sample_time_s": 0.001,
                            "watchdog_timeout_s": 0.5,
                            "master_out": "hil/master_out.csv",
                            "plant_out": "hil/plant_out.csv",
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(BridgeSchemaError, match="reference plant supports"):
            PlantScenario.from_json_file(bad)

    def test_rejects_missing_fields(self, tmp_path: Path) -> None:
        bad = tmp_path / "missing.json"
        bad.write_text(json.dumps({"name": "x", "plant": {"kind": "marine-common-rail-injector"}}), encoding="utf-8")
        with pytest.raises(BridgeSchemaError, match="missing required"):
            PlantScenario.from_json_file(bad)

    def test_rejects_non_positive_times(self, tmp_path: Path) -> None:
        bad = tmp_path / "neg.json"
        bad.write_text(
            json.dumps(
                {
                    "name": "x",
                    "plant": {
                        "kind": "marine-common-rail-injector",
                        "bridge": {
                            "sample_time_s": 0.0,
                            "watchdog_timeout_s": 0.5,
                            "master_out": "hil/master_out.csv",
                            "plant_out": "hil/plant_out.csv",
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(BridgeSchemaError, match="sample_time_s"):
            PlantScenario.from_json_file(bad)


class TestHeaderValidation:
    def test_plant_out_header_is_canonical(self, tmp_path: Path) -> None:
        scenario_path = _scenario_json(tmp_path, kind="marine-common-rail-injector")
        scenario = PlantScenario.from_json_file(scenario_path)
        runner = ReferencePlant(scenario, tmp_path)
        runner.open_plant_out()
        runner.close()
        rows = _read_plant_rows(tmp_path)
        assert tuple(rows[0]) == PLANT_OUT_HEADER

    def test_master_out_header_mismatch_refused(self, tmp_path: Path) -> None:
        scenario_path = _scenario_json(tmp_path, kind="marine-common-rail-injector")
        scenario = PlantScenario.from_json_file(scenario_path)
        master_path = tmp_path / "hil" / "master_out.csv"
        master_path.parent.mkdir(parents=True, exist_ok=True)
        master_path.write_text("not,the,right,header\n", encoding="ascii", newline="\n")
        runner = ReferencePlant(scenario, tmp_path)
        try:
            with pytest.raises(BridgeSchemaError, match="schema mismatch"):
                runner.run(duration_s=0.001)
        finally:
            runner.close()

    def test_missing_master_out_does_not_crash_first_step(self, tmp_path: Path) -> None:
        """A first tick before the master writes anything emits an ``init`` row."""
        scenario_path = _scenario_json(tmp_path, kind="marine-common-rail-injector")
        scenario = PlantScenario.from_json_file(scenario_path)
        runner = ReferencePlant(scenario, tmp_path)
        try:
            wrote = runner.step(now_s=0.0)
        finally:
            runner.close()
        assert wrote is True
        rows = _read_plant_rows(tmp_path)
        assert tuple(rows[0]) == PLANT_OUT_HEADER
        assert rows[1][4] == "init"


class TestWatchdog:
    def test_watchdog_holds_previous_command(self, tmp_path: Path) -> None:
        """No fresh master row beyond watchdog_timeout_s ⇒ ZOH + ``master_timeout`` event."""
        scenario_path = _scenario_json(
            tmp_path,
            kind="marine-common-rail-injector",
            sample_time_s=0.01,
            watchdog_timeout_s=0.05,
        )
        scenario = PlantScenario.from_json_file(scenario_path)
        _write_master_rows(tmp_path, [(0, 0, 1.0, 180.0, 0.0, 1)])
        runner = ReferencePlant(scenario, tmp_path)
        try:
            runner.step(now_s=0.0)
            for _i in range(10):
                runner.step(now_s=0.0)
            runner.step(now_s=1.0)
        finally:
            runner.close()
        rows = _read_plant_rows(tmp_path)
        events = [r[4] for r in rows[1:]]
        assert events.count("master_timeout") >= 1


class TestIdempotency:
    def test_repeat_reads_do_not_emit_extra_rows(self, tmp_path: Path) -> None:
        scenario_path = _scenario_json(tmp_path, kind="marine-common-rail-injector")
        scenario = PlantScenario.from_json_file(scenario_path)
        _write_master_rows(tmp_path, [(0, 0, 0.5, 180.0, 0.0, 1)])
        runner = ReferencePlant(scenario, tmp_path)
        try:
            assert runner.step(now_s=0.0) is True
            assert runner.step(now_s=0.0001) is False
            assert runner.step(now_s=0.0002) is False
        finally:
            runner.close()
        rows = _read_plant_rows(tmp_path)
        body = rows[1:]
        assert len(body) == 1, f"expected 1 plant row, got {len(body)}: {body}"


class TestMarineODE:
    def test_step_response_is_monotonic(self, tmp_path: Path) -> None:
        """Marine first-order pressure ODE rises monotonically for a held step.

        Feeds one master row per simulated tick so the plant integrates
        50 times (one master row -> one plant row per ``step``).
        """
        scenario_path = _scenario_json(tmp_path, kind="marine-common-rail-injector", sample_time_s=0.001)
        scenario = PlantScenario.from_json_file(scenario_path)
        runner = ReferencePlant(scenario, tmp_path)
        try:
            for i in range(50):
                _write_master_rows(tmp_path, [(j, j * 1000, 1.0, 1.5, 0.0, 1) for j in range(i + 1)])
                runner.step(now_s=i * 0.001)
        finally:
            runner.close()
        plant_rows = _read_plant_rows(tmp_path)[1:]
        meas = [float(r[2]) for r in plant_rows]
        assert len(meas) == 50
        for prev, cur in pairwise(meas):
            assert cur >= prev - 1e-12
        assert meas[-1] > meas[0]
        assert meas[-1] < 1.5

    def test_clamp_event_fires_when_command_above_range(self, tmp_path: Path) -> None:
        scenario_path = _scenario_json(tmp_path, kind="marine-common-rail-injector")
        scenario = PlantScenario.from_json_file(scenario_path)
        _write_master_rows(tmp_path, [(0, 0, 5.0, 180.0, 0.0, 1)])
        runner = ReferencePlant(scenario, tmp_path)
        try:
            runner.step(now_s=0.0)
        finally:
            runner.close()
        rows = _read_plant_rows(tmp_path)[1:]
        assert rows[0][4] == "clamp"


class TestSpaceODE:
    def test_second_order_state_advances(self, tmp_path: Path) -> None:
        """Space ODE produces non-zero speed + position after a positive torque step."""
        scenario_path = _scenario_json(tmp_path, kind="space-reaction-wheel", sample_time_s=0.001)
        scenario = PlantScenario.from_json_file(scenario_path)
        runner = ReferencePlant(scenario, tmp_path)
        try:
            for i in range(20):
                _write_master_rows(tmp_path, [(j, j * 1000, 0.5, 10.0, 0.0, 1) for j in range(i + 1)])
                runner.step(now_s=i * 0.001)
        finally:
            runner.close()
        plant_rows = _read_plant_rows(tmp_path)[1:]
        speeds = [float(r[2]) for r in plant_rows]
        positions = [float(r[3]) for r in plant_rows]
        assert len(speeds) == 20
        assert speeds[-1] > 0.0
        assert positions[-1] > 0.0
        for prev, cur in pairwise(speeds):
            assert cur >= prev - 1e-12


class TestChecksumGuard:
    def test_bad_checksum_row_is_dropped(self, tmp_path: Path) -> None:
        """A master row with the wrong checksum is skipped."""
        scenario_path = _scenario_json(tmp_path, kind="marine-common-rail-injector")
        scenario = PlantScenario.from_json_file(scenario_path)
        master_path = tmp_path / "hil" / "master_out.csv"
        master_path.parent.mkdir(parents=True, exist_ok=True)
        with master_path.open("w", encoding="ascii", newline="\n") as fh:
            fh.write(",".join(MASTER_OUT_HEADER) + "\n")
            fh.write("0,0,0.500000,180.000000,0.000000,1,0\n")
        runner = ReferencePlant(scenario, tmp_path)
        try:
            wrote = runner.step(now_s=0.0)
        finally:
            runner.close()
        assert wrote is True
        rows = _read_plant_rows(tmp_path)[1:]
        assert rows[0][4] == "init"


def test_row_checksum_is_crc32_zip() -> None:
    fields = ("0", "0", "1.000000", "0.000000", "0.000000", "1")
    expected = zlib.crc32(",".join(fields).encode("ascii")) & 0xFFFFFFFF
    assert _row_checksum(fields) == expected
