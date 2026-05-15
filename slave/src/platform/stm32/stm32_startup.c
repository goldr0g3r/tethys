/*
 * src/platform/stm32/stm32_startup.c - minimal reset handler + default
 * interrupt handler stubs for STM32 Cortex-M targets.
 *
 * Module: tethys::platform::stm32::startup
 * Profiles: marine, space.
 * Standards:
 *   - ARMv7-M ARM §B1.5.5 (reset behaviour).
 *   - Newlib + nano libc startup contract.
 *
 * This file is the *minimum* the linker needs to satisfy undefined symbols
 * when building libtethys_slave.a in cross-compile mode. A full bring-up
 * requires:
 *   - A linker script (.ld) defining .text, .data, .bss, _stack_top, etc.
 *   - A vector table (typically in .isr_vector).
 *   - A copy-data-from-flash-to-RAM loop in Reset_Handler.
 *
 * Both of those live in the hardware-bring-up PR. The static-library build
 * we ship at the foundation PR stage does NOT link an ELF executable;
 * libtethys_slave.a is intended to be linked INTO an application that
 * provides its own crt0 / startup. The default-handler stubs below give the
 * application a fall-through for any vector it does not implement itself
 * (so undefined references at link time are caught with a clear name).
 *
 * Note: the stubs are marked `weak` so an application can override any
 * single handler without touching this file.
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */

#include <stdint.h>

#if defined(__GNUC__) || defined(__clang__)
#  define TETHYS_WEAK_  __attribute__((weak))
#  define TETHYS_NORET_ __attribute__((noreturn))
#else
#  define TETHYS_WEAK_
#  define TETHYS_NORET_
#endif

/* ---- Default handler ----------------------------------------------------- */

TETHYS_WEAK_ TETHYS_NORET_ void Default_Handler(void);
void Default_Handler(void)
{
    /*
     * Unhandled interrupt: spin and let the IWDG reset us. Bounded loop is
     * unbounded by design here; the IWDG is the external bound. This is
     * the exception to the no-recursion-no-goto bounded-loop rule and is
     * documented in docs/misra-deviations.md (rule 15.4 - exception for
     * panic / hard-fault paths).
     */
    for (;;)
    {
#if defined(__GNUC__) || defined(__clang__)
        __asm__ volatile("nop");
#endif
    }
}

/* ---- ARMv7-M core exception aliases ------------------------------------- */

TETHYS_WEAK_ void NMI_Handler(void);
void NMI_Handler(void)        { Default_Handler(); }
TETHYS_WEAK_ void HardFault_Handler(void);
void HardFault_Handler(void)  { Default_Handler(); }
TETHYS_WEAK_ void MemManage_Handler(void);
void MemManage_Handler(void)  { Default_Handler(); }
TETHYS_WEAK_ void BusFault_Handler(void);
void BusFault_Handler(void)   { Default_Handler(); }
TETHYS_WEAK_ void UsageFault_Handler(void);
void UsageFault_Handler(void) { Default_Handler(); }
TETHYS_WEAK_ void SVC_Handler(void);
void SVC_Handler(void)        { Default_Handler(); }
TETHYS_WEAK_ void DebugMon_Handler(void);
void DebugMon_Handler(void)   { Default_Handler(); }
TETHYS_WEAK_ void PendSV_Handler(void);
void PendSV_Handler(void)     { Default_Handler(); }
