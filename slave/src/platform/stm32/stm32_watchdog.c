/*
 * src/platform/stm32/stm32_watchdog.c - IWDG (Independent Watchdog) driver.
 *
 * Module: tethys::platform::stm32::watchdog
 * Profiles: marine (optional kick), space (mandatory kick on DAQ tick).
 * Standards:
 *   - ST RM0410 §40 (F7 IWDG).
 *   - ST RM0433 §47 (H7 IWDG).
 *   - ST RM0090 §26 (F4 IWDG).
 *   - ECSS-E-ST-40C Rev.1 §5.4 (independent monitoring chain for
 *     safety-critical software).
 *   - .cursor/rules/space-profile-invariants.mdc - watchdog mandatory.
 *   - ADR-0005 - no dynamic allocation.
 *
 * IWDG sources its clock from the LSI (~32 kHz internal RC). Pre-scaler +
 * reload give the timeout. Default here is ~1 s timeout (prescaler /256,
 * reload 125 -> ~1000 ms); the space profile may shrink this to 32 ms in
 * the bring-up PR after measuring worst-case DAQ tick jitter.
 *
 * Compile-only stub: register pokes are guarded by TETHYS_PLATFORM_STM32.
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */

#include "tethys/platform.h"

#include <stdint.h>

#ifndef TETHYS_IWDG_TIMEOUT_MS
#  define TETHYS_IWDG_TIMEOUT_MS (1000U)
#endif

#define TETHYS_IWDG_LSI_HZ_   (32000U)
#define TETHYS_IWDG_PRESCALE_ (256U)
#define TETHYS_IWDG_RELOAD_                                                 \
    (((TETHYS_IWDG_LSI_HZ_ / TETHYS_IWDG_PRESCALE_)                          \
      * TETHYS_IWDG_TIMEOUT_MS) / 1000U)

#if defined(TETHYS_PLATFORM_STM32)
#  define TETHYS_IWDG_BASE_ (0x40003000U)
#  define TETHYS_IWDG_KR_   (*(volatile uint32_t*)(TETHYS_IWDG_BASE_ + 0x00U))
#  define TETHYS_IWDG_PR_   (*(volatile uint32_t*)(TETHYS_IWDG_BASE_ + 0x04U))
#  define TETHYS_IWDG_RLR_  (*(volatile uint32_t*)(TETHYS_IWDG_BASE_ + 0x08U))
#  define TETHYS_IWDG_SR_   (*(volatile uint32_t*)(TETHYS_IWDG_BASE_ + 0x0CU))

#  define TETHYS_IWDG_KR_RELOAD_     (0x0000AAAAU)
#  define TETHYS_IWDG_KR_START_      (0x0000CCCCU)
#  define TETHYS_IWDG_KR_UNLOCK_     (0x00005555U)

#  define TETHYS_IWDG_PR_DIV256_     (0x6U)
#endif

void tethys_stm32_watchdog_init(void);
void tethys_stm32_watchdog_init(void)
{
#if defined(TETHYS_PLATFORM_STM32)
    /*
     * IWDG configuration sequence (RM0410 §40.4.4):
     *   1. Write 0x5555 to IWDG_KR to enable register access.
     *   2. Write prescaler (0..7 -> /4 ../256).
     *   3. Write reload value (12-bit; 0..4095).
     *   4. Wait for IWDG_SR.RVU + .PVU to clear.
     *   5. Write 0xCCCC to IWDG_KR to start the watchdog.
     */
    TETHYS_IWDG_KR_  = TETHYS_IWDG_KR_UNLOCK_;
    TETHYS_IWDG_PR_  = TETHYS_IWDG_PR_DIV256_;
    TETHYS_IWDG_RLR_ = TETHYS_IWDG_RELOAD_ & 0x0FFFU;
    /*
     * Bounded wait loop: SR clear takes at most ~5 LSI cycles (~160 us).
     * Cap at 1 000 iterations as a defensive watchdog-on-watchdog bound.
     */
    for (uint32_t i = 0U; i < 1000U; ++i)
    {
        if (TETHYS_IWDG_SR_ == 0U)
        {
            break;
        }
    }
    TETHYS_IWDG_KR_ = TETHYS_IWDG_KR_START_;
#endif
}

void tethys_platform_watchdog_kick(void)
{
#if defined(TETHYS_PLATFORM_STM32)
    /*
     * One 32-bit write (atomic on Cortex-M3+). Safe from any context
     * including ISRs.
     */
    TETHYS_IWDG_KR_ = TETHYS_IWDG_KR_RELOAD_;
#endif
}
