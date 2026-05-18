# HIL scenarios

> Declarative scenario JSONs consumed by
> `tethys-master demo <scenario>` (master side) and
> `tethys-sim plant --scenario <scenario>` (simulator side, pure-Python
> reference plant). The two committed scenarios drive the Phase 9
> demos (parent plan §8 Phase 9):
>
> | File | Profile | Plant kind | Used by |
> | --- | --- | --- | --- |
> | [`marine-common-rail-injector.json`](marine-common-rail-injector.json) | `marine` | First-order pressure ODE. | Master demo + reference plant. |
> | [`space-reaction-wheel.json`](space-reaction-wheel.json) | `space` | Second-order torque ODE. | Master demo + reference plant. |

## JSON schema (Pydantic v2 — `master/src/tethys_master/hil/scenario.py`)

```json
{
  "name": "<kebab-case identifier; must match the filename stem>",
  "profile": "marine" | "space",
  "duration_s": <float, > 0>,
  "transport": {
    "kind": "udp" | "tcp" | "socketcan" | "uart_sxi" | "loopback",
    "target": "<scheme>://<host>:<port>  OR  <can-device>  OR  <serial-port>",
    "timeout_ms": <int, > 0>
  },
  "a2l": {
    "path": "<path/to/file.a2l, relative to repo root>",
    "hash": "<sha256 hex of the A2L file at this commit, optional>"
  },
  "daq": {
    "event_channel": <int, >= 0>,
    "signals": ["<MEASUREMENT name>", ...],
    "rate_hz": <int, > 0>
  },
  "plant": {
    "kind": "marine-common-rail-injector" | "space-reaction-wheel",
    "bridge": {
      "sample_time_s": <float, > 0; typical 0.001 .. 0.005>,
      "watchdog_timeout_s": <float, > 0; typical >= 10 x sample_time_s>,
      "master_out": "<path; typical hil/master_out.csv>",
      "plant_out":  "<path; typical hil/plant_out.csv>"
    }
  },
  "auth": {
    "key_file": "<path/to/<scenario>.key, 16-byte raw AES-128; mandatory for space, optional for marine>"
  },
  "report_html": "<output path; typical hil/reports/<scenario>-<UTC>.html>",
  "trace": {
    "standards": [
      "ASAM XCP 1.4 Part 2 §...",
      "IACS UR E22 Rev.3 §...",
      "ECSS-E-ST-40C Rev.1 §..."
    ]
  }
}
```

## Profile invariants honoured by the loader

The Pydantic model rejects scenarios that violate either:

- **Marine** (`marine-profile-invariants.mdc`): `auth.key_file` MAY be
  omitted; if present, it points at a 4-byte file (the 4-byte simple
  challenge/response of marine seed-and-key).
- **Space** (`space-profile-invariants.mdc`): `auth.key_file` MUST be
  present and point at a 16-byte raw AES-128 key (see
  [`../keys/README.md`](../keys/README.md)).

## File-name discipline

The `name` field MUST match the filename stem (e.g.
`marine-common-rail-injector.json` carries `"name": "marine-common-rail-injector"`).
This makes the scenario JSON path predictable from the name alone
(`hil/scenarios/<name>.json`).

## Cross-references

- [`master_out.schema.md`](../bridge/master_out.schema.md) — master →
  plant CSV bridge.
- [`plant_out.schema.md`](../bridge/plant_out.schema.md) — plant →
  master CSV bridge.
- [`../keys/README.md`](../keys/README.md) — AES-128 seed-and-key
  provenance.
- [`../recordings/README.md`](../recordings/README.md) — MDF4 output
  shape.
- [`../reports/README.md`](../reports/README.md) — HTML demo report
  shape.
- Parent plan §8 Phase 9; ADR-0006 (AES-128 seed-and-key).
