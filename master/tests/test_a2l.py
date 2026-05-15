"""Unit tests for the minimal A2L parser facade.

The tests cover three surfaces:

1. Inline ``A2L_MINIMAL`` string - quick smoke + error-path coverage.
2. The 3 checked-in fixtures under ``slave/tests/fixtures/`` (added by
   Worker D in PR #31, designed in coordination with this parser):
   trivial, realistic, edge_case_if_data. Each fixture documents in its
   header which parser features it stresses.
3. The :py:meth:`roundtrip` CLI entry point that the
   ``a2l-roundtrip.yml`` workflow drives.

Cite: ASAM MCD-2 MC v1.6 §4.4.10 CHARACTERISTIC + §4.4.18 MEASUREMENT
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tethys_master.protocol.a2l import (
    A2LDatatype,
    A2LFile,
    A2LParseError,
    CharacteristicType,
    to_a2l_string,
)
from tethys_master.protocol.a2l_roundtrip import roundtrip

# The fixtures live in slave/tests/fixtures/ (Worker D / PR #31).
FIXTURE_DIR = Path(__file__).resolve().parents[2] / "slave" / "tests" / "fixtures"

A2L_MINIMAL = """\
/begin PROJECT tethys_test "Tethys A2L round-trip fixture"
  /begin MODULE marine_demo "Marine profile demo signals"
    /begin MEASUREMENT
      engine_rpm
      "Engine RPM at the flywheel"
      UWORD
      rpm_conversion
      1
      0.5
      0.0
      8000.0
      ECU_ADDRESS 0x20001000
    /end MEASUREMENT
    /begin MEASUREMENT
      coolant_temp
      "Coolant temperature degC"
      SWORD
      degc_conversion
      1
      0.25
      -40.0
      125.0
      ECU_ADDRESS 0x20001004
      ECU_ADDRESS_EXTENSION 1
    /end MEASUREMENT
    /begin CHARACTERISTIC
      injector_duty_map
      "16x16 injector duty cycle lookup"
      MAP
      0x20002000
      INJECTOR_RL
      0.0
      pct_conversion
      0.0
      100.0
    /end CHARACTERISTIC
  /end MODULE
/end PROJECT
"""


class TestTokeniser:
    def test_loads_minimal(self) -> None:
        file = A2LFile.loads(A2L_MINIMAL)
        assert file.project_name == "tethys_test"
        assert file.project_long_identifier == "Tethys A2L round-trip fixture"
        assert file.module_name == "marine_demo"
        assert "engine_rpm" in file.measurements
        assert "coolant_temp" in file.measurements
        assert "injector_duty_map" in file.characteristics

    def test_strips_block_comments(self) -> None:
        text = A2L_MINIMAL.replace(
            "/begin PROJECT", "/* Header comment */\n/begin PROJECT"
        )
        file = A2LFile.loads(text)
        assert file.project_name == "tethys_test"

    def test_strips_line_comments(self) -> None:
        text = A2L_MINIMAL.replace(
            "engine_rpm\n",
            "engine_rpm  // signal name follows positional layout\n",
        )
        file = A2LFile.loads(text)
        assert "engine_rpm" in file.measurements


class TestMeasurement:
    def test_engine_rpm_fields(self) -> None:
        file = A2LFile.loads(A2L_MINIMAL)
        m = file.measurements["engine_rpm"]
        assert m.long_identifier == "Engine RPM at the flywheel"
        assert m.datatype == A2LDatatype.UWORD
        assert m.conversion == "rpm_conversion"
        assert m.resolution == 1
        assert m.accuracy == 0.5
        assert m.lower_limit == 0.0
        assert m.upper_limit == 8000.0
        assert m.address == 0x20001000
        assert m.address_extension == 0

    def test_optional_address_extension(self) -> None:
        file = A2LFile.loads(A2L_MINIMAL)
        m = file.measurements["coolant_temp"]
        assert m.address == 0x20001004
        assert m.address_extension == 1

    def test_unknown_datatype_raises(self) -> None:
        bad = A2L_MINIMAL.replace("UWORD", "FANCY_TYPE")
        with pytest.raises(A2LParseError, match="datatype"):
            A2LFile.loads(bad)


class TestCharacteristic:
    def test_injector_map_fields(self) -> None:
        file = A2LFile.loads(A2L_MINIMAL)
        c = file.characteristics["injector_duty_map"]
        assert c.characteristic_type == CharacteristicType.MAP
        assert c.address == 0x20002000
        assert c.record_layout == "INJECTOR_RL"
        assert c.maxdiff == 0.0
        assert c.conversion == "pct_conversion"
        assert c.lower_limit == 0.0
        assert c.upper_limit == 100.0

    def test_unknown_characteristic_type_raises(self) -> None:
        bad = A2L_MINIMAL.replace("MAP\n", "FANCY\n")
        with pytest.raises(A2LParseError, match="type"):
            A2LFile.loads(bad)


class TestErrors:
    def test_missing_project_raises(self) -> None:
        text = "/begin MODULE m \"x\"\n/end MODULE"
        with pytest.raises(A2LParseError, match="PROJECT"):
            A2LFile.loads(text)

    def test_missing_module_raises(self) -> None:
        text = '/begin PROJECT p "x"\n/end PROJECT'
        with pytest.raises(A2LParseError, match="MODULE"):
            A2LFile.loads(text)

    def test_truncated_measurement_raises(self) -> None:
        text = (
            '/begin PROJECT p "x"\n'
            '  /begin MODULE m "x"\n'
            "    /begin MEASUREMENT\n"
            "      foo\n"
            "    /end MEASUREMENT\n"
            "  /end MODULE\n"
            "/end PROJECT\n"
        )
        with pytest.raises(A2LParseError, match="MEASUREMENT"):
            A2LFile.loads(text)

    def test_unterminated_block_raises(self) -> None:
        text = (
            '/begin PROJECT p "x"\n'
            '  /begin MODULE m "x"\n'
            "    /begin MEASUREMENT\n"
            "      foo\n"
            "      bar\n"
            "  /end MODULE\n"
            "/end PROJECT\n"
        )
        with pytest.raises(A2LParseError, match="Unterminated"):
            A2LFile.loads(text)


class TestRoundTrip:
    def test_emit_then_parse_equals_original(self) -> None:
        original = A2LFile.loads(A2L_MINIMAL)
        emitted = to_a2l_string(original)
        re_parsed = A2LFile.loads(emitted)
        assert re_parsed == original

    def test_unknown_blocks_are_silently_skipped(self) -> None:
        text = A2L_MINIMAL.replace(
            "  /end MODULE",
            "    /begin COMPU_METHOD some_method\n"
            "      \"long\" RAT_FUNC \"%4.0\" \"rpm\"\n"
            "    /end COMPU_METHOD\n"
            "  /end MODULE",
        )
        file = A2LFile.loads(text)
        # Measurements and characteristics still parsed; COMPU_METHOD ignored.
        assert "engine_rpm" in file.measurements

    def test_roundtrip_cli_helper_succeeds_on_temp_fixture(self, tmp_path: Path) -> None:
        fixture = tmp_path / "demo.a2l"
        fixture.write_text(A2L_MINIMAL, encoding="utf-8")
        assert roundtrip(fixture) == 0

    def test_roundtrip_cli_helper_fails_on_garbage(self, tmp_path: Path) -> None:
        # Empty file -> parse error -> non-zero exit
        fixture = tmp_path / "empty.a2l"
        fixture.write_text("", encoding="utf-8")
        with pytest.raises(A2LParseError):
            roundtrip(fixture)


# ---- Fixture-driven tests (slave/tests/fixtures/*.a2l, owned by Worker D) ----


@pytest.mark.skipif(
    not (FIXTURE_DIR / "trivial.a2l").exists(),
    reason="A2L fixtures not present (Worker D's PR #31 must merge first).",
)
class TestTrivialFixture:
    @pytest.fixture
    def trivial(self) -> A2LFile:
        return A2LFile.load(FIXTURE_DIR / "trivial.a2l")

    def test_project_and_module(self, trivial: A2LFile) -> None:
        assert trivial.project_name == "tethys_trivial"
        assert trivial.module_name == "trivial_mod"

    def test_single_measurement(self, trivial: A2LFile) -> None:
        assert list(trivial.measurements) == ["sample_signal"]
        m = trivial.measurements["sample_signal"]
        assert m.datatype == A2LDatatype.UWORD
        assert m.address == 0x20000100
        assert m.upper_limit == 65535.0

    def test_single_characteristic(self, trivial: A2LFile) -> None:
        assert list(trivial.characteristics) == ["sample_constant"]
        c = trivial.characteristics["sample_constant"]
        assert c.characteristic_type == CharacteristicType.VALUE
        assert c.address == 0x20000200
        assert c.upper_limit == 100.0

    def test_roundtrip(self, trivial: A2LFile) -> None:
        re_parsed = A2LFile.loads(to_a2l_string(trivial))
        assert re_parsed == trivial

    def test_cli_roundtrip(self) -> None:
        assert roundtrip(FIXTURE_DIR / "trivial.a2l") == 0


@pytest.mark.skipif(
    not (FIXTURE_DIR / "realistic.a2l").exists(),
    reason="A2L fixtures not present (Worker D's PR #31 must merge first).",
)
class TestRealisticFixture:
    @pytest.fixture
    def realistic(self) -> A2LFile:
        return A2LFile.load(FIXTURE_DIR / "realistic.a2l")

    def test_size_matches_fixture_header(self, realistic: A2LFile) -> None:
        # Fixture header advertises 12 MEASUREMENT + 6 CHARACTERISTIC blocks.
        assert len(realistic.measurements) == 12
        assert len(realistic.characteristics) == 6

    def test_known_signals_present(self, realistic: A2LFile) -> None:
        # Spot-check the marine-engine signals the fixture documents.
        for required in ("engine_rpm", "coolant_temp", "fuel_rail_pressure"):
            assert required in realistic.measurements, required
        for required in ("injector_duty_map", "boost_target_curve", "idle_target_rpm"):
            assert required in realistic.characteristics, required

    def test_datatype_coverage(self, realistic: A2LFile) -> None:
        """Each of the supported primitive datatypes appears at least once."""
        used = {m.datatype for m in realistic.measurements.values()}
        # The realistic fixture uses UWORD, SWORD, UBYTE, FLOAT32_IEEE.
        assert A2LDatatype.UWORD in used
        assert A2LDatatype.SWORD in used
        assert A2LDatatype.UBYTE in used
        assert A2LDatatype.FLOAT32_IEEE in used

    def test_characteristic_types_coverage(self, realistic: A2LFile) -> None:
        kinds = {c.characteristic_type for c in realistic.characteristics.values()}
        # Realistic fixture exercises MAP, CURVE, VALUE, ASCII.
        assert CharacteristicType.MAP in kinds
        assert CharacteristicType.CURVE in kinds
        assert CharacteristicType.VALUE in kinds
        assert CharacteristicType.ASCII in kinds

    def test_roundtrip(self, realistic: A2LFile) -> None:
        re_parsed = A2LFile.loads(to_a2l_string(realistic))
        assert re_parsed == realistic

    def test_cli_roundtrip(self) -> None:
        assert roundtrip(FIXTURE_DIR / "realistic.a2l") == 0


@pytest.mark.skipif(
    not (FIXTURE_DIR / "edge_case_if_data.a2l").exists(),
    reason="A2L fixtures not present (Worker D's PR #31 must merge first).",
)
class TestEdgeCaseFixture:
    """Exercises _skip_block / _find_end recursion via deeply-nested IF_DATA."""

    @pytest.fixture
    def edge(self) -> A2LFile:
        return A2LFile.load(FIXTURE_DIR / "edge_case_if_data.a2l")

    def test_buried_signal_survives_skipped_neighbours(self, edge: A2LFile) -> None:
        assert "buried_signal" in edge.measurements
        m = edge.measurements["buried_signal"]
        assert m.datatype == A2LDatatype.SWORD
        assert m.address == 0x20000300

    def test_buried_characteristic_survives_nested_if_data(self, edge: A2LFile) -> None:
        assert "buried_constant" in edge.characteristics
        c = edge.characteristics["buried_constant"]
        assert c.characteristic_type == CharacteristicType.VALUE
        assert c.address == 0x20000400

    def test_unsupported_blocks_silently_skipped(self, edge: A2LFile) -> None:
        # COMPU_METHOD / COMPU_VTAB / RECORD_LAYOUT must not appear as
        # measurements or characteristics (the parser only recognises those
        # two block kinds today).
        for unsupported in ("identity_conv", "fault_vtab", "SCALAR_RL"):
            assert unsupported not in edge.measurements
            assert unsupported not in edge.characteristics

    def test_cli_roundtrip(self) -> None:
        # Round-trip projects onto the supported subset (IF_DATA / COMPU_*
        # are stripped by the canonical emitter); both sides agree.
        assert roundtrip(FIXTURE_DIR / "edge_case_if_data.a2l") == 0
