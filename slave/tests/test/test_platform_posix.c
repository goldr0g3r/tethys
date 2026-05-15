/*
 * test_platform_posix.c - smoke tests for the host-side platform layer.
 *
 * Verifies that tethys_platform_now_us() is monotonic and tethys_platform
 * _yield()/watchdog_kick() are no-ops that don't crash. Runs on every
 * `cmake --preset=dev` + ceedling test invocation.
 *
 * Standards trace:
 *   - ADR-0002 - profile-based build system (POSIX is the simulator platform).
 *   - slave/include/tethys/platform.h - public PAL contract.
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */

#include "tethys/platform.h"
#include "unity.h"

#include <stdint.h>

void setUp(void)    { /* no-op fixture */ }
void tearDown(void) { /* no-op fixture */ }

void test_platform_now_us_returns_nonzero(void)
{
    uint64_t const t = tethys_platform_now_us();
    /* Either CLOCK_MONOTONIC since boot or QueryPerformanceCounter; both
     * produce values measured in hundreds of thousands of us within a
     * second of CI start. */
    TEST_ASSERT_TRUE_MESSAGE(t > 0U, "platform_now_us must be > 0 post-boot");
}

void test_platform_now_us_monotonic(void)
{
    uint64_t const t0 = tethys_platform_now_us();
    /*
     * Spin a small bounded loop (no recursion, no goto per
     * .cursor/rules/no-recursion-no-goto.mdc) until at least one us elapses.
     * Cap at 100_000 iterations as a defensive bound (modern hardware
     * completes in < 100).
     */
    uint64_t t1 = t0;
    for (uint32_t i = 0U; i < 100000U; ++i)
    {
        t1 = tethys_platform_now_us();
        if (t1 > t0)
        {
            break;
        }
    }
    TEST_ASSERT_TRUE_MESSAGE(t1 >= t0, "platform_now_us must be monotonic");
}

void test_platform_yield_is_safe(void)
{
    tethys_platform_yield();
    tethys_platform_yield();
    /* No crash = pass. */
    TEST_PASS();
}

void test_platform_watchdog_kick_is_safe(void)
{
    tethys_platform_watchdog_kick();
    tethys_platform_watchdog_kick();
    /* No crash = pass. */
    TEST_PASS();
}
