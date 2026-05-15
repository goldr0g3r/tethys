# Tethys traceability matrix (human-readable view)

> **Canonical source:** [`traceability.csv`](traceability.csv) — when the two diverge, the CSV wins. Regenerate this view per the procedure in [`docs/runbooks/traceability-matrix-maintenance.md`](runbooks/traceability-matrix-maintenance.md).
>
> **Row counts at PR-A merge (Phase 10 foundation):**
>
> | Bucket | Prefix | Count |
> | --- | --- | --- |
> | ADR decisions | `TETHYS-ADR-*` | 10 |
> | Design elements (XCP dispatcher + A2L facade) | `TETHYS-DES-*` | 11 |
> | Fault-injection catalogue (per ADR-0010 §10.1) | `TETHYS-REQ-FAULT-*` | 16 |
> | Packet-loss budget rows (per ADR-0010 §6.1) | `TETHYS-REQ-LOSS-*` | 12 |
> | Marine profile acceptance | `TETHYS-REQ-MARINE-*` | 3 |
> | Phase-0 acceptance | `TETHYS-REQ-P0-*` | 10 |
> | Phase-1 acceptance (hello-world) | `TETHYS-REQ-P1-*` | 2 |
> | Space profile acceptance | `TETHYS-REQ-SPACE-*` | 5 |
> | Verification suite | `TETHYS-REQ-VER-*` | 4 |
> | Transport conformance | `TETHYS-REQ-XPRT-*` | 6 |
> | **Total rows** | | **79** |
>
> **Conventions:** rows with `TODO(Phase-N)` in the description point at code that does not exist yet — they are forward trackers that the relevant phase will fill in. Standards are cited in the form `ASAM XCP 1.4 Part 2 §1.3.2.4`, `ECSS-E-ST-40C Rev.1 §5.4.3.1`, `ISO 26262-6:2018 §6.4.3`. Multiple cites separated by `;`. See [`.cursor/rules/always-cite-standards.mdc`](../.cursor/rules/always-cite-standards.mdc).

---

## 1. By standard objective

### 1.1 ASAM XCP 1.4 (protocol; S1)

The XCP protocol spec is the single tightest specification any Tethys row cites — every protocol command has a §-anchored row.

| id | one-line summary | phase | profile |
| --- | --- | --- | --- |
| TETHYS-ADR-0001 | XCP positioned as development-time protocol; flight default quiescent | 0 | marine\|space |
| TETHYS-ADR-0004 | Transport-abstraction-layer interface with loss-event metadata | 0 | marine\|space |
| TETHYS-ADR-0006 | AES-128 derived seed-and-key gate | 0 | space |
| TETHYS-ADR-0010 | Packet-loss tolerance budget | 0 | marine\|space |
| TETHYS-DES-0001 | XCP command dispatcher top-level | 1 | marine\|space |
| TETHYS-DES-0002 | CONNECT command (XCP §1.3.2.4) | 1 | marine\|space |
| TETHYS-DES-0003 | DISCONNECT command (XCP §1.3.2.5) | 1 | marine\|space |
| TETHYS-DES-0004 | GET_STATUS command (XCP §1.3.2.6) | 1 | marine\|space |
| TETHYS-DES-0005 | GET_VERSION command (XCP §1.4.2.1) | 1 | marine\|space |
| TETHYS-DES-0006 | Session init (XCP §1.3.1) | 1 | marine\|space |
| TETHYS-DES-0008 | SET_MTA command (XCP §1.3.3.1) | 2 | marine\|space |
| TETHYS-DES-0009 | UPLOAD command (XCP §1.3.3.2) | 2 | marine\|space |
| TETHYS-DES-0010 | SHORT_UPLOAD command (XCP §1.3.3.6) | 2 | marine\|space |
| TETHYS-REQ-FAULT-001 | Drop 1-of-N DTO → DAQ_GAP via CTR | 10 | marine\|space |
| TETHYS-REQ-FAULT-002 | Burst-K DTO loss → single DAQ_GAP | 10 | marine\|space |
| TETHYS-REQ-FAULT-003 | Reorder DTO at distance D | 10 | marine\|space |
| TETHYS-REQ-FAULT-004 | Duplicate DTO at rate R | 10 | marine\|space |
| TETHYS-REQ-FAULT-006 | Single-bit CTO corruption → master retry | 10 | marine\|space |
| TETHYS-REQ-FAULT-007 | CTO timeout → retry cap 3 → connection lost | 10 | marine\|space |
| TETHYS-REQ-FAULT-008 | Slave reboot mid-DAQ → CONNECT detects | 10 | marine\|space |
| TETHYS-REQ-FAULT-009 | A2L drift hash mismatch on CONNECT | 10 | marine\|space |
| TETHYS-REQ-FAULT-010 | CRC mismatch on CAL write → rollback | 10 | marine\|space |
| TETHYS-REQ-FAULT-013 | Service-mode auth failure → lockout | 10 | space |
| TETHYS-REQ-FAULT-014 | MTU overflow CTO → ERR_CMD_SYNTAX (RUNS NOW) | 10 | marine\|space |
| TETHYS-REQ-FAULT-015 | Malformed PID → ERR_CMD_UNKNOWN (RUNS NOW) | 10 | marine\|space |
| TETHYS-REQ-FAULT-016 | Continuous-loss > blackout bound alert | 10 | marine\|space |
| TETHYS-REQ-LOSS-001 | Marine/UDP/master→slave/CTO budget | 5 | marine |
| TETHYS-REQ-LOSS-002 | Marine/UDP/slave→master/DAQ budget | 5 | marine |
| TETHYS-REQ-LOSS-003 | Marine/UDP/CAL response budget | 5 | marine |
| TETHYS-REQ-LOSS-006 | Marine/CAN-FD/DAQ budget | 5 | marine |
| TETHYS-REQ-LOSS-009 | Space/TM CCSDS DAQ budget | 8 | space |
| TETHYS-REQ-LOSS-011 | Space/CAN-FT/DAQ budget | 8 | space |
| TETHYS-REQ-P1-001 | Hello-world XCP CONNECT/DISCONNECT (slave side) | 1 | marine\|space |
| TETHYS-REQ-P1-002 | Hello-world XCP exchange (master CLI side) | 1 | marine\|space |
| TETHYS-REQ-SPACE-002 | AES-128 seed-and-key (XCP §1.3.5) | 8 | space |
| TETHYS-REQ-SPACE-004 | Service-mode authenticated unlock | 8 | space |
| TETHYS-REQ-XPRT-001 | UDP/IPv4 (XCP on Ethernet) | 5 | marine |
| TETHYS-REQ-XPRT-002 | TCP/IPv4 (XCP on Ethernet) | 5 | marine |
| TETHYS-REQ-XPRT-003 | CAN-FD (XCP on CAN) | 5 | marine\|space |

### 1.2 ASAM MCD-2 MC v1.7 (A2L; S31)

| id | one-line summary | phase | profile |
| --- | --- | --- | --- |
| TETHYS-DES-0011 | A2L parser facade — parse + emit canonical | 2 | marine\|space |
| TETHYS-REQ-FAULT-009 | A2L hash drift on CONNECT | 10 | marine\|space |

### 1.3 MISRA C:2023 (coding gate)

Mandatory + Required: zero deviations on merge. Advisory: documented in `docs/misra-deviations.md`.

| id | one-line summary | phase | profile |
| --- | --- | --- | --- |
| TETHYS-ADR-0003 | MISRA C:2023 as hard merge gate | 0 | marine\|space |
| TETHYS-ADR-0005 | No dynamic allocation (Dir 4.12) | 0 | marine\|space |
| TETHYS-DES-0006 | Session init null-pointer safe (Rule 17.7) | 1 | marine\|space |
| TETHYS-DES-0007 | Attach-memory hook (Dir 4.12) | 1 | marine\|space |
| TETHYS-REQ-FAULT-015 | Malformed PID — no UB (MISRA-clean) | 10 | marine\|space |
| TETHYS-REQ-P0-005 | clang-format + clang-tidy + cppcheck MISRA + pre-commit | 0 | marine\|space |
| TETHYS-REQ-VER-002 | libFuzzer corpora committed | 10 | marine\|space |
| TETHYS-REQ-VER-004 | gcovr ≥95% + zero MISRA M/R deviations | 10 | marine\|space |

### 1.4 IEC 61508 / IEC 61784-3 (functional safety + safe-comm residual; S7, S8)

| id | one-line summary | phase | profile |
| --- | --- | --- | --- |
| TETHYS-ADR-0004 | Transport interface surfaces loss-event metadata | 0 | marine\|space |
| TETHYS-ADR-0010 | SIL 2 lower-band residual anchor | 0 | marine\|space |
| TETHYS-REQ-FAULT-002 | Burst loss budget | 10 | marine\|space |
| TETHYS-REQ-FAULT-005 | CTO corruption → transport CRC | 10 | marine\|space |
| TETHYS-REQ-FAULT-006 | CTO corruption → master retry | 10 | marine\|space |
| TETHYS-REQ-FAULT-016 | Blackout bound alert | 10 | marine\|space |
| TETHYS-REQ-LOSS-001 | Marine/UDP/CTO residual envelope | 5 | marine |
| TETHYS-REQ-P0-009 | Standards landscape + ADR-0010 | 0 | marine\|space |
| TETHYS-REQ-VER-003 | Robustness suite (16 scenarios) | 10 | marine\|space |

### 1.5 ISO 26262:2018 (automotive; referenced not claimed; S9)

Anchors the upper end of the residual-error envelope (ASIL D PFH ≤ 1e-8/h). Tethys is **not** automotive — these rows reference ISO 26262 because (a) XCP is automotive by origin and (b) ISO 26262 is the most mature application of IEC 61508.

| id | one-line summary | phase | profile |
| --- | --- | --- | --- |
| TETHYS-ADR-0002 | Profile-based build (Part 6 §7) | 0 | marine\|space |
| TETHYS-ADR-0003 | MISRA gate (Part 6 §5.4.4) | 0 | marine\|space |
| TETHYS-ADR-0005 | No dynamic allocation (Part 6 §8.4.4) | 0 | marine\|space |
| TETHYS-ADR-0010 | Packet-loss budget (Part 9 §6) | 0 | marine\|space |
| TETHYS-REQ-P0-005 | Coding standards (Part 6 §5.4.4) | 0 | marine\|space |
| TETHYS-REQ-P0-009 | Standards landscape (Part 9 §6) | 0 | marine\|space |
| TETHYS-REQ-SPACE-003 | Deterministic ODT (Part 6 §7.4.16) | 8 | space |

### 1.6 ECSS-E-ST-40C Rev.1 (April 2025) — ESA software engineering (S18)

Primary process-layer anchor for the space profile.

| id | one-line summary | phase | profile |
| --- | --- | --- | --- |
| TETHYS-ADR-0001 | XCP dev-time positioning (§4) | 0 | marine\|space |
| TETHYS-ADR-0002 | Profile-based build (§5.4.2) | 0 | marine\|space |
| TETHYS-ADR-0005 | No dynamic allocation (§5.4.3.4) | 0 | marine\|space |
| TETHYS-ADR-0006 | AES-128 seed-and-key (§5.5.2) | 0 | space |
| TETHYS-DES-0001 | Dispatcher top-level (§5.4) | 1 | marine\|space |
| TETHYS-DES-0007 | Attach-memory hook (§5.4.3.4) | 1 | marine\|space |
| TETHYS-REQ-FAULT-012 | EDAC double-bit fault (§5.4.3.4) | 10 | space |
| TETHYS-REQ-SPACE-001 | EDAC SEC-DED Hamming (§5.4.3.4) | 8 | space |
| TETHYS-REQ-SPACE-003 | Deterministic ODT (§5.4.3.1) | 8 | space |
| TETHYS-REQ-SPACE-005 | MC/DC ≥95% + fault bench (§6.3.5) | 8 | space |
| TETHYS-REQ-VER-001 | Living traceability matrix (§5.7) | 10 | marine\|space |
| TETHYS-REQ-VER-002 | libFuzzer corpora (§5.5) | 10 | marine\|space |
| TETHYS-REQ-VER-004 | gcovr ≥95% + MISRA-clean (§6.3.5) | 10 | marine\|space |

### 1.7 NPR 7150.2D — NASA software engineering (S20)

| id | one-line summary | phase | profile |
| --- | --- | --- | --- |
| TETHYS-ADR-0001 | XCP dev-time positioning (§3) | 0 | marine\|space |
| TETHYS-REQ-SPACE-001 | EDAC (§3) | 8 | space |
| TETHYS-REQ-SPACE-004 | Service-mode auth (§3) | 8 | space |
| TETHYS-REQ-SPACE-005 | MC/DC ≥95% (§4) | 8 | space |
| TETHYS-REQ-VER-001 | Living traceability matrix (§3) | 10 | marine\|space |

### 1.8 IACS UR E22 Rev.3 + UR E26 Rev.1 (marine class society; S11, S12, S21)

| id | one-line summary | phase | profile |
| --- | --- | --- | --- |
| TETHYS-ADR-0001 | XCP dev-time positioning (§5) | 0 | marine\|space |
| TETHYS-ADR-0002 | Profile-based build (§5) | 0 | marine\|space |
| TETHYS-REQ-MARINE-001 | 24h soak; watchdog never tripped (§5) | 7 | marine |
| TETHYS-REQ-MARINE-003 | Marine traceability rows filled | 7 | marine |

### 1.9 DO-178C (avionics; informational; S22)

Tethys does not claim DAL-B; the rows reference DO-178C because the verification techniques (MC/DC, requirements-based testing) are the strongest available reference for our coverage and traceability gates.

| id | one-line summary | phase | profile |
| --- | --- | --- | --- |
| TETHYS-ADR-0003 | MISRA C:2023 (§6.3.4) | 0 | marine\|space |
| TETHYS-REQ-SPACE-003 | Deterministic ODT (§6.3) | 8 | space |
| TETHYS-REQ-SPACE-005 | MC/DC ≥95% (§6.4.4.2) | 8 | space |
| TETHYS-REQ-VER-001 | Living traceability matrix (§11.21) | 10 | marine\|space |
| TETHYS-REQ-VER-002 | libFuzzer corpora (§6.4.4.1) | 10 | marine\|space |
| TETHYS-REQ-VER-003 | Robustness suite (§6.4.2) | 10 | marine\|space |
| TETHYS-REQ-VER-004 | gcovr ≥95% MC/DC (§6.4.4.2) | 10 | marine\|space |

### 1.10 CCSDS 232.1-B-2 (COP-1) + CCSDS 132.0-B-3 (TM) — space transport (S10, S14)

| id | one-line summary | phase | profile |
| --- | --- | --- | --- |
| TETHYS-REQ-LOSS-008 | Space/SxI+COP-1 AD residual (post-ARQ ≤1e-12) | 8 | space |
| TETHYS-REQ-LOSS-009 | Space/TM CCSDS DAQ (no recovery per protocol) | 8 | space |
| TETHYS-REQ-LOSS-010 | Space/CAN-FT/CTO + EDAC | 8 | space |
| TETHYS-REQ-XPRT-005 | UART/SxI + COP-1 AD wrapper | 8 | space |

### 1.11 ISO 11898-1:2024 (CAN family; S29)

| id | one-line summary | phase | profile |
| --- | --- | --- | --- |
| TETHYS-REQ-FAULT-011 | Bus-off + recovery | 10 | marine\|space |
| TETHYS-REQ-LOSS-005 | Marine/CAN-FD/CTO residual ≤4.7e-11 | 5 | marine |
| TETHYS-REQ-LOSS-006 | Marine/CAN-FD/DAQ residual | 5 | marine |
| TETHYS-REQ-LOSS-007 | SocketCAN host scheduling | 5 | marine |
| TETHYS-REQ-LOSS-010 | Space/CAN-FT/CTO residual ≤1e-9 | 8 | space |
| TETHYS-REQ-LOSS-011 | Space/CAN-FT/DAQ residual | 8 | space |
| TETHYS-REQ-MARINE-002 | CAN-FD + W5500 on STM32 | 7 | marine |
| TETHYS-REQ-XPRT-003 | CAN-FD via CANable 2.0 | 5 | marine\|space |
| TETHYS-REQ-XPRT-004 | SocketCAN minimum-throughput smoke | 5 | marine |
| TETHYS-REQ-XPRT-006 | CAN 1-wire fault-tolerant (space) | 8 | space |

### 1.12 NIST FIPS 197 (AES-128 crypto)

| id | one-line summary | phase | profile |
| --- | --- | --- | --- |
| TETHYS-ADR-0006 | AES-128 derived seed-and-key | 0 | space |
| TETHYS-REQ-FAULT-013 | Service-mode auth failure → lockout | 10 | space |
| TETHYS-REQ-SPACE-002 | AES-128 16-byte challenge/response | 8 | space |

### 1.13 AUTOSAR PRS E2E (fault-class vocabulary; reference only; S6)

Used as a vocabulary anchor (see `phase-0-system-requirements.md` §4.5) — every fault-injection scenario maps to one of the 7 E2E fault classes (Repetition / Loss / Delay / Insertion / Corruption / Masquerade / Addressing).

| id | one-line summary | phase | profile |
| --- | --- | --- | --- |
| TETHYS-ADR-0004 | Transport interface surfaces loss-event metadata | 0 | marine\|space |
| TETHYS-REQ-FAULT-001 | Drop 1-of-N (Loss) | 10 | marine\|space |
| TETHYS-REQ-FAULT-002 | Burst-K (Loss) | 10 | marine\|space |
| TETHYS-REQ-FAULT-003 | Reorder (Insertion) | 10 | marine\|space |
| TETHYS-REQ-FAULT-004 | Duplicate (Repetition) | 10 | marine\|space |
| TETHYS-REQ-FAULT-005 | DTO corruption (Corruption) | 10 | marine\|space |
| TETHYS-REQ-FAULT-007 | CTO timeout (Delay) | 10 | marine\|space |
| TETHYS-REQ-FAULT-011 | Bus-off recovery | 10 | marine\|space |
| TETHYS-REQ-VER-003 | Robustness suite (16 scenarios) | 10 | marine\|space |

### 1.14 Tooling / process (no standard cited)

| id | one-line summary | phase | profile |
| --- | --- | --- | --- |
| TETHYS-ADR-0007 | Python master tool; no Vehicle Network Toolbox | 0 | marine\|space |
| TETHYS-ADR-0008 | License-free toolchain + MIT repo license | 0 | marine\|space |
| TETHYS-ADR-0009 | Migrate to Repository Ruleset | 0 | marine\|space |
| TETHYS-REQ-LOSS-012 | Loopback (posix-sim) — zero-loss floor | 3 | marine\|space |
| TETHYS-REQ-P0-001 | Monorepo bootstrap via CLI only | 0 | marine\|space |
| TETHYS-REQ-P0-002 | Twelve .cursor/rules + mirrors | 0 | marine\|space |
| TETHYS-REQ-P0-003 | README + system-context + ADRs | 0 | marine\|space |
| TETHYS-REQ-P0-004 | Eleven CI workflows + templates | 0 | marine\|space |
| TETHYS-REQ-P0-006 | Seven runbooks + index | 0 | marine\|space |
| TETHYS-REQ-P0-007 | Twelve milestones + 52 labels + issues | 0 | marine\|space |
| TETHYS-REQ-P0-008 | github-setup runbook | 0 | marine\|space |
| TETHYS-REQ-P0-010 | Ceedling + layout rebrand | 0 | marine\|space |

---

## 2. By phase

| Phase | Theme | Row count | Notes |
| --- | --- | --- | --- |
| 0 | Foundations (scaffold + rules + ADRs + CI + runbooks) | 19 | ADRs 0001-0010 + REQ-P0-001..010 (less ADRs already counted via phase) |
| 1 | Shared infrastructure + hello-world XCP | 9 | REQ-P1-001..002 + DES-0001..0007 |
| 2 | XCP protocol core (read path) | 4 | DES-0008..0011 |
| 3 | DAQ + STIM | 1 | REQ-LOSS-012 (loopback acceptance) |
| 5 | Transport pluggability | 13 | REQ-LOSS-001..007 + REQ-XPRT-001..006 (some overlap) |
| 7 | Marine profile on STM32F4/F7 | 3 | REQ-MARINE-001..003 |
| 8 | Space profile on STM32H7 | 9 | REQ-SPACE-001..005 + REQ-LOSS-008..011 |
| 10 | Verification pack | 20 | REQ-FAULT-001..016 + REQ-VER-001..004 |

Phases 4, 6, 9, 11 have no rows yet — they'll fill in as those phases land (CAL+PAG, GUI, HIL, release).

---

## 3. By kind

| Kind | Count | Description |
| --- | --- | --- |
| `DEC` (Architecture decision) | 10 | One row per accepted ADR (0001..0010) |
| `DES` (Design element) | 11 | One row per XCP dispatcher handler + A2L facade |
| `REQ` (Requirement) | 58 | Phase-N acceptance criteria + fault scenarios + loss budgets + transport conformance |

---

## 4. Forward-tracker (TODO) rows

Rows where `implemented_by` or `verified_by` points at code that does not yet exist; the row is a tracker for the relevant phase.

| Phase | Rows |
| --- | --- |
| Phase-2 (PR-30 A2L parser) | DES-0011, FAULT-009 |
| Phase-3 (DAQ + ODT engine) | FAULT-001..004, FAULT-008, FAULT-016, LOSS-012 |
| Phase-4 (CAL + PAG + BUILD_CHECKSUM) | FAULT-010 |
| Phase-5 (Transports) | FAULT-001..007, FAULT-011, LOSS-001..007, XPRT-001..004 |
| Phase-7 (Marine on STM32) | MARINE-001..003 |
| Phase-8 (Space on STM32H7) | FAULT-012, FAULT-013, LOSS-008..011, SPACE-001..005, XPRT-005, XPRT-006 |
| **Runs today** | FAULT-014, FAULT-015 (against the existing `tethys_xcp_dispatch` Phase-1+2 read path) |

---

## 5. Maintenance

- **Edit the CSV first** — the markdown view is regenerated from the CSV; never edit by hand without re-syncing the CSV.
- **Alphabetical sort by `id`** is enforced in PR-A; keep new rows sorted (CI lints in the future PR that adds the gate).
- **No commas in description** — use `;` for separators. This view's tables render in markdown but the CSV stays plain-text-readable.
- **TODO(Phase-N)** flag in description column marks forward-tracker rows.
- **Adding a new ADR** — increment to `TETHYS-ADR-NNNN` matching the ADR number, add one row, cite the standards the ADR consumes.
- **Adding a new fault scenario** — extend `TETHYS-REQ-FAULT-NNN`; mirror the row in [`docs/research/phase-0-system-requirements.md`](research/phase-0-system-requirements.md) §10.

---

## 6. References

- Header definition: [`.cursor/rules/ecss-traceability.mdc`](../.cursor/rules/ecss-traceability.mdc)
- Citation format: [`.cursor/rules/always-cite-standards.mdc`](../.cursor/rules/always-cite-standards.mdc)
- Standards source IDs (S1-S35): [`docs/research/phase-0-standards-matrix.csv`](research/phase-0-standards-matrix.csv)
- Fault catalogue rationale: [`docs/research/phase-0-system-requirements.md`](research/phase-0-system-requirements.md) §10
- Packet-loss budget: [`docs/adr/0010-packet-loss-tolerance-budget.md`](adr/0010-packet-loss-tolerance-budget.md)
- Phase 10 foundation research note: [`docs/research/phase-10-verification-foundations.md`](research/phase-10-verification-foundations.md)
