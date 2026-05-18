# `hil/plant_out.csv` — bridge schema (plant → master)

> The HIL bridge between the plant runner (`tethys-sim plant` for the
> pure-Python alternative; Simulink for the Phase 9 closed-loop bench)
> and `tethys-master demo <scenario>` (master side). The plant writes
> one row per `plant.bridge.sample_time_s` tick of the scenario; the
> master reads the **fresh tail** of the file every loop iteration.
>
> Parent plan section 8 (Phase 9 — HIL + MATLAB integration).
> Companion: [`master_out.schema.md`](master_out.schema.md) for the
> reverse direction.

## File shape

- Encoding: ASCII (no BOM).
- Line endings: `LF` only (`\n`); never CRLF. CI enforces this via the
  `.gitattributes` `text eol=lf` rule.
- Header: **exactly one** header row, **exactly** as below.
- Body: zero or more data rows, **strictly increasing `sample_index`**
  and **monotonic non-decreasing `timestamp_us`**.
- File grows append-only; the master reads the new tail every loop
  iteration. The plant runner never rewrites or truncates a row.

## Header row

```text
sample_index,timestamp_us,measurement,plant_state,event,checksum
```

| Column | Type | Units | Range | Meaning |
| --- | --- | --- | --- | --- |
| `sample_index` | `u64` | — | `>= 0`, strictly increasing | Monotonic counter assigned by the plant. Starts at 0 for the first row, +1 per `plant.bridge.sample_time_s`. |
| `timestamp_us` | `u64` | µs since plant start | `>= 0`, monotonic non-decreasing | Plant-side monotonic clock at row emission. |
| `measurement` | `f64` | scenario-specific | finite | Plant output the master reads as the measured value. Marine: rail pressure (bar). Space: wheel speed (rad/s). |
| `plant_state` | `f64` | scenario-specific | finite | Auxiliary plant internal state. Marine: integrator state of the first-order pressure ODE. Space: angular position (rad) integrated from speed. |
| `event` | `str` (lowercase ASCII, no commas) | — | one of `ok`, `master_timeout`, `clamp`, `init` | Tags the row with the operational condition the plant observed. `ok` is the steady-state; `master_timeout` means the watchdog fired; `clamp` means the command was saturated; `init` is the first sample. |
| `checksum` | `u32` | — | `>= 0` | CRC-32/ZIP of the leading five columns joined by `,`. Master MAY verify; the demo report counts rows with mismatching checksums under `bridge.plant.checksum_fail`. |

## Plant ODE recipes (reference)

The pure-Python reference plant implements two scenarios:

1. **`marine-common-rail-injector`** — first-order pressure ODE.

   ```text
   dx/dt = (gain * command - x) / tau
   measurement = x
   plant_state = x
   ```

   With `gain=1.5`, `tau=0.050 s` (50 ms time constant). Step response
   is monotonically non-decreasing for positive `command`.

2. **`space-reaction-wheel`** — second-order torque ODE.

   ```text
   J * d2theta/dt2 + b * dtheta/dt = command
   measurement = dtheta/dt (wheel speed, rad/s)
   plant_state = theta (angular position, rad)
   ```

   With `J=0.01 kg·m²` (rotor inertia), `b=0.05 N·m·s` (viscous
   damping). Integrated with the explicit-Euler scheme; sample-time
   `<= 0.005 s` is safe for the chosen `J` / `b` pair (Phase 9 PR
   may switch to RK4 if the demo recording shows numerical artefacts).

## Schema-mismatch behaviour

If the header row deviates from the canonical text above, the master
SHALL refuse to start with a structured error
(`bridge.schema.mismatch`) listing the expected vs observed header.

## Event-tag semantics

| Tag | When |
| --- | --- |
| `init` | First row only. |
| `ok` | Every row where the master command was fresh + within range. |
| `master_timeout` | Master command stale beyond `plant.bridge.watchdog_timeout_s` (see [`master_out.schema.md`](master_out.schema.md)). |
| `clamp` | Plant runner saturated the actuator (e.g. injector duty > 1.0). |

## Example

```text
sample_index,timestamp_us,measurement,plant_state,event,checksum
0,0,0.000000,0.000000,init,2271398174
1,1000,0.001245,0.001245,ok,3019283419
2,2000,0.003821,0.003821,ok,2841927510
```

(`marine-common-rail-injector` scenario, `sample_time_s=0.001`, first
three rows after plant start. Pressure rises monotonically toward the
`gain * command` steady state.)
