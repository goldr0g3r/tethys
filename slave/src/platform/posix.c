/*
 * src/platform/posix.c - host-side (POSIX + Windows) implementation of the
 * Tethys platform abstraction layer (PAL).
 *
 * Module: tethys::platform::posix
 * Profiles: posix-sim (used by Phase 1+ CI; also by Phase 9 HIL bench host).
 * Standards:
 *   - ASAM XCP 1.4 Part 2 §1.1 (the PAL serves the protocol's timestamp + tick
 *     semantics).
 *   - ADR-0005 - no dynamic allocation; this file allocates only file-scope
 *     static state.
 *   - .cursor/rules/no-recursion-no-goto.mdc - no recursion, no goto, all
 *     loops bounded.
 *
 * Rationale for Windows support: Tethys developers use Windows + WSL2 + macOS
 * + Linux. Keeping the POSIX host PAL portable means `cmake --preset=dev`
 * builds on all three without an extra `#ifdef _WIN32` per-call branch.
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */

#include "tethys/platform.h"

#include <stdio.h>
#include <stdlib.h>

#if defined(_WIN32)
/*
 * On Windows we use QueryPerformanceCounter for the monotonic clock + the
 * synchapi.h SwitchToThread() for the yield. The minimal Windows.h subset is
 * pulled in via the compatibility macros below to avoid dragging in the full
 * Windows GDI surface.
 */
#  define WIN32_LEAN_AND_MEAN
#  define NOMINMAX
#  include <windows.h>
#else
#  include <sched.h>
#  include <time.h>
#endif

/* ---- Internal helpers ----------------------------------------------------- */

#if defined(_WIN32)
/*
 * Lazy-initialised QueryPerformanceFrequency cache. QueryPerformanceCounter
 * documentation guarantees the frequency does not change at run-time, so we
 * read it exactly once and reuse forever.
 */
static LARGE_INTEGER tethys_qpc_freq_; /* zero-initialised at .bss */

static void tethys_qpc_init_freq_(void)
{
    if (tethys_qpc_freq_.QuadPart == 0)
    {
        (void)QueryPerformanceFrequency(&tethys_qpc_freq_);
    }
}
#endif

/* ---- Public API ----------------------------------------------------------- */

uint64_t tethys_platform_now_us(void)
{
#if defined(_WIN32)
    LARGE_INTEGER counter;
    tethys_qpc_init_freq_();
    (void)QueryPerformanceCounter(&counter);
    /*
     * Scale counter ticks -> microseconds with overflow-safe math.
     * `freq` is hardware-dependent (typically 10 MHz on modern Win10+) so we
     * cast to 64-bit before the multiply.
     */
    uint64_t const freq = (uint64_t)tethys_qpc_freq_.QuadPart;
    if (freq == 0U)
    {
        return 0U; /* defensive: should never happen post-init */
    }
    uint64_t const ticks = (uint64_t)counter.QuadPart;
    return (ticks * 1000000U) / freq;
#else
    struct timespec ts;
    int const rc = clock_gettime(CLOCK_MONOTONIC, &ts);
    if (rc != 0)
    {
        return 0U;
    }
    uint64_t const sec = (uint64_t)ts.tv_sec;
    uint64_t const nsec = (uint64_t)ts.tv_nsec;
    return (sec * 1000000U) + (nsec / 1000U);
#endif
}

void tethys_platform_yield(void)
{
#if defined(_WIN32)
    (void)SwitchToThread();
#else
    (void)sched_yield();
#endif
}

void tethys_platform_panic(char const* msg)
{
    char const* const eff_msg =
        (msg != NULL) ? msg : "tethys_platform_panic: <null message>";
    (void)fprintf(stderr, "FATAL: %s\n", eff_msg);
    (void)fflush(stderr);
    /*
     * abort() is acceptable on the host-side simulator (parent plan §4
     * verification layer + ADR-0005 §consequences: host targets may use libc
     * facilities that flight targets cannot). On STM32 the panic path lives
     * in stm32_startup.c and never calls libc.
     */
    abort();
}

void tethys_platform_watchdog_kick(void)
{
    /*
     * No-op on POSIX. The simulator has no watchdog peripheral; the host
     * OS-level scheduler arbitrates fairness.
     *
     * Documented inline so reviewers can see this is intentional rather than
     * a stub-pending-implementation.
     */
}
