/*
 * src/transport/loopback.c - In-process loopback transport.
 *
 * Module: tethys::transport::loopback
 * Profiles: all (foundation for the Phase-5 conformance suite)
 * Standards: ADR-0004; ADR-0005 (no dynamic allocation); ADR-0010 row 12
 * Trace: docs/traceability.csv (TETHYS-DES-0031 loopback transport)
 *
 * Ring-buffer pair. Single-threaded only. Used as:
 *   1. The universal baseline for the conformance suite (every other
 *      transport must pass the same shape of tests).
 *   2. A test fixture so the dispatcher can be exercised without bringing
 *      up real hardware (Phase 1 - 4 also rely on it implicitly).
 *
 * No dynamic allocation. The ring is a `static` array of fixed-MTU slots
 * (TETHYS_LOOPBACK_MTU x TETHYS_LOOPBACK_DEPTH = 2 KiB total). Each slot
 * holds one frame plus its length.
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */
#include "tethys/transport_loopback.h"

#include <stddef.h>
#include <stdint.h>
#include <string.h>

/* ---- Ring storage ----------------------------------------------------- */

typedef struct {
    uint8_t  bytes[TETHYS_LOOPBACK_MTU];
    size_t   len;
    bool     valid;
} loopback_slot_t;

static loopback_slot_t g_ring[TETHYS_LOOPBACK_DEPTH];
static size_t          g_head = 0U; /* next write slot */
static size_t          g_tail = 0U; /* next read slot */
static size_t          g_count = 0U;
static bool            g_connected = false;

/* ---- Vtable implementation ------------------------------------------- */

static tethys_tr_status_t loopback_connect(void)
{
    g_connected = true;
    g_head = 0U;
    g_tail = 0U;
    g_count = 0U;
    /* Clear ring so a recv after re-connect on a dirty state can't return
     * stale data. */
    for (size_t i = (size_t)0U; i < TETHYS_LOOPBACK_DEPTH; ++i) {
        g_ring[i].len = (size_t)0U;
        g_ring[i].valid = false;
    }
    return TETHYS_TR_OK;
}

static tethys_tr_status_t loopback_disconnect(void)
{
    g_connected = false;
    return TETHYS_TR_OK;
}

static tethys_tr_status_t loopback_send(const uint8_t *frame, size_t len)
{
    if (!g_connected) {
        return TETHYS_TR_DISCONNECTED;
    }
    if (len > (size_t)TETHYS_LOOPBACK_MTU) {
        return TETHYS_TR_INVAL;
    }
    if (g_count >= TETHYS_LOOPBACK_DEPTH) {
        /* Ring full: declare loss of the oldest frame so the conformance
         * suite can observe back-pressure semantics. */
        tethys_tr_event_t const ev = {
            .kind = TETHYS_TR_EVT_LOSS,
            .timestamp_us = (uint32_t)0U,
            .count = (uint16_t)1U,
            .reserved = (uint16_t)0U,
        };
        tethys_tr_emit_event(&ev);
        /* Advance tail: drop oldest. */
        g_ring[g_tail].valid = false;
        g_tail = (g_tail + (size_t)1U) % TETHYS_LOOPBACK_DEPTH;
        g_count -= (size_t)1U;
    }
    loopback_slot_t *const slot = &g_ring[g_head];
    /* Bounded copy: len is already <= MTU. */
    for (size_t i = (size_t)0U; i < len; ++i) {
        slot->bytes[i] = frame[i];
    }
    slot->len = len;
    slot->valid = true;
    g_head = (g_head + (size_t)1U) % TETHYS_LOOPBACK_DEPTH;
    g_count += (size_t)1U;
    return TETHYS_TR_OK;
}

static tethys_tr_status_t loopback_recv(
    uint8_t *buf, size_t buf_len, size_t *out_len, uint32_t timeout_us)
{
    /* timeout_us is meaningless for an in-process loopback. We don't sleep;
     * we just check the ring. The conformance suite uses 0 (poll) and never
     * calls a blocking variant on this transport. */
    (void)timeout_us;
    if (!g_connected) {
        return TETHYS_TR_DISCONNECTED;
    }
    if (g_count == (size_t)0U) {
        return TETHYS_TR_TIMEOUT;
    }
    loopback_slot_t *const slot = &g_ring[g_tail];
    if (!slot->valid) {
        /* Should not happen if accounting is correct; defensive return. */
        g_count = (size_t)0U;
        return TETHYS_TR_FRAME_ERR;
    }
    if (buf_len < slot->len) {
        return TETHYS_TR_INVAL;
    }
    for (size_t i = (size_t)0U; i < slot->len; ++i) {
        buf[i] = slot->bytes[i];
    }
    *out_len = slot->len;
    slot->valid = false;
    slot->len = (size_t)0U;
    g_tail = (g_tail + (size_t)1U) % TETHYS_LOOPBACK_DEPTH;
    g_count -= (size_t)1U;
    return TETHYS_TR_OK;
}

/* ---- Descriptor (single static const instance) ----------------------- */

static const tethys_tr_descriptor_t g_loopback_descriptor = {
    .id = TETHYS_TR_LOOPBACK,
    .name = "loopback",
    .mtu = TETHYS_LOOPBACK_MTU,
    .supports_reliable = true,
    .supports_ordering = true,
    .max_burst_loss = (uint16_t)0U,
    .typical_latency_us = (uint32_t)0U,
    .typical_loss_ppb = (uint32_t)0U,
    .connect = loopback_connect,
    .disconnect = loopback_disconnect,
    .send = loopback_send,
    .recv = loopback_recv,
};

/* ---- Public accessors ------------------------------------------------- */

const tethys_tr_descriptor_t *tethys_tr_loopback_descriptor(void)
{
    return &g_loopback_descriptor;
}

void tethys_tr_loopback_reset(void)
{
    g_head = (size_t)0U;
    g_tail = (size_t)0U;
    g_count = (size_t)0U;
    g_connected = false;
    for (size_t i = (size_t)0U; i < TETHYS_LOOPBACK_DEPTH; ++i) {
        g_ring[i].len = (size_t)0U;
        g_ring[i].valid = false;
    }
}

void tethys_tr_loopback_inject_loss(uint16_t count)
{
    if (count == (uint16_t)0U) {
        return;
    }
    uint16_t to_drop = count;
    if ((size_t)to_drop > g_count) {
        to_drop = (uint16_t)g_count;
    }
    for (uint16_t i = (uint16_t)0U; i < to_drop; ++i) {
        g_ring[g_tail].valid = false;
        g_ring[g_tail].len = (size_t)0U;
        g_tail = (g_tail + (size_t)1U) % TETHYS_LOOPBACK_DEPTH;
        g_count -= (size_t)1U;
    }
    tethys_tr_event_t const ev = {
        .kind = TETHYS_TR_EVT_LOSS,
        .timestamp_us = (uint32_t)0U,
        .count = to_drop,
        .reserved = (uint16_t)0U,
    };
    tethys_tr_emit_event(&ev);
}

size_t tethys_tr_loopback_pending(void)
{
    return g_count;
}
