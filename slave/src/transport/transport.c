/*
 * src/transport/transport.c - Transport Abstraction Layer dispatcher.
 *
 * Module: tethys::transport (TAL active-descriptor forwarder)
 * Profiles: all
 * Standards: ASAM XCP 1.4 Part 1 §1.1; MISRA C:2023; ECSS-E-ST-40C Rev.1 §5.4
 * Trace: docs/traceability.csv (TETHYS-DES-0030 transport interface)
 *
 * Owns the single active-descriptor pointer plus the event callback. Concrete
 * transports never reference each other; they all go through this file.
 *
 * No dynamic allocation (ADR-0005). State is two file-scope pointers - a
 * read-only descriptor pointer (owned by the transport's .c file) and a
 * function pointer for the optional event sink. No locks: single-threaded
 * call contract per `tethys/tethys_transport.h`.
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */
#include "tethys/tethys_transport.h"

#include <stddef.h>
#include <stdint.h>

/* ---- File-scope state ------------------------------------------------- */

static const tethys_tr_descriptor_t *g_active = NULL;
static tethys_tr_event_cb_t          g_event_cb = NULL;

/* ---- Internal helpers ------------------------------------------------- */

/**
 * @brief Validate that a descriptor satisfies the TAL contract.
 *
 * The TAL never invokes a NULL vtable entry; callers either supply all four
 * operational functions or get TETHYS_TR_INVAL at register-time.
 */
static bool descriptor_is_valid(const tethys_tr_descriptor_t *desc)
{
    if (desc == NULL) {
        return false;
    }
    if (desc->id == TETHYS_TR_UNDEFINED) {
        return false;
    }
    if (desc->mtu == (uint16_t)0U) {
        return false;
    }
    if (desc->name == NULL) {
        return false;
    }
    if ((desc->connect == NULL)
        || (desc->disconnect == NULL)
        || (desc->send == NULL)
        || (desc->recv == NULL)) {
        return false;
    }
    return true;
}

/* ---- Public API ------------------------------------------------------- */

tethys_tr_status_t tethys_tr_register_transport(const tethys_tr_descriptor_t *desc)
{
    if (!descriptor_is_valid(desc)) {
        return TETHYS_TR_INVAL;
    }
    if (g_active == desc) {
        return TETHYS_TR_OK;
    }
    if (g_active != NULL) {
        /* Best-effort disconnect of the previous transport before swap.
         * Return value intentionally ignored: the caller chose to switch, so
         * we don't propagate the old transport's disconnect status. */
        (void)g_active->disconnect();
    }
    g_active = desc;
    return TETHYS_TR_OK;
}

void tethys_tr_reset(void)
{
    g_active = NULL;
    g_event_cb = NULL;
}

const tethys_tr_descriptor_t *tethys_tr_active_descriptor(void)
{
    return g_active;
}

tethys_tr_status_t tethys_tr_connect(void)
{
    if (g_active == NULL) {
        return TETHYS_TR_DISCONNECTED;
    }
    return g_active->connect();
}

tethys_tr_status_t tethys_tr_disconnect(void)
{
    if (g_active == NULL) {
        return TETHYS_TR_DISCONNECTED;
    }
    return g_active->disconnect();
}

tethys_tr_status_t tethys_tr_send(const uint8_t *frame, size_t len)
{
    if (g_active == NULL) {
        return TETHYS_TR_DISCONNECTED;
    }
    if ((frame == NULL) || (len == (size_t)0U)) {
        return TETHYS_TR_INVAL;
    }
    if (len > (size_t)g_active->mtu) {
        return TETHYS_TR_INVAL;
    }
    return g_active->send(frame, len);
}

tethys_tr_status_t tethys_tr_recv(
    uint8_t *buf, size_t buf_len, size_t *out_len, uint32_t timeout_us)
{
    if (g_active == NULL) {
        return TETHYS_TR_DISCONNECTED;
    }
    if ((buf == NULL) || (out_len == NULL) || (buf_len == (size_t)0U)) {
        return TETHYS_TR_INVAL;
    }
    if (buf_len < (size_t)g_active->mtu) {
        return TETHYS_TR_INVAL;
    }
    return g_active->recv(buf, buf_len, out_len, timeout_us);
}

void tethys_tr_set_event_cb(tethys_tr_event_cb_t cb)
{
    g_event_cb = cb;
}

void tethys_tr_emit_event(const tethys_tr_event_t *ev)
{
    if ((g_event_cb == NULL) || (ev == NULL)) {
        return;
    }
    g_event_cb(ev);
}
