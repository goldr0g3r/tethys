/*
 * test_xcp_daq.c - Unity tests for the DAQ engine + dispatcher routing.
 *
 * Module: tests::test_xcp_daq
 * Profiles: posix-sim
 * Standards: ASAM XCP 1.4 Part 2 §1.4 (DAQ command set)
 * Trace: docs/traceability.csv (rows TETHYS-TST-0060..0084 land at PR-10)
 *
 * Phase 3 PR-3a tests:
 *   - ALLOC/FREE pathways (full + partial + double-alloc)
 *   - SET_DAQ_PTR bounds enforcement
 *   - WRITE_DAQ + WRITE_DAQ_MULTIPLE
 *   - START_STOP_DAQ_LIST per-list + START_STOP_SYNCH all-lists
 *   - DTO pack/unpack round-trip
 *   - dispatcher routes every DAQ command code through the engine
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */
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

#define TEST_MEM_SIZE  ((size_t)256U)

static tethys_xcp_state_t  g_state;
static tethys_daq_engine_t g_daq;
static uint8_t             g_memory[TEST_MEM_SIZE];
static uint8_t             g_response[TETHYS_XCP_MAX_CTO];
static size_t              g_resp_len;

static void seed_ramp(void)
{
    for (size_t i = (size_t)0U; i < TEST_MEM_SIZE; ++i) {
        g_memory[i] = (uint8_t)(i & 0xFFU);
    }
}

static void connect_session(void)
{
    uint8_t req[2] = {TETHYS_XCP_CMD_CONNECT, 0U};
    (void)tethys_xcp_dispatch(
        &g_state, req, sizeof req, g_response, sizeof g_response, &g_resp_len);
}

void setUp(void)
{
    tethys_xcp_init(&g_state);
    tethys_daq_init(&g_daq);
    seed_ramp();
    tethys_xcp_attach_memory(&g_state, g_memory, TEST_MEM_SIZE);
    tethys_xcp_attach_daq(&g_state, &g_daq);
    (void)memset(g_response, 0, sizeof g_response);
    g_resp_len = (size_t)0U;
}

void tearDown(void) { /* no-op */ }

/* ---- Engine init + reset -------------------------------------------- */

void test_init_clears_engine(void)
{
    TEST_ASSERT_EQUAL_UINT8(0U, g_daq.list_count);
    TEST_ASSERT_EQUAL_UINT16(0U, g_daq.dto_counter);
    TEST_ASSERT_FALSE(g_daq.ptr_valid);
}

void test_init_null_safe(void)
{
    tethys_daq_init(NULL);
    TEST_PASS();
}

/* ---- ALLOC pathways ------------------------------------------------- */

void test_alloc_succeeds(void)
{
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_alloc(&g_daq, (uint16_t)2U));
    TEST_ASSERT_EQUAL_UINT8(2U, g_daq.list_count);
    TEST_ASSERT_TRUE(g_daq.lists[0].allocated);
    TEST_ASSERT_TRUE(g_daq.lists[1].allocated);
}

void test_alloc_zero_rejected(void)
{
    TEST_ASSERT_EQUAL_INT(-1, tethys_daq_alloc(&g_daq, (uint16_t)0U));
}

void test_alloc_overflow_rejected(void)
{
    TEST_ASSERT_EQUAL_INT(-1, tethys_daq_alloc(&g_daq,
        (uint16_t)(TETHYS_DAQ_MAX_LISTS + (uint8_t)1U)));
}

void test_alloc_odt_succeeds(void)
{
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_alloc(&g_daq, (uint16_t)1U));
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_alloc_odt(&g_daq, (uint16_t)0U, (uint8_t)3U));
    TEST_ASSERT_EQUAL_UINT8(3U, g_daq.lists[0].odt_count);
}

void test_alloc_odt_entry_succeeds(void)
{
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_alloc(&g_daq, (uint16_t)1U));
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_alloc_odt(&g_daq, (uint16_t)0U, (uint8_t)1U));
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_alloc_odt_entry(&g_daq,
        (uint16_t)0U, (uint8_t)0U, (uint8_t)4U));
    TEST_ASSERT_EQUAL_UINT8(4U, g_daq.lists[0].odts[0].entry_count);
}

void test_free_resets_all_lists(void)
{
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_alloc(&g_daq, (uint16_t)2U));
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_free(&g_daq));
    TEST_ASSERT_EQUAL_UINT8(0U, g_daq.list_count);
    TEST_ASSERT_FALSE(g_daq.lists[0].allocated);
}

/* ---- SET_DAQ_PTR + WRITE_DAQ --------------------------------------- */

void test_set_ptr_rejects_out_of_range_list(void)
{
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_alloc(&g_daq, (uint16_t)1U));
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_alloc_odt(&g_daq, (uint16_t)0U, (uint8_t)1U));
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_alloc_odt_entry(&g_daq,
        (uint16_t)0U, (uint8_t)0U, (uint8_t)1U));
    TEST_ASSERT_EQUAL_INT(-1, tethys_daq_set_ptr(&g_daq, (uint16_t)5U, (uint8_t)0U, (uint8_t)0U));
}

void test_set_ptr_rejects_out_of_range_odt(void)
{
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_alloc(&g_daq, (uint16_t)1U));
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_alloc_odt(&g_daq, (uint16_t)0U, (uint8_t)2U));
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_alloc_odt_entry(&g_daq,
        (uint16_t)0U, (uint8_t)0U, (uint8_t)1U));
    TEST_ASSERT_EQUAL_INT(-1, tethys_daq_set_ptr(&g_daq, (uint16_t)0U, (uint8_t)2U, (uint8_t)0U));
}

void test_set_ptr_rejects_out_of_range_entry(void)
{
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_alloc(&g_daq, (uint16_t)1U));
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_alloc_odt(&g_daq, (uint16_t)0U, (uint8_t)1U));
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_alloc_odt_entry(&g_daq,
        (uint16_t)0U, (uint8_t)0U, (uint8_t)2U));
    TEST_ASSERT_EQUAL_INT(-1, tethys_daq_set_ptr(&g_daq, (uint16_t)0U, (uint8_t)0U, (uint8_t)5U));
}

void test_write_entry_populates_and_advances_pointer(void)
{
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_alloc(&g_daq, (uint16_t)1U));
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_alloc_odt(&g_daq, (uint16_t)0U, (uint8_t)1U));
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_alloc_odt_entry(&g_daq,
        (uint16_t)0U, (uint8_t)0U, (uint8_t)2U));
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_set_ptr(&g_daq, (uint16_t)0U, (uint8_t)0U, (uint8_t)0U));
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_write_entry(&g_daq, TETHYS_DAQ_BIT_OFFSET_NONE,
        (uint8_t)4U, (uint8_t)0U, (uint32_t)0x100U));
    TEST_ASSERT_EQUAL_UINT8(1U, g_daq.lists[0].odts[0].entries[0].in_use);
    TEST_ASSERT_EQUAL_UINT32(0x100U, g_daq.lists[0].odts[0].entries[0].address);
    TEST_ASSERT_EQUAL_UINT8(1U, g_daq.ptr_entry); /* advanced */
}

void test_write_entry_without_set_ptr_fails(void)
{
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_alloc(&g_daq, (uint16_t)1U));
    TEST_ASSERT_EQUAL_INT(-1, tethys_daq_write_entry(&g_daq, TETHYS_DAQ_BIT_OFFSET_NONE,
        (uint8_t)4U, (uint8_t)0U, (uint32_t)0U));
}

/* ---- START/STOP ----------------------------------------------------- */

void test_start_stop_list_starts_only_target(void)
{
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_alloc(&g_daq, (uint16_t)2U));
    uint8_t fp = (uint8_t)0xEEU;
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_start_stop_list(&g_daq, (uint16_t)1U,
        TETHYS_DAQ_START_STOP_START, &fp));
    TEST_ASSERT_FALSE(g_daq.lists[0].running);
    TEST_ASSERT_TRUE(g_daq.lists[1].running);
}

void test_synch_starts_only_selected_lists(void)
{
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_alloc(&g_daq, (uint16_t)3U));
    uint8_t fp = (uint8_t)0xEEU;
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_start_stop_list(&g_daq, (uint16_t)0U,
        TETHYS_DAQ_START_STOP_SELECT, &fp));
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_start_stop_list(&g_daq, (uint16_t)2U,
        TETHYS_DAQ_START_STOP_SELECT, &fp));
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_start_stop_synch(&g_daq,
        TETHYS_DAQ_SYNCH_START_SELECTED));
    TEST_ASSERT_TRUE(g_daq.lists[0].running);
    TEST_ASSERT_FALSE(g_daq.lists[1].running);
    TEST_ASSERT_TRUE(g_daq.lists[2].running);
}

void test_synch_stop_all_stops_running_lists(void)
{
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_alloc(&g_daq, (uint16_t)2U));
    uint8_t fp = (uint8_t)0U;
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_start_stop_list(&g_daq, (uint16_t)0U,
        TETHYS_DAQ_START_STOP_START, &fp));
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_start_stop_synch(&g_daq, TETHYS_DAQ_SYNCH_STOP_ALL));
    TEST_ASSERT_FALSE(g_daq.lists[0].running);
}

/* ---- DTO pack -------------------------------------------------------- */

static void configure_one_dto_list(uint8_t mode)
{
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_alloc(&g_daq, (uint16_t)1U));
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_alloc_odt(&g_daq, (uint16_t)0U, (uint8_t)1U));
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_alloc_odt_entry(&g_daq,
        (uint16_t)0U, (uint8_t)0U, (uint8_t)2U));
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_set_ptr(&g_daq, (uint16_t)0U, (uint8_t)0U, (uint8_t)0U));
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_write_entry(&g_daq, TETHYS_DAQ_BIT_OFFSET_NONE,
        (uint8_t)4U, (uint8_t)0U, (uint32_t)0U));
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_write_entry(&g_daq, TETHYS_DAQ_BIT_OFFSET_NONE,
        (uint8_t)2U, (uint8_t)0U, (uint32_t)32U));
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_set_list_mode(&g_daq, (uint16_t)0U,
        mode, (uint16_t)2U, (uint8_t)1U, (uint8_t)0U));
    uint8_t fp = (uint8_t)0U;
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_start_stop_list(&g_daq, (uint16_t)0U,
        TETHYS_DAQ_START_STOP_START, &fp));
}

void test_pack_dto_with_pid_no_timestamp(void)
{
    configure_one_dto_list((uint8_t)0U);
    uint8_t buf[TETHYS_DAQ_MAX_DTO_BYTES];
    size_t  len = (size_t)0U;
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_pack_dto(
        &g_daq, (uint16_t)0U, (uint8_t)0U, buf, sizeof buf, &len));
    TEST_ASSERT_EQUAL_size_t((size_t)7U, len); /* PID + 4 + 2 */
    TEST_ASSERT_EQUAL_UINT8(0U, buf[0]); /* first_pid 0, odt 0 */
    TEST_ASSERT_EQUAL_UINT8(0U, buf[1]); /* memory[0] */
    TEST_ASSERT_EQUAL_UINT8(32U, buf[5]); /* memory[32] */
    TEST_ASSERT_EQUAL_UINT16(1U, g_daq.dto_counter);
}

void test_pack_dto_with_timestamp_prefix(void)
{
    configure_one_dto_list(TETHYS_DAQ_MODE_TIMESTAMP);
    g_daq.timestamp_now_us = (uint32_t)0x11223344U;
    uint8_t buf[TETHYS_DAQ_MAX_DTO_BYTES];
    size_t  len = (size_t)0U;
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_pack_dto(
        &g_daq, (uint16_t)0U, (uint8_t)0U, buf, sizeof buf, &len));
    TEST_ASSERT_EQUAL_size_t((size_t)11U, len); /* PID + 4-byte ts + 4 + 2 */
    TEST_ASSERT_EQUAL_UINT8(0x44U, buf[1]);
    TEST_ASSERT_EQUAL_UINT8(0x33U, buf[2]);
    TEST_ASSERT_EQUAL_UINT8(0x22U, buf[3]);
    TEST_ASSERT_EQUAL_UINT8(0x11U, buf[4]);
}

void test_apply_stim_dto_writes_memory(void)
{
    configure_one_dto_list(TETHYS_DAQ_MODE_DIRECTION_STIM);
    /* Wipe memory + craft a STIM DTO that writes 0x42 across the 4-byte +
     * 2-byte entries. */
    (void)memset(g_memory, 0, sizeof g_memory);
    uint8_t stim[7];
    stim[0] = (uint8_t)0U; /* PID = first_pid 0 + odt 0 */
    for (size_t i = (size_t)1U; i < sizeof stim; ++i) {
        stim[i] = (uint8_t)0x42U;
    }
    TEST_ASSERT_EQUAL_INT(0, tethys_daq_apply_stim_dto(
        &g_daq, (uint16_t)0U, (uint8_t)0U, stim, sizeof stim));
    TEST_ASSERT_EQUAL_UINT8(0x42U, g_memory[0]);
    TEST_ASSERT_EQUAL_UINT8(0x42U, g_memory[3]);
    TEST_ASSERT_EQUAL_UINT8(0x42U, g_memory[32]);
    TEST_ASSERT_EQUAL_UINT8(0x42U, g_memory[33]);
    TEST_ASSERT_EQUAL_UINT8(0x00U, g_memory[34]); /* unchanged */
}

/* ---- Dispatcher routing -------------------------------------------- */

static void dispatch(uint8_t const* req, size_t req_len)
{
    int const rc = tethys_xcp_dispatch(
        &g_state, req, req_len, g_response, sizeof g_response, &g_resp_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
}

void test_dispatch_alloc_daq_responds_res(void)
{
    connect_session();
    uint8_t req[4] = {TETHYS_XCP_CMD_ALLOC_DAQ, 0U, 0x02U, 0x00U};
    dispatch(req, sizeof req);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_RES, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(2U, g_daq.list_count);
}

void test_dispatch_alloc_daq_overflow_responds_memory_overflow(void)
{
    connect_session();
    uint8_t req[4] = {TETHYS_XCP_CMD_ALLOC_DAQ, 0U, 0xFFU, 0x00U};
    dispatch(req, sizeof req);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_ERR, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_ERR_MEMORY_OVERFLOW, g_response[1]);
}

void test_dispatch_set_daq_ptr_responds_res(void)
{
    connect_session();
    uint8_t alloc[4]    = {TETHYS_XCP_CMD_ALLOC_DAQ, 0U, 0x01U, 0x00U};
    uint8_t alloc_odt[5]= {TETHYS_XCP_CMD_ALLOC_ODT, 0U, 0x00U, 0x00U, 0x01U};
    uint8_t alloc_e[6]  = {TETHYS_XCP_CMD_ALLOC_ODT_ENTRY, 0U, 0x00U, 0x00U, 0x00U, 0x02U};
    uint8_t set_ptr[6]  = {TETHYS_XCP_CMD_SET_DAQ_PTR, 0U, 0x00U, 0x00U, 0x00U, 0x00U};
    dispatch(alloc,    sizeof alloc);
    dispatch(alloc_odt,sizeof alloc_odt);
    dispatch(alloc_e,  sizeof alloc_e);
    dispatch(set_ptr,  sizeof set_ptr);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_RES, g_response[0]);
    TEST_ASSERT_TRUE(g_daq.ptr_valid);
}

void test_dispatch_start_stop_returns_first_pid(void)
{
    connect_session();
    uint8_t alloc[4]    = {TETHYS_XCP_CMD_ALLOC_DAQ, 0U, 0x02U, 0x00U};
    uint8_t alloc_odt0[5]={TETHYS_XCP_CMD_ALLOC_ODT, 0U, 0x00U, 0x00U, 0x02U};
    uint8_t alloc_odt1[5]={TETHYS_XCP_CMD_ALLOC_ODT, 0U, 0x01U, 0x00U, 0x03U};
    uint8_t start1[4]    ={TETHYS_XCP_CMD_START_STOP_DAQ_LIST,
                            TETHYS_DAQ_START_STOP_START, 0x01U, 0x00U};
    dispatch(alloc,     sizeof alloc);
    dispatch(alloc_odt0,sizeof alloc_odt0);
    dispatch(alloc_odt1,sizeof alloc_odt1);
    dispatch(start1,    sizeof start1);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_RES, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(2U, g_response[1]); /* first_pid of list 1 = odt_count of list 0 = 2 */
}

void test_dispatch_get_daq_processor_info(void)
{
    connect_session();
    uint8_t req[1] = {TETHYS_XCP_CMD_GET_DAQ_PROCESSOR_INFO};
    dispatch(req, sizeof req);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_RES, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_DAQ_MAX_LISTS, g_response[2]);
}

void test_dispatch_get_daq_resolution_info(void)
{
    connect_session();
    uint8_t req[1] = {TETHYS_XCP_CMD_GET_DAQ_RESOLUTION_INFO};
    dispatch(req, sizeof req);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_RES, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(1U, g_response[1]); /* granularity_odt */
}

void test_dispatch_daq_without_engine_responds_cmd_unknown(void)
{
    /* Detach the engine and try to ALLOC. */
    tethys_xcp_attach_daq(&g_state, NULL);
    connect_session();
    uint8_t req[4] = {TETHYS_XCP_CMD_ALLOC_DAQ, 0U, 0x01U, 0x00U};
    dispatch(req, sizeof req);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_ERR, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_ERR_CMD_UNKNOWN, g_response[1]);
}

void test_write_daq_multiple_one_entry(void)
{
    connect_session();
    uint8_t alloc[4]    = {TETHYS_XCP_CMD_ALLOC_DAQ, 0U, 0x01U, 0x00U};
    uint8_t alloc_odt[5]= {TETHYS_XCP_CMD_ALLOC_ODT, 0U, 0x00U, 0x00U, 0x01U};
    uint8_t alloc_e[6]  = {TETHYS_XCP_CMD_ALLOC_ODT_ENTRY, 0U, 0x00U, 0x00U, 0x00U, 0x01U};
    uint8_t set_ptr[6]  = {TETHYS_XCP_CMD_SET_DAQ_PTR, 0U, 0x00U, 0x00U, 0x00U, 0x00U};
    dispatch(alloc,    sizeof alloc);
    dispatch(alloc_odt,sizeof alloc_odt);
    dispatch(alloc_e,  sizeof alloc_e);
    dispatch(set_ptr,  sizeof set_ptr);
    /* WRITE_DAQ_MULTIPLE: PID + N + 1×8-byte block = 10 bytes total but
     * MAX_CTO is 8 - the slave receives the full 10-byte request via the
     * dispatcher's req_len argument (the transport may chunk on the wire
     * but here we feed the whole CTO). */
    uint8_t multi[10] = {
        TETHYS_XCP_CMD_WRITE_DAQ_MULTIPLE,
        (uint8_t)1U,        /* N */
        TETHYS_DAQ_BIT_OFFSET_NONE,
        (uint8_t)4U,        /* size */
        (uint8_t)0U,        /* ext */
        (uint8_t)0U,        /* reserved */
        (uint8_t)0x42U, (uint8_t)0x00U, (uint8_t)0x00U, (uint8_t)0x00U /* addr LE */
    };
    int const rc = tethys_xcp_dispatch(
        &g_state, multi, sizeof multi, g_response, sizeof g_response, &g_resp_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_RES, g_response[0]);
    TEST_ASSERT_EQUAL_UINT32(0x42U, g_daq.lists[0].odts[0].entries[0].address);
}
