/*
 * src/transport/uart_sxi.c - Raw UART / SxI byte-stream transport.
 *
 * Module: tethys::transport::uart_sxi
 * Profiles: space (dev bench); marine (dev bench)
 * Standards: ADR-0004; ADR-0005; ADR-0010 row 8
 * Trace: docs/traceability.csv (TETHYS-DES-0035 UART/SxI transport)
 *
 * Framing (matches `tethys/transport_uart_sxi.h`):
 *
 *   [0]    start byte 0xAA
 *   [1]    length L (1..MTU)
 *   [2..]  payload
 *   [2+L]  checksum (XOR of bytes [0..2+L-1])
 *
 * Single-threaded only. No dynamic allocation: TX and RX rings are
 * `static` arrays of fixed-MTU + 3 bytes (start + length + payload + cksum).
 *
 * CCSDS COP-1 AD is **NOT** implemented here - that is Phase 8 space-profile
 * work. The Phase-5 contract is raw bytes only.
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */
#include "tethys/transport_uart_sxi.h"

#include <stddef.h>
#include <stdint.h>

/* ---- Frame storage ---------------------------------------------------- */

/* Encoded TX frame: start + length + payload + checksum. */
#define UART_FRAME_OVERHEAD ((size_t)3U)
#define UART_FRAME_MAX_SIZE ((size_t)TETHYS_UART_MTU + UART_FRAME_OVERHEAD)

typedef struct {
    uint8_t  payload[TETHYS_UART_MTU];
    size_t   len;
    bool     valid;
} uart_rx_slot_t;

/* RX side: ring of decoded payload slots. */
static uart_rx_slot_t g_rx_ring[TETHYS_UART_DEPTH];
static size_t         g_rx_head = 0U;
static size_t         g_rx_tail = 0U;
static size_t         g_rx_count = 0U;

/* TX side: byte ring (the host integration drains bytes). One slot is
 * sized to hold the encoded frame of one MTU-sized payload. */
static uint8_t        g_tx_bytes[TETHYS_UART_DEPTH * UART_FRAME_MAX_SIZE];
static size_t         g_tx_head = 0U;
static size_t         g_tx_tail = 0U;
static size_t         g_tx_count = 0U;

/* RX framer state machine. */
typedef enum {
    UART_RX_WAIT_START = 0,
    UART_RX_WAIT_LEN,
    UART_RX_WAIT_PAYLOAD,
    UART_RX_WAIT_CKSUM
} uart_rx_state_t;

static uart_rx_state_t g_rx_state = UART_RX_WAIT_START;
static uint8_t         g_rx_pending_len = 0U;
static size_t          g_rx_pending_idx = 0U;
static uint8_t         g_rx_pending_payload[TETHYS_UART_MTU];
static uint8_t         g_rx_running_xor = 0U;
static bool            g_connected = false;

/* ---- Internal helpers ------------------------------------------------- */

static void emit_loss_event(uint16_t count)
{
    tethys_tr_event_t const ev = {
        .kind = TETHYS_TR_EVT_LOSS,
        .timestamp_us = (uint32_t)0U,
        .count = count,
        .reserved = (uint16_t)0U,
    };
    tethys_tr_emit_event(&ev);
}

static void framer_reset(void)
{
    g_rx_state = UART_RX_WAIT_START;
    g_rx_pending_len = (uint8_t)0U;
    g_rx_pending_idx = (size_t)0U;
    g_rx_running_xor = (uint8_t)0U;
}

static void enqueue_decoded_payload(void)
{
    if (g_rx_count >= TETHYS_UART_DEPTH) {
        /* RX ring full - drop oldest, declare loss. */
        emit_loss_event((uint16_t)1U);
        g_rx_ring[g_rx_tail].valid = false;
        g_rx_tail = (g_rx_tail + (size_t)1U) % TETHYS_UART_DEPTH;
        g_rx_count -= (size_t)1U;
    }
    uart_rx_slot_t *const slot = &g_rx_ring[g_rx_head];
    slot->len = (size_t)g_rx_pending_len;
    slot->valid = true;
    /* Bounded copy. */
    for (size_t i = (size_t)0U; i < slot->len; ++i) {
        slot->payload[i] = g_rx_pending_payload[i];
    }
    g_rx_head = (g_rx_head + (size_t)1U) % TETHYS_UART_DEPTH;
    g_rx_count += (size_t)1U;
}

/* ---- Vtable implementation ------------------------------------------- */

static tethys_tr_status_t uart_connect(void)
{
    g_connected = true;
    /* Clear rings; framer reset to start state. */
    g_rx_head = (size_t)0U;
    g_rx_tail = (size_t)0U;
    g_rx_count = (size_t)0U;
    g_tx_head = (size_t)0U;
    g_tx_tail = (size_t)0U;
    g_tx_count = (size_t)0U;
    for (size_t i = (size_t)0U; i < TETHYS_UART_DEPTH; ++i) {
        g_rx_ring[i].len = (size_t)0U;
        g_rx_ring[i].valid = false;
    }
    framer_reset();
    return TETHYS_TR_OK;
}

static tethys_tr_status_t uart_disconnect(void)
{
    g_connected = false;
    return TETHYS_TR_OK;
}

static tethys_tr_status_t uart_send(const uint8_t *frame, size_t len)
{
    if (!g_connected) {
        return TETHYS_TR_DISCONNECTED;
    }
    if ((len == (size_t)0U) || (len > (size_t)TETHYS_UART_MTU)) {
        return TETHYS_TR_INVAL;
    }
    size_t const encoded = len + UART_FRAME_OVERHEAD;
    if ((g_tx_count + encoded) > sizeof g_tx_bytes) {
        return TETHYS_TR_OOM_STATIC;
    }

    uint8_t cksum = (uint8_t)0U;

    /* Write start byte. */
    g_tx_bytes[g_tx_head] = TETHYS_UART_START_BYTE;
    cksum ^= TETHYS_UART_START_BYTE;
    g_tx_head = (g_tx_head + (size_t)1U) % sizeof g_tx_bytes;

    /* Write length. */
    g_tx_bytes[g_tx_head] = (uint8_t)len;
    cksum ^= (uint8_t)len;
    g_tx_head = (g_tx_head + (size_t)1U) % sizeof g_tx_bytes;

    /* Write payload (bounded by len <= MTU). */
    for (size_t i = (size_t)0U; i < len; ++i) {
        g_tx_bytes[g_tx_head] = frame[i];
        cksum ^= frame[i];
        g_tx_head = (g_tx_head + (size_t)1U) % sizeof g_tx_bytes;
    }

    /* Write checksum. */
    g_tx_bytes[g_tx_head] = cksum;
    g_tx_head = (g_tx_head + (size_t)1U) % sizeof g_tx_bytes;

    g_tx_count += encoded;
    return TETHYS_TR_OK;
}

static tethys_tr_status_t uart_recv(
    uint8_t *buf, size_t buf_len, size_t *out_len, uint32_t timeout_us)
{
    (void)timeout_us; /* polling-only on this in-process transport. */
    if (!g_connected) {
        return TETHYS_TR_DISCONNECTED;
    }
    if (g_rx_count == (size_t)0U) {
        return TETHYS_TR_TIMEOUT;
    }
    uart_rx_slot_t *const slot = &g_rx_ring[g_rx_tail];
    if (!slot->valid) {
        g_rx_count = (size_t)0U;
        return TETHYS_TR_FRAME_ERR;
    }
    if (buf_len < slot->len) {
        return TETHYS_TR_INVAL;
    }
    for (size_t i = (size_t)0U; i < slot->len; ++i) {
        buf[i] = slot->payload[i];
    }
    *out_len = slot->len;
    slot->valid = false;
    slot->len = (size_t)0U;
    g_rx_tail = (g_rx_tail + (size_t)1U) % TETHYS_UART_DEPTH;
    g_rx_count -= (size_t)1U;
    return TETHYS_TR_OK;
}

/* ---- Descriptor (single static const instance) ----------------------- */

/* ADR-0010 row 8: raw BER 1e-7 budgeted; COP-1 ARQ wrap (Phase 8) brings
 * residual to <= 1e-12/frame. The raw transport here declares no reliable
 * delivery and a small burst-loss tolerance for line-noise scenarios. */
static const tethys_tr_descriptor_t g_uart_descriptor = {
    .id = TETHYS_TR_UART_SXI,
    .name = "uart_sxi",
    .mtu = TETHYS_UART_MTU,
    .supports_reliable = false,
    .supports_ordering = true,
    .max_burst_loss = (uint16_t)8U,
    .typical_latency_us = (uint32_t)2000U, /* ~2 ms at 115200 baud for 64-byte frame */
    .typical_loss_ppb = (uint32_t)100U,    /* 1e-7 raw BER ≈ 100 PPB */
    .connect = uart_connect,
    .disconnect = uart_disconnect,
    .send = uart_send,
    .recv = uart_recv,
};

/* ---- Public accessors ------------------------------------------------- */

const tethys_tr_descriptor_t *tethys_tr_uart_sxi_descriptor(void)
{
    return &g_uart_descriptor;
}

void tethys_tr_uart_sxi_reset(void)
{
    g_rx_head = (size_t)0U;
    g_rx_tail = (size_t)0U;
    g_rx_count = (size_t)0U;
    g_tx_head = (size_t)0U;
    g_tx_tail = (size_t)0U;
    g_tx_count = (size_t)0U;
    g_connected = false;
    for (size_t i = (size_t)0U; i < TETHYS_UART_DEPTH; ++i) {
        g_rx_ring[i].len = (size_t)0U;
        g_rx_ring[i].valid = false;
    }
    framer_reset();
}

void tethys_tr_uart_sxi_inject_rx_byte(uint8_t byte)
{
    switch (g_rx_state) {
    case UART_RX_WAIT_START:
        if (byte == TETHYS_UART_START_BYTE) {
            g_rx_state = UART_RX_WAIT_LEN;
            g_rx_running_xor = byte;
        }
        /* else: discard byte (resync). */
        break;
    case UART_RX_WAIT_LEN:
        if ((byte == (uint8_t)0U) || ((size_t)byte > (size_t)TETHYS_UART_MTU)) {
            /* Invalid length - resync. Declare loss for visibility. */
            emit_loss_event((uint16_t)1U);
            framer_reset();
        }
        else {
            g_rx_pending_len = byte;
            g_rx_pending_idx = (size_t)0U;
            g_rx_running_xor ^= byte;
            g_rx_state = UART_RX_WAIT_PAYLOAD;
        }
        break;
    case UART_RX_WAIT_PAYLOAD:
        g_rx_pending_payload[g_rx_pending_idx] = byte;
        g_rx_running_xor ^= byte;
        g_rx_pending_idx += (size_t)1U;
        if (g_rx_pending_idx == (size_t)g_rx_pending_len) {
            g_rx_state = UART_RX_WAIT_CKSUM;
        }
        break;
    case UART_RX_WAIT_CKSUM:
        if (byte == g_rx_running_xor) {
            enqueue_decoded_payload();
        }
        else {
            emit_loss_event((uint16_t)1U);
        }
        framer_reset();
        break;
    default:
        framer_reset();
        break;
    }
}

size_t tethys_tr_uart_sxi_drain_tx_bytes(uint8_t *buf, size_t cap)
{
    if ((buf == NULL) || (cap == (size_t)0U)) {
        return (size_t)0U;
    }
    size_t n = g_tx_count;
    if (n > cap) {
        n = cap;
    }
    for (size_t i = (size_t)0U; i < n; ++i) {
        buf[i] = g_tx_bytes[g_tx_tail];
        g_tx_tail = (g_tx_tail + (size_t)1U) % sizeof g_tx_bytes;
    }
    g_tx_count -= n;
    return n;
}

size_t tethys_tr_uart_sxi_rx_pending(void)
{
    return g_rx_count;
}

size_t tethys_tr_uart_sxi_tx_pending(void)
{
    return g_tx_count;
}
