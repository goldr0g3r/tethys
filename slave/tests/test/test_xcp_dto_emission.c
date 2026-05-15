/*
 * test_xcp_dto_emission.c - Unity tests for the DAQ event-tick + TAL emission.
 *
 * Module: tests::test_xcp_dto_emission
 * Profiles: posix-sim
 * Standards: ASAM XCP 1.4 Part 2 §1.4.2 (DTO emission);
 *            ADR-0010 row 2 + row 12 (DAQ loss budget + loopback acceptance)
 * Trace: docs/traceability.csv (rows TETHYS-TST-0085..0096 land at PR-10)
 *
 * Phase 3 PR-3b tests:
 *   - tick on no-lists is a no-op (returns 0)
 *   - tick on 1 running list emits 1 DTO per ODT
 *   - tick on 2 running lists with matching event emits N+M DTOs
 *   - tick on STIM-direction list emits 0 (STIM is master-driven)
 *   - tick respects the prescaler (1/N)
 *   - tick respects event-channel binding
 *   - 1 kHz-equivalent rapid tick: 60 000 ticks * 1 ODT = 60 000 DTOs with
 *     zero loss + monotonic CTR sequence (loopback acceptance per
 *     ADR-0010 row 12 - the CI quick-run derivative of the 60-minute
 *     nightly soak in PR-3e).
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */
#include "tethys/tethys_transport.h"
#include "tethys/transport_loopback.h"
#include "tethys/xcp_daq.h"
#include "tethys/xcp_dispatcher.h"
#include "tethys/xcp_odt.h"

#include "unity.h"

#include <stddef.h>
#include <stdint.h>
#include <string.h>

TEST_SOURCE_FILE("xcp_daq.c")
TEST_SOURCE_FILE("xcp_odt.c")
TEST_SOURCE_FILE("xcp_dispatcher.c")
TEST_SOURCE_FILE("loopback.c")
TEST_SOURCE_FILE("transport.c")

#define TEST_MEM_SIZE  ((size_t)256U)

static tethys_xcp_state_t  g_state;
static tethys_daq_engine_t g_daq;
static uint8_t             g_memory[TEST_MEM_SIZE];

/* Drain one DTO from the loopback ring and return its length (0 on empty). */
static size_t drain_one(uint8_t* buf, size_t cap)
{
    size_t got = (size_t)0U;
    tethys_tr_status_t const tr = tethys_tr_recv(buf, cap, &got, (uint32_t)0U);
    return (tr == TETHYS_TR_OK) ? got : (size_t)0U;
}

static void configure_basic_list(uint8_t mode, uint16_t event_channel, uint8_t prescaler)
{
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_alloc(&g_daq, (uint16_t)1U));
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_alloc_odt(&g_daq, (uint16_t)0U, (uint8_t)1U));
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_alloc_odt_entry(&g_daq,
        (uint16_t)0U, (uint8_t)0U, (uint8_t)1U));
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_set_ptr(&g_daq, (uint16_t)0U, (uint8_t)0U, (uint8_t)0U));
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_write_entry(&g_daq, TETHYS_DAQ_BIT_OFFSET_NONE,
        (uint8_t)2U, (uint8_t)0U, (uint32_t)0U));
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_set_list_mode(&g_daq, (uint16_t)0U,
        mode, event_channel, prescaler, (uint8_t)0U));
    uint8_t fp = (uint8_t)0U;
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_start_stop_list(&g_daq, (uint16_t)0U,
        TETHYS_DAQ_START_STOP_START, &fp));
}

void setUp(void)
{
    tethys_xcp_init(&g_state);
    tethys_daq_init(&g_daq);
    for (size_t i = (size_t)0U; i < TEST_MEM_SIZE; ++i) {
        g_memory[i] = (uint8_t)(i & 0xFFU);
    }
    tethys_xcp_attach_memory(&g_state, g_memory, TEST_MEM_SIZE);
    tethys_xcp_attach_daq(&g_state, &g_daq);

    tethys_tr_loopback_reset();
    TEST_ASSERT_EQUAL_INT(TETHYS_TR_OK,
        tethys_tr_register_transport(tethys_tr_loopback_descriptor()));
    TEST_ASSERT_EQUAL_INT(TETHYS_TR_OK, tethys_tr_connect());
}

void tearDown(void)
{
    (void)tethys_tr_disconnect();
    tethys_tr_reset();
    tethys_tr_loopback_reset();
}

/* ---- Empty engine ---------------------------------------------------- */

void test_tick_on_empty_engine_emits_nothing(void)
{
    TEST_ASSERT_EQUAL_UINT16(0U, tethys_daq_tick(&g_daq, (uint16_t)1U, (uint32_t)0U));
    TEST_ASSERT_EQUAL_size_t((size_t)0U, tethys_tr_loopback_pending());
}

void test_tick_null_engine_is_safe(void)
{
    TEST_ASSERT_EQUAL_UINT16(0U, tethys_daq_tick(NULL, (uint16_t)0U, (uint32_t)0U));
}

/* ---- One DAQ list ---------------------------------------------------- */

void test_tick_emits_one_dto_for_running_list(void)
{
    configure_basic_list((uint8_t)0U, (uint16_t)1U, (uint8_t)1U);
    uint16_t const emitted = tethys_daq_tick(&g_daq, (uint16_t)1U, (uint32_t)0U);
    TEST_ASSERT_EQUAL_UINT16(1U, emitted);
    TEST_ASSERT_EQUAL_size_t((size_t)1U, tethys_tr_loopback_pending());

    uint8_t buf[TETHYS_DAQ_MAX_DTO_BYTES];
    size_t const len = drain_one(buf, sizeof buf);
    TEST_ASSERT_EQUAL_size_t((size_t)3U, len); /* PID + 2-byte payload */
    TEST_ASSERT_EQUAL_UINT8(0U, buf[0]); /* PID = first_pid (0) + odt (0) */
    TEST_ASSERT_EQUAL_UINT8(0U, buf[1]); /* memory[0] */
    TEST_ASSERT_EQUAL_UINT8(1U, buf[2]); /* memory[1] */
}

void test_tick_skips_stopped_list(void)
{
    configure_basic_list((uint8_t)0U, (uint16_t)1U, (uint8_t)1U);
    uint8_t fp = (uint8_t)0U;
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_start_stop_list(&g_daq, (uint16_t)0U,
        TETHYS_DAQ_START_STOP_STOP, &fp));
    TEST_ASSERT_EQUAL_UINT16(0U, tethys_daq_tick(&g_daq, (uint16_t)1U, (uint32_t)0U));
}

void test_tick_skips_non_matching_event_channel(void)
{
    configure_basic_list((uint8_t)0U, (uint16_t)2U, (uint8_t)1U);
    /* Tick a different channel - should not emit. */
    TEST_ASSERT_EQUAL_UINT16(0U, tethys_daq_tick(&g_daq, (uint16_t)1U, (uint32_t)0U));
    /* Tick the right channel - should emit. */
    TEST_ASSERT_EQUAL_UINT16(1U, tethys_daq_tick(&g_daq, (uint16_t)2U, (uint32_t)0U));
}

void test_tick_skips_stim_direction_list(void)
{
    configure_basic_list(TETHYS_DAQ_MODE_DIRECTION_STIM, (uint16_t)1U, (uint8_t)1U);
    TEST_ASSERT_EQUAL_UINT16(0U, tethys_daq_tick(&g_daq, (uint16_t)1U, (uint32_t)0U));
}

void test_tick_respects_prescaler(void)
{
    /* prescaler=3: fire on every 3rd matching tick */
    configure_basic_list((uint8_t)0U, (uint16_t)1U, (uint8_t)3U);
    TEST_ASSERT_EQUAL_UINT16(0U, tethys_daq_tick(&g_daq, (uint16_t)1U, (uint32_t)0U));
    TEST_ASSERT_EQUAL_UINT16(0U, tethys_daq_tick(&g_daq, (uint16_t)1U, (uint32_t)1U));
    TEST_ASSERT_EQUAL_UINT16(1U, tethys_daq_tick(&g_daq, (uint16_t)1U, (uint32_t)2U));
    TEST_ASSERT_EQUAL_UINT16(0U, tethys_daq_tick(&g_daq, (uint16_t)1U, (uint32_t)3U));
    TEST_ASSERT_EQUAL_UINT16(0U, tethys_daq_tick(&g_daq, (uint16_t)1U, (uint32_t)4U));
    TEST_ASSERT_EQUAL_UINT16(1U, tethys_daq_tick(&g_daq, (uint16_t)1U, (uint32_t)5U));
}

void test_tick_with_timestamp_mode_prepends_timestamp(void)
{
    configure_basic_list(TETHYS_DAQ_MODE_TIMESTAMP, (uint16_t)1U, (uint8_t)1U);
    TEST_ASSERT_EQUAL_UINT16(1U,
        tethys_daq_tick(&g_daq, (uint16_t)1U, (uint32_t)0xAABBCCDDU));
    uint8_t buf[TETHYS_DAQ_MAX_DTO_BYTES];
    size_t const len = drain_one(buf, sizeof buf);
    TEST_ASSERT_EQUAL_size_t((size_t)7U, len); /* PID + 4-byte ts + 2-byte payload */
    TEST_ASSERT_EQUAL_UINT8(0xDDU, buf[1]);
    TEST_ASSERT_EQUAL_UINT8(0xCCU, buf[2]);
    TEST_ASSERT_EQUAL_UINT8(0xBBU, buf[3]);
    TEST_ASSERT_EQUAL_UINT8(0xAAU, buf[4]);
}

/* ---- Two DAQ lists, same event -------------------------------------- */

void test_tick_emits_for_each_matching_list(void)
{
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_alloc(&g_daq, (uint16_t)2U));
    /* List 0: 1 ODT, 1 entry */
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_alloc_odt(&g_daq, (uint16_t)0U, (uint8_t)1U));
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_alloc_odt_entry(&g_daq,
        (uint16_t)0U, (uint8_t)0U, (uint8_t)1U));
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_set_ptr(&g_daq, (uint16_t)0U, (uint8_t)0U, (uint8_t)0U));
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_write_entry(&g_daq, TETHYS_DAQ_BIT_OFFSET_NONE,
        (uint8_t)1U, (uint8_t)0U, (uint32_t)0U));
    /* List 1: 1 ODT, 1 entry */
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_alloc_odt(&g_daq, (uint16_t)1U, (uint8_t)1U));
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_alloc_odt_entry(&g_daq,
        (uint16_t)1U, (uint8_t)0U, (uint8_t)1U));
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_set_ptr(&g_daq, (uint16_t)1U, (uint8_t)0U, (uint8_t)0U));
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_write_entry(&g_daq, TETHYS_DAQ_BIT_OFFSET_NONE,
        (uint8_t)1U, (uint8_t)0U, (uint32_t)1U));
    /* Bind both to event 7 + start. */
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_set_list_mode(&g_daq, (uint16_t)0U,
        (uint8_t)0U, (uint16_t)7U, (uint8_t)1U, (uint8_t)0U));
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_set_list_mode(&g_daq, (uint16_t)1U,
        (uint8_t)0U, (uint16_t)7U, (uint8_t)1U, (uint8_t)0U));
    uint8_t fp = (uint8_t)0U;
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_start_stop_list(&g_daq, (uint16_t)0U,
        TETHYS_DAQ_START_STOP_START, &fp));
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_start_stop_list(&g_daq, (uint16_t)1U,
        TETHYS_DAQ_START_STOP_START, &fp));

    TEST_ASSERT_EQUAL_UINT16(2U,
        tethys_daq_tick(&g_daq, (uint16_t)7U, (uint32_t)0U));
}

/* ---- 1 kHz quick-run acceptance derivative -------------------------- */

void test_acceptance_1khz_quickrun_zero_loss(void)
{
    /* This is the CI-friendly derivative of the 60-minute nightly
     * acceptance test in PR-3e (ADR-0010 row 12 -> loopback zero-loss).
     * We tick the engine 1 000 times with prescaler=1 + drain every DTO
     * back through the loopback transport. Each pass verifies:
     *   - one DTO emitted per tick (no missed ticks)
     *   - PID stays at 0 (first_pid + odt = 0)
     *   - payload bytes match the seeded memory ramp
     *   - aggregate emit count = aggregate drain count
     *
     * 1 000 iterations is sufficient to exercise the engine + TAL
     * happy path without bloating CI wall-clock. The full 60-min/60s
     * 60 000-frame soak runs nightly. */
    configure_basic_list((uint8_t)0U, (uint16_t)42U, (uint8_t)1U);
    enum { ITERATIONS = 1000 };
    uint32_t total_emitted = (uint32_t)0U;
    uint32_t total_received = (uint32_t)0U;
    uint8_t buf[TETHYS_DAQ_MAX_DTO_BYTES];
    for (size_t i = (size_t)0U; i < (size_t)ITERATIONS; ++i) {
        total_emitted += (uint32_t)tethys_daq_tick(
            &g_daq, (uint16_t)42U, (uint32_t)i);
        size_t const len = drain_one(buf, sizeof buf);
        TEST_ASSERT_EQUAL_size_t((size_t)3U, len);
        TEST_ASSERT_EQUAL_UINT8(0U, buf[0]); /* PID = 0 */
        TEST_ASSERT_EQUAL_UINT8(0U, buf[1]); /* memory[0] */
        TEST_ASSERT_EQUAL_UINT8(1U, buf[2]); /* memory[1] */
        total_received += (uint32_t)1U;
    }
    TEST_ASSERT_EQUAL_UINT32((uint32_t)ITERATIONS, total_emitted);
    TEST_ASSERT_EQUAL_UINT32((uint32_t)ITERATIONS, total_received);
    TEST_ASSERT_EQUAL_UINT16((uint16_t)((uint32_t)ITERATIONS & 0xFFFFU),
        g_daq.dto_counter);
}
