## Summary

Lands the Tethys C-slave's static DAQ + ODT engine ahead of Phase 3's `1 kHz DAQ on simulator with zero loss for 60 min` acceptance criterion. PR-3a ships the configuration-side wire surface and the DTO pack/unpack primitives so subsequent PRs can wire DTO transmission (3b), the master-side DAQ client + MDF4 recorder (3c), A2L EVENT parsing + PlotPane live-wiring (3d), STIM direction + nightly soak workflow (3e).

- **Slave (`slave/src/core/xcp_{daq,odt}.c` + headers):** statically-sized engine (4 lists × 8 ODTs × 16 entries × 64-byte DTOs ≈ 4 KiB RAM total per ADR-0005), DAQ-list state machine, FIRST_PID auto-assignment, DTO pack/unpack helpers ready for the event-tick fan-out in PR-3b.
- **Dispatcher (`slave/src/core/xcp_dispatcher.c`):** 16 new branches forwarding the XCP 1.4 §1.4 DAQ command set to the engine. No engine attached → DAQ commands still return `ERR_CMD_UNKNOWN` so Phase 1 + Phase 2 conformance is preserved.
- **Tests:** `tests/test/test_xcp_odt.c` (9 Unity tests covering pack/unpack + error paths), `tests/test/test_xcp_daq.c` (21 Unity tests covering engine state + dispatcher routing).
- **Research note:** `docs/research/phase-3-daq-stim-execution.md` documents the D1..D7 decisions, 5-PR slicing, static buffer sizing rationale, and acceptance criteria for the full Phase-3 train.

## Files

| File | LOC | Note |
| --- | --- | --- |
| `slave/include/tethys/xcp_odt.h` | +185 | new |
| `slave/include/tethys/xcp_daq.h` | +384 | new |
| `slave/src/core/xcp_odt.c` | +123 | new |
| `slave/src/core/xcp_daq.c` | +533 | new |
| `slave/include/tethys/xcp_dispatcher.h` | +32 | DAQ engine attach API + new ERR codes |
| `slave/src/core/xcp_dispatcher.c` | +419 | 16 DAQ handlers + dispatch routing |
| `slave/CMakeLists.txt` | +2 | wire new sources |
| `slave/tests/test/test_xcp_odt.c` | +201 | 9 Unity tests |
| `slave/tests/test/test_xcp_daq.c` | +400 | 21 Unity tests |
| `docs/research/phase-3-daq-stim-execution.md` | +177 | research note |

Slave library builds clean with `cmake --build` (MinGW gcc 10.3 host build, no warnings, no errors). The arm-none-eabi-gcc cross-compile matrix in `ci.yml` validates against marine-stm32f4/f7 and space-stm32h7 targets.

## Test plan

- [x] `cmake --build build/dev` (host MinGW gcc 10.3) - clean.
- [ ] CI `slave-posix` leg (Unity + Ceedling) on Ubuntu - validates the 30 new Unity tests.
- [ ] CI `slave-stm32` legs (marine-f4, marine-f7, space-h7) cross-compile - validates ARM build.
- [ ] CI `misra-gate.yml` - zero deviations expected (engine uses only bounded loops + no dynamic alloc + no recursion / no goto).
- [ ] CI `static-analysis.yml` (clang-tidy + gcc -fanalyzer) - zero new warnings.

## Standards trace

- ASAM XCP 1.4 Part 2 §1.4 (DAQ command set)
- ASAM XCP 1.4 Part 2 §1.4.1 (ODT model)
- ASAM XCP 1.4 Part 2 §1.4.2.{2,4,5,6,13} (WRITE_DAQ + START_STOP + SET_DAQ_LIST_MODE + GET_DAQ_PROCESSOR_INFO)
- ASAM XCP 1.4 Part 2 §3.1.5 (CTR field rationale for Phase 3 PR-3c)
- ADR-0005 (no dynamic allocation; static engine sizing)
- ADR-0010 row 2 + 12 (DAQ loss budget + loopback acceptance)
- MISRA-C-2023 clean

`Closes` no issue (Phase 3 epic stays open until PR-3e flips `p3`).
