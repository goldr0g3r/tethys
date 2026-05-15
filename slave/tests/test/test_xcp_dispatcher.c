/*
 * test_xcp_dispatcher.c - Unity tests for the XCP command dispatcher.
 *
 * Module: tests::test_xcp_dispatcher
 * Profiles: posix-sim (host-side test build)
 * Standards: ASAM XCP 1.4 Part 2 §1.3.2 + §1.4.2.1
 * Trace: docs/traceability.csv (rows TETHYS-TST-0001..0010 land at PR-10)
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

static tethys_xcp_state_t g_state;
static uint8_t            g_response[TETHYS_XCP_MAX_CTO];
static size_t             g_response_len;

void setUp(void)
{
    tethys_xcp_init(&g_state);
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
