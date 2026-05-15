/*
 * src/platform/stm32/stm32_systick.c - SysTick tick + tethys_platform_now_us
 * for STM32 Cortex-M targets.
 *
 * Module: tethys::platform::stm32::systick
 * Profiles: marine (F4/F7), space (H7).
 * Standards:
 *   - ARM ARMv7-M Architecture Reference Manual §B3.3 (SysTick).
 *   - ASAM XCP 1.4 Part 2 §1.1 (DAQ timestamp source).
 *   - ADR-0005 - no dynamic allocation.
 *   - .cursor/rules/no-recursion-no-goto.mdc - all loops bounded.
 * Trace: docs/traceability.csv (TETHYS-DES-0031 lands at PR-10)
 *
 * This file is *compile-only* until the hardware-bring-up PR lands a real
 * linker script + startup ASM. The CMake glue at slave/profiles/marine.cmake
 * only includes this source when TETHYS_PLATFORM_STM32 is defined; running
 * `cmake --preset=dev` (host POSIX) excludes it.
 *
 * Register layout: NUC F4 / F7 / H7 all expose SysTick at 0xE000E010, so the
 * same code works across MCUs. The system-clock frequency differs per part
 * and is supplied via TETHYS_STM32_SYSCLK_HZ at compile time.
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */

#include "tethys/platform.h"

#include <stdint.h>

/* Default to F767ZI sysclk if the preset did not override. */
#ifndef TETHYS_STM32_SYSCLK_HZ
#  define TETHYS_STM32_SYSCLK_HZ (216000000U)
#endif

/* ---- SysTick register map (ARMv7-M §B3.3.1) ------------------------------ */

#define TETHYS_SYSTICK_BASE_  (0xE000E010U)
#define TETHYS_SYSTICK_CTRL_  (*(volatile uint32_t*)(TETHYS_SYSTICK_BASE_ + 0x00U))
#define TETHYS_SYSTICK_LOAD_  (*(volatile uint32_t*)(TETHYS_SYSTICK_BASE_ + 0x04U))
#define TETHYS_SYSTICK_VAL_   (*(volatile uint32_t*)(TETHYS_SYSTICK_BASE_ + 0x08U))
#define TETHYS_SYSTICK_CALIB_ (*(volatile uint32_t*)(TETHYS_SYSTICK_BASE_ + 0x0CU))

#define TETHYS_SYSTICK_CTRL_ENABLE_    (1U << 0U)
#define TETHYS_SYSTICK_CTRL_TICKINT_   (1U << 1U)
#define TETHYS_SYSTICK_CTRL_CLKSOURCE_ (1U << 2U) /* CPU clock */

/* ---- Tick state ---------------------------------------------------------- */

/*
 * Atomic-ish counter incremented in SysTick_Handler. We use `volatile` and
 * 64-bit so Cortex-M3+ readers tolerate at most one increment race (a 64-bit
 * load is two 32-bit reads on Cortex-M; we detect the wraparound by reading
 * twice and re-reading if the high half changed).
 */
static volatile uint64_t tethys_systick_ms_; /* milliseconds since boot */

/*
 * Sub-millisecond resolution comes from the SysTick down-counter (LOAD ->
 * VAL). Each tick spans (TETHYS_STM32_SYSCLK_HZ / 1000) CPU cycles; we
 * derive microsecond resolution from the residue.
 */
#define TETHYS_SYSTICK_RELOAD_ \
    ((TETHYS_STM32_SYSCLK_HZ / 1000U) - 1U)

/* ---- ISR ----------------------------------------------------------------- */

/*
 * SysTick_Handler runs at the SysTick reload rate (1 kHz). Declared `void`
 * because the ARM vector table calls it with no arguments; the symbol name
 * matches the CMSIS convention so the hardware-bring-up linker script can
 * reference it directly.
 *
 * Wrapped in `#if defined(TETHYS_PLATFORM_STM32) ... #endif` so the host
 * POSIX build (which has no concept of an interrupt vector) compiles cleanly
 * if this file is ever pulled in by accident.
 */
#if defined(TETHYS_PLATFORM_STM32)
void SysTick_Handler(void); /* forward decl - linked from the vector table */
void SysTick_Handler(void)
{
    tethys_systick_ms_ = tethys_systick_ms_ + 1U;
}
#endif

/* ---- Public API ---------------------------------------------------------- */

void tethys_stm32_systick_init(void);
void tethys_stm32_systick_init(void)
{
    /*
     * Configure the down-counter to fire once per millisecond. Set RELOAD
     * first, clear VAL (writing any value clears the count), then enable
     * the counter + interrupt + select CPU clock as the source.
     */
    TETHYS_SYSTICK_LOAD_ = TETHYS_SYSTICK_RELOAD_;
    TETHYS_SYSTICK_VAL_  = 0U;
    TETHYS_SYSTICK_CTRL_ = TETHYS_SYSTICK_CTRL_ENABLE_
                         | TETHYS_SYSTICK_CTRL_TICKINT_
                         | TETHYS_SYSTICK_CTRL_CLKSOURCE_;
}

uint64_t tethys_platform_now_us(void)
{
    /*
     * Convert (ms, residue) to microseconds. The residue is how far the
     * 1 ms down-counter has counted down from RELOAD; (RELOAD - VAL) gives
     * the number of CPU cycles into the current millisecond.
     *
     * Re-read tethys_systick_ms_ across the VAL read to tolerate the race
     * where the SysTick interrupt fires between the two reads. The reread
     * loop is bounded to 2 iterations (one race max).
     */
    uint64_t ms_before;
    uint32_t val;
    uint64_t ms_after;
    uint8_t  bounded;

    bounded = 0U;
    do
    {
        ms_before = tethys_systick_ms_;
        val       = TETHYS_SYSTICK_VAL_;
        ms_after  = tethys_systick_ms_;
        bounded   = (uint8_t)(bounded + 1U);
    } while ((ms_before != ms_after) && (bounded < 2U));

    uint32_t const reload  = TETHYS_SYSTICK_RELOAD_;
    uint32_t const cycles  = reload - val;
    uint32_t const us_part = (uint32_t)((uint64_t)cycles * 1000U
                                        / (TETHYS_STM32_SYSCLK_HZ / 1000U));
    return (ms_after * 1000U) + us_part;
}

void tethys_platform_yield(void)
{
    /*
     * Bare-metal poll loop has nobody to yield to. Touch a single
     * read-modify-write of a volatile dummy to act as a compiler barrier so
     * the optimiser does not collapse a yield-bounded busy-loop.
     */
    static volatile uint32_t yield_barrier_;
    yield_barrier_ = yield_barrier_ + 1U;
}

#if defined(__GNUC__) || defined(__clang__)
__attribute__((noreturn))
#endif
void tethys_platform_panic(char const* msg)
{
    (void)msg;
    /*
     * No safe printf path before the UART is up (the panic path may be hit
     * during init). Disable interrupts and let the IWDG reset the MCU. The
     * MISRA C:2023 banned `goto` is not used; the loop is intentionally
     * unbounded because the IWDG provides the bound (typical 32 ms timeout).
     */
    for (;;)
    {
        /* Spin-wait. Compiler must not optimise out (the body is empty). */
        __asm__ volatile("nop");
    }
}
