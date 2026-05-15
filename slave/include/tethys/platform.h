/*
 * tethys/platform.h - portable platform abstraction layer (PAL).
 *
 * Module: tethys::platform
 * Profiles: all (marine, space, posix-sim)
 * Standards:
 *   - ASAM XCP 1.4 Part 2 §1.1 (the protocol requires a monotonic clock for
 *     timestamping; PAL exposes it).
 *   - ECSS-E-ST-40C Rev.1 §5.4.2.2 (HAL / device-abstraction concept).
 *   - ADR-0005 - no dynamic allocation; PAL only exposes value types or
 *     caller-owned buffers.
 *   - .cursor/rules/no-recursion-no-goto.mdc - all PAL implementations are
 *     non-recursive and goto-free.
 * Trace: docs/traceability.csv (rows TETHYS-DES-0030..0033 land at PR-10)
 *
 * Implementations:
 *   - slave/src/platform/posix.c       - host-side simulator (Phase 1+ CI)
 *   - slave/src/platform/stm32/        - STM32F4 / F7 / H7 (Phase 7 + 8)
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */
#ifndef TETHYS_PLATFORM_H
#define TETHYS_PLATFORM_H

#pragma once

#include "tethys/tethys_export.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Monotonic microsecond clock.
 *
 * Strictly non-decreasing across calls (subject to overflow at ~584 000 years
 * on a 64-bit counter). Required by the XCP DAQ timestamp path so frames are
 * stamped at capture time, not at transmit time.
 *
 * @return Microseconds since an unspecified epoch (boot on bare-metal, OS
 *         monotonic clock on POSIX, `QueryPerformanceCounter` on Windows).
 *
 * @safety MISRA C:2023 clean. Re-entrant. Safe to call from ISR on STM32 (the
 *         SysTick handler increments an `atomic` overflow counter; readers
 *         tolerate at most one increment race).
 */
TETHYS_EXPORT uint64_t tethys_platform_now_us(void);

/**
 * @brief Cooperative yield.
 *
 * On POSIX calls `sched_yield()`; on Windows calls `SwitchToThread()`; on
 * bare-metal STM32 it is a no-op (the polling loop has no other task to give
 * the CPU to). Used by transports that poll an ingress buffer.
 *
 * @safety MISRA C:2023 clean. Non-blocking.
 */
TETHYS_EXPORT void tethys_platform_yield(void);

/**
 * @brief Never-returns panic. Logs @p msg via the platform-defined sink and
 *        halts execution.
 *
 * On POSIX writes to stderr then calls `abort()`. On STM32 writes the message
 * over the dedicated debug UART then enters a tight `for(;;)` loop and lets
 * the IWDG (independent watchdog) reset the MCU.
 *
 * @param[in] msg Null-terminated C string describing the fault. May be NULL
 *                in which case a default string is used.
 *
 * @note `abort()` on POSIX is acceptable because the POSIX target is the
 *       host-side simulator (Phase 1+ CI), not flight code. Flight builds
 *       use the STM32 platform which never calls libc abort().
 *
 * @safety MISRA C:2023 clean. Marked `noreturn` via attribute when the
 *         compiler supports it (GCC, Clang).
 */
#if defined(__GNUC__) || defined(__clang__)
__attribute__((noreturn))
#endif
TETHYS_EXPORT void tethys_platform_panic(char const* msg);

/**
 * @brief Kick the platform watchdog (no-op on POSIX).
 *
 * Called from the DAQ tick. The space profile requires this on every tick
 * (`.cursor/rules/space-profile-invariants.mdc`). The marine profile makes
 * it optional via `TETHYS_MARINE_WATCHDOG_ON_DAQ_TICK`.
 *
 * @safety MISRA C:2023 clean. Re-entrant.
 */
TETHYS_EXPORT void tethys_platform_watchdog_kick(void);

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* TETHYS_PLATFORM_H */
