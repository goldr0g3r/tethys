/*
 * src/platform/stm32/stm32_canfd.c - CAN-FD (FDCAN on F7/H7, bxCAN on F4)
 * minimal driver for STM32 Nucleo. Used by Worker B's SocketCAN-style
 * transport for both the marine (CAN-FD) and space (1-wire fault-tolerant
 * CAN) profiles.
 *
 * Module: tethys::platform::stm32::canfd
 * Profiles: marine (F4 bxCAN; F7+ FDCAN), space (H7 FDCAN 1-wire FT).
 * Standards:
 *   - ISO 11898-1:2024 (CAN data link layer).
 *   - ISO 11898-7 (CAN FD).
 *   - ST RM0410 §32 (F7 FDCAN).
 *   - ST RM0433 §57 (H7 FDCAN).
 *   - ST RM0090 §32 (F4 bxCAN).
 *   - ADR-0005 - no dynamic allocation: TX/RX buffers are file-scope.
 *   - .cursor/rules/no-recursion-no-goto.mdc - all loops bounded; no goto.
 *
 * This file is compile-only at the foundation PR stage: register I/O is
 * gated by TETHYS_PLATFORM_STM32 so a host posix-sim build sees only the
 * ring-buffer arithmetic.
 *
 * Wire-level details (mode, bitrates, filter scheme) are mission-specific
 * and live in the hardware-bring-up PR's IF_DATA A2L block. Defaults:
 *   - marine: 500 kbps arbitration / 2 Mbps data (per CANopen + J1939
 *             commonality).
 *   - space:  125 kbps arbitration (1-wire FT CAN tolerates lower rates).
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifndef TETHYS_CANFD_TX_QUEUE_DEPTH
#  define TETHYS_CANFD_TX_QUEUE_DEPTH (16U)
#endif

#ifndef TETHYS_CANFD_RX_QUEUE_DEPTH
#  define TETHYS_CANFD_RX_QUEUE_DEPTH (32U)
#endif

#define TETHYS_CANFD_MAX_DLC_       (64U)  /* CAN-FD payload max */
#define TETHYS_CAN_CLASSIC_MAX_DLC_ (8U)

/* ---- Frame type ---------------------------------------------------------- */

typedef struct
{
    uint32_t id;       /* 11- or 29-bit identifier */
    uint8_t  dlc;      /* payload length in bytes (0..64) */
    uint8_t  flags;    /* bit 0 = extended id; bit 1 = FD; bit 2 = BRS */
    uint8_t  data[TETHYS_CANFD_MAX_DLC_];
} tethys_canfd_frame_t;

#define TETHYS_CANFD_FLAG_EXT_ (1U << 0U)
#define TETHYS_CANFD_FLAG_FD_  (1U << 1U)
#define TETHYS_CANFD_FLAG_BRS_ (1U << 2U)

/* ---- Ring buffers (ADR-0005) -------------------------------------------- */

static tethys_canfd_frame_t tethys_canfd_tx_ring_[TETHYS_CANFD_TX_QUEUE_DEPTH];
static volatile uint16_t    tethys_canfd_tx_head_;
static volatile uint16_t    tethys_canfd_tx_tail_;

static tethys_canfd_frame_t tethys_canfd_rx_ring_[TETHYS_CANFD_RX_QUEUE_DEPTH];
static volatile uint16_t    tethys_canfd_rx_head_;
static volatile uint16_t    tethys_canfd_rx_tail_;

/* Health counters (read by master via DAQ housekeeping channel). */
static volatile uint32_t tethys_canfd_rx_overflow_;
static volatile uint32_t tethys_canfd_tx_overflow_;
static volatile uint32_t tethys_canfd_bus_off_count_;

#if defined(TETHYS_PLATFORM_STM32)
/* ---- Register map sketch (FDCAN1 on F7+/H7) ----------------------------- */
/*
 * Real bring-up needs ~30 register writes to configure timing, filter banks,
 * RX/TX FIFOs, and IRQ routing. We stub the *minimum* the dispatcher needs
 * to verify the symbol-resolution path and let the linker do its job at
 * cross-compile time.
 *
 * F7 + H7 base = 0x40006400 (FDCAN1). F4's bxCAN is at 0x40006400 too but
 * with a different register layout; documented inline in
 * stm32_canfd_init_bxcan_().
 */
#  define TETHYS_FDCAN1_BASE_  (0x40006400U)
#  define TETHYS_FDCAN_CCCR_   (*(volatile uint32_t*)(TETHYS_FDCAN1_BASE_ + 0x00U))
#  define TETHYS_FDCAN_CCCR_INIT_ (1U << 0U)
#endif

/* ---- Init ---------------------------------------------------------------- */

void tethys_stm32_canfd_init(uint32_t nominal_bps, uint32_t data_bps);
void tethys_stm32_canfd_init(uint32_t nominal_bps, uint32_t data_bps)
{
    tethys_canfd_tx_head_ = 0U;
    tethys_canfd_tx_tail_ = 0U;
    tethys_canfd_rx_head_ = 0U;
    tethys_canfd_rx_tail_ = 0U;
    tethys_canfd_rx_overflow_   = 0U;
    tethys_canfd_tx_overflow_   = 0U;
    tethys_canfd_bus_off_count_ = 0U;

    (void)nominal_bps;
    (void)data_bps;

#if defined(TETHYS_PLATFORM_STM32)
    /*
     * Real init sequence (to be expanded at hardware-bring-up time):
     *   1. Enable FDCAN1 clock in RCC.AHB1ENR (PCKL src = HSE 25 MHz).
     *   2. Set CCCR.INIT = 1; wait for CCCR.INIT_BACK = 1.
     *   3. CCCR.CCE = 1 (config-change enable).
     *   4. Program NBTP for nominal_bps and DBTP for data_bps.
     *   5. Program standard filter (XIDAM / SIDFC) to accept all.
     *   6. Map TX FIFO at MRBA + RX FIFO 0 at MRBA + 64.
     *   7. Clear CCCR.INIT to leave config mode.
     *   8. Enable FDCAN1_IT0_IRQn at NVIC.
     */
    TETHYS_FDCAN_CCCR_ = TETHYS_FDCAN_CCCR_INIT_;
#endif
}

/* ---- TX ------------------------------------------------------------------ */

bool tethys_stm32_canfd_send(tethys_canfd_frame_t const* frame);
bool tethys_stm32_canfd_send(tethys_canfd_frame_t const* frame)
{
    if ((frame == NULL) || (frame->dlc > TETHYS_CANFD_MAX_DLC_))
    {
        return false;
    }
    uint16_t const next = (uint16_t)((tethys_canfd_tx_head_ + 1U)
                                     % TETHYS_CANFD_TX_QUEUE_DEPTH);
    if (next == tethys_canfd_tx_tail_)
    {
        tethys_canfd_tx_overflow_ = tethys_canfd_tx_overflow_ + 1U;
        return false;
    }
    tethys_canfd_tx_ring_[tethys_canfd_tx_head_] = *frame;
    tethys_canfd_tx_head_ = next;

#if defined(TETHYS_PLATFORM_STM32)
    /*
     * Real impl: copy into the TX FIFO mailbox + set TXBAR bit. Compile-only
     * stub here.
     */
#endif
    return true;
}

/* ---- RX ------------------------------------------------------------------ */

bool tethys_stm32_canfd_recv(tethys_canfd_frame_t* out);
bool tethys_stm32_canfd_recv(tethys_canfd_frame_t* out)
{
    if (out == NULL)
    {
        return false;
    }
    if (tethys_canfd_rx_head_ == tethys_canfd_rx_tail_)
    {
        return false;
    }
    *out = tethys_canfd_rx_ring_[tethys_canfd_rx_tail_];
    tethys_canfd_rx_tail_ = (uint16_t)((tethys_canfd_rx_tail_ + 1U)
                                       % TETHYS_CANFD_RX_QUEUE_DEPTH);
    return true;
}

/* ---- Telemetry ---------------------------------------------------------- */

uint32_t tethys_stm32_canfd_rx_overflow_count(void);
uint32_t tethys_stm32_canfd_rx_overflow_count(void)
{
    return tethys_canfd_rx_overflow_;
}

uint32_t tethys_stm32_canfd_tx_overflow_count(void);
uint32_t tethys_stm32_canfd_tx_overflow_count(void)
{
    return tethys_canfd_tx_overflow_;
}

uint32_t tethys_stm32_canfd_bus_off_count(void);
uint32_t tethys_stm32_canfd_bus_off_count(void)
{
    return tethys_canfd_bus_off_count_;
}

#if defined(TETHYS_PLATFORM_STM32)
void FDCAN1_IT0_IRQHandler(void); /* forward decl - linked from vector table */
void FDCAN1_IT0_IRQHandler(void)
{
    /*
     * Pull frames from the FIFO into tethys_canfd_rx_ring_. Real impl lives
     * in the hardware-bring-up PR. The stub guards prevent the linker from
     * complaining about an undefined symbol if the vector table references
     * this handler.
     */
}
#endif
