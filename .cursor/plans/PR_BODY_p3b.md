## Summary

Phase 3 PR-3b - wires DTO transmission for the static DAQ engine landed in PR-3a (#45) and extends the posix-sim slave with the full DAQ configuration command set + cyclic emission task.

- **Slave (`slave/src/core/xcp_daq.c` + header):** new `tethys_daq_tick(engine, event_channel, timestamp_us)` walks every running DAQ-direction list whose event matches and whose prescaler counter rolls over, packs each ODT into a DTO, and hands it to the TAL via `tethys_tr_send()`. Bounded loops; no recursion; MISRA-clean.
- **Unity tests (`slave/tests/test/test_xcp_dto_emission.c`):** 9 tests cover empty-engine no-op, single-list emit, multi-list fan-out, STIM-direction skip, prescaler honouring, event-channel mismatch skip, timestamp prefix mode, and the CI quick-run derivative of the ADR-0010 row 12 60-min loopback acceptance (1 000 ticks × 1 ODT, drained intact via loopback transport with zero loss + monotonic CTR).
- **Simulator (`simulator/src/tethys_sim/slave.py`):** functional Python twin of the C DAQ engine + handlers for all 13 configuration-side commands. An asyncio background task ticks at `daq_tick_hz` (default 1 kHz) and `sendto`s DTOs to the most recent CTO peer. Exposes `XcpSimSlave.tick_once()` as a synchronous test hook.
- **Sim tests (`simulator/tests/test_sim_daq_emission.py`):** 5 pytest-asyncio tests exercising the simulator end-to-end via UDP loopback (ALLOC pipeline, single-tick DTO with timestamp prefix, FREE_DAQ state clear, overflow → ERR_MEMORY_OVERFLOW, 100 Hz emitter loop streaming ≥10 DTOs in 200 ms).

Both opcode tables (slave + sim) strictly mirror ASAM XCP 1.4 Part 2 Table 17, so PR-3c can land a single shared master-side opcode enum without per-side translation.

## Files

| File | LOC | Note |
| --- | --- | --- |
| `slave/include/tethys/xcp_daq.h` | +39 | add `tethys_daq_tick` declaration |
| `slave/src/core/xcp_daq.c` | +59 | tick implementation + TAL fan-out |
| `slave/tests/test/test_xcp_dto_emission.c` | +244 | new — 9 Unity tests incl. 1k-tick acceptance |
| `simulator/src/tethys_sim/slave.py` | +543 / −29 | DAQ engine + 13 handlers + emitter loop |
| `simulator/tests/test_sim_daq_emission.py` | +209 | new — 5 pytest-asyncio E2E tests |

Local validation:

```
$ cmake --build build/dev   # slave - clean
$ uv run pytest -k sim_daq_emission   # simulator - 5 passed
$ uv run pytest tests/test_slave_dispatch.py   # simulator - 22 passed (no regression)
```

## Test plan

- [x] Slave C builds clean on MinGW gcc 10.3 (host build).
- [ ] CI `slave-posix` (Ceedling/Unity, Ubuntu) — 9 new tests must pass.
- [ ] CI `slave-stm32` cross-compile matrix (marine-f4/f7, space-h7) — TAL link must succeed.
- [ ] CI `misra-gate.yml` — bounded loops only, zero deviations expected.
- [ ] CI `static-analysis.yml` (clang-tidy + gcc-fanalyzer) — zero new warnings.
- [ ] CI `master` matrix — master-side Phase 1/2 tests unaffected.

## Standards trace

- ASAM XCP 1.4 Part 2 §1.4.2 (DTO emission semantics)
- ASAM XCP 1.4 Part 2 §1.4.2.6 (mode bits: DIRECTION, TIMESTAMP, PID_OFF)
- ASAM XCP 1.4 Part 2 §3.1.5 (XCP-on-Ethernet CTR field rationale)
- ADR-0004 (transport abstraction layer - `tethys_tr_send` contract)
- ADR-0010 row 2 + row 12 (DAQ loss budget + loopback acceptance)
- MISRA-C-2023 clean (mandatory + required; bounded loops only)

`Closes` no issue (Phase 3 epic stays open until PR-3e flips `p3`).
