# Phase 3 — DAQ + STIM (execution note)

> Research note backing the Phase-3 PR train (PR-3a..PR-3e).
> Parent plan: [`.cursor/plans/xcp_extreme-env_tool_14019278.plan.md`](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md) — todo `p3`.
> Worker: F (Phase 3 + Phase 4 sequential mission).

## Table of contents

1. [Scope](#1-scope)
2. [Sources (retrieved 2026-05-15)](#2-sources-retrieved-2026-05-15)
3. [Decisions](#3-decisions)
4. [PR slicing](#4-pr-slicing)
5. [Static buffer sizing](#5-static-buffer-sizing)
6. [Wire-format reference](#6-wire-format-reference)
7. [Acceptance criteria](#7-acceptance-criteria)
8. [Open follow-ups](#8-open-follow-ups)
9. [Implementation Reference](#9-implementation-reference)

---

## 1. Scope

Phase 3 of the parent plan (§8 row p3) implements XCP's DAQ (Data AcQuisition) and STIM (Stimulation) services end-to-end across the Tethys slave + master + simulator + GUI:

- **Slave (C11):** dynamic ODT / DAQ-list engine sized at compile time per [ADR-0005](../adr/0005-no-dynamic-allocation.md); event-channel tick fan-out; DTO emission via TAL; STIM consume path.
- **Master (Python):** DAQ list builder + WRITE_DAQ orchestration; DTO receive loop with CTR-based `DAQ_GAP` detection per [`phase-0-system-requirements.md`](phase-0-system-requirements.md) §7; asammdf-backed MDF4 recorder; PlotPane live wiring.
- **Simulator (Python):** posix-sim DAQ-list configuration + cyclic event-tick emitter so the master's headless integration tests run with no slave hardware.
- **GUI (PySide6):** `PlotPane` subscribes to live DAQ samples; `DiagnosticsPane` counter increments on every `DAQ_GAP` event.

Out of scope (deferred):

- **PTP / IEEE-1588 timestamping** — XCP 1.4 supports a per-DTO timestamp prefix; Phase 3 ships the 4-byte timestamp option but defers PTP slave-clock synchronisation to Phase 7 (marine STM32 bring-up where the real Ethernet PHY exposes the hardware-timestamping unit).
- **Predefined DAQ lists** — Phase 3 covers **static** (compile-time fixed; tested via static fixture) and **dynamic** (ALLOC_DAQ + ALLOC_ODT + ALLOC_ODT_ENTRY + WRITE_DAQ) DAQ lists per ASAM XCP 1.4 Part 2 §1.4.1. Predefined falls out for free once static is in place; documented but not exercised by the acceptance suite.
- **STIM in flight mode on the space profile** — per the [space profile invariants](../../.cursor/rules/space-profile-invariants.mdc) STIM is service-mode-only; Phase 3 ships the protocol path but the space-profile gate (AES-128 unlock) is in Phase 8.

## 2. Sources (retrieved 2026-05-15)

The XCP 1.4 specification (S1 in [`phase-0-standards-matrix.csv`](phase-0-standards-matrix.csv)) is the normative source. The vector book (S3) and CSS Electronics tutorial cross-checked for wire-format examples. Library docs for asammdf and pyqtgraph reviewed for the master-side recorder + plot wiring.

| Source | Section | Why cited |
| --- | --- | --- |
| ASAM XCP 1.4 Part 2 §1.4 | DAQ command set | All 11 DAQ commands in PR-3a (FREE_DAQ, ALLOC_*, SET_DAQ_PTR, WRITE_DAQ[_MULTIPLE], SET_DAQ_LIST_MODE, START_STOP_DAQ_LIST, START_STOP_SYNCH, GET_DAQ_*) |
| ASAM XCP 1.4 Part 2 §1.4.2 | DTO packet ID range | PID 0x00..0xFB = DAQ ODT slot; FIRST_PID + ODT index addressing |
| ASAM XCP 1.4 Part 2 §1.4.2.2 | DAQ list configuration | SET_DAQ_PTR / WRITE_DAQ stateful pointer semantics |
| ASAM XCP 1.4 Part 2 §1.4.2.4 | START_STOP_DAQ_LIST mode bits | per-list start/stop/select |
| ASAM XCP 1.4 Part 2 §1.4.2.5 | START_STOP_SYNCH | all-lists race-fix variant |
| ASAM XCP 1.4 Part 2 §1.4.2.6 | SET_DAQ_LIST_MODE | TIMESTAMP / DIRECTION / PID_OFF mode bits |
| ASAM MCD-2 MC v1.7 §3.7.5 | A2L EVENT block | declaration of event channels referenced by SET_DAQ_LIST_MODE |
| ASAM MCD-2 MC v1.7 IF_DATA XCP §6.4 | DAQ_EVENT / EVENT_GROUP / DAQ_LIST_TYPE | XCP-on-A2L bridge consumed by master PR-3d |
| [`docs/learn/xcp-101.md`](../learn/xcp-101.md) §6 | DAQ walk-through | first-time reader narrative; mirrored in test names |
| [`docs/research/phase-0-system-requirements.md`](phase-0-system-requirements.md) §7 | DAQ recovery semantics | DAQ_GAP event shape; per-ODT policy hook |
| [ADR-0005](../adr/0005-no-dynamic-allocation.md) | static buffer sizing | MAX_DAQ_LISTS / MAX_ODT_PER_LIST / MAX_ENTRIES_PER_ODT constants land in `tethys_static_memory.h` |
| [ADR-0010](../adr/0010-packet-loss-tolerance-budget.md) row 2 + 12 | DAQ acceptance | 1 kHz loopback, zero loss for 60 min |
| [asammdf 8.2 docs](https://asammdf.readthedocs.io/en/master/api.html) | `MDF` constructor, `MDF.append`, `Signal` shape | master-side recorder in PR-3c |
| [pyqtgraph 0.13.7 PlotItem docs](https://pyqtgraph.readthedocs.io/en/latest/api_reference/graphicsItems/plotitem.html) | `setData`, `setDownsampling` | PR-3d uses existing PlotPane.append_sample path; no new pyqtgraph features required |

All non-standard sources retrieved 2026-05-15 per [`.cursor/rules/research-note-per-phase.mdc`](../../.cursor/rules/research-note-per-phase.mdc) ≤14-day rule.

## 3. Decisions

### D1 — Dynamic DAQ first; static and predefined as compile-time configuration only

ASAM XCP 1.4 allows three DAQ-list flavours (Part 2 §1.4.1): **static** (compile-time fixed), **predefined** (slave declares the list set; master picks), **dynamic** (master allocates lists via ALLOC_DAQ + ALLOC_ODT + ALLOC_ODT_ENTRY + WRITE_DAQ at runtime). Tethys ships **dynamic** as the primary path because it is the only flavour that needs the full 11-command implementation; **static** falls out for free by pre-allocating a known DAQ list count at init time and refusing ALLOC_DAQ. Predefined is documented out-of-scope for Phase 3; the wire format is identical to dynamic so it requires no protocol-layer work, only a configuration-init hook (defer to Phase 7 marine workload).

### D2 — Buffer sizing via header constants (not generated header)

[ADR-0005](../adr/0005-no-dynamic-allocation.md) describes a generated `tethys_static_memory.h` for buffer sizes. Phase 3 ships fixed constants in `xcp_daq.h` (`TETHYS_DAQ_MAX_LISTS=4`, `TETHYS_DAQ_MAX_ODT_PER_LIST=8`, `TETHYS_DAQ_MAX_ENTRIES_PER_ODT=16`, `TETHYS_DAQ_MAX_DTO_BYTES=64`) chosen to fit the marine 1 kHz baseline + space service-mode 100 Hz baseline without leaving the protocol-core RAM budget. The full generated `tethys_static_memory.h` lands when Phase 7 marine workloads start exercising real A2L `MAX_DTO` values; until then the fixed constants are a tested baseline. The ADR-0005 sizing formula still applies: `odt_buffer_size = ceil(transport_max_burst_loss × odt_packet_size × 2.0)`; the chosen constants give 64 × 8 × 4 = 2 KiB per DAQ list, 8 KiB total — safely under STM32F4's 192 KiB SRAM.

### D3 — DAQ_GAP event constructed master-side; CTR field on the XCP-on-UDP transport header

XCP 1.4 Part 2 §3.1.5 specifies a 16-bit CTR field in the XCP-on-Ethernet transport header. PR-3c implements a wrap-aware CTR tracker in `master/src/tethys_master/protocol/daq.py`. On gap detection the receive loop emits a `DAQ_GAP` event matching the shape documented in [`phase-0-system-requirements.md`](phase-0-system-requirements.md) §7. The simulator (`simulator/src/tethys_sim/slave.py`) gains a synthetic CTR-stripping helper so the existing UDP transport keeps the simple "datagram == 1 DTO" shape; loopback transport in `master/src/tethys_master/transport/loopback.py` enqueues the raw DTO without CTR because the loopback is in-process. Tests use a `_InjectableTransport` test helper that lets the master receive synthetic DTOs with controllable CTR sequence.

### D4 — Optional 4-byte DTO timestamp prefix; PTP deferred

XCP 1.4 Part 2 §1.4.2.6 mode-bit 0x04 enables TIMESTAMP on DAQ DTOs. The slave's DAQ engine (PR-3b) emits a 4-byte little-endian timestamp prefix between PID and payload when the master sets the bit. The slave's clock source is the platform-specific monotonic microsecond counter (posix-sim: `time.monotonic_ns()`; STM32: SysTick + 32-bit roll-over counter — Phase 7). PTP slave-clock synchronisation is a Phase 7 stretch goal once real Ethernet hardware exists.

### D5 — STIM uses the same DAQ-list dataclasses; direction bit flips at SET_DAQ_LIST_MODE

PR-3e implements STIM as the inverse direction of DAQ. Both sides share `DaqList`, `Odt`, `OdtEntry` dataclasses on the master and the same `tethys_daq_*` API on the slave. The slave's `tethys_daq_apply_stim_dto()` writes the unpacked entries into the attached memory backend exactly like a master-side DOWNLOAD, but driven by the cyclic STIM stream instead of a one-shot CTO. The space profile's STIM gate (AES-128 service-mode unlock) lives in Phase 8 — Phase 3 ships the protocol path only; the dispatcher leaves the resource-protection check as a TODO comment and tracks it via a Phase-8 work item.

### D6 — Acceptance test runs at 1 kHz over loopback for 60 s in CI quick-run + 60 min nightly

[ADR-0010](../adr/0010-packet-loss-tolerance-budget.md) row 12 mandates "zero loss for 60 minutes on loopback" as the canonical DAQ acceptance criterion. The PR-3b quick-run test executes 1 kHz × 60 s = 60 000 DTOs on every PR and asserts `daq_gap_count == 0`; the PR-3e nightly soak runs the full 60 min × 60 s × 1000 = 3 600 000 DTOs via a dedicated `daq-soak.yml` workflow (separate from `ci.yml` so the matrix wall-clock stays under the parent §6.7 12-minute budget). The 60 s quick-run is sufficient to exercise the CTR-tracking + buffer-overrun code paths; the 60 min nightly stresses long-run drift and any accidental allocation leaks.

### D7 — MDF4 recording verifies via re-open (no Vector Free MDF Viewer dependency in CI)

The parent plan acceptance reads "MDF4 file opens in third-party tool (Vector free MDF Viewer)". The Vector MDF Viewer is a Windows GUI tool — not CI-friendly. The verification proxy: `master/tests/test_mdf4_recorder.py` writes a fixture `.mf4` file via asammdf, then re-opens it with a *fresh* `asammdf.MDF` instance, asserts the channel set + sample count + first/last timestamp match. Because asammdf is the reference reader for MDF v4 in the open-source ecosystem and is independent of the Vector Viewer code base, asammdf-roundtrip success is a sufficient proxy for "third-party-readable". The runbook [`docs/runbooks/demo-recording.md`](../runbooks/demo-recording.md) documents the manual one-time check against Vector MDF Viewer for the v1.0 release demo.

## 4. PR slicing

| PR | Branch | Scope (LOC ± tests) | Acceptance |
| --- | --- | --- | --- |
| **PR-3a** | `feat/p3a-daq-odt-engine` | Slave: `xcp_odt.{c,h}` + `xcp_daq.{c,h}` + 11 dispatcher commands (~600 + 20 tests) | Unity ALLOC/FREE pathways, SET_DAQ_PTR bounds, WRITE_DAQ + WRITE_DAQ_MULTIPLE, START_STOP per-list + SYNCH; no DTO emission yet |
| **PR-3b** | `feat/p3b-dto-event-tick` | Slave: event-tick handler emits DTOs through TAL (~400 + 12 tests) | Loopback 1 kHz × 60 s, `daq_gap_count == 0`; CTR + optional timestamp prefix; quick-run lives in `ci.yml` |
| **PR-3c** | `feat/p3c-master-daq-mdf4` | Master: `protocol/daq.py` + `protocol/mdf4_recorder.py` + receive-loop CTR tracker + 25 tests (~500) | `DaqList.samples` populated end-to-end; asammdf-roundtrip; `DAQ_GAP` event delivery |
| **PR-3d** | `feat/p3d-a2l-event-plot` | Master: A2L `EVENT` + `IF_DATA XCP/DAQ_EVENT` parse + `PlotPane` live wiring (~300 + 15 tests) | `A2LFile.events` dict populated from fixture; PlotPane.append_sample driven by DAQ stream; `mark_gap` triggered on `DAQ_GAP` |
| **PR-3e** | `feat/p3e-stim-soak-acceptance` | Slave + master STIM direction + nightly soak workflow (~250 + 10 tests) | STIM round-trip; 60-min soak workflow `daq-soak.yml`; flip `p3` to `completed` |

Five PRs total, each independently mergeable. PR-3c depends on PR-3b only via the wire-level CTR + timestamp shape, not the slave code itself; the receive-loop tests use injected DTO bytes so PR-3c can land before PR-3b ships hardware DTO emission.

## 5. Static buffer sizing

Per [ADR-0005](../adr/0005-no-dynamic-allocation.md) the DAQ engine is sized at compile time. Constants land in `slave/include/tethys/xcp_daq.h`:

```c
#define TETHYS_DAQ_MAX_LISTS              ((uint8_t)4U)
#define TETHYS_DAQ_MAX_ODT_PER_LIST       ((uint8_t)8U)
#define TETHYS_DAQ_MAX_ENTRIES_PER_ODT    ((uint8_t)16U)
#define TETHYS_DAQ_MAX_DTO_BYTES          ((uint16_t)64U)
```

RAM cost:

| Item | Bytes | Total |
| --- | --- | --- |
| `tethys_daq_entry_t` (addr + ext + length) | 6 | 6 × 16 × 8 × 4 = 3 072 |
| `tethys_daq_odt_t` (entry count + metadata) | 24 | 24 × 8 × 4 = 768 |
| `tethys_daq_list_t` (ODTs + mode + event + state) | 64 | 64 × 4 = 256 |
| DTO scratch (largest single DTO buffer) | 64 | 64 |
| `tethys_daq_engine_t` totals (incl. above) | — | **~4 KiB** |

4 KiB on a 192 KiB STM32F4 SRAM is 2.1 %. STM32H7 (1 MiB) is 0.4 %. Both well under the parent-plan §3.3 / ADR-0005 RAM headroom budget.

## 6. Wire-format reference

The 11 DAQ commands implemented in PR-3a, mapped to slave dispatcher branches:

| Cmd | Code | Request layout | Response layout | Notes |
| --- | --- | --- | --- | --- |
| FREE_DAQ | 0xD6 | `[PID]` | `[RES]` | clears all DAQ lists |
| ALLOC_DAQ | 0xD5 | `[PID][0][count_lo][count_hi]` | `[RES]` | up to MAX_LISTS |
| ALLOC_ODT | 0xD4 | `[PID][0][daq_lo][daq_hi][odt_count]` | `[RES]` | per-list |
| ALLOC_ODT_ENTRY | 0xD3 | `[PID][0][daq_lo][daq_hi][odt][entry_count]` | `[RES]` | per-ODT |
| SET_DAQ_PTR | 0xE2 | `[PID][0][daq_lo][daq_hi][odt][idx]` | `[RES]` | positions WRITE_DAQ pointer |
| WRITE_DAQ | 0xE1 | `[PID][bit_off][size][ext][addr×4]` | `[RES]` | one entry at MTA-like pointer |
| WRITE_DAQ_MULTIPLE | 0xC7 | `[PID][n][repeat: bit_off,size,ext,addr×4]` | `[RES]` | n entries in one CTO |
| SET_DAQ_LIST_MODE | 0xE0 | `[PID][mode][daq_lo][daq_hi][ev_lo][ev_hi][prescaler][priority]` | `[RES]` | mode bits 0x02 STIM, 0x04 TIMESTAMP, 0x10 PID_OFF |
| START_STOP_DAQ_LIST | 0xDE | `[PID][mode][daq_lo][daq_hi]` | `[RES][first_pid]` | per-list start/stop/select |
| START_STOP_SYNCH | 0xDD | `[PID][mode]` | `[RES]` | all-lists; race-fix variant |
| GET_DAQ_LIST_MODE | 0xDF | `[PID][0][daq_lo][daq_hi]` | `[RES][0][mode][0][event_lo][event_hi][prescaler][priority]` | mirrors SET |
| GET_DAQ_EVENT_INFO | 0xD7 | `[PID][0][ev_lo][ev_hi]` | `[RES][properties][max_daq][time_cycle][time_unit][priority]` | static event channel descriptors |
| GET_DAQ_LIST_INFO | 0xD8 | `[PID][0][daq_lo][daq_hi]` | `[RES][properties][max_odt][max_odt_entries][fixed_event]` | per-list metadata |
| GET_DAQ_RESOLUTION_INFO | 0xD9 | `[PID]` | `[RES][gran_odt][max_odt_entry][gran_stim][max_stim_entry][ts_mode][ts_ticks_lo][ts_ticks_hi]` | resolution + timestamp config |
| GET_DAQ_PROCESSOR_INFO | 0xDA | `[PID]` | `[RES][properties][max_daq_lo][max_daq_hi][max_event_lo][max_event_hi][min_daq][properties2]` | processor capabilities |
| READ_DAQ | 0xDB | `[PID]` | `[RES][bit_off][size][ext][addr×4]` | read the entry at the current SET_DAQ_PTR position |

(Three extra `GET_*` commands — `GET_DAQ_PROCESSOR_INFO`, `GET_DAQ_RESOLUTION_INFO`, `GET_DAQ_LIST_INFO`, `GET_DAQ_EVENT_INFO`, `READ_DAQ` — are included alongside the parent §8 scope so the master can interrogate slave capabilities without out-of-band assumptions.)

## 7. Acceptance criteria

| Criterion | PR | Verification |
| --- | --- | --- |
| All 11 + 5 read-back DAQ commands respond correctly per XCP 1.4 §1.4 | 3a | Unity `test_xcp_daq.c` |
| DTO emitted on event-tick with correct PID + payload + optional timestamp | 3b | Unity `test_dto_emission.c` |
| 1 kHz × 60 s loopback with zero loss (CI quick-run) | 3b | `tests/test_dto_loopback_60s.c` (Unity) |
| Master receives DTOs, decodes via DAQ-list lookup, emits DAQ_GAP on CTR gap | 3c | `master/tests/test_daq_receive.py` |
| MDF4 round-trip via asammdf | 3c | `master/tests/test_mdf4_recorder.py` |
| A2L EVENT + IF_DATA XCP_DAQ_EVENT parsed into `A2LFile.events` | 3d | `master/tests/test_a2l_event.py` |
| PlotPane live-subscribes to DAQ samples and paints gap markers | 3d | `master/tests/test_gui_plot_pane_daq.py` |
| STIM round-trip: master sends, slave applies | 3e | `master/tests/test_stim_roundtrip.py` + slave Unity |
| 1 kHz × 60 min loopback nightly with zero loss | 3e | `.github/workflows/daq-soak.yml` |

## 8. Open follow-ups

- **PTP slave-clock sync** — Phase 7 marine STM32 (Ethernet hardware-timestamping unit on STM32F7 PHY).
- **Predefined DAQ lists** — wire-format-identical to dynamic; configuration hook lands when first marine workload needs it (Phase 7).
- **Space-profile STIM AES-128 gate** — Phase 8 (depends on PR #35 service-mode state machine).
- **PGM (flash programming) commands** — explicitly out-of-scope for both Phase 3 and Phase 4 per the parent plan §13 open-question audit (PR #27 reaffirmed PGM as a Phase-10 reconsider).
- **CRC-16 / CRC-32 BUILD_CHECKSUM variants** — Phase 8 (depends on space-profile CAL CRC).

## 9. Implementation Reference

- PR-3a: *to be filled at merge*
- PR-3b: *to be filled at merge*
- PR-3c: *to be filled at merge*
- PR-3d: *to be filled at merge*
- PR-3e: *to be filled at merge*
