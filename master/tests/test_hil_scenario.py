"""Unit tests for the Phase 9 HIL scenario loader.

Validates that the Pydantic model accepts both committed scenarios
and rejects representative malformed payloads, plus that the profile
invariants from ``marine-profile-invariants.mdc`` and
``space-profile-invariants.mdc`` are enforced.

Cite: parent plan §8 (Phase 9 — HIL + MATLAB integration).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tethys_master.hil import (
    Scenario,
    ScenarioError,
    load_scenario,
)
from tethys_master.hil.scenario import Profile, ScenarioKind, TransportKind

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIOS_DIR = REPO_ROOT / "hil" / "scenarios"


class TestCommittedScenarios:
    def test_marine_loads(self) -> None:
        scenario = Scenario.from_json_path(SCENARIOS_DIR / "marine-common-rail-injector.json")
        assert scenario.name == "marine-common-rail-injector"
        assert scenario.profile is Profile.MARINE
        assert scenario.plant.kind is ScenarioKind.MARINE_INJECTOR
        assert scenario.transport.kind is TransportKind.UDP
        assert scenario.auth is None
        assert scenario.duration_s > 0
        assert scenario.plant.bridge.sample_time_s > 0
        assert scenario.plant.bridge.watchdog_timeout_s >= scenario.plant.bridge.sample_time_s
        assert "ASAM XCP 1.4" in " ".join(scenario.trace.standards)

    def test_space_loads(self) -> None:
        scenario = Scenario.from_json_path(SCENARIOS_DIR / "space-reaction-wheel.json")
        assert scenario.name == "space-reaction-wheel"
        assert scenario.profile is Profile.SPACE
        assert scenario.plant.kind is ScenarioKind.SPACE_REACTION_WHEEL
        assert scenario.transport.kind is TransportKind.UART_SXI
        assert scenario.auth is not None
        assert scenario.auth.key_file.startswith("hil/keys/")

    def test_load_by_name(self) -> None:
        scenario = load_scenario("marine-common-rail-injector", repo_root=REPO_ROOT)
        assert scenario.name == "marine-common-rail-injector"

    def test_load_unknown_scenario_raises(self) -> None:
        with pytest.raises(ScenarioError, match="not found"):
            load_scenario("does-not-exist", repo_root=REPO_ROOT)


class TestProfileInvariants:
    def test_space_without_auth_rejected(self, tmp_path: Path) -> None:
        """Per ADR-0006 + space-profile-invariants.mdc, space MUST declare auth.key_file."""
        bad = tmp_path / "space-bad.json"
        payload = json.loads((SCENARIOS_DIR / "space-reaction-wheel.json").read_text(encoding="utf-8"))
        payload["auth"] = None
        bad.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ScenarioError, match="auth.key_file"):
            Scenario.from_json_path(bad.rename(tmp_path / "space-reaction-wheel.json"))

    def test_marine_with_space_plant_rejected(self, tmp_path: Path) -> None:
        """Marine profile + space-reaction-wheel plant is incompatible."""
        bad = tmp_path / "marine-bad.json"
        payload = json.loads((SCENARIOS_DIR / "marine-common-rail-injector.json").read_text(encoding="utf-8"))
        payload["plant"]["kind"] = "space-reaction-wheel"
        bad.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ScenarioError, match="incompatible"):
            Scenario.from_json_path(bad.rename(tmp_path / "marine-common-rail-injector.json"))


class TestNameFilenameDiscipline:
    def test_name_must_match_filename_stem(self, tmp_path: Path) -> None:
        bad = tmp_path / "marine-common-rail-injector.json"
        payload = json.loads((SCENARIOS_DIR / "marine-common-rail-injector.json").read_text(encoding="utf-8"))
        payload["name"] = "wrong-name"
        bad.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ScenarioError, match="does not match filename stem"):
            Scenario.from_json_path(bad)


class TestSchemaRejections:
    def test_missing_required_field(self, tmp_path: Path) -> None:
        bad = tmp_path / "marine-common-rail-injector.json"
        payload = json.loads((SCENARIOS_DIR / "marine-common-rail-injector.json").read_text(encoding="utf-8"))
        payload.pop("transport")
        bad.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ScenarioError, match="validation failed"):
            Scenario.from_json_path(bad)

    def test_negative_duration_rejected(self, tmp_path: Path) -> None:
        bad = tmp_path / "marine-common-rail-injector.json"
        payload = json.loads((SCENARIOS_DIR / "marine-common-rail-injector.json").read_text(encoding="utf-8"))
        payload["duration_s"] = -1.0
        bad.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ScenarioError, match="validation failed"):
            Scenario.from_json_path(bad)

    def test_extra_field_rejected(self, tmp_path: Path) -> None:
        """``model_config = ConfigDict(extra='forbid')`` keeps the schema tight."""
        bad = tmp_path / "marine-common-rail-injector.json"
        payload = json.loads((SCENARIOS_DIR / "marine-common-rail-injector.json").read_text(encoding="utf-8"))
        payload["surprise_field"] = "should be rejected"
        bad.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ScenarioError, match="validation failed"):
            Scenario.from_json_path(bad)

    def test_invalid_json_rejected(self, tmp_path: Path) -> None:
        bad = tmp_path / "broken.json"
        bad.write_text("not really json {", encoding="utf-8")
        with pytest.raises(ScenarioError, match="parse error"):
            Scenario.from_json_path(bad)


class TestResolveHelpers:
    def test_resolve_a2l_returns_none_for_missing(self, tmp_path: Path) -> None:
        scenario = Scenario.from_json_path(SCENARIOS_DIR / "marine-common-rail-injector.json")
        assert scenario.resolve_a2l(tmp_path) is None

    def test_resolve_a2l_returns_bytes_when_present(self, tmp_path: Path) -> None:
        scenario = Scenario.from_json_path(SCENARIOS_DIR / "marine-common-rail-injector.json")
        a2l_path = tmp_path / scenario.a2l.path
        a2l_path.parent.mkdir(parents=True, exist_ok=True)
        a2l_path.write_bytes(b"; A2L stub for tests\n")
        result = scenario.resolve_a2l(tmp_path)
        assert result is not None
        assert b"A2L stub" in result

    def test_resolve_key_returns_none_when_no_auth(self, tmp_path: Path) -> None:
        scenario = Scenario.from_json_path(SCENARIOS_DIR / "marine-common-rail-injector.json")
        assert scenario.resolve_key(tmp_path) is None

    def test_resolve_key_returns_bytes_when_present(self, tmp_path: Path) -> None:
        scenario = Scenario.from_json_path(SCENARIOS_DIR / "space-reaction-wheel.json")
        assert scenario.auth is not None
        key_path = tmp_path / scenario.auth.key_file
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_bytes(b"\x00" * 16)
        result = scenario.resolve_key(tmp_path)
        assert result == b"\x00" * 16
