/*
 * test_transport_loopback.c - Unity tests for the in-process loopback transport.
 *
 * Module: tests::test_transport_loopback
 * Profiles: posix-sim (host-side test build)
 * Standards: ADR-0004 (transport-abstraction-layer interface);
 *            ADR-0010 row 12 (loopback zero-loss budget)
 * Trace: docs/traceability.csv (TETHYS-TST-0050..0057 - loopback transport tests)
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */
#include "tethys/transport_loopback.h"
#include "tethys/tethys_transport.h"

#include "unity.h"

#include <stddef.h>
#include <stdint.h>
#include <string.h>

/* Ceedling source discovery: explicit because both .c files are nested under
 * transport/. The TAL dispatcher (transport.c) is the public API; the loopback
 * descriptor lives in loopback.c. */
TEST_SOURCE_FILE("transport.c")
TEST_SOURCE_FILE("loopback.c")

#define LOOPBACK_TEST_FRAME_LEN ((size_t)16U)

static uint16_t g_event_count;
static tethys_tr_evt_kind_t g_last_event_kind;

static void capturing_event_cb(const tethys_tr_event_t *ev)
{
    if (ev == NULL) {
        return;
    }
    g_event_count = (uint16_t)(g_event_count + (uint16_t)1U);
    g_last_event_kind = ev->kind;
}

void setUp(void)
{
    tethys_tr_reset();
    tethys_tr_loopback_reset();
    g_event_count = (uint16_t)0U;
    g_last_event_kind = TETHYS_TR_EVT_LOSS;
    /* Register loopback as the active transport for every test. */
    tethys_tr_status_t const rc = tethys_tr_register_transport(tethys_tr_loopback_descriptor());
    TEST_ASSERT_EQUAL_INT(TETHYS_TR_OK, rc);
    TEST_ASSERT_EQUAL_INT(TETHYS_TR_OK, tethys_tr_connect());
}

void tearDown(void)
{
    (void)tethys_tr_disconnect();
    tethys_tr_reset();
    tethys_tr_loopback_reset();
}

/* -------- Descriptor / metadata sanity -------------------------------- */

void test_loopback_descriptor_fields(void)
{
    tethys_tr_descriptor_t const *const desc = tethys_tr_loopback_descriptor();
    TEST_ASSERT_NOT_NULL(desc);
    TEST_ASSERT_EQUAL_INT(TETHYS_TR_LOOPBACK, desc->id);
    TEST_ASSERT_NOT_NULL(desc->name);
    TEST_ASSERT_EQUAL_STRING("loopback", desc->name);
    TEST_ASSERT_TRUE(desc->mtu > (uint16_t)0U);
    TEST_ASSERT_TRUE(desc->supports_reliable);
    TEST_ASSERT_TRUE(desc->supports_ordering);
    TEST_ASSERT_EQUAL_UINT16((uint16_t)0U, desc->max_burst_loss);
    TEST_ASSERT_EQUAL_UINT32((uint32_t)0U, desc->typical_loss_ppb);
}

void test_active_descriptor_after_register(void)
{
    tethys_tr_descriptor_t const *const active = tethys_tr_active_descriptor();
    TEST_ASSERT_NOT_NULL(active);
    TEST_ASSERT_EQUAL_INT(TETHYS_TR_LOOPBACK, active->id);
}

void test_reset_clears_active_descriptor(void)
{
    (void)tethys_tr_disconnect();
    tethys_tr_reset();
    TEST_ASSERT_NULL(tethys_tr_active_descriptor());
    /* Operational calls after reset must return DISCONNECTED. */
    uint8_t buf[LOOPBACK_TEST_FRAME_LEN];
    size_t out_len = (size_t)0U;
    TEST_ASSERT_EQUAL_INT(TETHYS_TR_DISCONNECTED, tethys_tr_send(buf, LOOPBACK_TEST_FRAME_LEN));
    TEST_ASSERT_EQUAL_INT(TETHYS_TR_DISCONNECTED, tethys_tr_recv(buf, sizeof buf, &out_len, (uint32_t)0U));
}

/* -------- Operational API -------------------------------------------- */

void test_send_recv_round_trip(void)
{
    uint8_t const tx_bytes[LOOPBACK_TEST_FRAME_LEN] = {
        0x01U, 0x02U, 0x03U, 0x04U, 0x05U, 0x06U, 0x07U, 0x08U,
        0x09U, 0x0AU, 0x0BU, 0x0CU, 0x0DU, 0x0EU, 0x0FU, 0x10U,
    };
    TEST_ASSERT_EQUAL_INT(TETHYS_TR_OK, tethys_tr_send(tx_bytes, LOOPBACK_TEST_FRAME_LEN));

    uint8_t rx_bytes[TETHYS_LOOPBACK_MTU];
    size_t out_len = (size_t)0U;
    TEST_ASSERT_EQUAL_INT(TETHYS_TR_OK, tethys_tr_recv(rx_bytes, sizeof rx_bytes, &out_len, (uint32_t)0U));
    TEST_ASSERT_EQUAL_size_t(LOOPBACK_TEST_FRAME_LEN, out_len);
    TEST_ASSERT_EQUAL_MEMORY(tx_bytes, rx_bytes, LOOPBACK_TEST_FRAME_LEN);
}

void test_recv_when_empty_returns_timeout(void)
{
    uint8_t buf[TETHYS_LOOPBACK_MTU];
    size_t out_len = (size_t)0U;
    TEST_ASSERT_EQUAL_INT(TETHYS_TR_TIMEOUT, tethys_tr_recv(buf, sizeof buf, &out_len, (uint32_t)0U));
}

void test_send_rejects_oversized_frame(void)
{
    static uint8_t oversize[TETHYS_LOOPBACK_MTU + (size_t)1U];
    (void)memset(oversize, 0, sizeof oversize);
    TEST_ASSERT_EQUAL_INT(TETHYS_TR_INVAL, tethys_tr_send(oversize, sizeof oversize));
}

void test_send_rejects_null_frame(void)
{
    TEST_ASSERT_EQUAL_INT(TETHYS_TR_INVAL, tethys_tr_send(NULL, (size_t)4U));
}

void test_recv_into_buffer_smaller_than_mtu_returns_inval(void)
{
    uint8_t tiny[1];
    size_t out_len = (size_t)0U;
    TEST_ASSERT_EQUAL_INT(TETHYS_TR_INVAL, tethys_tr_recv(tiny, sizeof tiny, &out_len, (uint32_t)0U));
}

/* -------- Ring-buffer back-pressure --------------------------------- */

void test_ring_overflow_emits_loss_event_and_drops_oldest(void)
{
    tethys_tr_set_event_cb(capturing_event_cb);
    uint8_t payload[1] = {0xAAU};
    /* Push depth+1 frames. The first should be dropped with a LOSS event. */
    for (size_t i = (size_t)0U; i <= TETHYS_LOOPBACK_DEPTH; ++i) {
        payload[0] = (uint8_t)(i & 0xFFU);
        (void)tethys_tr_send(payload, sizeof payload);
    }
    TEST_ASSERT_TRUE(g_event_count >= (uint16_t)1U);
    TEST_ASSERT_EQUAL_INT(TETHYS_TR_EVT_LOSS, g_last_event_kind);
    TEST_ASSERT_EQUAL_size_t(TETHYS_LOOPBACK_DEPTH, tethys_tr_loopback_pending());

    /* First received frame should be slot 1 (slot 0 was dropped). */
    uint8_t rx[TETHYS_LOOPBACK_MTU];
    size_t out_len = (size_t)0U;
    TEST_ASSERT_EQUAL_INT(TETHYS_TR_OK, tethys_tr_recv(rx, sizeof rx, &out_len, (uint32_t)0U));
    TEST_ASSERT_EQUAL_UINT8((uint8_t)1U, rx[0]);
}

/* -------- Event-callback wiring -------------------------------------- */

void test_inject_loss_fires_event(void)
{
    tethys_tr_set_event_cb(capturing_event_cb);
    uint8_t payload[1] = {0xCCU};
    /* Queue 3 frames then declare them lost. */
    for (size_t i = (size_t)0U; i < (size_t)3U; ++i) {
        (void)tethys_tr_send(payload, sizeof payload);
    }
    tethys_tr_loopback_inject_loss((uint16_t)2U);
    TEST_ASSERT_EQUAL_UINT16((uint16_t)1U, g_event_count);
    TEST_ASSERT_EQUAL_INT(TETHYS_TR_EVT_LOSS, g_last_event_kind);
    /* One frame should still be queued (3 - 2 = 1). */
    TEST_ASSERT_EQUAL_size_t((size_t)1U, tethys_tr_loopback_pending());
}

void test_emit_event_with_no_callback_is_safe(void)
{
    tethys_tr_set_event_cb(NULL);
    tethys_tr_event_t ev = {
        .kind = TETHYS_TR_EVT_BUS_OFF,
        .timestamp_us = (uint32_t)0U,
        .count = (uint16_t)1U,
        .reserved = (uint16_t)0U,
    };
    /* MUST NOT crash. */
    tethys_tr_emit_event(&ev);
    TEST_ASSERT_EQUAL_UINT16((uint16_t)0U, g_event_count);
}
