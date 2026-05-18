"""Tethys master HIL helpers (Phase 9 — parent plan §8).

The :mod:`tethys_master.hil` package owns the master side of the
hardware-in-the-loop bench: the declarative scenario JSON loader, the
CSV bridge driver that the ``tethys-master demo`` CLI uses, and the
Jinja2 HTML demo-report renderer.

The simulator-side reference plant (``tethys_sim.hil.reference_plant``)
is independent of this package; the two share file paths via the JSON
scenarios under :file:`hil/scenarios/`.

Cite: parent plan §8 (Phase 9 — HIL + MATLAB integration);
:ref:`marine-profile-invariants.mdc` + :ref:`space-profile-invariants.mdc`
(scenario field constraints honoured by the loader).
"""

from __future__ import annotations

from tethys_master.hil.scenario import (
    Profile,
    Scenario,
    ScenarioA2L,
    ScenarioAuth,
    ScenarioBridge,
    ScenarioDaq,
    ScenarioError,
    ScenarioKind,
    ScenarioPlant,
    ScenarioTrace,
    ScenarioTransport,
    TransportKind,
    load_scenario,
)

__all__ = [
    "Profile",
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
