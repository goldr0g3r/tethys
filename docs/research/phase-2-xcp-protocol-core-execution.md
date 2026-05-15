# Phase 2 - XCP protocol core (research note)

> Research note backing the Phase 2 PRs (`p2`).
> Parent plan: [`xcp_extreme-env_tool_14019278.plan.md`](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md) §8 Phase 2.
> Sub-plan (part A): [`p2_xcp_protocol_core_a_8f4d2a01.plan.md`](../../../../Users/wnp1cob/.cursor/plans/p2_xcp_protocol_core_a_8f4d2a01.plan.md)

## Scope

Phase 2 lands the XCP Standard Command core that turns the Phase 1 hello-world
slave into something a calibration tool can actually use: address-pointed
reads (UPLOAD path), address-pointed writes (DOWNLOAD path), integrity
verification (BUILD_CHECKSUM), and state-machine resync (SYNCH). The work is
split across four PRs to keep each one reviewable:

| PR | Title | Surface | Status |
|---|---|---|---|
| PR-28 | `feat(slave): SET_MTA + UPLOAD + SHORT_UPLOAD per XCP 1.4 §1.3.3` | 3 commands across slave + simulator + master + tests | this PR |
| PR-29 | `feat(slave): DOWNLOAD + BUILD_CHECKSUM + SYNCH per XCP 1.4` | 3 commands + checksum machinery + SYNCH semantics | next |
| PR-30 | `feat(master): A2L MEASUREMENT + CHARACTERISTIC parser facade` | thin facade over Sauci/pya2l | next |
| PR-31 | `test(master): differential test against pyxcp reference` | acceptance criterion + flip p2 to completed | last |

This note is opened by PR-28 and amended by the subsequent three PRs as their
"Implementation Reference" rows fill in. PR-28 establishes the design
decisions and tooling choices that propagate.

## Sources (retrieved 2026-05-15)

| # | Source | URL | Retrieval date | Relevance |
|---|---|---|---|---|
| 1 | ASAM MCD-1 XCP 1.4 Part 2 - Protocol Layer Specification | <https://www.asam.net/standards/detail/mcd-1-xcp/wiki/> | 2026-05-15 | §1.3.2 Standard Commands; §1.3.3 SET_MTA/UPLOAD/SHORT_UPLOAD; §1.3.4 DOWNLOAD/MODIFY_BITS; §1.5 BUILD_CHECKSUM; §1.3.1.2 SYNCH; Table 5 (command codes); Table 12 (error codes) |
| 2 | Vector XCP Book (reference, NOT normative) | <https://www.vector.com/int/en/know-how/protocols/xcp-measurement-and-calibration-protocol/> | 2026-05-15 | Cross-check for wire formats; ASAM is authoritative per `xcp-protocol-discipline.mdc` |
| 3 | pyxcp (christoph2) - reference master implementation (LGPLv3) | <https://github.com/christoph2/pyxcp> | 2026-05-15 | Differential-test target in PR-31; release `v0.22.x` series; pyxcp.master.Master.upload() / .setMta() / .shortUpload() / .download() / .buildChecksum() are the comparison surface |
| 4 | Sauci/pya2l - A2L parser (BSD-3) | <https://github.com/Sauci/pya2l> | 2026-05-15 | PR-30 facade engine; `pya2l.parser.A2lYaccParser` exposes MODULE, MEASUREMENT, CHARACTERISTIC, COMPU_METHOD, RECORD_LAYOUT, etc. |
| 5 | ADR-0005 - No dynamic allocation in the slave | [`docs/adr/0005-no-dynamic-allocation.md`](../adr/0005-no-dynamic-allocation.md) | local | Drives the caller-attached memory design (D11 below) |
| 6 | ADR-0010 - Packet-loss tolerance budget | [`docs/adr/0010-packet-loss-tolerance-budget.md`](../adr/0010-packet-loss-tolerance-budget.md) | local | Drives the per-command timeout matrix in `phase-0-system-requirements.md` §4.3 |
| 7 | `phase-0-system-requirements.md` §4 CTO/DTO semantics | [`phase-0-system-requirements.md`](phase-0-system-requirements.md) | local | Defines CTO ACK + retry; the UPLOAD/DOWNLOAD short-frame budgets derive from these |
| 8 | NIST FIPS-180-4 SHA / CRC reference for BUILD_CHECKSUM | <https://csrc.nist.gov/pubs/fips/180-4/upd1/final> | 2026-05-15 | Reference for the CRC-32 variant used in PR-29 (Cite at PR-29 commit) |

## Decisions

| # | Decision | Choice | Rejected | Cite / Trace |
|---|---|---|---|---|
| D11 | Slave memory backend ownership | Caller-attached buffer via `tethys_xcp_attach_memory(state, mem, size)` exposed in the public API; dispatcher reads/writes only within `[0 .. size)` | Module-level static memory (forbids parallel test fixtures, couples dispatcher to a global, harder to wrap with ECC in Phase 8 space profile) | ADR-0005; ECSS-E-ST-40C Rev.1 §5.4 |
| D12 | Endianness on the wire | Hardcode little-endian for `address` field in SET_MTA / SHORT_UPLOAD (matches XCP `BYTE_ORDER` = Intel default per `CommModeBasic` Phase 1 default) | Big-endian (Motorola) - to land in Phase 8 space profile via runtime detect | XCP 1.4 Part 2 §1.3.2.4 Table 7 |
| D13 | Single-frame max upload size | MAX_CTO=8 -> 7-byte payload per UPLOAD; multi-CTO block-transfer mode deferred to Phase 3 (DAQ ODT block transfer machinery shares the infrastructure) | Implement block-transfer now (premature; doubles handler size; Phase 1 acceptance was single-frame) | XCP 1.4 Part 2 §1.3.3.2 |
| D14 | MTA auto-increment side-effect | UPLOAD increments MTA by N on success; SHORT_UPLOAD does NOT (stateless per spec); DOWNLOAD increments by N on success (lands in PR-29) | Always increment (breaks SHORT_UPLOAD spec) | XCP 1.4 Part 2 §1.3.3.2 + §1.3.3.6 |
| D15 | Error semantics for out-of-range address | Return `ERR_OUT_OF_RANGE` (0x22) for both: N > MAX_CTO-1 AND address+N > memory_size. Defensive u32-overflow check before the comparison | Silently truncate (corrupts the master's view of slave memory) | XCP 1.4 Part 2 Table 12 |
| D16 | SET_MTA / UPLOAD response shape | SET_MTA: PID-only positive response (1 byte); UPLOAD / SHORT_UPLOAD: PID + N data bytes | Multi-byte SET_MTA response with echoed MTA (non-standard) | XCP 1.4 Part 2 §1.3.3.1 |
| D17 (PR-29) | Checksum type default | `XCP_ADD_44` (running 32-bit sum) for marine; `XCP_CRC_32` for space profile (Polynomial 0x04C11DB7, IEEE 802.3) | CRC-CCITT-16 (too short for space-profile budget) | XCP 1.4 Part 2 §1.5 |
| D18 (PR-29) | SYNCH semantics | Slave always returns `ERR_CMD_SYNCH` (0x00) per spec; master treats as a marker, not as a fatal error | Return positive RES (breaks state-machine reset) | XCP 1.4 Part 2 §1.3.1.2 |
| D19 (PR-2C) | A2L parser engine | **Hand-rolled minimal reader** in `tethys_master.protocol.a2l` (~300 LOC) covering the MODULE / MEASUREMENT / CHARACTERISTIC subset Tethys needs today. Unknown blocks (COMPU_METHOD, COMPU_VTAB, RECORD_LAYOUT, IF_DATA, AXIS_DESCR, …) are silently skipped. Canonical round-trip emitter. | `Sauci/pya2l` (BSD-3) — 64 MB wheel + grpcio + grpcio-tools runtime dep, heavy for Phase 2's needs; deferred to Phase 6 GUI work where richer COMPU_METHOD / IF_DATA reads land. The `A2LFile` facade is the swap point. christoph2/pyA2L (GPLv2) ruled out — copyleft contamination. | ASAM MCD-2 MC v1.7 §4.4.10 / §4.4.18; ADR-0007 |
| D20 (PR-2D) | Differential test scope | Cross-implementation parse-equivalence: Tethys encodes every CTO request and every response body; `pyxcp.types` Construct schemas parse the same bytes and report matching field values. pyxcp pinned at `==0.29.8` in the `diff-test` optional extra (LGPLv3, runtime-imported only by `master/tests/test_protocol_diff_pyxcp.py`). | Live side-by-side `pyxcp.Master` vs `tethys-master` against the simulator (requires the simulator to speak XCP-on-Ethernet framing, which is Phase 5 transport work — premature). Full DAQ + STIM diff deferred to Phase 3 acceptance. | parent §8 Phase 2 acceptance; ADR-0007 + PR-22 D1 |

## Implementation Reference

- **PR-28** (SET_MTA + UPLOAD + SHORT_UPLOAD): merged on 2026-05-15 as squash commit `790e541`. 19 Unity tests + 18 master pytest cases. Caller-attached memory backend per D11.
- **PR-29** (DOWNLOAD + BUILD_CHECKSUM + SYNCH): merged on 2026-05-15 as squash commit `e322b58`. +16 Unity + +15 master pytest cases. Completes the dispatcher half of the Phase 2 acceptance criterion (10 commands).
- **PR-2C** (A2L parser facade): merged on 2026-05-15 as PR #38. Hand-rolled minimal reader per the revised D19. Validated against Worker D's 3 fixtures from PR #31 (`trivial`, `realistic`, `edge_case_if_data`); all 3 round-trip cleanly. 31 master pytest cases.
- **PR-2D** (this PR — differential test vs pyxcp): pyxcp 0.29.8 pinned in `diff-test` optional extra. 20 pytest cases covering (i) command-PID equivalence against `pyxcp.types.Command`, (ii) response-body parse equivalence (Tethys encodes / pyxcp parses) for CONNECT / GET_STATUS / BUILD_CHECKSUM, (iii) request-body wire-layout equivalence for SET_MTA, (iv) `ERR_CMD_SYNCH` success-case semantics per spec. Closes the Phase 2 acceptance criterion and flips `p2` → completed.

## Open follow-ups

- `Sauci/pya2l` is the long-term parser of choice per ADR-0007 but deferred to
  the Phase 6 GUI work (D19 above). The `A2LFile` facade is the swap point;
  callers depend on the facade, not on the parser internals.
- A live side-by-side `pyxcp.Master` ↔ `tethys-master` differential test
  needs the simulator to speak XCP-on-Ethernet framing (4-byte LEN/CTR
  header per CTO). This is Phase 5 transport work — premature for Phase 2.
  The cross-implementation parse-equivalence test (D20) covers the wire
  layout half of the acceptance criterion; the live-master half lands at
  Phase 5 once the transport conformance suite exists.
- Multi-CTO block-transfer mode for UPLOAD / DOWNLOAD reuses the DAQ ODT
  machinery from Phase 3. Defer until then.
- Coverage gate: parent §12 wants ≥95% statement + ≥90% MC/DC on the protocol
  core by P2. `coverage.yml` already enforces this against `slave/src/core/`
  via gcovr.
- Frama-C/WP optional verification of the dispatcher's bounds checks is
  parked for Phase 8 (space profile) — the ACSL contracts encode exactly the
  invariants D15 enforces with runtime checks.
