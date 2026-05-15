/*
 * test_xcp_dispatcher.c - Unity tests for the XCP command dispatcher.
 *
 * Module: tests::test_xcp_dispatcher
 * Profiles: posix-sim (host-side test build)
 * Standards: ASAM XCP 1.4 Part 2 §1.3.2 + §1.3.3 + §1.4.2.1
 * Trace: docs/traceability.csv (rows TETHYS-TST-0001..0028 land at PR-10)
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */
#include "tethys/xcp_dispatcher.h"

#include "unity.h"

#include <stddef.h>
#include <stdint.h>
#include <string.h>

/* Ceedling source discovery: explicit because the .c is nested under core/. */
TEST_SOURCE_FILE("xcp_dispatcher.c")

#define TEST_MEMORY_SIZE   ((size_t)256U)

static tethys_xcp_state_t g_state;
static uint8_t            g_response[TETHYS_XCP_MAX_CTO];
static size_t             g_response_len;
static uint8_t            g_memory[TEST_MEMORY_SIZE];

static void seed_ramp_memory(void)
{
    for (size_t i = 0U; i < TEST_MEMORY_SIZE; ++i) {
        g_memory[i] = (uint8_t)(i & 0xFFU);
    }
}

/* CONNECT, leaving the state machine ready for downstream commands. */
static void do_connect(void)
{
    uint8_t connect_req[2] = {TETHYS_XCP_CMD_CONNECT, 0U};
    (void)tethys_xcp_dispatch(
        &g_state, connect_req, sizeof connect_req, g_response, sizeof g_response, &g_response_len);
}

void setUp(void)
{
    tethys_xcp_init(&g_state);
    seed_ramp_memory();
    tethys_xcp_attach_memory(&g_state, g_memory, TEST_MEMORY_SIZE);
    (void)memset(g_response, 0, sizeof g_response);
    g_response_len = (size_t)0U;
}

void tearDown(void)
{
    /* No-op. */
}

/* -------- Initial state ------------------------------------------------ */

void test_init_clears_session(void)
{
    TEST_ASSERT_FALSE(g_state.connected);
    TEST_ASSERT_EQUAL_UINT8(0U, g_state.session_status);
    TEST_ASSERT_EQUAL_UINT8(0U, g_state.resource_protection);
}

void test_init_null_state_does_not_crash(void)
{
    tethys_xcp_init(NULL); /* must not segfault */
    TEST_PASS();
}

/* -------- Argument errors --------------------------------------------- */

void test_dispatch_null_state(void)
{
    uint8_t req = TETHYS_XCP_CMD_CONNECT;
    int rc = tethys_xcp_dispatch(NULL, &req, sizeof req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(-1, rc);
}

void test_dispatch_null_request(void)
{
    int rc = tethys_xcp_dispatch(&g_state, NULL, (size_t)1U, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(-1, rc);
}

void test_dispatch_null_response(void)
{
    uint8_t req = TETHYS_XCP_CMD_CONNECT;
    int rc = tethys_xcp_dispatch(&g_state, &req, sizeof req, NULL, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(-1, rc);
}

void test_dispatch_null_response_len(void)
{
    uint8_t req = TETHYS_XCP_CMD_CONNECT;
    int rc = tethys_xcp_dispatch(&g_state, &req, sizeof req, g_response, sizeof g_response, NULL);
    TEST_ASSERT_EQUAL_INT(-1, rc);
}

void test_dispatch_response_buffer_too_small(void)
{
    uint8_t req = TETHYS_XCP_CMD_CONNECT;
    uint8_t small_buffer[1];
    int rc = tethys_xcp_dispatch(&g_state, &req, sizeof req, small_buffer, sizeof small_buffer, &g_response_len);
    TEST_ASSERT_EQUAL_INT(-1, rc);
}

void test_dispatch_empty_request_returns_syntax_error(void)
{
    int rc = tethys_xcp_dispatch(&g_state, g_response, (size_t)0U, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_ERR, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_ERR_CMD_SYNTAX, g_response[1]);
}

/* -------- CONNECT ----------------------------------------------------- */

void test_dispatch_connect_succeeds(void)
{
    uint8_t req[2] = {TETHYS_XCP_CMD_CONNECT, 0U};
    int rc = tethys_xcp_dispatch(&g_state, req, sizeof req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_size_t((size_t)8U, g_response_len);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_RES, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_MAX_CTO, g_response[3]);
    /* max_dto little-endian */
    TEST_ASSERT_EQUAL_UINT8((uint8_t)(TETHYS_XCP_MAX_DTO & 0xFFU), g_response[4]);
    TEST_ASSERT_EQUAL_UINT8((uint8_t)((TETHYS_XCP_MAX_DTO >> 8U) & 0xFFU), g_response[5]);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PROTO_VERSION, g_response[6]);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_XPRT_VERSION, g_response[7]);
    TEST_ASSERT_TRUE(g_state.connected);
}

/* -------- DISCONNECT -------------------------------------------------- */

void test_dispatch_disconnect_after_connect(void)
{
    uint8_t connect_req[2] = {TETHYS_XCP_CMD_CONNECT, 0U};
    uint8_t disconnect_req = TETHYS_XCP_CMD_DISCONNECT;
    (void)tethys_xcp_dispatch(&g_state, connect_req, sizeof connect_req, g_response, sizeof g_response, &g_response_len);
    int rc = tethys_xcp_dispatch(&g_state, &disconnect_req, sizeof disconnect_req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_size_t((size_t)1U, g_response_len);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_RES, g_response[0]);
    TEST_ASSERT_FALSE(g_state.connected);
}

void test_dispatch_disconnect_without_connect(void)
{
    /* DISCONNECT is always allowed - per XCP 1.4 the master may DISCONNECT
       in any state. The slave just acks. */
    uint8_t req = TETHYS_XCP_CMD_DISCONNECT;
    int rc = tethys_xcp_dispatch(&g_state, &req, sizeof req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_RES, g_response[0]);
    TEST_ASSERT_FALSE(g_state.connected);
}

/* -------- GET_STATUS -------------------------------------------------- */

void test_dispatch_get_status_before_connect_denied(void)
{
    uint8_t req = TETHYS_XCP_CMD_GET_STATUS;
    int rc = tethys_xcp_dispatch(&g_state, &req, sizeof req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_ERR, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_ERR_ACCESS_DENIED, g_response[1]);
}

void test_dispatch_get_status_after_connect(void)
{
    uint8_t connect_req[2] = {TETHYS_XCP_CMD_CONNECT, 0U};
    uint8_t status_req = TETHYS_XCP_CMD_GET_STATUS;
    (void)tethys_xcp_dispatch(&g_state, connect_req, sizeof connect_req, g_response, sizeof g_response, &g_response_len);
    int rc = tethys_xcp_dispatch(&g_state, &status_req, sizeof status_req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_size_t((size_t)6U, g_response_len);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_RES, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(0x80U, g_response[1]); /* session_status bit7 set */
}

/* -------- GET_VERSION ------------------------------------------------- */

void test_dispatch_get_version_before_connect_denied(void)
{
    uint8_t req = TETHYS_XCP_CMD_GET_VERSION;
    int rc = tethys_xcp_dispatch(&g_state, &req, sizeof req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_ERR, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_ERR_ACCESS_DENIED, g_response[1]);
}

void test_dispatch_get_version_after_connect(void)
{
    uint8_t connect_req[2] = {TETHYS_XCP_CMD_CONNECT, 0U};
    uint8_t version_req = TETHYS_XCP_CMD_GET_VERSION;
    (void)tethys_xcp_dispatch(&g_state, connect_req, sizeof connect_req, g_response, sizeof g_response, &g_response_len);
    int rc = tethys_xcp_dispatch(&g_state, &version_req, sizeof version_req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_size_t((size_t)6U, g_response_len);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_RES, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(1U, g_response[2]); /* protocol major */
    TEST_ASSERT_EQUAL_UINT8(4U, g_response[3]); /* protocol minor */
    TEST_ASSERT_EQUAL_UINT8(1U, g_response[4]); /* transport major */
    TEST_ASSERT_EQUAL_UINT8(4U, g_response[5]); /* transport minor */
}

/* -------- Unknown command -------------------------------------------- */

void test_dispatch_unknown_command_returns_cmd_unknown(void)
{
    uint8_t req = (uint8_t)0x42U; /* arbitrary; not in our subset */
    int rc = tethys_xcp_dispatch(&g_state, &req, sizeof req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_ERR, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_ERR_CMD_UNKNOWN, g_response[1]);
}

/* ---- Phase 2: SET_MTA / UPLOAD / SHORT_UPLOAD tests ------------------ */

void test_init_clears_phase2_state(void)
{
    tethys_xcp_state_t fresh;
    tethys_xcp_init(&fresh);
    TEST_ASSERT_EQUAL_UINT32(0U, fresh.mta_address);
    TEST_ASSERT_EQUAL_UINT8(0U, fresh.mta_extension);
    TEST_ASSERT_NULL(fresh.memory);
    TEST_ASSERT_EQUAL_size_t(0U, fresh.memory_size);
}

void test_attach_memory_sets_pointer_and_size(void)
{
    tethys_xcp_state_t fresh;
    tethys_xcp_init(&fresh);
    tethys_xcp_attach_memory(&fresh, g_memory, TEST_MEMORY_SIZE);
    TEST_ASSERT_EQUAL_PTR(g_memory, fresh.memory);
    TEST_ASSERT_EQUAL_size_t(TEST_MEMORY_SIZE, fresh.memory_size);
}

void test_attach_memory_null_buffer_detaches(void)
{
    tethys_xcp_attach_memory(&g_state, NULL, 1234U);
    TEST_ASSERT_NULL(g_state.memory);
    TEST_ASSERT_EQUAL_size_t(0U, g_state.memory_size);
}

void test_attach_memory_null_state_does_not_crash(void)
{
    tethys_xcp_attach_memory(NULL, g_memory, TEST_MEMORY_SIZE);
    TEST_PASS();
}

/* -------- SET_MTA ----------------------------------------------------- */

void test_set_mta_before_connect_denied(void)
{
    uint8_t req[8] = {TETHYS_XCP_CMD_SET_MTA, 0U, 0U, 0U, 0x10U, 0x00U, 0x00U, 0x00U};
    int rc = tethys_xcp_dispatch(&g_state, req, sizeof req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_ERR, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_ERR_ACCESS_DENIED, g_response[1]);
}

void test_set_mta_truncated_request_returns_syntax_error(void)
{
    do_connect();
    uint8_t req[4] = {TETHYS_XCP_CMD_SET_MTA, 0U, 0U, 0U};
    int rc = tethys_xcp_dispatch(&g_state, req, sizeof req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_ERR, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_ERR_CMD_SYNTAX, g_response[1]);
}

void test_set_mta_records_address_and_extension(void)
{
    do_connect();
    uint8_t req[8] = {
        TETHYS_XCP_CMD_SET_MTA, 0U, 0U,
        0xABU,                                          /* address_extension */
        0x78U, 0x56U, 0x34U, 0x12U                      /* address = 0x12345678 LE */
    };
    int rc = tethys_xcp_dispatch(&g_state, req, sizeof req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_size_t(1U, g_response_len);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_RES, g_response[0]);
    TEST_ASSERT_EQUAL_UINT32(0x12345678U, g_state.mta_address);
    TEST_ASSERT_EQUAL_UINT8(0xABU, g_state.mta_extension);
}

/* -------- UPLOAD ------------------------------------------------------ */

void test_upload_before_connect_denied(void)
{
    uint8_t req[2] = {TETHYS_XCP_CMD_UPLOAD, 4U};
    int rc = tethys_xcp_dispatch(&g_state, req, sizeof req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_ERR, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_ERR_ACCESS_DENIED, g_response[1]);
}

void test_upload_with_no_memory_attached_denied(void)
{
    do_connect();
    tethys_xcp_attach_memory(&g_state, NULL, 0U);
    uint8_t req[2] = {TETHYS_XCP_CMD_UPLOAD, 4U};
    int rc = tethys_xcp_dispatch(&g_state, req, sizeof req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_ERR, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_ERR_ACCESS_DENIED, g_response[1]);
}

void test_upload_truncated_request_returns_syntax_error(void)
{
    do_connect();
    uint8_t req[1] = {TETHYS_XCP_CMD_UPLOAD};
    int rc = tethys_xcp_dispatch(&g_state, req, sizeof req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_ERR, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_ERR_CMD_SYNTAX, g_response[1]);
}

void test_upload_zero_bytes_returns_out_of_range(void)
{
    do_connect();
    uint8_t req[2] = {TETHYS_XCP_CMD_UPLOAD, 0U};
    int rc = tethys_xcp_dispatch(&g_state, req, sizeof req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_ERR, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_ERR_OUT_OF_RANGE, g_response[1]);
}

void test_upload_too_many_bytes_returns_out_of_range(void)
{
    do_connect();
    /* MAX_CTO = 8, so the body limit is 7 bytes per UPLOAD. */
    uint8_t req[2] = {TETHYS_XCP_CMD_UPLOAD, (uint8_t)(TETHYS_XCP_MAX_CTO)};
    int rc = tethys_xcp_dispatch(&g_state, req, sizeof req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_ERR, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_ERR_OUT_OF_RANGE, g_response[1]);
}

void test_upload_outside_attached_memory_returns_out_of_range(void)
{
    do_connect();
    g_state.mta_address = (uint32_t)(TEST_MEMORY_SIZE - 2U);
    uint8_t req[2] = {TETHYS_XCP_CMD_UPLOAD, 4U}; /* would read past the end */
    int rc = tethys_xcp_dispatch(&g_state, req, sizeof req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_ERR, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_ERR_OUT_OF_RANGE, g_response[1]);
}

void test_upload_succeeds_and_auto_increments_mta(void)
{
    do_connect();
    g_state.mta_address = 0x10U;
    uint8_t req[2] = {TETHYS_XCP_CMD_UPLOAD, 4U};
    int rc = tethys_xcp_dispatch(&g_state, req, sizeof req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_size_t(5U, g_response_len); /* PID + 4 bytes */
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_RES, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(0x10U, g_response[1]); /* ramp pattern at offset 0x10 */
    TEST_ASSERT_EQUAL_UINT8(0x11U, g_response[2]);
    TEST_ASSERT_EQUAL_UINT8(0x12U, g_response[3]);
    TEST_ASSERT_EQUAL_UINT8(0x13U, g_response[4]);
    TEST_ASSERT_EQUAL_UINT32(0x14U, g_state.mta_address); /* auto-incremented by 4 */
}

/* -------- SHORT_UPLOAD ------------------------------------------------ */

void test_short_upload_before_connect_denied(void)
{
    uint8_t req[8] = {TETHYS_XCP_CMD_SHORT_UPLOAD, 4U, 0U, 0U, 0x10U, 0U, 0U, 0U};
    int rc = tethys_xcp_dispatch(&g_state, req, sizeof req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_ERR, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_ERR_ACCESS_DENIED, g_response[1]);
}

void test_short_upload_with_no_memory_attached_denied(void)
{
    do_connect();
    tethys_xcp_attach_memory(&g_state, NULL, 0U);
    uint8_t req[8] = {TETHYS_XCP_CMD_SHORT_UPLOAD, 4U, 0U, 0U, 0x10U, 0U, 0U, 0U};
    int rc = tethys_xcp_dispatch(&g_state, req, sizeof req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_ERR, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_ERR_ACCESS_DENIED, g_response[1]);
}

void test_short_upload_truncated_request_returns_syntax_error(void)
{
    do_connect();
    uint8_t req[3] = {TETHYS_XCP_CMD_SHORT_UPLOAD, 4U, 0U};
    int rc = tethys_xcp_dispatch(&g_state, req, sizeof req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_ERR, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_ERR_CMD_SYNTAX, g_response[1]);
}

void test_short_upload_outside_attached_memory_returns_out_of_range(void)
{
    do_connect();
    uint8_t req[8] = {
        TETHYS_XCP_CMD_SHORT_UPLOAD, 4U, 0U, 0U,
        0xFEU, 0x00U, 0x00U, 0x00U /* address 0xFE, want 4 bytes past 256-byte buffer */
    };
    int rc = tethys_xcp_dispatch(&g_state, req, sizeof req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_ERR, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_ERR_OUT_OF_RANGE, g_response[1]);
}

void test_short_upload_succeeds_and_leaves_mta_unchanged(void)
{
    do_connect();
    g_state.mta_address = 0x55U; /* deliberate; should NOT be modified */
    uint8_t req[8] = {
        TETHYS_XCP_CMD_SHORT_UPLOAD, 3U, 0U, 0U,
        0x20U, 0x00U, 0x00U, 0x00U /* address = 0x20 */
    };
    int rc = tethys_xcp_dispatch(&g_state, req, sizeof req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_size_t(4U, g_response_len); /* PID + 3 bytes */
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_RES, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(0x20U, g_response[1]);
    TEST_ASSERT_EQUAL_UINT8(0x21U, g_response[2]);
    TEST_ASSERT_EQUAL_UINT8(0x22U, g_response[3]);
    TEST_ASSERT_EQUAL_UINT32(0x55U, g_state.mta_address); /* unchanged */
}

/* -------- DOWNLOAD ---------------------------------------------------- */

void test_download_before_connect_denied(void)
{
    uint8_t req[3] = {TETHYS_XCP_CMD_DOWNLOAD, 1U, 0xAAU};
    int rc = tethys_xcp_dispatch(&g_state, req, sizeof req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_ERR, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_ERR_ACCESS_DENIED, g_response[1]);
}

void test_download_with_no_memory_attached_denied(void)
{
    do_connect();
    tethys_xcp_attach_memory(&g_state, NULL, 0U);
    uint8_t req[3] = {TETHYS_XCP_CMD_DOWNLOAD, 1U, 0xAAU};
    int rc = tethys_xcp_dispatch(&g_state, req, sizeof req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_ERR, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_ERR_ACCESS_DENIED, g_response[1]);
}

void test_download_truncated_header_returns_syntax(void)
{
    do_connect();
    uint8_t req[1] = {TETHYS_XCP_CMD_DOWNLOAD};
    int rc = tethys_xcp_dispatch(&g_state, req, sizeof req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_ERR, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_ERR_CMD_SYNTAX, g_response[1]);
}

void test_download_missing_payload_returns_syntax(void)
{
    do_connect();
    /* Declares 4 bytes but only ships 2 actual payload bytes (req_len = 2+2 = 4 < 2+4 = 6). */
    uint8_t req[4] = {TETHYS_XCP_CMD_DOWNLOAD, 4U, 0xAAU, 0xBBU};
    int rc = tethys_xcp_dispatch(&g_state, req, sizeof req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_ERR, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_ERR_CMD_SYNTAX, g_response[1]);
}

void test_download_zero_bytes_returns_out_of_range(void)
{
    do_connect();
    uint8_t req[2] = {TETHYS_XCP_CMD_DOWNLOAD, 0U};
    int rc = tethys_xcp_dispatch(&g_state, req, sizeof req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_ERR, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_ERR_OUT_OF_RANGE, g_response[1]);
}

void test_download_too_many_bytes_returns_out_of_range(void)
{
    do_connect();
    /* MAX_CTO=8, so max payload = MAX_CTO-2 = 6. Requesting 7 is out of range. */
    uint8_t req[9] = {TETHYS_XCP_CMD_DOWNLOAD, 7U, 0x01U, 0x02U, 0x03U, 0x04U, 0x05U, 0x06U, 0x07U};
    int rc = tethys_xcp_dispatch(&g_state, req, sizeof req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_ERR, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_ERR_OUT_OF_RANGE, g_response[1]);
}

void test_download_outside_attached_memory_returns_out_of_range(void)
{
    do_connect();
    g_state.mta_address = (uint32_t)(TEST_MEMORY_SIZE - 2U);
    uint8_t req[6] = {TETHYS_XCP_CMD_DOWNLOAD, 4U, 0xAAU, 0xBBU, 0xCCU, 0xDDU};
    int rc = tethys_xcp_dispatch(&g_state, req, sizeof req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_ERR, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_ERR_OUT_OF_RANGE, g_response[1]);
}

void test_download_succeeds_and_increments_mta(void)
{
    do_connect();
    g_state.mta_address = 0x40U;
    uint8_t req[6] = {TETHYS_XCP_CMD_DOWNLOAD, 4U, 0xDEU, 0xADU, 0xBEU, 0xEFU};
    int rc = tethys_xcp_dispatch(&g_state, req, sizeof req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_size_t(1U, g_response_len);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_RES, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(0xDEU, g_memory[0x40U]);
    TEST_ASSERT_EQUAL_UINT8(0xADU, g_memory[0x41U]);
    TEST_ASSERT_EQUAL_UINT8(0xBEU, g_memory[0x42U]);
    TEST_ASSERT_EQUAL_UINT8(0xEFU, g_memory[0x43U]);
    TEST_ASSERT_EQUAL_UINT32(0x44U, g_state.mta_address);
}

/* -------- BUILD_CHECKSUM --------------------------------------------- */

void test_build_checksum_before_connect_denied(void)
{
    uint8_t req[8] = {TETHYS_XCP_CMD_BUILD_CHECKSUM, 0U, 0U, 0U, 0x10U, 0U, 0U, 0U};
    int rc = tethys_xcp_dispatch(&g_state, req, sizeof req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_ERR, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_ERR_ACCESS_DENIED, g_response[1]);
}

void test_build_checksum_zero_block_returns_out_of_range(void)
{
    do_connect();
    uint8_t req[8] = {TETHYS_XCP_CMD_BUILD_CHECKSUM, 0U, 0U, 0U, 0U, 0U, 0U, 0U};
    int rc = tethys_xcp_dispatch(&g_state, req, sizeof req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_ERR, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_ERR_OUT_OF_RANGE, g_response[1]);
}

void test_build_checksum_outside_memory_returns_out_of_range(void)
{
    do_connect();
    g_state.mta_address = (uint32_t)(TEST_MEMORY_SIZE - 4U);
    uint8_t req[8] = {TETHYS_XCP_CMD_BUILD_CHECKSUM, 0U, 0U, 0U,
                      0x10U, 0x00U, 0x00U, 0x00U}; /* 16 bytes, past the end */
    int rc = tethys_xcp_dispatch(&g_state, req, sizeof req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_ERR, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_ERR_OUT_OF_RANGE, g_response[1]);
}

void test_build_checksum_truncated_request_returns_syntax(void)
{
    do_connect();
    uint8_t req[5] = {TETHYS_XCP_CMD_BUILD_CHECKSUM, 0U, 0U, 0U, 0x10U};
    int rc = tethys_xcp_dispatch(&g_state, req, sizeof req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_ERR, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_ERR_CMD_SYNTAX, g_response[1]);
}

void test_build_checksum_succeeds_and_advances_mta(void)
{
    do_connect();
    g_state.mta_address = 0x10U;
    /* Sum of ramp bytes at offsets 0x10..0x13 = 0x10+0x11+0x12+0x13 = 0x46. */
    uint8_t req[8] = {TETHYS_XCP_CMD_BUILD_CHECKSUM, 0U, 0U, 0U,
                      0x04U, 0x00U, 0x00U, 0x00U}; /* block_size = 4 */
    int rc = tethys_xcp_dispatch(&g_state, req, sizeof req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_size_t(8U, g_response_len);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_RES, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_CHECKSUM_ADD_44, g_response[1]);
    /* Little-endian u32 of 0x46. */
    TEST_ASSERT_EQUAL_UINT8(0x46U, g_response[4]);
    TEST_ASSERT_EQUAL_UINT8(0x00U, g_response[5]);
    TEST_ASSERT_EQUAL_UINT8(0x00U, g_response[6]);
    TEST_ASSERT_EQUAL_UINT8(0x00U, g_response[7]);
    TEST_ASSERT_EQUAL_UINT32(0x14U, g_state.mta_address);
}

/* -------- SYNCH ------------------------------------------------------- */

void test_synch_returns_err_cmd_synch_even_before_connect(void)
{
    /* SYNCH is allowed in any state - it is the state-machine reset signal. */
    uint8_t req = TETHYS_XCP_CMD_SYNCH;
    int rc = tethys_xcp_dispatch(&g_state, &req, sizeof req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_size_t(2U, g_response_len);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_ERR, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_ERR_CMD_SYNCH, g_response[1]);
}

void test_synch_after_connect_still_returns_err_cmd_synch(void)
{
    do_connect();
    uint8_t req = TETHYS_XCP_CMD_SYNCH;
    int rc = tethys_xcp_dispatch(&g_state, &req, sizeof req, g_response, sizeof g_response, &g_response_len);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_PID_ERR, g_response[0]);
    TEST_ASSERT_EQUAL_UINT8(TETHYS_XCP_ERR_CMD_SYNCH, g_response[1]);
    /* Session stays connected; SYNCH does not implicitly disconnect. */
    TEST_ASSERT_TRUE(g_state.connected);
}
