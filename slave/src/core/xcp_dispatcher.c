/*
 * src/core/xcp_dispatcher.c - XCP command dispatcher (Phase 1 subset).
 *
 * Module: tethys::core::xcp_dispatcher
 * Profiles: all
 * Standards: ASAM XCP 1.4 Part 2 §1.3.2 + §1.4.2.1; MISRA C:2023
 * Trace: docs/traceability.csv (rows TETHYS-DES-0001..0004 land at PR-10)
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */
#include "tethys/xcp_dispatcher.h"

#include <stddef.h>
#include <stdint.h>
#include <string.h>

/* ---- Internal helpers ------------------------------------------------- */

/**
 * @brief Write a 1-byte ERR response (PID + error code).
 *
 * @return 2 (number of bytes written) on success, 0 if buffer too small.
 */
static size_t write_error_response(uint8_t* response, size_t resp_cap, uint8_t code)
{
    if (resp_cap < (size_t)2U) {
        return (size_t)0U;
    }
    response[0] = TETHYS_XCP_PID_ERR;
    response[1] = code;
    return (size_t)2U;
}

/**
 * @brief Write a CONNECT positive response body (8 bytes total: PID + 7 body).
 *
 * @return 8 on success, 0 if buffer too small.
 */
static size_t write_connect_response(uint8_t* response, size_t resp_cap)
{
    if (resp_cap < (size_t)8U) {
        return (size_t)0U;
    }
    response[0] = TETHYS_XCP_PID_RES;
    response[1] = (uint8_t)(TETHYS_XCP_RES_DAQ | TETHYS_XCP_RES_CAL_PAG);
    response[2] = TETHYS_XCP_COMM_OPTIONAL;
    response[3] = TETHYS_XCP_MAX_CTO;
    /* max_dto - little-endian uint16 */
    response[4] = (uint8_t)(TETHYS_XCP_MAX_DTO & 0xFFU);
    response[5] = (uint8_t)((TETHYS_XCP_MAX_DTO >> 8U) & 0xFFU);
    response[6] = TETHYS_XCP_PROTO_VERSION;
    response[7] = TETHYS_XCP_XPRT_VERSION;
    return (size_t)8U;
}

/**
 * @brief Write a GET_STATUS positive response body (6 bytes total).
 *
 * @return 6 on success, 0 if buffer too small.
 */
static size_t write_get_status_response(uint8_t* response, size_t resp_cap, tethys_xcp_state_t const* state)
{
    if (resp_cap < (size_t)6U) {
        return (size_t)0U;
    }
    response[0] = TETHYS_XCP_PID_RES;
    response[1] = state->session_status;
    response[2] = state->resource_protection;
    response[3] = state->state_number;
    response[4] = (uint8_t)(state->session_configuration_id & 0xFFU);
    response[5] = (uint8_t)((state->session_configuration_id >> 8U) & 0xFFU);
    return (size_t)6U;
}

/**
 * @brief Write a GET_VERSION positive response body (6 bytes total).
 *
 * @return 6 on success, 0 if buffer too small.
 */
static size_t write_get_version_response(uint8_t* response, size_t resp_cap)
{
    if (resp_cap < (size_t)6U) {
        return (size_t)0U;
    }
    response[0] = TETHYS_XCP_PID_RES;
    response[1] = (uint8_t)0U; /* reserved */
    response[2] = (uint8_t)1U; /* protocol major */
    response[3] = (uint8_t)4U; /* protocol minor */
    response[4] = (uint8_t)1U; /* transport major */
    response[5] = (uint8_t)4U; /* transport minor */
    return (size_t)6U;
}

/**
 * @brief Write a DISCONNECT positive response (PID only).
 *
 * @return 1 on success, 0 if buffer too small.
 */
static size_t write_disconnect_response(uint8_t* response, size_t resp_cap)
{
    if (resp_cap < (size_t)1U) {
        return (size_t)0U;
    }
    response[0] = TETHYS_XCP_PID_RES;
    return (size_t)1U;
}

/* ---- Public API ------------------------------------------------------- */

void tethys_xcp_init(tethys_xcp_state_t* state)
{
    if (state == NULL) {
        return;
    }
    state->connected = false;
    state->session_status = (uint8_t)0U;
    state->resource_protection = (uint8_t)0U;
    state->state_number = (uint8_t)0U;
    state->session_configuration_id = (uint16_t)0xABCDU; /* arbitrary; A2L XCP_ID picks the real one */
}

int tethys_xcp_dispatch(
    tethys_xcp_state_t* state,
    uint8_t const*      request,
    size_t              req_len,
    uint8_t*            response,
    size_t              resp_cap,
    size_t*             resp_len)
{
    if ((state == NULL) || (request == NULL) || (response == NULL) || (resp_len == NULL)) {
        return -1;
    }
    if (resp_cap < (size_t)TETHYS_XCP_MAX_CTO) {
        return -1;
    }
    if (req_len == (size_t)0U) {
        *resp_len = write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_SYNTAX);
        return 0;
    }

    uint8_t const cmd = request[0];
    size_t written = (size_t)0U;

    if (cmd == TETHYS_XCP_CMD_CONNECT) {
        state->connected = true;
        state->session_status = (uint8_t)0x80U; /* SESSION_CONFIG_VALID */
        written = write_connect_response(response, resp_cap);
    }
    else if (cmd == TETHYS_XCP_CMD_DISCONNECT) {
        state->connected = false;
        state->session_status = (uint8_t)0U;
        written = write_disconnect_response(response, resp_cap);
    }
    else if (cmd == TETHYS_XCP_CMD_GET_STATUS) {
        if (!state->connected) {
            written = write_error_response(response, resp_cap, TETHYS_XCP_ERR_ACCESS_DENIED);
        }
        else {
            written = write_get_status_response(response, resp_cap, state);
        }
    }
    else if (cmd == TETHYS_XCP_CMD_GET_VERSION) {
        if (!state->connected) {
            written = write_error_response(response, resp_cap, TETHYS_XCP_ERR_ACCESS_DENIED);
        }
        else {
            written = write_get_version_response(response, resp_cap);
        }
    }
    else {
        written = write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_UNKNOWN);
    }

    if (written == (size_t)0U) {
        return -1;
    }
    *resp_len = written;
    /* Suppress unused-warning when -Wunused-parameter is on but we don't need req_len after cmd byte */
    (void)req_len;
    return 0;
}
