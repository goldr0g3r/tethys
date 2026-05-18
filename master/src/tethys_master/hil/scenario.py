"""Pydantic v2 scenario loader for ``tethys-master demo <scenario>``.

A scenario JSON declares everything the master needs to drive a Phase 9
HIL demo end to end: the XCP transport target, the A2L fixture path, the
DAQ list, the CSV bridge wiring to the simulator-side plant, the
optional AES-128 seed-and-key path, and the standards traceability
string list rendered into the demo report.

The schema is documented in :file:`hil/scenarios/README.md`. The model
enforces:

* Filename / ``name`` field agreement is the caller's responsibility
  (the loader exposes ``Scenario.from_json_path`` so it can validate
  both).
* Profile invariants from :ref:`marine-profile-invariants.mdc` and
  :ref:`space-profile-invariants.mdc`: the marine profile MAY omit
  ``auth``; the space profile MUST declare ``auth.key_file``.
* Positive non-zero ``duration_s`` and bridge timing.

Cite: parent plan §8 (Phase 9 — HIL + MATLAB integration).
Cite: ADR-0006 (AES-128 seed-and-key) — drives the ``auth.key_file``
field semantics on the space profile.
Cite: ASAM MCD-2 MC v1.7 §1 — A2L file path field.
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

__all__ = [
    "Scenario",
    "ScenarioA2L",
    "ScenarioAuth",
    "ScenarioBridge",
    "ScenarioDaq",
    "ScenarioError",
    "ScenarioKind",
    "ScenarioPlant",
    "ScenarioTrace",
    "ScenarioTransport",
    "TransportKind",
    "load_scenario",
]


class ScenarioError(ValueError):
    """Raised when scenario JSON loading or validation fails."""


class Profile(str, Enum):
    MARINE = "marine"
    SPACE = "space"


class TransportKind(str, Enum):
    """Supported transports - mirrors :class:`tethys_master.transport.TransportId`."""

    LOOPBACK = "loopback"
    UDP = "udp"
    TCP = "tcp"
    SOCKETCAN = "socketcan"
    UART_SXI = "uart_sxi"


class ScenarioKind(str, Enum):
    """Reference-plant kinds; mirror :data:`tethys_sim.hil.SUPPORTED_SCENARIOS`."""

    MARINE_INJECTOR = "marine-common-rail-injector"
    SPACE_REACTION_WHEEL = "space-reaction-wheel"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ScenarioTransport(_Strict):
    """XCP transport target for the master."""

    kind: TransportKind
    target: str = Field(min_length=1)
    timeout_ms: Annotated[int, Field(gt=0, le=600_000)] = 1000


class ScenarioA2L(_Strict):
    """A2L fixture path (parsed by pya2l in Phase 3+; just opened by demo)."""

    path: str = Field(min_length=1)
    hash: str | None = Field(
        default=None,
        description="Optional SHA-256 hex of the A2L file at this commit.",
    )


class ScenarioDaq(_Strict):
    """DAQ list declaration for the master demo."""

    event_channel: Annotated[int, Field(ge=0, le=255)] = 0
    signals: list[str] = Field(min_length=1)
    rate_hz: Annotated[int, Field(gt=0, le=100_000)] = 1000


class ScenarioBridge(_Strict):
    """master_out.csv / plant_out.csv CSV-bridge wiring."""

    sample_time_s: Annotated[float, Field(gt=0.0, le=1.0)] = 0.001
    watchdog_timeout_s: Annotated[float, Field(gt=0.0, le=60.0)] = 0.05
    master_out: str = Field(min_length=1)
    plant_out: str = Field(min_length=1)


class ScenarioPlant(_Strict):
    """Plant declaration (kind + bridge wiring)."""

    kind: ScenarioKind
    bridge: ScenarioBridge


class ScenarioAuth(_Strict):
    """Seed-and-key wiring; ADR-0006."""

    key_file: str = Field(min_length=1)


class ScenarioTrace(_Strict):
    """Standards traceability strings rendered into the demo report."""

    standards: list[str] = Field(default_factory=list)


class Scenario(_Strict):
    """Top-level scenario model loaded from a ``hil/scenarios/<name>.json``."""

    name: str = Field(min_length=1)
    profile: Profile
    duration_s: Annotated[float, Field(gt=0.0, le=86_400.0)] = 5.0
    transport: ScenarioTransport
    a2l: ScenarioA2L
    daq: ScenarioDaq
    plant: ScenarioPlant
    auth: ScenarioAuth | None = None
    report_html: str = Field(min_length=1)
    trace: ScenarioTrace = Field(default_factory=ScenarioTrace)

    @model_validator(mode="after")
    def _validate_profile_invariants(self) -> Scenario:
        """Honour the marine/space profile rules.

        Space profile: ``auth.key_file`` is mandatory (16-byte AES-128
        per ADR-0006). The loader only checks that the field is
        populated; the actual key-file contents are read at demo time.

        Marine profile: ``auth`` is optional; when present, treated as
        the 4-byte simple challenge/response variant.

        Marine-injector / space-reaction-wheel plant kinds must match
        the corresponding profile.
        """
        if self.profile is Profile.SPACE and self.auth is None:
            msg = "space profile requires auth.key_file (ADR-0006)."
            raise ValueError(msg)
        plant_kind = self.plant.kind
        if self.profile is Profile.MARINE and plant_kind is not ScenarioKind.MARINE_INJECTOR:
            msg = f"marine profile + plant.kind={plant_kind.value!r} is incompatible."
            raise ValueError(msg)
        if self.profile is Profile.SPACE and plant_kind is not ScenarioKind.SPACE_REACTION_WHEEL:
            msg = f"space profile + plant.kind={plant_kind.value!r} is incompatible."
            raise ValueError(msg)
        return self

    @classmethod
    def from_json_path(cls, path: Path) -> Scenario:
        """Load + validate a scenario JSON.

        Also enforces the ``name == filename.stem`` discipline declared
        in :file:`hil/scenarios/README.md`.
        """
        if not path.is_file():
            msg = f"scenario JSON not found: {path}"
            raise ScenarioError(msg)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            msg = f"scenario JSON parse error in {path}: {exc}"
            raise ScenarioError(msg) from exc
        try:
            scenario = cls.model_validate(raw)
        except ValidationError as exc:
            msg = f"scenario JSON validation failed for {path}: {exc}"
            raise ScenarioError(msg) from exc
        if scenario.name != path.stem:
            msg = (
                f"scenario name {scenario.name!r} does not match filename "
                f"stem {path.stem!r}; see hil/scenarios/README.md."
            )
            raise ScenarioError(msg)
        return scenario

    def resolve_a2l(self, repo_root: Path) -> bytes | None:
        """Resolve + open the A2L file; return its bytes (or ``None`` if missing).

        Phase 3 will wire pya2l in here. Until then the demo just reads
        the file bytes to confirm the path resolves; absence is logged
        but does not fail the run (the scenario JSONs may point at
        files seeded later under :file:`hil/a2l/`).
        """
        path = repo_root / self.a2l.path
        if not path.is_file():
            return None
        return path.read_bytes()

    def resolve_key(self, repo_root: Path) -> bytes | None:
        """Resolve + read the 16-byte AES-128 key file (space profile)."""
        if self.auth is None:
            return None
        path = repo_root / self.auth.key_file
        if not path.is_file():
            return None
        return path.read_bytes()


def load_scenario(name_or_path: str, *, repo_root: Path) -> Scenario:
    """Resolve ``<name>`` to ``<repo_root>/hil/scenarios/<name>.json`` or use the literal path."""
    candidate = Path(name_or_path)
    if candidate.is_file():
        return Scenario.from_json_path(candidate.resolve())
    by_name = repo_root / "hil" / "scenarios" / f"{name_or_path}.json"
    if by_name.is_file():
        return Scenario.from_json_path(by_name)
    msg = f"scenario {name_or_path!r} not found; tried {candidate!s} and {by_name!s}."
    raise ScenarioError(msg)
