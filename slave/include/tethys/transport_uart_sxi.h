/*
 * tethys/transport_uart_sxi.h - Raw UART / SxI byte-stream transport.
 *
 * Module: tethys::transport::uart_sxi
 * Profiles: space (dev bench); marine (dev bench)
 * Standards: ADR-0004 (transport-abstraction-layer interface);
 *            ADR-0010 row 8 (UART/SxI raw budget; COP-1 AD wrap is Phase 8)
 * Trace: docs/traceability.csv (TETHYS-DES-0035 UART/SxI transport)
 *
 * Provides a simple length-prefixed framing over a byte stream:
 *
 *   [0]    start byte 0xAA
 *   [1]    length L (1..TETHYS_UART_MTU)
 *   [2..]  L payload bytes
 *   [2+L]  checksum (XOR of bytes [0..2+L-1])
 *
 * No escape characters: the slave's protocol layer already prefixes every
 * CTO/DTO with a length so byte-stuffing isn't required. Receiver resynces
 * by skipping bytes until the next 0xAA after a checksum mismatch.
 *
 * The slave-side transport is **portable**: it doesn't open a tty / SPI
 * device itself. Instead the host integration code feeds inbound bytes via
 * `tethys_tr_uart_sxi_inject_rx_byte()` and drains outbound bytes via
 * `tethys_tr_uart_sxi_drain_tx_bytes()`. This keeps the C code identical
 * across STM32F7 (USART ISR), STM32H7 (USART + DMA), and posix-sim (where
 * the simulator transport drives the bytes through a pseudo-terminal pair
 * managed by pyserial on the master side).
 *
 * **CCSDS COP-1 AD wrap is deferred to Phase 8** per ADR-0010 row 8. The
 * Phase-5 transport is raw bytes only; the COP-1 ARQ wrapper (N(S), N(R),
 * CLCW, RETRY count) lands in Phase 8 alongside the space profile.
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */
#ifndef TETHYS_TRANSPORT_UART_SXI_H
#define TETHYS_TRANSPORT_UART_SXI_H

#pragma once

#include "tethys/tethys_export.h"
#include "tethys/tethys_transport.h"

#ifdef __cplusplus
extern "C" {
#endif

/** UART/SxI MTU - 64 bytes. Smaller than loopback's 256 to stay within the
 *  STM32F7 USART ISR fast-path memory budget (each frame fits in one DMA
 *  transfer). MAX_CTO + DAQ ODT fit comfortably. */
#define TETHYS_UART_MTU   ((uint16_t)64U)

/** Inbound and outbound ring depths (frames). 8 matches the loopback depth
 *  so the same conformance scenarios apply without re-tuning. */
#define TETHYS_UART_DEPTH ((size_t)8U)

/** Wire start byte. 0xAA is conventional for serial protocols with
 *  alternating bit pattern (10101010) for clock recovery. */
#define TETHYS_UART_START_BYTE ((uint8_t)0xAAU)

/**
 * @brief Get the UART/SxI transport descriptor.
 *
 * @return Non-NULL descriptor pointer.
 */
TETHYS_EXPORT const tethys_tr_descriptor_t *tethys_tr_uart_sxi_descriptor(void);

/**
 * @brief Reset both ring buffers and the receive state machine.
 *
 * Tests call this between cases. Idempotent.
 */
TETHYS_EXPORT void tethys_tr_uart_sxi_reset(void);

/**
 * @brief Feed one inbound byte to the receive state machine.
 *
 * Called by host integration code (USART ISR on STM32, pyserial bridge on
 * posix-sim). The state machine accumulates bytes until a full frame is
 * decoded, then queues the payload for the next `tethys_tr_recv()` call.
 * A checksum mismatch emits `TETHYS_TR_EVT_LOSS` and resynces on the next
 * `0xAA` byte.
 *
 * @param[in] byte The byte received from the wire.
 */
TETHYS_EXPORT void tethys_tr_uart_sxi_inject_rx_byte(uint8_t byte);

/**
 * @brief Drain pending outbound bytes from the TX ring.
 *
 * Called by host integration code to feed bytes into the wire. Copies up
 * to @p cap bytes from the TX ring into @p buf and returns the number of
 * bytes copied (0 if the ring is empty).
 *
 * @param[out] buf  Caller-owned buffer.
 * @param[in]  cap  Capacity of @p buf in bytes.
 *
 * @return Number of bytes copied (0..cap).
 */
TETHYS_EXPORT size_t tethys_tr_uart_sxi_drain_tx_bytes(uint8_t *buf, size_t cap);

/**
 * @brief Report how many decoded frames are queued for `tethys_tr_recv()`.
 *
 * @return 0..TETHYS_UART_DEPTH.
 */
TETHYS_EXPORT size_t tethys_tr_uart_sxi_rx_pending(void);

/**
 * @brief Report how many encoded bytes are queued for `drain_tx_bytes()`.
 *
 * @return number of bytes in the TX ring.
 */
TETHYS_EXPORT size_t tethys_tr_uart_sxi_tx_pending(void);

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* TETHYS_TRANSPORT_UART_SXI_H */
