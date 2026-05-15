/*
 * test_transport_uart_sxi.c - Unity tests for the raw UART/SxI transport.
 *
 * Module: tests::test_transport_uart_sxi
 * Profiles: posix-sim (host-side test build)
 * Standards: ADR-0004; ADR-0010 row 8
 * Trace: docs/traceability.csv (TETHYS-TST-0070..0077 - UART/SxI tests)
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */
#include "tethys/transport_uart_sxi.h"
#include "tethys/tethys_transport.h"

#include "unity.h"

#include <stddef.h>
#include <stdint.h>
#include <string.h>

TEST_SOURCE_FILE("transport.c")
TEST_SOURCE_FILE("uart_sxi.c")

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

/* Compute the BSD-XOR checksum of a span. Mirrors the wire format. */
static uint8_t xor_checksum(uint8_t const *bytes, size_t len)
{
    uint8_t x = (uint8_t)0U;
    for (size_t i = (size_t)0U; i < len; ++i) {
        x ^= bytes[i];
    }
    return x;
}

void setUp(void)
{
    tethys_tr_reset();
    tethys_tr_uart_sxi_reset();
    g_event_count = (uint16_t)0U;
    g_last_event_kind = TETHYS_TR_EVT_LOSS;
    TEST_ASSERT_EQUAL_INT(TETHYS_TR_OK,
        tethys_tr_register_transport(tethys_tr_uart_sxi_descriptor()));
    TEST_ASSERT_EQUAL_INT(TETHYS_TR_OK, tethys_tr_connect());
}

void tearDown(void)
{
    (void)tethys_tr_disconnect();
    tethys_tr_reset();
    tethys_tr_uart_sxi_reset();
}

/* -------- Descriptor sanity ------------------------------------------ */

void test_uart_descriptor_fields(void)
{
    tethys_tr_descriptor_t const *const desc = tethys_tr_uart_sxi_descriptor();
    TEST_ASSERT_NOT_NULL(desc);
    TEST_ASSERT_EQUAL_INT(TETHYS_TR_UART_SXI, desc->id);
    TEST_ASSERT_EQUAL_STRING("uart_sxi", desc->name);
    TEST_ASSERT_EQUAL_UINT16((uint16_t)64U, desc->mtu);
    TEST_ASSERT_FALSE(desc->supports_reliable);
    TEST_ASSERT_TRUE(desc->supports_ordering);
    TEST_ASSERT_EQUAL_UINT16((uint16_t)8U, desc->max_burst_loss);
}

/* -------- Send encodes a valid frame -------------------------------- */

void test_send_emits_framed_bytes_in_tx_ring(void)
{
    uint8_t const payload[4] = {0x11U, 0x22U, 0x33U, 0x44U};
    TEST_ASSERT_EQUAL_INT(TETHYS_TR_OK, tethys_tr_send(payload, sizeof payload));

    /* Expect 3 + 4 = 7 bytes in the TX ring. */
    TEST_ASSERT_EQUAL_size_t((size_t)7U, tethys_tr_uart_sxi_tx_pending());

    uint8_t encoded[16];
    size_t const got = tethys_tr_uart_sxi_drain_tx_bytes(encoded, sizeof encoded);
    TEST_ASSERT_EQUAL_size_t((size_t)7U, got);
    TEST_ASSERT_EQUAL_UINT8(0xAAU, encoded[0]); /* start */
    TEST_ASSERT_EQUAL_UINT8((uint8_t)4U, encoded[1]); /* length */
    TEST_ASSERT_EQUAL_UINT8(0x11U, encoded[2]);
    TEST_ASSERT_EQUAL_UINT8(0x22U, encoded[3]);
    TEST_ASSERT_EQUAL_UINT8(0x33U, encoded[4]);
    TEST_ASSERT_EQUAL_UINT8(0x44U, encoded[5]);
    TEST_ASSERT_EQUAL_UINT8(xor_checksum(encoded, (size_t)6U), encoded[6]);
}

/* -------- Inject decodes a valid frame ------------------------------ */

void test_inject_bytes_decodes_valid_frame(void)
{
    /* Hand-crafted frame: start + len=3 + 'A','B','C' + checksum. */
    uint8_t frame[6] = {0xAAU, 0x03U, 'A', 'B', 'C', 0U};
    frame[5] = xor_checksum(frame, (size_t)5U);

    for (size_t i = (size_t)0U; i < sizeof frame; ++i) {
        tethys_tr_uart_sxi_inject_rx_byte(frame[i]);
    }
    TEST_ASSERT_EQUAL_size_t((size_t)1U, tethys_tr_uart_sxi_rx_pending());

    uint8_t rx[TETHYS_UART_MTU];
    size_t out_len = (size_t)0U;
    TEST_ASSERT_EQUAL_INT(TETHYS_TR_OK, tethys_tr_recv(rx, sizeof rx, &out_len, (uint32_t)0U));
    TEST_ASSERT_EQUAL_size_t((size_t)3U, out_len);
    TEST_ASSERT_EQUAL_UINT8('A', rx[0]);
    TEST_ASSERT_EQUAL_UINT8('B', rx[1]);
    TEST_ASSERT_EQUAL_UINT8('C', rx[2]);
}

/* -------- Checksum mismatch fires loss event + resyncs --------------- */

void test_checksum_mismatch_emits_loss_event(void)
{
    tethys_tr_set_event_cb(capturing_event_cb);
    uint8_t frame[6] = {0xAAU, 0x03U, 'X', 'Y', 'Z', 0xFFU /* bad */};

    for (size_t i = (size_t)0U; i < sizeof frame; ++i) {
        tethys_tr_uart_sxi_inject_rx_byte(frame[i]);
    }
    TEST_ASSERT_EQUAL_UINT16((uint16_t)1U, g_event_count);
    TEST_ASSERT_EQUAL_INT(TETHYS_TR_EVT_LOSS, g_last_event_kind);
    /* No frame queued. */
    TEST_ASSERT_EQUAL_size_t((size_t)0U, tethys_tr_uart_sxi_rx_pending());

    /* After resync, a valid frame should still decode. */
    uint8_t good[6] = {0xAAU, 0x03U, 'A', 'B', 'C', 0U};
    good[5] = xor_checksum(good, (size_t)5U);
    for (size_t i = (size_t)0U; i < sizeof good; ++i) {
        tethys_tr_uart_sxi_inject_rx_byte(good[i]);
    }
    TEST_ASSERT_EQUAL_size_t((size_t)1U, tethys_tr_uart_sxi_rx_pending());
}

/* -------- Garbage prefix resynces on next 0xAA --------------------- */

void test_garbage_prefix_is_discarded_until_start_byte(void)
{
    uint8_t junk[5] = {0x00U, 0x11U, 0x55U, 0x12U, 0x34U};
    for (size_t i = (size_t)0U; i < sizeof junk; ++i) {
        tethys_tr_uart_sxi_inject_rx_byte(junk[i]);
    }
    /* Now feed a clean frame. */
    uint8_t frame[5] = {0xAAU, 0x02U, 'H', 'I', 0U};
    frame[4] = xor_checksum(frame, (size_t)4U);
    for (size_t i = (size_t)0U; i < sizeof frame; ++i) {
        tethys_tr_uart_sxi_inject_rx_byte(frame[i]);
    }
    TEST_ASSERT_EQUAL_size_t((size_t)1U, tethys_tr_uart_sxi_rx_pending());
}

/* -------- Invalid length byte is rejected with loss event --------- */

void test_zero_length_byte_emits_loss_and_resyncs(void)
{
    tethys_tr_set_event_cb(capturing_event_cb);
    /* start + len=0 - illegal per framing. */
    tethys_tr_uart_sxi_inject_rx_byte(0xAAU);
    tethys_tr_uart_sxi_inject_rx_byte(0x00U);
    TEST_ASSERT_EQUAL_UINT16((uint16_t)1U, g_event_count);
    TEST_ASSERT_EQUAL_INT(TETHYS_TR_EVT_LOSS, g_last_event_kind);
}

void test_oversize_length_byte_emits_loss_and_resyncs(void)
{
    tethys_tr_set_event_cb(capturing_event_cb);
    /* start + len = MTU + 1 - illegal. */
    tethys_tr_uart_sxi_inject_rx_byte(0xAAU);
    tethys_tr_uart_sxi_inject_rx_byte((uint8_t)(TETHYS_UART_MTU + (size_t)1U));
    TEST_ASSERT_EQUAL_UINT16((uint16_t)1U, g_event_count);
    TEST_ASSERT_EQUAL_INT(TETHYS_TR_EVT_LOSS, g_last_event_kind);
}

/* -------- send-then-recv via internal loopback (TX bytes feed RX) ---- */

void test_full_round_trip_through_byte_pipe(void)
{
    /* Send a frame on the master end; drain its bytes; feed them back
     * into the framer's RX path; recv should reproduce the payload. */
    uint8_t const tx[8] = {0xDEU, 0xADU, 0xBEU, 0xEFU, 0xCAU, 0xFEU, 0xBAU, 0xBEU};
    TEST_ASSERT_EQUAL_INT(TETHYS_TR_OK, tethys_tr_send(tx, sizeof tx));

    uint8_t pipe[32];
    size_t const got = tethys_tr_uart_sxi_drain_tx_bytes(pipe, sizeof pipe);
    TEST_ASSERT_TRUE(got > (size_t)0U);
    for (size_t i = (size_t)0U; i < got; ++i) {
        tethys_tr_uart_sxi_inject_rx_byte(pipe[i]);
    }

    uint8_t rx[TETHYS_UART_MTU];
    size_t out_len = (size_t)0U;
    TEST_ASSERT_EQUAL_INT(TETHYS_TR_OK, tethys_tr_recv(rx, sizeof rx, &out_len, (uint32_t)0U));
    TEST_ASSERT_EQUAL_size_t(sizeof tx, out_len);
    TEST_ASSERT_EQUAL_MEMORY(tx, rx, sizeof tx);
}
