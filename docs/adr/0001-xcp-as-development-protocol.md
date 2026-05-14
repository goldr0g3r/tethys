# ADR-0001 - XCP as a development-time protocol

- **Status:** accepted
- **Date:** 2026-05-14
- **Deciders:** @goldr0g3r (project owner)
- **Consulted:** (solo decision; backed by [`docs/research/phase-0-system-requirements.md`](../research/phase-0-system-requirements.md))
- **Informed:** future maintainers via this file
- **Supersedes:** —
- **Superseded by:** —
- **Accepted by:** PR-3 `docs(architecture)` (elevated from the draft seeded in PR-0c)

## Context and Problem Statement

XCP (ASAM MCD-1 XCP 1.4) is, by design, a calibration and measurement protocol used during ECU development and integration. It is **not** an operational telemetry bus. In real production deployments:

- **Space:** operational telemetry runs over CCSDS on SpaceWire / MIL-STD-1553B / UART.
- **Marine (classed):** runtime data runs over NMEA 2000 / J1939 / Modbus / IEC 61162.

Tethys is positioned as a portable, license-free XCP implementation for marine and space-adjacent extreme environments (parent plan §1, §2). The product question: should Tethys ever run in flight, or only on the ground / on the integration bench?

## Decision Drivers

- ASAM XCP 1.4 is a development-time protocol per its own scope statement (S1 in [`phase-0-standards-matrix.csv`](../research/phase-0-standards-matrix.csv)).
- Marine class societies (IACS UR E22 Rev.3, S11) and space process standards (ECSS-E-ST-40C Rev.1, S18; NPR 7150.2D, S20) explicitly require certified telemetry buses for runtime data; XCP is not certified for either.
- Operators want **service-mode debug telemetry** during in-flight anomalies; compile-time exclusion forecloses this capability.
- Bandwidth on flight buses (especially CAN-FD on marine, UART/SxI on space) is precious; an always-on XCP path competes with the operational bus.

## Considered Options

1. **Always-on XCP in flight.** XCP active throughout the mission, sharing the operational bus.
2. **No XCP in flight ever (compile-time exclusion).** Tethys-slave is stripped from flight builds.
3. **Dual-mode with default-quiescent flight, authenticated service-mode unlock.** XCP module compiles in but is gated by a per-profile flight-mode whitelist; service mode opens a configurable subset for a bounded inactivity-timeout window.

## Decision Outcome

Chose **Option 3** (dual-mode with default-quiescent flight + authenticated service-mode unlock):

1. **Development mode (default):** XCP is active. CTO + CAL + DAQ + STIM all available subject to A2L whitelisting. Marine and space profiles share this mode on the development bench / HIL.
2. **Flight / operational mode (default = quiescent):** XCP is silent. The slave's XCP module compiles in but is gated by a per-profile flight-mode whitelist. The default whitelist for both profiles is empty (no commands accepted while flight-mode flag is set).
3. **Service mode (in-flight override):** Authenticated service-mode unlock (16-byte AES-128 seed-and-key per [ADR-0006](0006-aes-128-seed-and-key.md)) opens a configurable subset of XCP commands for a bounded inactivity-timeout window (default 60 s).

The per-profile **flight-mode whitelist** when service mode is active:

- **Marine profile:** read-only DAQ on entries explicitly tagged `MARINE_FLIGHT_READABLE` in the A2L IF_DATA section.
- **Space profile:** DAQ disabled even in service mode by default; CAL writes blocked; only `GET_VERSION`, `GET_STATUS`, `GET_DAQ_CLOCK` permitted. STIM is service-mode-only and gated by the A2L whitelist (per [`phase-0-system-requirements.md` §9](../research/phase-0-system-requirements.md#9-stim-safety)).

## Consequences

- **Positive:** Operators get debug telemetry on demand; flight bandwidth is preserved by default; certification story is honest (no claim that XCP is a flight protocol).
- **Positive:** All packet-loss budgets in [ADR-0010](0010-packet-loss-tolerance-budget.md) apply to **all three modes** uniformly — wire-level behaviour is identical; only command-whitelist semantics change.
- **Positive:** Tethys is positioned as a **dev-time** protocol; it is never a safety function. The SIL 2 lower-band residual (1e-9/hour) anchor in [ADR-0010](0010-packet-loss-tolerance-budget.md) is a conservative defensive posture, not a safety-function claim.
- **Negative:** Adds a `tethys_service_mode.c` state machine (Phase 8 deliverable) plus per-MEASUREMENT / per-CHARACTERISTIC `flight_mode` flag in A2L IF_DATA — extra plumbing complexity.
- **Risk:** Operators in pressure scenarios may unlock service mode and forget to re-lock, leaving XCP exposed during the rest of flight. **Mitigation:** 60 s inactivity auto-lock + audit log of every service-mode unlock attempt (failures counted; 3 failed attempts in 10 minutes triggers a 10-minute lockout per [ADR-0006](0006-aes-128-seed-and-key.md)).

## References

- [`docs/research/phase-0-system-requirements.md`](../research/phase-0-system-requirements.md) §1, §2.4, §9.
- Parent plan section 1 ("Reality check before we build"); section 3.3 (profile table).
- [ADR-0006](0006-aes-128-seed-and-key.md) - AES-128 seed-and-key mechanism.
- [ADR-0010](0010-packet-loss-tolerance-budget.md) - packet-loss budget applies uniformly across modes.
- [`marine-profile-invariants.mdc`](../../.cursor/rules/marine-profile-invariants.mdc), [`space-profile-invariants.mdc`](../../.cursor/rules/space-profile-invariants.mdc) - machine-readable expressions of the whitelist invariants.
