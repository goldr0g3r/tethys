"""Pure-Python reference plant for the Phase 9 HIL bench.

This module implements the Simulink-free alternative for the
``master_out.csv`` ↔ ``plant_out.csv`` CSV bridge documented under
:file:`hil/bridge/`. It runs two trivial plant scenarios:

* ``marine-common-rail-injector`` — first-order pressure ODE,
  ``dx/dt = (gain * command - x) / tau`` with ``gain=1.5`` and
  ``tau=0.050 s`` (50 ms time constant).
* ``space-reaction-wheel`` — second-order torque ODE,
  ``J * d2theta/dt2 + b * dtheta/dt = command`` with ``J=0.01 kg·m²``
  and ``b=0.05 N·m·s``. Integrated via explicit Euler.

Both scenarios honour the scenario JSON's
``plant.bridge.watchdog_timeout_s`` field: when no fresh master row
arrives within that window, the plant logs ``bridge.master.timeout``
and zero-order-holds the previous master command (the
``master_out.schema.md`` watchdog clause).

The module owns no XCP protocol code and no profile invariant logic, so
it does NOT carry a ``Cite:`` against an XCP / ECSS / IACS standard.
The parent plan citation below is the only mandatory reference.

Cite: parent plan §8 (Phase 9 — HIL + MATLAB integration); §9 (tooling
parity table — pure-Python equivalent for Vehicle Network Toolbox).
"""

from __future__ import annotations

import csv
import json
import time
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any

from tethys_master.logging_setup import get_logger

if TYPE_CHECKING:  # csv writer object has no public type alias in typeshed
    _CsvWriter = Any
else:
    _CsvWriter = Any

__all__ = [
    "SUPPORTED_SCENARIOS",
    "BridgeSchemaError",
    "PlantScenario",
    "ReferencePlant",
]


MASTER_OUT_HEADER = (
    "sample_index",
    "timestamp_us",
    "command",
    "setpoint",
    "gain",
    "enable",
    "checksum",
)
PLANT_OUT_HEADER = (
    "sample_index",
    "timestamp_us",
    "measurement",
    "plant_state",
    "event",
    "checksum",
)

SUPPORTED_SCENARIOS: tuple[str, ...] = (
    "marine-common-rail-injector",
    "space-reaction-wheel",
)


class BridgeSchemaError(ValueError):
    """Raised when ``master_out.csv`` does not match the canonical header."""


@dataclass(frozen=True, slots=True)
class PlantScenario:
    """Minimal scenario subset the reference plant needs.

    The master-side :mod:`tethys_master.hil.scenario` Pydantic model has a
    much richer field set (auth.key_file, transport, daq.signals, ...).
    The reference plant parses only the plant-side bridge subset to
    avoid a circular dep on the master package (it already imports
    :mod:`tethys_master.logging_setup`; pulling in the Pydantic model
    would couple every plant test to pydantic).
    """

    name: str
    kind: str
    sample_time_s: float
    watchdog_timeout_s: float
    master_out: Path
    plant_out: Path

    @classmethod
    def from_json_file(cls, path: Path) -> PlantScenario:
        """Load just the ``plant.{kind,bridge}`` subset from a scenario JSON.

        The JSON shape is documented in ``hil/scenarios/README.md``. We
        do not validate the full scenario here; the master-side loader
        (``tethys-master demo``) does that.
        """
        raw = json.loads(path.read_text(encoding="utf-8"))
        try:
            name = str(raw["name"])
            plant = raw["plant"]
            kind = str(plant["kind"])
            bridge = plant["bridge"]
            sample_time_s = float(bridge["sample_time_s"])
            watchdog_timeout_s = float(bridge["watchdog_timeout_s"])
            master_out = Path(str(bridge["master_out"]))
            plant_out = Path(str(bridge["plant_out"]))
        except (KeyError, TypeError, ValueError) as exc:
            msg = f"scenario {path} is missing required plant.bridge fields: {exc}"
            raise BridgeSchemaError(msg) from exc
        if kind not in SUPPORTED_SCENARIOS:
            msg = f"reference plant supports {SUPPORTED_SCENARIOS}; scenario kind={kind!r}"
            raise BridgeSchemaError(msg)
        if sample_time_s <= 0.0:
            msg = f"plant.bridge.sample_time_s must be > 0; got {sample_time_s}"
            raise BridgeSchemaError(msg)
        if watchdog_timeout_s <= 0.0:
            msg = f"plant.bridge.watchdog_timeout_s must be > 0; got {watchdog_timeout_s}"
            raise BridgeSchemaError(msg)
        return cls(
            name=name,
            kind=kind,
            sample_time_s=sample_time_s,
            watchdog_timeout_s=watchdog_timeout_s,
            master_out=master_out,
            plant_out=plant_out,
        )


def _row_checksum(fields: tuple[str, ...]) -> int:
    """CRC-32/ZIP of the joined fields (the schema's ``checksum`` rule)."""
    return zlib.crc32(",".join(fields).encode("ascii")) & 0xFFFFFFFF


class ReferencePlant:
    """Drive the master ↔ plant CSV bridge for the two demo scenarios.

    Lifecycle: caller invokes :meth:`step` repeatedly (or :meth:`run` to
    self-loop) until the scenario JSON's ``duration_s`` elapses.
    :meth:`step` is idempotent — re-reading the same ``master_out.csv``
    row produces no duplicate ``plant_out.csv`` row.

    The class does not own a clock; the caller passes ``now_s`` to
    :meth:`step` so unit tests can drive deterministic time. The CLI
    wrapper passes :func:`time.monotonic` for live runs.
    """

    def __init__(self, scenario: PlantScenario, repo_root: Path) -> None:
        self._scenario = scenario
        self._repo_root = repo_root
        self._logger = get_logger("tethys-sim.hil.reference_plant")
        self._last_consumed_index: int = -1
        self._last_master_command: float = 0.0
        self._last_master_seen_at_s: float | None = None
        self._sample_index: int = 0
        self._t0_s: float | None = None
        # Plant integrator state. Indexed by scenario kind.
        # marine-common-rail-injector: x (pressure-proxy integrator)
        # space-reaction-wheel: (dtheta/dt, theta)
        self._marine_x: float = 0.0
        self._space_speed: float = 0.0
        self._space_position: float = 0.0
        self._plant_out_writer: _CsvWriter | None = None
        self._plant_out_file: IO[str] | None = None

    @property
    def scenario(self) -> PlantScenario:
        return self._scenario

    @property
    def master_out_path(self) -> Path:
        return self._repo_root / self._scenario.master_out

    @property
    def plant_out_path(self) -> Path:
        return self._repo_root / self._scenario.plant_out

    @property
    def sample_index(self) -> int:
        return self._sample_index

    def open_plant_out(self) -> None:
        """Create or rewind ``plant_out.csv``; write the header row exactly once.

        Opens with ``newline=""`` (the recommended csv-aware mode) and an
        explicit ``lineterminator="\n"`` so the file is LF-only on every
        host (the schema bans CRLF).
        """
        path = self.plant_out_path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._plant_out_file = path.open("w", encoding="ascii", newline="")
        self._plant_out_writer = csv.writer(
            self._plant_out_file,
            lineterminator="\n",
            quoting=csv.QUOTE_MINIMAL,
        )
        self._plant_out_writer.writerow(PLANT_OUT_HEADER)
        self._plant_out_file.flush()

    def close(self) -> None:
        if self._plant_out_file is not None:
            self._plant_out_file.close()
            self._plant_out_file = None
            self._plant_out_writer = None

    def _verify_header(self) -> None:
        """Refuse to start when ``master_out.csv`` header is wrong."""
        path = self.master_out_path
        if not path.exists():
            return
        with path.open("r", encoding="ascii", newline="") as fh:
            reader = csv.reader(fh)
            try:
                header = tuple(next(reader))
            except StopIteration:
                return
        if header != MASTER_OUT_HEADER:
            msg = f"master_out.csv schema mismatch: expected {MASTER_OUT_HEADER}; observed {header}"
            self._logger.error(
                "bridge.schema.mismatch",
                expected=list(MASTER_OUT_HEADER),
                observed=list(header),
            )
            raise BridgeSchemaError(msg)

    def _read_fresh_master_rows(self) -> list[tuple[int, int, float, int]]:
        """Return ``(sample_index, timestamp_us, command, enable)`` tuples newer than the cursor."""
        path = self.master_out_path
        if not path.exists():
            return []
        fresh: list[tuple[int, int, float, int]] = []
        with path.open("r", encoding="ascii", newline="") as fh:
            reader = csv.reader(fh)
            try:
                header = tuple(next(reader))
            except StopIteration:
                return []
            if header != MASTER_OUT_HEADER:
                msg = f"master_out.csv schema mismatch: expected {MASTER_OUT_HEADER}; " f"observed {header}"
                raise BridgeSchemaError(msg)
            for raw in reader:
                if len(raw) != len(MASTER_OUT_HEADER):
                    continue
                idx = int(raw[0])
                if idx <= self._last_consumed_index:
                    continue
                ts_us = int(raw[1])
                command = float(raw[2])
                enable = int(raw[5])
                claimed_checksum = int(raw[6])
                computed = _row_checksum(tuple(raw[:6]))
                if computed != claimed_checksum:
                    self._logger.warning(
                        "bridge.master.checksum_fail",
                        sample_index=idx,
                        claimed=claimed_checksum,
                        computed=computed,
                    )
                    continue
                fresh.append((idx, ts_us, command, enable))
        return fresh

    def step(self, *, now_s: float) -> bool:
        """Read any fresh master rows, integrate the ODE, emit one plant row.

        Returns ``True`` if a plant row was written, ``False`` if the
        plant ran a watchdog tick (or the master_out file is missing).
        Idempotency: the method never re-emits a plant row for a master
        sample_index it has already serviced; rerunning :meth:`step`
        without a new master row only produces a fresh plant row if the
        watchdog clause fires (zero-order-hold).
        """
        if self._plant_out_writer is None:
            self.open_plant_out()
        if self._t0_s is None:
            self._t0_s = now_s

        fresh = self._read_fresh_master_rows()
        if fresh:
            for idx, _ts_us, command, enable in fresh:
                self._last_consumed_index = idx
                if enable:
                    self._last_master_command = command
                else:
                    self._last_master_command = 0.0
            self._last_master_seen_at_s = now_s
            event = "init" if self._sample_index == 0 else "ok"
        elif self._last_master_seen_at_s is None:
            # Pre-master: emit the canonical first row so the plant_out.csv
            # body always starts with an ``init`` sample (the schema's
            # event-tag rule), then wait for the first master row before
            # arming the watchdog.
            if self._sample_index != 0:
                return False
            event = "init"
        else:
            stale_s = now_s - self._last_master_seen_at_s
            if stale_s > self._scenario.watchdog_timeout_s:
                self._logger.warning(
                    "bridge.master.timeout",
                    scenario=self._scenario.name,
                    stale_s=stale_s,
                    last_command=self._last_master_command,
                )
                event = "master_timeout"
            else:
                return False

        measurement, state, clamped = self._integrate(self._last_master_command)
        if clamped:
            event = "clamp"
        ts_us = int((now_s - self._t0_s) * 1_000_000)
        idx_str = str(self._sample_index)
        ts_str = str(ts_us)
        meas_str = f"{measurement:.6f}"
        state_str = f"{state:.6f}"
        fields = (idx_str, ts_str, meas_str, state_str, event)
        checksum = _row_checksum(fields)
        assert self._plant_out_writer is not None
        self._plant_out_writer.writerow((*fields, str(checksum)))
        assert self._plant_out_file is not None
        self._plant_out_file.flush()
        self._sample_index += 1
        return True

    def _integrate(self, command: float) -> tuple[float, float, bool]:
        """Integrate one step of the chosen plant ODE.

        Returns ``(measurement, plant_state, clamped)``. ``clamped`` is
        ``True`` when the actuator command had to be saturated to fit
        the plant's physical envelope.
        """
        dt = self._scenario.sample_time_s
        if self._scenario.kind == "marine-common-rail-injector":
            clamped = False
            actuator = command
            if actuator < 0.0:
                actuator = 0.0
                clamped = True
            elif actuator > 1.0:
                actuator = 1.0
                clamped = True
            gain = 1.5
            tau = 0.050
            self._marine_x += (gain * actuator - self._marine_x) * (dt / tau)
            return self._marine_x, self._marine_x, clamped
        if self._scenario.kind == "space-reaction-wheel":
            clamped = False
            actuator = command
            if actuator < -1.0:
                actuator = -1.0
                clamped = True
            elif actuator > 1.0:
                actuator = 1.0
                clamped = True
            inertia = 0.01
            damping = 0.05
            accel = (actuator - damping * self._space_speed) / inertia
            self._space_speed += accel * dt
            self._space_position += self._space_speed * dt
            return self._space_speed, self._space_position, clamped
        msg = f"unsupported plant kind {self._scenario.kind!r}"
        raise BridgeSchemaError(msg)

    def run(
        self,
        *,
        duration_s: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> int:
        """Self-loop ``step`` until ``duration_s`` elapses; return rows written."""
        self._verify_header()
        if self._plant_out_writer is None:
            self.open_plant_out()
        t0 = clock()
        rows_written = 0
        try:
            while True:
                now_s = clock()
                if now_s - t0 >= duration_s:
                    break
                if self.step(now_s=now_s):
                    rows_written += 1
                next_tick = t0 + (self._sample_index + 1) * self._scenario.sample_time_s
                sleep_s = next_tick - clock()
                if sleep_s > 0.0:
                    time.sleep(sleep_s)
        finally:
            self.close()
        return rows_written
