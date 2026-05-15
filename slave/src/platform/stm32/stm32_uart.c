/*
 * src/platform/stm32/stm32_uart.c - USART2 bare-metal driver for STM32 Nucleo
 * boards. Used by Worker B's UART/SxI transport on the space profile and as
 * the debug-log sink on both profiles.
 *
 * Module: tethys::platform::stm32::uart
 * Profiles: marine (USART3 on F767ZI; mapped via define), space (UART4 on
 * H753ZI). Default to USART2 if no override.
 * Standards:
 *   - ARM ARMv7-M ARM (vector table).
 *   - STM32F7 RM0410 §34 (USART register map).
 *   - STM32H7 RM0433 §53 (USART register map).
 *   - ADR-0005 - no dynamic allocation: ring buffers are file-scope arrays.
 *   - .cursor/rules/no-recursion-no-goto.mdc - all loops bounded; no goto.
 *
 * Framing contract (when used by Worker B's UART/SxI transport):
 *   Until Worker B's master-side transport lands, this file assumes the
 *   pragmatic Tethys framing:
 *
 *     [0x7E][len-hi][len-lo][payload..len][crc8]
 *
 *   * 0x7E start byte (HDLC tradition; easy to resync).
 *   * 16-bit big-endian length (payload bytes only).
 *   * payload (up to TETHYS_UART_MAX_FRAME bytes; default 1024).
 *   * CRC-8 of the payload only (polynomial 0x07; init 0x00; reflect
 *     in/out off).
 *
 *   This is documented as the contract here so Worker B can match it
 *   exactly; if they choose different framing, this file gets one PR to
 *   align.
 *
 * Compile-only stub: the public API is implemented but the register-poke
 * code paths are gated by `#if defined(TETHYS_PLATFORM_STM32)` so the host
 * POSIX build (which has no USART) does not pull register I/O in.
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifndef TETHYS_UART_BAUDRATE_HZ
#  define TETHYS_UART_BAUDRATE_HZ (115200U)
#endif

#ifndef TETHYS_UART_PCLK_HZ
/* USART2 hangs off APB1 on F767ZI (54 MHz) and H753ZI (100 MHz). Default to
 * F767ZI; overridden via preset for H7. */
#  define TETHYS_UART_PCLK_HZ (54000000U)
#endif

#ifndef TETHYS_UART_RX_RING_SIZE
#  define TETHYS_UART_RX_RING_SIZE (256U)
#endif

#ifndef TETHYS_UART_TX_RING_SIZE
#  define TETHYS_UART_TX_RING_SIZE (256U)
#endif

#define TETHYS_UART_FRAME_START_ ((uint8_t)0x7EU)
#define TETHYS_UART_MAX_FRAME_   ((uint16_t)1024U)
#define TETHYS_UART_CRC8_POLY_   ((uint8_t)0x07U)

/* ---- Ring buffers (file-scope static; ADR-0005) -------------------------- */

static uint8_t  tethys_uart_rx_buf_[TETHYS_UART_RX_RING_SIZE];
static volatile uint16_t tethys_uart_rx_head_;
static volatile uint16_t tethys_uart_rx_tail_;

static uint8_t  tethys_uart_tx_buf_[TETHYS_UART_TX_RING_SIZE];
static volatile uint16_t tethys_uart_tx_head_;
static volatile uint16_t tethys_uart_tx_tail_;

/* ---- USART register map (USART2 base) ----------------------------------- */

#if defined(TETHYS_PLATFORM_STM32)
#  define TETHYS_USART2_BASE_ (0x40004400U)
#  define TETHYS_USART_CR1_   (*(volatile uint32_t*)(TETHYS_USART2_BASE_ + 0x00U))
#  define TETHYS_USART_BRR_   (*(volatile uint32_t*)(TETHYS_USART2_BASE_ + 0x0CU))
#  define TETHYS_USART_ISR_   (*(volatile uint32_t*)(TETHYS_USART2_BASE_ + 0x1CU))
#  define TETHYS_USART_RDR_   (*(volatile uint32_t*)(TETHYS_USART2_BASE_ + 0x24U))
#  define TETHYS_USART_TDR_   (*(volatile uint32_t*)(TETHYS_USART2_BASE_ + 0x28U))

#  define TETHYS_USART_CR1_UE_     (1U << 0U)
#  define TETHYS_USART_CR1_RE_     (1U << 2U)
#  define TETHYS_USART_CR1_TE_     (1U << 3U)
#  define TETHYS_USART_CR1_RXNEIE_ (1U << 5U)

#  define TETHYS_USART_ISR_RXNE_   (1U << 5U)
#  define TETHYS_USART_ISR_TXE_    (1U << 7U)
#endif

/* ---- CRC-8 (poly 0x07; tiny + table-free) -------------------------------- */

static uint8_t tethys_uart_crc8_(uint8_t const* data, size_t len)
{
    uint8_t crc = 0x00U;
    for (size_t i = 0U; i < len; ++i)
    {
        crc = (uint8_t)(crc ^ data[i]);
        for (uint8_t bit = 0U; bit < 8U; ++bit)
        {
            if ((crc & 0x80U) != 0U)
            {
                crc = (uint8_t)((crc << 1) ^ TETHYS_UART_CRC8_POLY_);
            }
            else
            {
                crc = (uint8_t)(crc << 1);
            }
        }
    }
    return crc;
}

/* ---- Public API --------------------------------------------------------- */

void tethys_stm32_uart_init(void);
void tethys_stm32_uart_init(void)
{
    tethys_uart_rx_head_ = 0U;
    tethys_uart_rx_tail_ = 0U;
    tethys_uart_tx_head_ = 0U;
    tethys_uart_tx_tail_ = 0U;

#if defined(TETHYS_PLATFORM_STM32)
    /*
     * 1. GPIO + RCC + AFR setup is the hardware-bring-up PR's job. This
     *    function assumes the bring-up code has clocked USART2 and routed
     *    PA2 (TX) + PA3 (RX) to the alternate-function 7 (USART2).
     * 2. Configure baud rate: BRR = PCLK / baud (oversample-16 mode).
     * 3. Enable USART, TX, RX, RX-not-empty interrupt.
     */
    TETHYS_USART_CR1_ = 0U; /* disable while configuring */
    TETHYS_USART_BRR_ = TETHYS_UART_PCLK_HZ / TETHYS_UART_BAUDRATE_HZ;
    TETHYS_USART_CR1_ = TETHYS_USART_CR1_UE_
                      | TETHYS_USART_CR1_RE_
                      | TETHYS_USART_CR1_TE_
                      | TETHYS_USART_CR1_RXNEIE_;
#endif
}

bool tethys_stm32_uart_send_byte(uint8_t b);
bool tethys_stm32_uart_send_byte(uint8_t b)
{
    uint16_t const next = (uint16_t)((tethys_uart_tx_head_ + 1U)
                                     % TETHYS_UART_TX_RING_SIZE);
    if (next == tethys_uart_tx_tail_)
    {
        return false; /* tx ring full */
    }
    tethys_uart_tx_buf_[tethys_uart_tx_head_] = b;
    tethys_uart_tx_head_ = next;

#if defined(TETHYS_PLATFORM_STM32)
    /*
     * Block-write the byte directly when the TX register is empty. A full
     * interrupt-driven scheme can come later; this gives us a usable
     * transmitter without an IRQ handler.
     */
    while ((TETHYS_USART_ISR_ & TETHYS_USART_ISR_TXE_) == 0U)
    {
        /* Bounded by the UART byte time; no recursion. */
    }
    TETHYS_USART_TDR_ = (uint32_t)b;
    tethys_uart_tx_tail_ = next;
#endif
    return true;
}

size_t tethys_stm32_uart_send_frame(uint8_t const* payload, size_t len);
size_t tethys_stm32_uart_send_frame(uint8_t const* payload, size_t len)
{
    if ((payload == NULL) || (len == 0U) || (len > TETHYS_UART_MAX_FRAME_))
    {
        return 0U;
    }
    /*
     * Header (4 bytes) + payload + 1 CRC byte. Returns total bytes pushed
     * into the ring (caller can compare against len + 5).
     */
    uint8_t const len_hi = (uint8_t)((len >> 8) & 0xFFU);
    uint8_t const len_lo = (uint8_t)(len & 0xFFU);
    uint8_t const crc    = tethys_uart_crc8_(payload, len);

    size_t pushed = 0U;
    if (tethys_stm32_uart_send_byte(TETHYS_UART_FRAME_START_)) { ++pushed; }
    if (tethys_stm32_uart_send_byte(len_hi))                    { ++pushed; }
    if (tethys_stm32_uart_send_byte(len_lo))                    { ++pushed; }
    for (size_t i = 0U; i < len; ++i)
    {
        if (!tethys_stm32_uart_send_byte(payload[i]))
        {
            break;
        }
        ++pushed;
    }
    if (tethys_stm32_uart_send_byte(crc))                       { ++pushed; }
    return pushed;
}

bool tethys_stm32_uart_recv_byte(uint8_t* out);
bool tethys_stm32_uart_recv_byte(uint8_t* out)
{
    if (out == NULL)
    {
        return false;
    }
    if (tethys_uart_rx_head_ == tethys_uart_rx_tail_)
    {
        return false; /* rx ring empty */
    }
    *out = tethys_uart_rx_buf_[tethys_uart_rx_tail_];
    tethys_uart_rx_tail_ = (uint16_t)((tethys_uart_rx_tail_ + 1U)
                                      % TETHYS_UART_RX_RING_SIZE);
    return true;
}

#if defined(TETHYS_PLATFORM_STM32)
void USART2_IRQHandler(void); /* forward decl - linked from the vector table */
void USART2_IRQHandler(void)
{
    if ((TETHYS_USART_ISR_ & TETHYS_USART_ISR_RXNE_) != 0U)
    {
        uint8_t const b = (uint8_t)(TETHYS_USART_RDR_ & 0xFFU);
        uint16_t const next = (uint16_t)((tethys_uart_rx_head_ + 1U)
                                         % TETHYS_UART_RX_RING_SIZE);
        if (next != tethys_uart_rx_tail_)
        {
            tethys_uart_rx_buf_[tethys_uart_rx_head_] = b;
            tethys_uart_rx_head_ = next;
        }
        /* Else: rx ring full; drop. A real metric counter lands in the
         * hardware-bring-up PR (rx_overflow_count_). */
    }
}
#endif
