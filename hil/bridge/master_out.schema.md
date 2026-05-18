# `hil/master_out.csv` — bridge schema (master → plant)

> The HIL bridge between `tethys-master demo <scenario>` (master side)
> and the plant runner (`tethys-sim plant` for the pure-Python
> alternative; Simulink for the Phase 9 closed-loop bench). The master
> writes one row per `plant.bridge.sample_time_s` of the scenario; the
> plant runner reads the **fresh tail** of the file every tick.
>
> Parent plan section 8 (Phase 9 — HIL + MATLAB integration).
> Companion: [`plant_out.schema.md`](plant_out.schema.md) for the
> reverse direction.

## File shape

- Encoding: ASCII (no BOM).
- Line endings: `LF` only (`\n`); never CRLF. CI enforces this via the
  `.gitattributes` `text eol=lf` rule.
- Header: **exactly one** header row, **exactly** as below.
- Body: zero or more data rows, **strictly increasing `sample_index`**
  and **monotonic non-decreasing `timestamp_us`**. Time values may
  repeat across rows (two writes within one microsecond) only when
  `sample_index` still advances.
- File grows append-only; the plant runner reads the new tail every
  tick. The master never rewrites or truncates a row.

## Header row

```text
sample_index,timestamp_us,command,setpoint,gain,enable,checksum
```

| Column | Type | Units | Range | Meaning |
| --- | --- | --- | --- | --- |
| `sample_index` | `u64` | — | `>= 0`, strictly increasing | Monotonic counter assigned by the master. Starts at 0 for the first row, +1 per `plant.bridge.sample_time_s`. |
| `timestamp_us` | `u64` | µs since master `demo.start` | `>= 0`, monotonic non-decreasing | Master-side monotonic clock at row emission. `t = sample_index * round(sample_time_s * 1e6)`. |
| `command` | `f64` | dimensionless | finite | Scenario-specific actuator command. For marine common-rail injector this is normalised injector duty `[0.0, 1.0]`; for space reaction-wheel this is normalised torque request `[-1.0, 1.0]`. |
| `setpoint` | `f64` | scenario-specific | finite | Target the master is driving the plant toward. Marine: rail pressure (bar). Space: wheel speed (rad/s). |
| `gain` | `f64` | dimensionless | finite, `>= 0.0` | Loop gain applied by the master (open-loop demo writes `0.0`). |
| `enable` | `u8` | — | `0` or `1` | `1` = plant should execute the command. `0` = plant should hold (used for service-mode lock + scenario `--dry-run`). |
| `checksum` | `u32` | — | `>= 0` | CRC-32/ZIP of the leading six columns joined by `,`. Plant runner MAY verify; the pure-Python reference plant does verify and refuses rows whose checksum does not match. |

## Watchdog semantics

The plant runner SHALL declare a master-side timeout when no new row
arrives within `plant.bridge.watchdog_timeout_s` (taken from the
scenario JSON). On timeout:

1. Emit a `bridge.master.timeout` structured log event.
2. Zero-order-hold the **previous** master command (do NOT zero the
   actuator — that is a separate fault-injection path and would mask
   the timeout itself).
3. Keep advancing plant time so `plant_out.csv` still produces
   monotonic rows; the row count discrepancy (master vs plant) is the
   timeout's signature in the demo report.

## Idempotency

The plant runner reads the file by `(sample_index, timestamp_us, checksum)`
tuple. A row already consumed shall be skipped on a re-read. The
reference plant implementation tracks the highest `sample_index` it has
emitted a corresponding `plant_out.csv` row for; rows with
`sample_index <= last_consumed` are no-ops.

## Schema-mismatch behaviour

If the header row deviates from the canonical text above (column names
or order), the plant runner SHALL refuse to start with a structured
error (`bridge.schema.mismatch`) listing the expected vs observed
header. A mismatch is a master/plant version skew and not a recoverable
condition.

## Example

```text
sample_index,timestamp_us,command,setpoint,gain,enable,checksum
0,0,0.000000,180.000000,0.500000,1,3592456101
1,1000,0.052345,180.000000,0.500000,1,1827463992
2,2000,0.097612,180.000000,0.500000,1,3441592650
```

(`marine-common-rail-injector` scenario, `sample_time_s=0.001`,
`enable=1`, first three rows after `demo.start`.)
