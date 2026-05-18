"""Simulator-side HIL helpers - pure-Python alternative to Simulink.

The :mod:`tethys_sim.hil` package implements the host-only side of the
Phase 9 hardware-in-the-loop bench (parent plan §8). It complements the
master-side :mod:`tethys_master.hil` package: the master writes
``hil/master_out.csv``, the simulator-side reference plant in this
package reads it, integrates a trivial ODE, and writes the result back
out to ``hil/plant_out.csv``.

The schemas live in :file:`hil/bridge/master_out.schema.md` +
:file:`hil/bridge/plant_out.schema.md`. The package intentionally
exports a tight surface so downstream callers (CLI + tests) stay
decoupled from the integrator details.

Cite: parent plan §8 Phase 9 (HIL + MATLAB integration); §9 (no Vehicle
Network Toolbox dependency - this module replaces the Simulink leg).
"""

from __future__ import annotations

from tethys_sim.hil.reference_plant import (
    SUPPORTED_SCENARIOS,
    BridgeSchemaError,
    PlantScenario,
    ReferencePlant,
)

__all__ = [
    "SUPPORTED_SCENARIOS",
    "BridgeSchemaError",
    "PlantScenario",
    "ReferencePlant",
]
