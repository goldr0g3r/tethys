# ADR-0001 — XCP as a development-time protocol (draft)

- **Status:** proposed
- **Date:** 2026-05-14
- **Deciders:** project owner
- **Source PR:** PR-0c `docs(research): system requirements + packet-loss tolerance budget`
- **Promoted by:** PR-3 `docs(architecture)` (this draft will be elevated to MADR v3.0 accepted form)
- **Supersedes:** —
- **Superseded by:** —

> This is a **draft** seeded by [`docs/research/phase-0-system-requirements.md`](../../research/phase-0-system-requirements.md). PR-3 will fold it into the final `docs/adr/0001-xcp-as-development-protocol.md` with MADR v3.0 headers and a signed acceptance entry. Do not cite this draft from `docs/traceability.csv` until PR-3 lands.

## Context

XCP (ASAM MCD-1 XCP 1.4) is, by design, a calibration and measurement protocol used during ECU development and integration. It is **not** intended as a flight-time / operational telemetry bus. In real deployments:

- **Space:** operational telemetry runs over CCSDS on SpaceWire / MIL-STD-1553B / UART.
- **Marine (classed):** runtime data runs over NMEA 2000 / J1939 / Modbus / IEC 61162.

Tethys is positioned as a portable, license-free XCP implementation for marine and space-adjacent extreme environments. Question: should Tethys ever run in flight, or only on the ground / on the integration bench?

## Decision

Tethys treats XCP as **dual-mode**:

1. **Development mode (default):** XCP is active. CTO + CAL + DAQ + STIM all available subject to A2L whitelisting. Marine and space profiles share this mode on the development bench / HIL.
2. **Flight / operational mode (default = quiescent):** XCP is silent. The slave's XCP module compiles in but is gated by a per-profile flight-mode whitelist. The default whitelist for both profiles is empty (no commands accepted while flight-mode flag is set).
3. **Service mode (in-flight override):** Authenticated service-mode unlock (16-byte AES-128 seed-and-key per ADR-0006) opens a configurable subset of XCP commands for a bounded inactivity-timeout window (default 60 s).

The per-profile **flight-mode whitelist** when service mode is active:

- **Marine profile:** read-only DAQ on entries explicitly tagged `MARINE_FLIGHT_READABLE` in the A2L IF_DATA section.
- **Space profile:** DAQ disabled even in service mode by default; CAL writes blocked; only `GET_VERSION`, `GET_STATUS`, `GET_DAQ_CLOCK` are permitted. STIM is service-mode-only and gated by the A2L whitelist (per [`phase-0-system-requirements.md §9`](../../research/phase-0-system-requirements.md#9-stim-safety)).

## Consequences

- Tethys ships a `tethys_service_mode.c` state machine (Phase 8 deliverable).
- The A2L IF_DATA section gains a per-MEASUREMENT / per-CHARACTERISTIC `flight_mode` flag and a per-STIM-target whitelist marker.
- All packet-loss budgets in [ADR-0010 draft](adr-0010-packet-loss-tolerance-budget.md) are applicable to **all three modes** — flight-mode loss budgets are the same as service-mode budgets because the wire-level behaviour does not change.
- Tethys is a **dev-time** protocol; it is never a safety function. Therefore SIL 2 lower-band residual (1e-9 / hour) is the conservative defensive posture, not a safety-function claim. See [`phase-0-system-requirements.md §6.3`](../../research/phase-0-system-requirements.md#63-derivation--how-the-residual-targets-are-justified).

## Alternatives considered

- **Always-on XCP in flight.** Rejected because XCP is not certified as a flight-time protocol; competing for bandwidth with the operational bus would compromise certification.
- **No XCP in flight ever (build out at compile time).** Rejected because service-mode debug telemetry has high operational value; compile-time exclusion forecloses it.

## References

- [`docs/research/phase-0-system-requirements.md`](../../research/phase-0-system-requirements.md) §1, §2.4, §9.
- Parent plan section 1 ("Reality check before we build"); section 3.3 (profile table).
