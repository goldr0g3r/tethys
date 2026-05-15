/*
 * src/profiles/marine/marine_init.c - marine profile boot sequence.
 *
 * Module: tethys::profiles::marine::init
 * Profiles: marine.
 * Standards:
 *   - .cursor/rules/marine-profile-invariants.mdc - profile invariants.
 *   - IEC 60945 - environmental envelope (documented; no compile effect).
 *   - IACS UR E22 Rev.3 - marine class SW process anchor.
 *   - ADR-0002 profile-based build system.
 *
 * Boot sequence (Phase 7 baseline):
 *   1. SysTick (1 ms tick) - underpins tethys_platform_now_us().
 *   2. USART2 - debug log + dev-bench UART/SxI when enabled.
 *   3. CAN-FD (FDCAN1 or bxCAN1) - primary marine transport.
 *   4. W5500 Ethernet - secondary marine transport.
 *   5. IWDG watchdog - kicked by DAQ tick when
 *      TETHYS_MARINE_WATCHDOG_ON_DAQ_TICK=1; otherwise documented.
 *
 * tethys_marine_init() is the function the application's main() calls
 * before tethys_xcp_init(). It is host-callable so the simulator can
 * exercise the same code path (with HAL inits no-op'd via
 * !defined(TETHYS_PLATFORM_STM32)).
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */

#include "tethys/platform.h"

#include <stdbool.h>
#include <stdint.h>

#if defined(TETHYS_PROFILE_MARINE) && (TETHYS_PROFILE_MARINE == 1)

/* Forward declarations of the HAL inits (no header pollution for the
 * profile module; this is the only translation unit that needs them). */
void tethys_stm32_systick_init(void);
void tethys_stm32_uart_init(void);
void tethys_stm32_canfd_init(uint32_t nominal_bps, uint32_t data_bps);
void tethys_stm32_eth_init(void);
void tethys_stm32_watchdog_init(void);

#ifndef TETHYS_MARINE_CAN_NOMINAL_BPS
#  define TETHYS_MARINE_CAN_NOMINAL_BPS (500000U)
#endif
#ifndef TETHYS_MARINE_CAN_DATA_BPS
#  define TETHYS_MARINE_CAN_DATA_BPS (2000000U)
#endif

/* Boot-progress state (read by the master tool via DAQ housekeeping). */
typedef enum
{
    TETHYS_MARINE_BOOT_NONE   = 0,
    TETHYS_MARINE_BOOT_SYSTICK= 1,
    TETHYS_MARINE_BOOT_UART   = 2,
    TETHYS_MARINE_BOOT_CANFD  = 3,
    TETHYS_MARINE_BOOT_ETH    = 4,
    TETHYS_MARINE_BOOT_WDOG   = 5,
    TETHYS_MARINE_BOOT_READY  = 6
} tethys_marine_boot_phase_t;

static volatile tethys_marine_boot_phase_t tethys_marine_boot_;

tethys_marine_boot_phase_t tethys_marine_boot_phase(void);
tethys_marine_boot_phase_t tethys_marine_boot_phase(void)
{
    return tethys_marine_boot_;
}

bool tethys_marine_init(void);
bool tethys_marine_init(void)
{
    tethys_marine_boot_ = TETHYS_MARINE_BOOT_NONE;

#if defined(TETHYS_PLATFORM_STM32)
    tethys_stm32_systick_init();
    tethys_marine_boot_ = TETHYS_MARINE_BOOT_SYSTICK;

    tethys_stm32_uart_init();
    tethys_marine_boot_ = TETHYS_MARINE_BOOT_UART;

    tethys_stm32_canfd_init(TETHYS_MARINE_CAN_NOMINAL_BPS,
                             TETHYS_MARINE_CAN_DATA_BPS);
    tethys_marine_boot_ = TETHYS_MARINE_BOOT_CANFD;

    tethys_stm32_eth_init();
    tethys_marine_boot_ = TETHYS_MARINE_BOOT_ETH;

#  if (TETHYS_MARINE_WATCHDOG_ON_DAQ_TICK == 1)
    tethys_stm32_watchdog_init();
    tethys_marine_boot_ = TETHYS_MARINE_BOOT_WDOG;
#  endif
#endif

    tethys_marine_boot_ = TETHYS_MARINE_BOOT_READY;
    return true;
}

#endif /* TETHYS_PROFILE_MARINE */
