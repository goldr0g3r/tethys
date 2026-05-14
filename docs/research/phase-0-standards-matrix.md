# Phase 0 — Standards matrix (generated view)

> **This file is the human-readable view; the canonical source is [`phase-0-standards-matrix.csv`](phase-0-standards-matrix.csv).** When the two diverge, the CSV wins. Regenerate this file from the CSV via the procedure in [`docs/runbooks/traceability-matrix-maintenance.md`](../runbooks/traceability-matrix-maintenance.md) (lands in PR-6).
>
> Backing research note: [`phase-0-system-requirements.md`](phase-0-system-requirements.md).
>
> Cell legend for the three applicability columns:
>
> - **used** — a normative requirement traces back to this standard in `docs/traceability.csv`.
> - **referenced** — read and aligned-with; not normative.
> - **reference** — read for context; informational only.
> - **section-only** — cited at section level only in PR-0c; deeper mapping deferred to a later research note.
> - **not-applicable** — out of scope for this profile / bench.

## Matrix

| ID | Family | Name | Version | Scope | Marine | Space | Dev bench | Citation | Retrieved |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S1  | protocol | ASAM MCD-1 XCP | 1.4 (2017) | XCP protocol + transport layer | used | used | used | [§4.1](phase-0-system-requirements.md#41-xcp-packet-structure-refresher) | 2026-05-14 |
| S2  | protocol | AUTOSAR SWS XCP | R20-11 / R22-11 | AUTOSAR Classic XCP module | reference | reference | reference | [§4.1](phase-0-system-requirements.md#41-xcp-packet-structure-refresher) | 2026-05-14 |
| S3  | protocol | Vector XCP Book | V1.5 | XCP behaviour reference incl. CTR field | used | used | used | [§4.2](phase-0-system-requirements.md#42-the-ctr-field--xcps-only-built-in-loss-detection) | 2026-05-14 |
| S4  | protocol | pyxcp | latest | LGPLv3 reference Python master | used | used | used | parent §3.1 | 2026-05-14 |
| S5  | protocol | XCP 1.4 release-note summary | 2017 | `START_STOP_SYNC` race fix | reference | reference | reference | [§4.4](phase-0-system-requirements.md#44-synch-and-start_stop_sync--race-window-guidance) | 2026-05-14 |
| S6  | functional-safety | AUTOSAR PRS E2E Protocol | R17-10 R1.2.0 | E2E profiles 1-22 | reference | reference | reference | [§4.5](phase-0-system-requirements.md#45-autosar-e2e-profile-mapping) | 2026-05-14 |
| S7  | functional-safety | IEC 61508 | parts 1-7 | Functional safety of E/E/PE systems | referenced | referenced | referenced | [§3.2](phase-0-system-requirements.md#32-generic-functional-safety) | 2026-05-14 |
| S8  | functional-safety | IEC 61784-3 + residual-error paper | IEC 61784-3 ed.4 (2021) | Safe-comm residual-error / 1% PFH rule | referenced | referenced | referenced | [§6.3](phase-0-system-requirements.md#63-derivation--how-the-residual-targets-are-justified) | 2026-05-14 |
| S9  | functional-safety | ISO 26262 | :2018 (12 parts) | Road vehicles ASIL functional safety | reference | reference | reference | [§3.3](phase-0-system-requirements.md#33-automotive-added-at-user-request--first-class) | 2026-05-14 |
| S10 | space | CCSDS 232.1-B-2 (COP-1) | B-2 (Sep 2010) | COP-1 FARM-1 AD/BD service | not-applicable | used | used | [§5.6](phase-0-system-requirements.md#56-ccsds-tc--cop-1-space-profile-production-reference) | 2026-05-14 |
| S11 | marine | IACS UR E22 | Rev.3 (Jun 2023) | Computer-based systems on ships | used | not-applicable | reference | [§3.6](phase-0-system-requirements.md#36-marine) | 2026-05-14 |
| S12 | marine | IACS UR E22 corrigendum | Rev.3 Corr.1 (Sep 2025) | Corrigendum to UR E22 Rev.3 | used | not-applicable | reference | [§3.6](phase-0-system-requirements.md#36-marine) | 2026-05-14 |
| S13 | transport | IEC 61162-450 + industrial UDP refs | ed.3 (2024) | Maritime UDP Ethernet shipboard LAN | used | not-applicable | used | [§5.1](phase-0-system-requirements.md#51-udp-master--posix-sim-marine-dev-bench) | 2026-05-14 |
| S14 | space | CCSDS 132.0-B-3 + 130.0-G-3 | B-3 (Sep 2020) | TM Space Data Link Protocol | not-applicable | used | reference | [§5.6](phase-0-system-requirements.md#56-ccsds-tc--cop-1-space-profile-production-reference) | 2026-05-14 |
| S15 | transport | CAN-FD spec + CiA proceedings | now ISO 11898-1:2024 | CAN-FD wire format; HD>=6 | used | used | used | [§5.3](phase-0-system-requirements.md#53-can-fd) | 2026-05-14 |
| S16 | space | ECSS-E-ST-50C | C (2008) | ESA umbrella for space comms | not-applicable | used | reference | [§3.4](phase-0-system-requirements.md#34-space) | 2026-05-14 |
| S17 | space | ECSS-E-AS-50-25C Rev.1 | Rev.1 (Jan 2023) | CCSDS adoption notice | not-applicable | used | reference | [§3.4](phase-0-system-requirements.md#34-space) | 2026-05-14 |
| S18 | space | ECSS-E-ST-40C | Rev.1 (Apr 2025) | Software general requirements | not-applicable | used | reference | [§3.4](phase-0-system-requirements.md#34-space) | 2026-05-14 |
| S19 | space | ECSS-Q-ST-80C + ECSS-Q-ST-60-02C | 80C Rev.1 (2017); 60-02C (2008) | SW product assurance + ASIC/FPGA | not-applicable | referenced | referenced | [§3.4](phase-0-system-requirements.md#34-space) | 2026-05-14 |
| S20 | space | NPR 7150.2D + NASA-STD-8739.8 + NASA-HDBK-2203 | NPR 7150.2D (2022) | NASA SW engineering + assurance | not-applicable | used | reference | [§3.4](phase-0-system-requirements.md#34-space) | 2026-05-14 |
| S21 | marine | IACS UR E26 | Rev.1 (Nov 2023) | Cyber resilience of ships | used | not-applicable | reference | [§3.6](phase-0-system-requirements.md#36-marine) | 2026-05-14 |
| S22 | avionics | DO-178C + DO-330 | DO-178C (2011); DO-330 (2011) | Airborne software + tool qualification | reference | referenced | reference | [§3.5](phase-0-system-requirements.md#35-avionics-dal-b-target-per-parent-4) | 2026-05-14 |
| S23 | avionics-cyber | DO-326A / ED-202A | DO-326A (2014) | Airworthiness Security Process | section-only | section-only | section-only | [§3.5](phase-0-system-requirements.md#35-avionics-dal-b-target-per-parent-4) | 2026-05-14 |
| S24 | industrial-cyber | IEC 62443 | parts 1-4 | Industrial cybersecurity for IACS | section-only | section-only | section-only | [§3.2](phase-0-system-requirements.md#32-generic-functional-safety) | 2026-05-14 |
| S25 | marine | IEC 60945 + IEC 61162-1 + NMEA 2000 + ISO 24060 + IMO MSC.428(98) | IEC 60945 ed.4 (2002); ISO 24060:2021 | Marine env + NMEA + ship SW logging + IMO cyber | reference | not-applicable | reference | [§3.6](phase-0-system-requirements.md#36-marine) | 2026-05-14 |
| S26 | marine | DNV-CG-0264 + LR ShipRight Software | latest | Class-society SW guidance alternatives | reference | not-applicable | reference | [§3.6](phase-0-system-requirements.md#36-marine) | 2026-05-14 |
| S27 | protocol | Sauci/pya2l + christoph2/pyA2L | latest | A2L parser libraries | used | used | used | parent §3.1 | 2026-05-14 |
| S28 | protocol | vectorgrp/XCPlite | latest | MIT reference XCP slave (Ethernet) | reference | reference | reference | parent §3.2 | 2026-05-14 |
| S29 | transport | ISO 11898-1 | 2024 | CAN data link + physical; incl. CAN-FD | used | used | used | [§3.7](phase-0-system-requirements.md#37-can-family) | 2026-05-14 |
| S30 | marine | IACS UR E27 | Rev.1 (Nov 2023) | Cyber resilience of on-board systems | used | not-applicable | reference | [§3.6](phase-0-system-requirements.md#36-marine) | 2026-05-14 |
| S31 | protocol | ASAM MCD-2 MC (A2L) | 1.7 | A2L description file format | used | used | used | [§3.1](phase-0-system-requirements.md#31-protocol-layer-xcp-itself--nearest-cousins) | 2026-05-14 |
| S32 | space | CCSDS 232.0-B-4 | B-4 (Oct 2021) | TC Space Data Link Protocol | not-applicable | used | reference | [§3.4](phase-0-system-requirements.md#34-space) | 2026-05-14 |
| S33 | space | ECSS-E-ST-50-04C + ECSS-E-ST-50-03C + ECSS-E-ST-50-12C | 50-04C/03C (2008); 50-12C (2019) | TC + TM frame protocol + SpaceWire | not-applicable | used | reference | [§3.4](phase-0-system-requirements.md#34-space) | 2026-05-14 |
| S34 | industrial | IEC 61158 | multiple parts | Industrial fieldbus families | reference | reference | reference | [§3.2](phase-0-system-requirements.md#32-generic-functional-safety) | 2026-05-14 |
| S35 | quality | ISO/IEC 12207 + 15288 + 25000 + 90003 + ISO 10007 | various 2014-2018 | SW process and quality standards | used | used | used | [§3.6](phase-0-system-requirements.md#36-marine) | 2026-05-14 |

## Maintenance

- Add a row by editing the CSV, then regenerate this markdown view (see [`docs/runbooks/traceability-matrix-maintenance.md`](../runbooks/traceability-matrix-maintenance.md) in PR-6).
- Mark a row deprecated by appending `,deprecated_in: <PR>` to the CSV row; do not delete rows — `docs/traceability.csv` cites by `id`.
- Retrieval-date refresh cadence: every six months, or when a referenced standard publishes a new edition.
