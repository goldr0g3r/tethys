/*
 * src/profiles/space/space_init.c - space profile boot sequence.
 *
 * Module: tethys::profiles::space::init
 * Profiles: space.
 * Standards:
 *   - .cursor/rules/space-profile-invariants.mdc - profile invariants.
 *   - ECSS-E-ST-40C Rev.1 §5.4 - SW engineering DAL-B-equivalent.
 *   - NPR 7150.2D - NASA SW engineering requirements.
 *   - DO-178C - aviation crossover (target DAL-B).
 *   - ADR-0002 - profile-based build system.
 *   - ADR-0006 - AES-128 seed-and-key (mandatory init step).
 *
 * Boot sequence (Phase 8 baseline):
 *   1. SysTick - 1 ms tick for tethys_platform_now_us().
 *   2. USART2 - debug log + SxI bench wire when service-mode unlocked.
 *   3. FDCAN1 (1-wire FT) - primary space transport.
 *   4. IWDG watchdog - mandatory; tightened to 32 ms timeout
 *      (vs marine 1000 ms).
 *   5. AES-128 key schedule - precompute round keys from the per-target
 *      key burned into the flash sector at TETHYS_SPACE_AES_KEY_FLASH_ADDR.
 *   6. EDAC scrub start - flag to begin background scrubbing the CAL pages
 *      (real scrub task is the hardware-bring-up PR's job).
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */

#include "tethys/aes128_seed_and_key.h"
#include "tethys/platform.h"

#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#if defined(TETHYS_PROFILE_SPACE) && (TETHYS_PROFILE_SPACE == 1)

/* Forward decls of HAL inits. */
void tethys_stm32_systick_init(void);
void tethys_stm32_uart_init(void);
void tethys_stm32_canfd_init(uint32_t nominal_bps, uint32_t data_bps);
void tethys_stm32_watchdog_init(void);

#ifndef TETHYS_SPACE_CAN_NOMINAL_BPS
#  define TETHYS_SPACE_CAN_NOMINAL_BPS (125000U)  /* 1-wire FT CAN baseline */
#endif
#ifndef TETHYS_SPACE_CAN_DATA_BPS
#  define TETHYS_SPACE_CAN_DATA_BPS (125000U)     /* no BRS in 1-wire FT */
#endif

/* Per-target AES-128 key. In a real flight build this is read from the
 * read-protected flash sector at TETHYS_SPACE_AES_KEY_FLASH_ADDR (see the
 * runbook). At cross-compile time (no hardware) we use a documented test
 * pattern that the unit-test suite knows about. The test pattern is NOT
 * a real key; the bring-up PR overwrites this symbol with the real key
 * from flash. */
static uint8_t tethys_space_aes_key_[TETHYS_AES128_KEY_SIZE] = {
    0x2BU, 0x7EU, 0x15U, 0x16U, 0x28U, 0xAEU, 0xD2U, 0xA6U,
    0xABU, 0xF7U, 0x15U, 0x88U, 0x09U, 0xCFU, 0x4FU, 0x3CU
};

static uint32_t tethys_space_aes_round_keys_[TETHYS_AES128_ROUND_KEY_WORDS];

typedef enum
{
    TETHYS_SPACE_BOOT_NONE     = 0,
    TETHYS_SPACE_BOOT_SYSTICK  = 1,
    TETHYS_SPACE_BOOT_UART     = 2,
    TETHYS_SPACE_BOOT_CANFD    = 3,
    TETHYS_SPACE_BOOT_WDOG     = 4,
    TETHYS_SPACE_BOOT_AES      = 5,
    TETHYS_SPACE_BOOT_EDAC     = 6,
    TETHYS_SPACE_BOOT_READY    = 7
} tethys_space_boot_phase_t;

static volatile tethys_space_boot_phase_t tethys_space_boot_;

tethys_space_boot_phase_t tethys_space_boot_phase(void);
tethys_space_boot_phase_t tethys_space_boot_phase(void)
{
    return tethys_space_boot_;
}

uint32_t const* tethys_space_aes_round_keys(void);
uint32_t const* tethys_space_aes_round_keys(void)
{
    return tethys_space_aes_round_keys_;
}

bool tethys_space_init(void);
bool tethys_space_init(void)
{
    tethys_space_boot_ = TETHYS_SPACE_BOOT_NONE;

#if defined(TETHYS_PLATFORM_STM32)
    tethys_stm32_systick_init();
    tethys_space_boot_ = TETHYS_SPACE_BOOT_SYSTICK;

    tethys_stm32_uart_init();
    tethys_space_boot_ = TETHYS_SPACE_BOOT_UART;

    tethys_stm32_canfd_init(TETHYS_SPACE_CAN_NOMINAL_BPS,
                             TETHYS_SPACE_CAN_DATA_BPS);
    tethys_space_boot_ = TETHYS_SPACE_BOOT_CANFD;

    tethys_stm32_watchdog_init();
    tethys_space_boot_ = TETHYS_SPACE_BOOT_WDOG;
#endif

    /*
     * AES key schedule precompute - runs on host + STM32 (no hardware
     * dependency; it is pure compute over the in-memory key buffer).
     * The bring-up PR will replace the static key buffer with a read from
     * the protected flash sector at TETHYS_SPACE_AES_KEY_FLASH_ADDR before
     * this call.
     */
    tethys_aes128_key_schedule(tethys_space_aes_key_,
                                tethys_space_aes_round_keys_);
    tethys_space_boot_ = TETHYS_SPACE_BOOT_AES;

    /*
     * EDAC scrub stub - sets the "enable scrub" flag. The actual scrub
     * background task lives in the hardware-bring-up PR (it polls the CAL
     * page table at low priority and rewrites any single-bit-corrected
     * word back to flash). Here we just mark boot-ready.
     */
    tethys_space_boot_ = TETHYS_SPACE_BOOT_EDAC;

    tethys_space_boot_ = TETHYS_SPACE_BOOT_READY;
    return true;
}

#endif /* TETHYS_PROFILE_SPACE */
