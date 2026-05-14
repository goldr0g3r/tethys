# ADR-0010 — Packet-loss tolerance budget (draft, NEW)

- **Status:** proposed
- **Date:** 2026-05-14
- **Deciders:** project owner
- **Source PR:** PR-0c `docs(research): system requirements + packet-loss tolerance budget`
- **Promoted by:** PR-3 `docs(architecture)`
- **Supersedes:** —
- **Superseded by:** —

> This is a **new** ADR (number 0010, beyond the original ADR-0001..0008 from parent §6.3) seeded by [`docs/research/phase-0-system-requirements.md`](../../research/phase-0-system-requirements.md) §6.

## Context

The parent plan parks "How much packet loss can Tethys tolerate?" as an open question in section 13. The answer drives:

- Buffer sizing ([ADR-0005 draft](adr-0005-no-dynamic-allocation.md))
- Transport-interface contract ([ADR-0004 draft](adr-0004-transport-abstraction-layer.md))
- Phase 3 / 5 / 8 / 10 test acceptance criteria
- The CI robustness suite (parent §6.7 `fuzz-nightly.yml`)

Without an explicit budget, every downstream PR negotiates this implicitly; with an explicit budget, every downstream PR cites this ADR.

## Decision

The packet-loss tolerance budget is the per-row contract in §6.1 of [`phase-0-system-requirements.md`](../../research/phase-0-system-requirements.md#61-the-table). Each row binds a (**profile** × **transport** × **direction** × **XCP service**) tuple to a **raw loss target**, **residual error target**, and **detection / recovery mechanism**, with each cell traceable to a standards source.

### The budget table (canonical, copied verbatim from the research note)

| # | Profile | Transport | Direction | XCP service | Raw loss target | Residual error target | Detection / recovery | Standards source |
| - | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Marine | UDP (IEC 61162-450) | master→slave | CTO | ≤ 1e-4 / pkt | ≤ 1e-9 / cmd (post-retry, cap 3) | XCP CTO timeout + retry | S13, S1 |
| 2 | Marine | UDP | slave→master | DAQ | ≤ 1e-4 / pkt | n/a (DAQ is unreliable by design) | XCP CTR → `DAQ_GAP` event into MDF4 | S13, S3 |
| 3 | Marine | UDP | slave→master | CAL (= CTO response) | same as row 1 | same as row 1 | same as row 1 | S13, S1 |
| 4 | Marine | TCP | both | CTO + CAL writes | 0 (TCP) | TCP CRC residual (~1e-12) | TCP retransmit | S13 |
| 5 | Marine | CAN-FD | master→slave | CTO | ≤ ~error-frame rate | ≤ 4.7e-11 / frame | CAN error-frame + TEC/REC; CTO retry | S15 |
| 6 | Marine | CAN-FD | slave→master | DAQ | same as row 5 | ≤ 4.7e-11 / frame | CAN error-frame; XCP CTR | S15, S3 |
| 7 | Marine | SocketCAN (host) | both | any | depends on host scheduling | same as row 5 + host-drop ε | smoke test on minimum-throughput | — |
| 8 | Space | UART/SxI + COP-1 AD | master→slave | CTO + CAL + STIM | raw BER 1e-7 budgeted | ≤ 1e-12 / frame (post-ARQ) | COP-1 N(S)/N(R) automatic retransmission | S10 |
| 9 | Space | TM (CCSDS 132.0-B-3) | slave→master | DAQ | mission-window-defined | none (per protocol) | XCP CTR → `DAQ_GAP`; ground software interpolates | S14, S3 |
| 10 | Space | CAN (1-wire FT) | both | CTO | ≤ ~error-frame rate | ≤ 1e-9 / frame | CAN error-frame; mandatory EDAC on CAL payload | S15 |
| 11 | Space | CAN (1-wire FT) | slave→master | DAQ | same as row 10 | ≤ 1e-9 / frame | same; XCP CTR | S15, S3 |
| 12 | Any | Loopback (posix-sim) | both | any | 0 | 0 | observed loss = test failure | — |

### Continuous-loss (blackout) bounds

| Profile | Service | Max acceptable blackout | Rationale |
| --- | --- | --- | --- |
| Marine | DAQ @ 1 kHz | 100 ms (i.e. 100 packets) | Operator notification threshold. |
| Marine | DAQ @ 10 Hz | 1000 ms | Operator notification threshold. |
| Marine | CTO | 1000 ms (= 10× longest CTO timeout) | Connection-lost declared; auto-reconnect. |
| Space | DAQ in service mode | 1000 ms | Service-mode window is short. |
| Space | CTO | 5000 ms | Ground-link RTT can be high. |
| Any | Loopback | 0 | Loopback is reliable. |

### Standards anchoring

Per IEC 61784-3 (S8) and the residual-error paper (S8), the residual error rate for a communication channel should be ≤ 1% of the IEC 61508 PFH for the supported safety function. XCP is **not** the safety function in any Tethys deployment (per [ADR-0001 draft](adr-0001-xcp-as-development-protocol.md)). Tethys therefore conservatively anchors residual targets to **IEC 61508 SIL 2 lower band** (PFH 1e-7/h → residual ≤ 1e-9/h), which is **also equal to ISO 26262 ASIL B PFH (S9)**:

- Marine CTO residual ≤ 1e-9/cmd (row 1)
- Marine DAQ residual ≤ 4.7e-11/frame on CAN-FD (row 6)
- Space CTO residual ≤ 1e-12/frame on COP-1 AD (row 8) — tighter than required because COP-1 ARQ gives it for free.

The full PFH → residual derivation is in [`phase-0-system-requirements.md §6.3`](../../research/phase-0-system-requirements.md#63-derivation--how-the-residual-targets-are-justified).

## Consequences

- Every transport in `tethys_transport/` declares the relevant row of this table via its [ADR-0004](adr-0004-transport-abstraction-layer.md) metadata API.
- [ADR-0005 draft](adr-0005-no-dynamic-allocation.md) sizes buffers from the `transport_max_burst_loss` field, which is sourced from this table.
- Phase 3 (DAQ) acceptance test = row 12 (loopback zero-loss for 60 minutes). Phase 5 (transports) conformance suite = rows 1-11 (one test per row).
- Phase 10 (verification pack) robustness suite cross-checks all 12 rows.
- Numbers are **proposed**; Phase 3 + Phase 5 will produce measured data on the actual hardware and the budget may be revised in a follow-up ADR. PR-3 will elevate this ADR to **accepted** with the provisional numbers; subsequent measurement-driven revisions go in superseding ADRs (ADR-0010A, ADR-0010B, ...) per MADR v3.0 convention.

## Alternatives considered

- **Anchor to SIL 3 (PFH 1e-8/h → residual ≤ 1e-10/h).** Rejected — requires CAN-FD residual tighter than the protocol delivers (4.7e-11/frame is achieved, but the budget margin for SIL 3 would not be); SIL 2 is the right conservative posture for a dev-time tool.
- **No quantitative budget; let each phase decide.** Rejected — the parent plan flagged this explicitly as an open question; deferral means every phase makes a different unspoken assumption.
- **Use AUTOSAR E2E profile language directly.** Rejected as the primary form — the §4.5 mapping table in the research note covers it secondarily; for safety-engineering reviewers familiar with E2E, the mapping bridges the vocabulary.

## References

- [`docs/research/phase-0-system-requirements.md`](../../research/phase-0-system-requirements.md) §1, §5, §6, §10 (the fault-injection catalogue verifies these budgets).
- [`docs/research/phase-0-standards-matrix.csv`](../../research/phase-0-standards-matrix.csv) for the source IDs (S1-S35).
- [ADR-0001 draft](adr-0001-xcp-as-development-protocol.md), [ADR-0004 draft](adr-0004-transport-abstraction-layer.md), [ADR-0005 draft](adr-0005-no-dynamic-allocation.md) — all reference this budget.
- Parent plan section 13 open-question list (this ADR resolves the packet-loss item).
