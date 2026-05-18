# HIL Simulink models

> Reserved slot for the Phase 9 Simulink plant models that close the
> loop with the on-target slave through `tethys-master demo`. The slot
> is empty today because Simulink requires a paid MATLAB licence — see
> the **Pure-Python alternative (recommended)** section below for the
> license-free path that works without MATLAB.

Parent plan section 8 (Phase 9 — HIL + MATLAB integration) reserves
this directory for two `.slx` models that, when a Simulink licence is
available, can replace the [`tethys_sim.hil.reference_plant`](../../simulator/src/tethys_sim/hil/reference_plant.py)
ODE integrator. The CSV bridge (see [`../bridge/`](../bridge/)) is the
common interface — Simulink reads the same `hil/master_out.csv` and
writes the same `hil/plant_out.csv` columns documented in
[`master_out.schema.md`](../bridge/master_out.schema.md) +
[`plant_out.schema.md`](../bridge/plant_out.schema.md).

## Pure-Python alternative (recommended)

The repository ships a **pure-Python reference plant** that exercises
the same CSV bridge end-to-end without Simulink, MATLAB, or any paid
license. This is the recommended option for:

- contributors who want to validate the master ↔ plant loop on a CI
  runner (Linux / Windows / macOS, free GitHub Actions tier);
- portfolio reviewers who want to reproduce the Phase 9 demo without
  installing the MATLAB Campus edition;
- anyone iterating on the master-side `demo` command before the
  Simulink models are written.

Run the marine demo in one terminal:

```powershell
# Drive the pure-Python reference plant against hil/scenarios/marine-common-rail-injector.json
uv run --project simulator tethys-sim plant --scenario marine-common-rail-injector
```

And the master tool in another:

```powershell
# Master side - drives master_out.csv and reads plant_out.csv every
# plant.bridge.sample_time_s; renders the HTML report at scenario.report_html.
uv run --project master tethys-master demo marine-common-rail-injector --dry-run
```

`--dry-run` exercises the bridge without opening the XCP transport so
no on-target slave or simulator slave is required. Drop the flag when
you have `tethys-sim serve` running in a third terminal (Phase 1
acceptance bench, see [`docs/runbooks/hil-bench-setup.md`](../../docs/runbooks/hil-bench-setup.md)).

The reference plant supports the two committed scenarios:

| Scenario | Plant kind | ODE |
| --- | --- | --- |
| `marine-common-rail-injector` | First-order pressure ODE. | `dx/dt = (gain * command - x) / tau`, `gain=1.5`, `tau=50 ms`. |
| `space-reaction-wheel` | Second-order torque ODE. | `J * d2theta/dt2 + b * dtheta/dt = command`, `J=0.01 kg·m²`, `b=0.05 N·m·s`. |

## When to migrate to Simulink

Open a Phase 9 PR + research note when:

- A Simulink licence (Campus / Academic / Standard / Professional) is
  available and the test bench needs hardware-grade plant dynamics;
- The demo recording (per [`docs/runbooks/demo-recording.md`](../../docs/runbooks/demo-recording.md))
  requires the Simulink Scope viewer for stakeholder consumption.

Simulink models go under this directory as `.slx` files. The companion
bridge block reads `hil/master_out.csv` and writes `hil/plant_out.csv`
on the schema specified in [`../bridge/`](../bridge/) — the CSV format
is the integration contract between Python and Simulink so the two are
interchangeable.

## Constraints

- Per [`.cursor/rules/free-tool-only.mdc`](../../.cursor/rules/free-tool-only.mdc),
  MATLAB **Vehicle Network Toolbox** is banned (paid add-on). Use the
  built-in `py.` interface to call `tethys-master` from MATLAB
  directly, or stay on the pure-Python alternative.
- The `.slx` files MUST be saved with `Save As → Save with model
  format (MDL)` if the team also wants version-control diffability;
  binary `.slx` files compress but do not diff.
- A2L fixtures referenced by the scenarios live under [`../a2l/`](../a2l/)
  (Phase 9 PR seeds them).

## Cross-references

- [`../bridge/master_out.schema.md`](../bridge/master_out.schema.md)
- [`../bridge/plant_out.schema.md`](../bridge/plant_out.schema.md)
- [`../scenarios/README.md`](../scenarios/README.md)
- [`../../simulator/src/tethys_sim/hil/reference_plant.py`](../../simulator/src/tethys_sim/hil/reference_plant.py)
- [`../../master/src/tethys_master/hil/scenario.py`](../../master/src/tethys_master/hil/scenario.py)
- [`../../docs/runbooks/hil-bench-setup.md`](../../docs/runbooks/hil-bench-setup.md)
- Parent plan §8 (Phase 9) + §9 (tooling parity table — MATLAB / Vehicle Network Toolbox row).
