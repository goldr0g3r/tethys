# Phase 7+8 - cross-compile + EDAC + AES-128 + service-mode foundation (research note)

> Research note backing PRs #32 (`feat/p7-marine-stm32-foundation`),
> #35 (`feat/p8-space-edac-aes`), and #NN (`test/p8-service-mode-research`,
> this PR).
> Parent plan: [`.cursor/plans/xcp_extreme-env_tool_14019278.plan.md`](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md) - todos `p7` + `p8`.
> Sub-plans:
> [`p7p8-marine-stm32-cross-7a3c1d09.plan.md`](https://github.com/goldr0g3r/tethys/blob/main/.cursor/plans/),
> [`p7p8-space-edac-aes-4c92f8b1.plan.md`](https://github.com/goldr0g3r/tethys/blob/main/.cursor/plans/).

## Scope

This note captures the **compile-time + simulated-runtime** ground for the
Phase 7 (marine STM32F4/F7) and Phase 8 (space STM32H7) targets. It
documents (a) what shipped in CI, (b) what is deferred to physical
hardware, and (c) how the next implementer picks up when STM32 Nucleo
boards arrive.

The parent plan's Phase 7 + Phase 8 todos remain `pending` until the
deferred-to-hardware items below are signed off; this note records the
foundation work so the hardware-bring-up PR can reference exactly what is
already in place.

## What landed in CI (3 PRs)

### PR #32 - `feat(profile-marine): marine cmake + stm32 hal stubs + cross-compile ci`

* `slave/cmake/arm-none-eabi.cmake` - Cortex-M generic toolchain file
  (per-MCU `-mcpu` / `-mfpu` flags layered via `TETHYS_MCU_FLAGS`).
* `slave/cmake/marine.cmake` + `slave/profiles/marine.cmake` - marine
  profile compile flags (CAL CRC opt-in, watchdog kick opt-in, runtime
  endian, 1 kHz DAQ rate, seed-and-key scheme switch).
* `slave/include/tethys/platform.h` + `slave/src/platform/posix.c` -
  portable PAL (`tethys_platform_now_us`, `_yield`, `_panic`,
  `_watchdog_kick`).
* `slave/src/platform/stm32/` - six compile-only HAL stubs:
  - `stm32_systick.c` - SysTick + `tethys_platform_now_us()`.
  - `stm32_uart.c` - USART2 + Tethys framing
    `[0x7E][len-hi][len-lo][payload..][crc8]`.
  - `stm32_canfd.c` - FDCAN / bxCAN init + send/recv ring buffers.
  - `stm32_eth.c` - W5500 SPI shell.
  - `stm32_watchdog.c` - IWDG init + `tethys_platform_watchdog_kick()`.
  - `stm32_startup.c` - weak default-handler stubs for any IRQ vector.
* `slave/src/profiles/marine/` - `marine_init.c` + `marine_workload.c`
  (synthetic engine RPM / coolant temp / injector duty signals at the
  expected `_x100` integer scaling per parent §3.3 "no float in flight").
* `slave/CMakePresets.json` - three new configure presets:
  `marine-stm32f4`, `marine-stm32f7`, `space-stm32h7` (each pinning the
  ARM toolchain + per-MCU flags + correct profile/platform cache vars).
* `.github/workflows/ci.yml` - replaces the `slave-stm32` placeholder
  with a real matrix that cross-compiles + runs `arm-none-eabi-size` +
  uploads `libtethys_slave.a` as an artefact.

### PR #35 - `feat(profile-space): space profile + edac + aes-128 seed-and-key`

* `slave/cmake/space.cmake` + `slave/profiles/space.cmake` - space
  profile compile flags (mandatory EDAC, mandatory watchdog kick,
  AES-128 16-byte seed-and-key, compile-time-fixed endian, deterministic
  ODT scheduling, tight 32 ms IWDG timeout, mandatory advisory MISRA).
* `slave/include/tethys/edac.h` + `slave/src/profiles/space/edac.c` -
  shortened SEC-DED Hamming(72,64): 64 data + 8 parity (12.5 % overhead
  per ADR-0005). Unit-tested against:
  - encode/decode round-trip with no corruption,
  - all 64 single-bit data flips correctly recovered,
  - all 8 single-bit parity flips correctly recovered,
  - representative two-bit pairs reported as DED.
* `slave/include/tethys/aes128_seed_and_key.h` +
  `slave/src/security/aes128_seed_and_key.c` - clean-room FIPS-197
  AES-128 (SubBytes, ShiftRows, MixColumns via `xtime()`,
  KeyExpansion). Encrypt-only; `verify_response` is constant-time per
  ADR-0006. Unit-tested against:
  - FIPS-197 Appendix A.1 key-expansion (first 4 + last 4 round-key
    words),
  - FIPS-197 Appendix B encrypt block,
  - FIPS-197 Appendix C.1 encrypt block,
  - `verify_response` accepts the correct response,
  - `verify_response` rejects any single-byte modification,
  - `verify_response` rejects a wrong key.
* `slave/src/profiles/space/space_init.c` + `space_workload.c` - boot
  sequence with AES key-schedule precompute, plus reaction-wheel torque
  calibration placeholder signals.

### PR #NN - `test(profile-space): service-mode state machine + research note`

* `slave/include/tethys/service_mode.h` + `slave/src/profiles/space/service_mode.c`
  - the full state machine documented in ADR-0006 §scheme:
  ```
  [LOCKED] --GET_SEED--> [SEED_ISSUED] --UNLOCK(ok)--> [UNLOCKED]
                                       --UNLOCK(fail)-> [LOCKED + ++fail]
                                                            |
                              fail_count >= 3 in <= 10 min --+--> [LOCKED_OUT]
  [UNLOCKED] --60 s inactivity--> [LOCKED]
  [LOCKED_OUT] --10 min wallclock--> [LOCKED]
  ```
* `slave/tests/test/test_service_mode.c` - 11 Unity tests covering:
  - initial state is LOCKED,
  - happy-path GET_SEED + UNLOCK with correct response,
  - `check_unlocked` returns true after unlock,
  - wrong response returns to LOCKED,
  - 3 wrong responses trigger LOCKED_OUT,
  - LOCKED_OUT rejects GET_SEED,
  - LOCKED_OUT expires after 10 minutes,
  - UNLOCKED relocks after 60 s inactivity,
  - activity refreshes the inactivity timer,
  - explicit `lock()` returns to LOCKED,
  - stale seed (> 30 s) is rejected on UNLOCK,
  - UNLOCK without GET_SEED fails.
* This research note.

## Cross-compile output (CI artefacts)

Each CI run uploads `libtethys_slave.a` per target as a workflow artefact
with 7-day retention. Reproduce locally with:

```bash
sudo apt-get install -y gcc-arm-none-eabi cmake ninja-build
cd slave
cmake --preset=marine-stm32f4 && cmake --build --preset=marine-stm32f4
cmake --preset=marine-stm32f7 && cmake --build --preset=marine-stm32f7
cmake --preset=space-stm32h7  && cmake --build --preset=space-stm32h7
arm-none-eabi-size --totals build/marine-stm32f4/libtethys_slave.a
```

The static library is the **end of the foundation chain**; a downstream
"firmware" application (the hardware-bring-up PR) provides the linker
script, the crt0 / vector table, and the application entry point.

## Deferred to physical hardware

These items are explicitly out of scope for the foundation PRs and must be
covered by a follow-up "hardware bring-up" PR once Nucleo boards land on
the bench.

| Item | Why deferred | Where it lands |
| --- | --- | --- |
| `*.ld` linker script with `_stack_top`, `.text/.data/.bss` regions per part | needs real flash map per RM0410 / RM0433 / RM0090 | bring-up PR |
| `Reset_Handler` ASM + copy-data-flash-to-RAM | needs real startup ASM | bring-up PR |
| Full ARM vector table per MCU | needs the IRQ matrix from the part-specific RM | bring-up PR |
| GPIO + RCC clock-tree setup for USART2 / FDCAN1 / SPI1 (W5500) / FT232RL UART | needs scope + multimeter on the bench | bring-up PR |
| FreeRTOS (or bare-metal scheduler choice) | parent plan §7 baseline; the choice locks once we have task-budget measurements | bring-up PR |
| Real per-target AES-128 key burn into the read-protected flash sector | needs the per-board provisioning runbook | `docs/runbooks/hardware-setup-stm32.md` §6 |
| **Phase 7 acceptance**: 24 h soak on the F767ZI bench (zero leaks, watchdog never tripped) | needs the bench | parent plan `p7` |
| **Phase 7 trace rows**: IEC 60945 + IACS UR E22 Rev.3 lab measurements | needs environmental chamber + class society auditor | `docs/traceability.csv` |
| **Phase 8 acceptance**: fault-injection bench (single-event upset on CAL page, frame loss, frame corruption) | needs the bench + fault-injection harness | parent plan `p8` |
| **Phase 8 trace rows**: ECSS-E-ST-40C + NPR 7150.2D + DO-178C DAL-B objective fills with bench evidence | needs the bench | `docs/traceability.csv` |
| **Phase 8**: hardware-RNG characterisation for the H7 TRNG peripheral | needs scope statistics on the actual peripheral | new research note `docs/research/phase-8-security.md` (per ADR-0006) |
| **Phase 8**: side-channel posture review (DPA / SPA scope) | explicitly out of scope per ADR-0006 §risk for academic dev kit | future research note for any flight-hardware deployment |

## How the next implementer picks up

The runbook [`docs/runbooks/hardware-setup-stm32.md`](../runbooks/hardware-setup-stm32.md)
is the authoritative entry point. When Nucleo boards arrive:

1. **Parts + toolchain**: follow runbook §1 (parts list, USD budget) and
   §2 (toolchain install: ARM cross-compiler, ST-Link, udev rules,
   SocketCAN).
2. **Wiring**: runbook §3 (marine STM32F4/F7) or §4 (space STM32H7).
3. **First-time bring-up**: runbook §5 - blink-of-life via the vendor
   demo to prove the toolchain end-to-end.
4. **Drop in the missing pieces**:
   - Add `slave/src/platform/stm32/stm32f767zi.ld` (or `.h7`) and
     `stm32_startup.s` (or extend the existing `stm32_startup.c` with the
     vector table + Reset_Handler).
   - Wire GPIO + RCC clock-tree setup into the existing
     `tethys_stm32_uart_init`, `_canfd_init`, `_eth_init`,
     `_systick_init`, `_watchdog_init` (the function bodies' "Real init
     sequence" comments are step-by-step checklists).
5. **Flash + smoke**: runbook §6 (`st-flash write
   build/<preset>/tethys_slave.bin 0x8000000`).
6. **Connect**: runbook §7 (UDP for marine, UART or CAN for space).
7. **Soak + fault inject**:
   - Marine: 24 h continuous DAQ; assert watchdog never tripped.
   - Space: fault-injection bench - bit-flip CAL page, drop CAN frame,
     corrupt UART frame; assert EDAC / CRC catches each.
8. **Fill trace rows + flip parent-plan todos**: edit
   `docs/traceability.csv` and the parent plan `p7` / `p8` todos to
   `completed`.

## Cross-references

* Parent plan §3.3 (profile table).
* Parent plan §7 / §8 (phase scope).
* [ADR-0002](../adr/0002-profile-based-build-system.md) - profile-based
  build system (compile-time selection).
* [ADR-0005](../adr/0005-no-dynamic-allocation.md) - no dynamic allocation.
* [ADR-0006](../adr/0006-aes-128-seed-and-key.md) - the seed-and-key scheme
  this PR set implements end-to-end.
* [ADR-0010](../adr/0010-packet-loss-tolerance-budget.md) - packet-loss
  budgets (space rows 8-11; EDAC feeds the CAL-page bound).
* [`.cursor/rules/marine-profile-invariants.mdc`](../../.cursor/rules/marine-profile-invariants.mdc).
* [`.cursor/rules/space-profile-invariants.mdc`](../../.cursor/rules/space-profile-invariants.mdc).
* [`.cursor/rules/no-recursion-no-goto.mdc`](../../.cursor/rules/no-recursion-no-goto.mdc).
* [`.cursor/rules/no-dynamic-allocation.mdc`](../../.cursor/rules/no-dynamic-allocation.mdc).
* [`docs/runbooks/hardware-setup-stm32.md`](../runbooks/hardware-setup-stm32.md).
* NIST FIPS-197 - <https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.197-upd1.pdf>.

## Sources (retrieved 2026-05-15)

| Source | Retrieved | URL / spec |
| --- | --- | --- |
| NIST FIPS-197 AES specification | standards (no retrieval-date rule) | <https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.197-upd1.pdf> |
| ASAM XCP 1.4 Part 2 §1.3 seed-and-key | standards | ASAM MCD-1 XCP 1.4 Part 2 |
| ST RM0410 (STM32F76x/77x reference manual) | standards | <https://www.st.com/resource/en/reference_manual/rm0410-stm32f76xxx-and-stm32f77xxx-advanced-armbased-32bit-mcus-stmicroelectronics.pdf> |
| ST RM0433 (STM32H743/753 reference manual) | standards | <https://www.st.com/resource/en/reference_manual/rm0433-stm32h742-stm32h743753-and-stm32h750-value-line-advanced-armbased-32bit-mcus-stmicroelectronics.pdf> |
| ST RM0090 (STM32F4 reference manual) | standards | <https://www.st.com/resource/en/reference_manual/rm0090-stm32f405415-stm32f407417-stm32f427437-and-stm32f429439-advanced-armbased-32bit-mcus-stmicroelectronics.pdf> |
| WIZnet W5500 datasheet v1.1.0 | vendor | <https://docs.wiznet.io/Product/iEthernet/W5500/datasheet> |
| ECSS-E-ST-40C Rev.1 (April 2025) - software engineering | standards | ECSS Secretariat |
| NPR 7150.2D - NASA SW engineering requirements | standards | <https://nodis3.gsfc.nasa.gov/displayDir.cfm?Internal_ID=N_PR_7150_002D_> |
| IACS UR E22 Rev.3 (in force 2024-07-01) - marine SW process | standards | IACS |
| CMake 3.31 docs - cmake-presets(7) | 2026-05-15 | <https://cmake.org/cmake/help/latest/manual/cmake-presets.7.html> (used to diagnose the v3 schema requirement for `toolchainFile`) |
| Arm GNU Toolchain release notes (14.x) | 2026-05-15 | <https://developer.arm.com/Tools%20and%20Software/GNU%20Toolchain> |

(All standards documents are exempt from the 14-day retrieval-date rule
per [`.cursor/rules/research-note-per-phase.mdc`](../../.cursor/rules/research-note-per-phase.mdc)
"Standards documents (IEC, ECSS, NPR, DO, IACS, ASAM, ISO) are exempt
from the 14-day rule but must cite the edition/revision.")

## Decisions log

| Decision | Rationale |
| --- | --- |
| Clean-room AES-128 (not tiny-AES-c vendor) | Tighter trace into FIPS-197 §sections; no LICENSE-vendoring decision; only ~250 lines + tables. tiny-AES-c remains the documented fallback per the brief's stop-condition. |
| Encrypt-only AES API | The seed-and-key scheme per ADR-0006 needs only encrypt() on the slave; never decrypt(). Exposing decrypt would needlessly grow the attack surface. |
| Constant-time `verify_response` via XOR-accumulator | Defeats timing-side-channel oracle on the verify step per ADR-0006 §risk. |
| EDAC: shortened Hamming(72,64) separate-storage parity | Matches STM32H7's 64-bit-wide flash granularity; 12.5 % overhead matches ADR-0005 §consequences; simpler than interleaved-positions Hamming. |
| Service-mode wallclock as a parameter (not internal call) | Unit-testable: simulates the full 10-min lockout in microseconds. |
| Service-mode `lock()` preserves fail counters | Prevents a malicious DISCONNECT-loop from resetting the lockout window. |
| STM32 HAL stubs compile-only (register I/O gated by `TETHYS_PLATFORM_STM32`) | Lets cross-compile validate symbol resolution + the cmake substrate without needing real hardware; the hardware-bring-up PR fills in the register pokes. |
| `target_compile_features(... c_std_11)` replaced with `set_target_properties C_STANDARD/REQUIRED/EXTENSIONS` | CMake's compiler-feature DB has no entries for arm-none-eabi-gcc, so the feature-based form fails the cross-compile. |
| `install-rules.cmake` skipped when `CMAKE_CROSSCOMPILING` | Cross-built static library ships as a CI artefact; no system install needed. |

## Open follow-ups

| Item | Owner | When |
| --- | --- | --- |
| Linker script + startup ASM + vector table | hardware-bring-up PR | when Nucleo boards arrive |
| FreeRTOS choice + task budget | hardware-bring-up PR | after first soak |
| 24 h marine soak | Phase 7 acceptance | bench-time |
| Fault-injection bench (space) | Phase 8 acceptance | bench-time |
| Hardware-RNG characterisation | Phase 8 security research note | bench-time |
| Worker B's UART/SxI master transport framing alignment with `stm32_uart.c` | Worker B + me | when their PR lands; if their framing differs, one PR aligns `stm32_uart.c`. |
| Code Connect map for the master tool's connection-wizard profile selector | Worker C | Phase 6 |

## Implementation Reference

| PR | URL | Merged on |
| --- | --- | --- |
| #32 - PR-A `feat(profile-marine)` | <https://github.com/goldr0g3r/tethys/pull/32> | *to be filled at merge* |
| #35 - PR-B `feat(profile-space)` | <https://github.com/goldr0g3r/tethys/pull/35> | *to be filled at merge* |
| #NN - PR-C `test(profile-space) service-mode + this note` | *opened with this PR* | *to be filled at merge* |
