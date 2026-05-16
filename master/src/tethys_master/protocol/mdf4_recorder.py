"""Live DAQ -> MDF4 recorder backed by asammdf.

Wraps a single :class:`asammdf.MDF` instance and accepts decoded
:class:`tethys_master.protocol.daq.DaqSample` records via
:meth:`Mdf4Recorder.feed_sample`. Channel naming convention:

    daq{daq_list_num}_odt{odt_num}_entry{entry_idx}_{signal_name}

Or, when the caller binds A2L MEASUREMENT names via
:meth:`Mdf4Recorder.bind_signal`, the bare signal name is used.

asammdf is an LGPL dependency that ships in the master ``[gui]`` extras
(see ``master/pyproject.toml``). The recorder lazy-imports it so the
core protocol module remains importable in environments without the GUI
extras installed (CLI-only users + Phase 1/2 tests).

The MDF4-roundtrip acceptance test in
``master/tests/test_mdf4_recorder.py`` is the third-party-reader proxy
for the parent §8 Phase 3 acceptance ("MDF4 opens in Vector Free MDF
Viewer"): we use a fresh asammdf instance to reopen the file written by
the recorder and assert the channel set + sample counts agree.

Cite: parent plan §8 Phase 3 (asammdf MDF4 logger)
Cite: ASAM MDF v4 (Standard for measurement data file format)
Cite: ADR-0010 row 2 (DAQ_GAP MDF4 annotation contract)
Trace: docs/traceability.csv row TETHYS-DES-0080 (lands at PR-10)
"""

from __future__ import annotations

import struct
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tethys_master.logging_setup import get_logger

if TYPE_CHECKING:
    from tethys_master.protocol.daq import DaqSample

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class SignalBinding:
    """Maps one slice of an ODT payload to a named MDF4 channel.

    ``byte_offset`` is the offset within the ODT payload (after the
    optional 4-byte timestamp prefix has been stripped by the receive
    loop). ``struct_format`` is a single ``struct``-module spec like
    ``"<f"`` (LE float32) or ``"<H"`` (LE uint16).
    """

    name: str
    daq_list_num: int
    odt_num: int
    byte_offset: int
    struct_format: str
    unit: str = ""


@dataclass(slots=True)
class _ChannelBuffer:
    name: str
    unit: str
    times: list[float]
    values: list[float]


class Mdf4Recorder:
    """Buffer + flush decoded DAQ samples to an MDF4 (.mf4) file.

    Typical lifecycle:

    .. code-block:: python

        recorder = Mdf4Recorder()
        recorder.bind_signal(SignalBinding("engine_rpm", 0, 0, 0, "<f"))
        recorder.bind_signal(SignalBinding("coolant_c", 0, 0, 4, "<h"))
        recorder.start()
        # ... wire feed_sample() into the DaqReceiveLoop's on_sample ...
        recorder.feed_sample(sample)
        recorder.stop()
        recorder.save(Path("session.mf4"))
    """

    def __init__(self) -> None:
        self._bindings: list[SignalBinding] = []
        self._channels: dict[str, _ChannelBuffer] = {}
        self._sample_count: int = 0
        self._t0_us: int | None = None
        self._started: bool = False

    # ---- Configuration ----------------------------------------------

    def bind_signal(self, binding: SignalBinding) -> None:
        if binding.name in self._channels:
            return
        self._bindings.append(binding)
        self._channels[binding.name] = _ChannelBuffer(
            name=binding.name, unit=binding.unit, times=[], values=[]
        )

    def bind_signals(self, bindings: Iterable[SignalBinding]) -> None:
        for binding in bindings:
            self.bind_signal(binding)

    @property
    def channel_names(self) -> tuple[str, ...]:
        return tuple(self._channels)

    @property
    def sample_count(self) -> int:
        return self._sample_count

    # ---- Lifecycle ---------------------------------------------------

    def start(self) -> None:
        if self._started:
            return
        for ch in self._channels.values():
            ch.times.clear()
            ch.values.clear()
        self._sample_count = 0
        self._t0_us = None
        self._started = True
        logger.info("mdf4.recorder.start", channels=len(self._channels))

    def stop(self) -> None:
        self._started = False
        logger.info(
            "mdf4.recorder.stop",
            channels=len(self._channels),
            samples=self._sample_count,
        )

    # ---- Sample ingestion -------------------------------------------

    def feed_sample(self, sample: DaqSample) -> None:
        """Decode every binding that matches ``sample`` and append to the buffer."""
        if not self._started:
            return
        ts_us = sample.timestamp_us if sample.timestamp_us is not None else 0
        if self._t0_us is None:
            self._t0_us = ts_us
        t_seconds = max(0, ts_us - self._t0_us) / 1_000_000.0
        for binding in self._bindings:
            if binding.daq_list_num != sample.daq_list_num:
                continue
            if binding.odt_num != sample.odt_num:
                continue
            need = struct.calcsize(binding.struct_format)
            end = binding.byte_offset + need
            if end > len(sample.payload):
                continue
            value = struct.unpack_from(
                binding.struct_format, sample.payload, binding.byte_offset
            )[0]
            ch = self._channels[binding.name]
            ch.times.append(t_seconds)
            ch.values.append(float(value))
        self._sample_count += 1

    def feed_samples(self, samples: Iterable[DaqSample]) -> None:
        for s in samples:
            self.feed_sample(s)

    # ---- Persistence -------------------------------------------------

    def save(self, path: str | Path) -> Path:
        """Write the buffered channels to an MDF4 file.

        :raises ImportError: when asammdf is not installed (install via
                             ``master[gui]`` extras).
        """
        path = Path(path)
        if not self._channels:
            msg = "Mdf4Recorder.save: no channels bound"
            raise ValueError(msg)
        mdf = _build_mdf(self._channels.values())
        mdf.save(path, overwrite=True)
        logger.info("mdf4.recorder.saved", path=str(path), samples=self._sample_count)
        return path

    @staticmethod
    def reopen(path: str | Path) -> Mdf4ReopenResult:
        """Re-read an MDF4 file and return its channel set + sample counts.

        Used by the round-trip acceptance test: every file written via
        :meth:`save` must re-open in a fresh asammdf instance with the
        same channel set + the same sample count per channel.
        """
        path = Path(path)
        mdf = _import_asammdf().MDF(str(path))
        channels: dict[str, int] = {}
        for ch_name in mdf.channels_db:
            if ch_name in {"t", "time", "TIMESTAMP"}:
                continue
            try:
                signal = mdf.get(ch_name)
            except Exception:  # pragma: no cover - asammdf-internal
                continue
            samples_arr = getattr(signal, "samples", None)
            if samples_arr is None:
                continue
            channels[ch_name] = len(samples_arr)
        mdf.close()
        return Mdf4ReopenResult(path=path, channels=channels)


@dataclass(frozen=True, slots=True)
class Mdf4ReopenResult:
    path: Path
    channels: dict[str, int]

    @property
    def channel_names(self) -> tuple[str, ...]:
        return tuple(sorted(self.channels))

    @property
    def total_samples(self) -> int:
        return sum(self.channels.values())


# ---- asammdf bridge (lazy import) ----------------------------------


def _import_asammdf() -> Any:
    try:
        import asammdf
    except ImportError as exc:  # pragma: no cover - environment dependent
        msg = (
            "asammdf is required for MDF4 recording / playback. "
            "Install it via `pip install tethys-master[gui]` "
            "(it ships with the gui optional-dependencies bundle)."
        )
        raise ImportError(msg) from exc
    return asammdf


def _build_mdf(channels: Iterable[_ChannelBuffer]) -> Any:
    """Build an :class:`asammdf.MDF` from buffered channel data."""
    asammdf = _import_asammdf()
    import numpy as np

    mdf = asammdf.MDF(version="4.10")
    signals: list[Any] = []
    for ch in channels:
        if not ch.times:
            continue
        ts = np.asarray(ch.times, dtype=np.float64)
        vs = np.asarray(ch.values, dtype=np.float64)
        signals.append(
            asammdf.Signal(
                samples=vs,
                timestamps=ts,
                name=ch.name,
                unit=ch.unit,
            )
        )
    if signals:
        mdf.append(signals)
    return mdf


def write_mdf4(
    path: str | Path,
    *,
    channels: Sequence[_ChannelBuffer],
) -> Path:
    """Module-level convenience: write a one-shot MDF4 file from buffered channels.

    Wraps :meth:`Mdf4Recorder.save` for callers that already have the
    channel buffers in hand and don't need the full recorder lifecycle.
    """
    mdf = _build_mdf(channels)
    mdf.save(str(path), overwrite=True)
    return Path(path)


__all__ = [
    "Mdf4ReopenResult",
    "Mdf4Recorder",
    "SignalBinding",
    "write_mdf4",
]
