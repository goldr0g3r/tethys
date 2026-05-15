/*
 * src/core/xcp_dispatcher.c - XCP command dispatcher (Phase 1 + Phase 2).
 *
 * Module: tethys::core::xcp_dispatcher
 * Profiles: all
 * Standards: ASAM XCP 1.4 Part 2 §1.3.1..§1.3.4 + §1.4.2.1 + §1.5; MISRA C:2023
 * Trace: docs/traceability.csv (rows TETHYS-DES-0001..0010 land at PR-10)
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */
#include "tethys/xcp_dispatcher.h"

#include "tethys/xcp_daq.h"

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

/**
 * @brief Decode a little-endian u32 from 4 wire bytes.
 *
 * MISRA-friendly byte-by-byte read; no aliased load.
 */
static uint32_t decode_u32_le(uint8_t const* p)
{
    return ((uint32_t)p[0])
         | ((uint32_t)p[1] << 8U)
         | ((uint32_t)p[2] << 16U)
         | ((uint32_t)p[3] << 24U);
}

/**
 * @brief Decode a little-endian u16 from 2 wire bytes.
 */
static uint16_t decode_u16_le(uint8_t const* p)
{
    return (uint16_t)((uint16_t)p[0] | ((uint16_t)p[1] << 8U));
}

/**
 * @brief Check whether the requested span lies within attached memory.
 *
 * Defensive against u32 overflow (address + len wrap).
 */
static bool memory_span_ok(tethys_xcp_state_t const* state, uint32_t address, size_t len)
{
    if (state->memory == NULL) {
        return false;
    }
    if (len == (size_t)0U) {
        return true;
    }
    if (address > (uint32_t)0xFFFFFFFFU - (uint32_t)len) {
        return false;
    }
    uint64_t const end = (uint64_t)address + (uint64_t)len;
    return end <= (uint64_t)state->memory_size;
}

/**
 * @brief Write the body of an UPLOAD or SHORT_UPLOAD response.
 *
 * Layout: [0] PID=RES, [1..N] N bytes copied from memory[start .. start+N).
 *
 * @return 1 + n_bytes on success; 0 if response buffer is too small.
 */
static size_t write_upload_response(
    uint8_t*       response,
    size_t         resp_cap,
    uint8_t const* memory,
    uint32_t       start,
    uint8_t        n_bytes)
{
    size_t const required = (size_t)1U + (size_t)n_bytes;
    if (resp_cap < required) {
        return (size_t)0U;
    }
    response[0] = TETHYS_XCP_PID_RES;
    /* MISRA-compliant bounded copy: n_bytes is u8 so the loop is bounded by 0..255. */
    for (uint8_t i = (uint8_t)0U; i < n_bytes; ++i) {
        response[(size_t)1U + (size_t)i] = memory[(size_t)start + (size_t)i];
    }
    return required;
}

/* ---- Phase 2 read-path handlers --------------------------------------- */

/**
 * @brief Handle SET_MTA (0xF6).
 *
 * Wire layout (XCP 1.4 Part 2 §1.3.3.1):
 *   [0]    PID = 0xF6
 *   [1..2] reserved
 *   [3]    address_extension
 *   [4..7] address (4 bytes, little-endian)
 *
 * @return number of bytes written to @p response.
 */
static size_t handle_set_mta(
    tethys_xcp_state_t* state,
    uint8_t const*      request,
    size_t              req_len,
    uint8_t*            response,
    size_t              resp_cap)
{
    if (!state->connected) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_ACCESS_DENIED);
    }
    if (req_len < (size_t)8U) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_SYNTAX);
    }
    state->mta_extension = request[3];
    state->mta_address   = decode_u32_le(&request[4]);
    if (resp_cap < (size_t)1U) {
        return (size_t)0U;
    }
    response[0] = TETHYS_XCP_PID_RES;
    return (size_t)1U;
}

/**
 * @brief Handle UPLOAD (0xF5).
 *
 * Wire layout (XCP 1.4 Part 2 §1.3.3.2):
 *   [0] PID = 0xF5
 *   [1] N (1..MAX_CTO-1 = 1..7)
 *
 * Side-effect: MTA auto-increments by N on success.
 *
 * @return number of bytes written to @p response.
 */
static size_t handle_upload(
    tethys_xcp_state_t* state,
    uint8_t const*      request,
    size_t              req_len,
    uint8_t*            response,
    size_t              resp_cap)
{
    if (!state->connected) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_ACCESS_DENIED);
    }
    if (state->memory == NULL) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_ACCESS_DENIED);
    }
    if (req_len < (size_t)2U) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_SYNTAX);
    }
    uint8_t const n_bytes = request[1];
    if ((n_bytes == (uint8_t)0U) || (n_bytes > (uint8_t)(TETHYS_XCP_MAX_CTO - 1U))) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_OUT_OF_RANGE);
    }
    if (!memory_span_ok(state, state->mta_address, (size_t)n_bytes)) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_OUT_OF_RANGE);
    }
    size_t const written = write_upload_response(
        response, resp_cap, state->memory, state->mta_address, n_bytes);
    if (written == (size_t)0U) {
        return (size_t)0U;
    }
    state->mta_address += (uint32_t)n_bytes;
    return written;
}

/**
 * @brief Handle SHORT_UPLOAD (0xF4).
 *
 * Wire layout (XCP 1.4 Part 2 §1.3.3.6):
 *   [0]    PID = 0xF4
 *   [1]    N (1..MAX_CTO-1)
 *   [2]    reserved
 *   [3]    address_extension
 *   [4..7] address (4 bytes, little-endian)
 *
 * Side-effect: MTA is NOT updated (stateless per spec).
 *
 * @return number of bytes written to @p response.
 */
static size_t handle_short_upload(
    tethys_xcp_state_t* state,
    uint8_t const*      request,
    size_t              req_len,
    uint8_t*            response,
    size_t              resp_cap)
{
    if (!state->connected) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_ACCESS_DENIED);
    }
    if (state->memory == NULL) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_ACCESS_DENIED);
    }
    if (req_len < (size_t)8U) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_SYNTAX);
    }
    uint8_t const n_bytes = request[1];
    if ((n_bytes == (uint8_t)0U) || (n_bytes > (uint8_t)(TETHYS_XCP_MAX_CTO - 1U))) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_OUT_OF_RANGE);
    }
    uint32_t const address = decode_u32_le(&request[4]);
    if (!memory_span_ok(state, address, (size_t)n_bytes)) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_OUT_OF_RANGE);
    }
    return write_upload_response(response, resp_cap, state->memory, address, n_bytes);
}

/* ---- Phase 2 write/checksum/sync handlers ---------------------------- */

/**
 * @brief Handle DOWNLOAD (0xF0).
 *
 * Wire layout (XCP 1.4 Part 2 §1.3.4.1):
 *   [0]      PID = 0xF0
 *   [1]      N (1..MAX_CTO-2 = 1..6)
 *   [2..1+N] data bytes to write at MTA
 *
 * Side-effect: MTA auto-increments by N on success.
 *
 * @return number of bytes written to @p response (always 1: PID-only RES).
 */
static size_t handle_download(
    tethys_xcp_state_t* state,
    uint8_t const*      request,
    size_t              req_len,
    uint8_t*            response,
    size_t              resp_cap)
{
    if (!state->connected) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_ACCESS_DENIED);
    }
    if (state->memory == NULL) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_ACCESS_DENIED);
    }
    if (req_len < (size_t)2U) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_SYNTAX);
    }
    uint8_t const n_bytes = request[1];
    /* DOWNLOAD payload starts at byte 2; max payload = MAX_CTO - 2. */
    if ((n_bytes == (uint8_t)0U) || (n_bytes > (uint8_t)(TETHYS_XCP_MAX_CTO - 2U))) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_OUT_OF_RANGE);
    }
    if (req_len < ((size_t)2U + (size_t)n_bytes)) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_SYNTAX);
    }
    if (!memory_span_ok(state, state->mta_address, (size_t)n_bytes)) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_OUT_OF_RANGE);
    }
    /* MISRA-compliant bounded copy. */
    for (uint8_t i = (uint8_t)0U; i < n_bytes; ++i) {
        state->memory[(size_t)state->mta_address + (size_t)i] = request[(size_t)2U + (size_t)i];
    }
    state->mta_address += (uint32_t)n_bytes;
    if (resp_cap < (size_t)1U) {
        return (size_t)0U;
    }
    response[0] = TETHYS_XCP_PID_RES;
    return (size_t)1U;
}

/**
 * @brief Compute the XCP_ADD_44 sum of @p len bytes starting at @p memory + @p start.
 *
 * Wraps modulo 2^32 (defined behaviour for uint32_t arithmetic).
 */
static uint32_t add_44_checksum(uint8_t const* memory, uint32_t start, uint32_t len)
{
    uint32_t sum = (uint32_t)0U;
    for (uint32_t i = (uint32_t)0U; i < len; ++i) {
        sum += (uint32_t)memory[(size_t)start + (size_t)i];
    }
    return sum;
}

/**
 * @brief Handle BUILD_CHECKSUM (0xF3).
 *
 * Wire layout (XCP 1.4 Part 2 §1.5.1):
 *   [0]    PID = 0xF3
 *   [1..3] reserved (zero)
 *   [4..7] block_size (4 bytes, little-endian)
 *
 * Response wire layout (8 bytes total):
 *   [0]    PID = 0xFF
 *   [1]    checksum_type (XCP_ADD_44 = 0x06)
 *   [2..3] reserved (zero)
 *   [4..7] checksum (4 bytes, little-endian)
 *
 * Side-effect: MTA auto-increments by block_size on success.
 *
 * Implementation note: Tethys currently advertises only the XCP_ADD_44
 * algorithm (simple running 32-bit sum). CRC-32 variants will be added
 * in the space-profile work at Phase 8 - see research note D17.
 *
 * @return number of bytes written to @p response.
 */
static size_t handle_build_checksum(
    tethys_xcp_state_t* state,
    uint8_t const*      request,
    size_t              req_len,
    uint8_t*            response,
    size_t              resp_cap)
{
    if (!state->connected) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_ACCESS_DENIED);
    }
    if (state->memory == NULL) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_ACCESS_DENIED);
    }
    if (req_len < (size_t)8U) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_SYNTAX);
    }
    uint32_t const block_size = decode_u32_le(&request[4]);
    if (block_size == (uint32_t)0U) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_OUT_OF_RANGE);
    }
    if (!memory_span_ok(state, state->mta_address, (size_t)block_size)) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_OUT_OF_RANGE);
    }
    if (resp_cap < (size_t)8U) {
        return (size_t)0U;
    }
    uint32_t const checksum = add_44_checksum(state->memory, state->mta_address, block_size);
    response[0] = TETHYS_XCP_PID_RES;
    response[1] = TETHYS_XCP_CHECKSUM_ADD_44;
    response[2] = (uint8_t)0U; /* reserved */
    response[3] = (uint8_t)0U; /* reserved */
    response[4] = (uint8_t)(checksum & 0xFFU);
    response[5] = (uint8_t)((checksum >> 8U) & 0xFFU);
    response[6] = (uint8_t)((checksum >> 16U) & 0xFFU);
    response[7] = (uint8_t)((checksum >> 24U) & 0xFFU);
    state->mta_address += block_size;
    return (size_t)8U;
}

/**
 * @brief Handle SYNCH (0xFC).
 *
 * Wire layout (XCP 1.4 Part 2 §1.3.1.2):
 *   [0] PID = 0xFC
 *
 * Per spec the slave ALWAYS responds with ERR_CMD_SYNCH (0x00) to mark the
 * end of any pending command sequence. This is NOT an error condition; it
 * is the documented contract for protocol state-machine resync.
 *
 * @return 2 (ERR PID + error code).
 */
static size_t handle_synch(uint8_t* response, size_t resp_cap)
{
    return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_SYNCH);
}

/* ---- Phase 3 DAQ handlers -------------------------------------------- */

static size_t write_res_only(uint8_t* response, size_t resp_cap)
{
    if (resp_cap < (size_t)1U) {
        return (size_t)0U;
    }
    response[0] = TETHYS_XCP_PID_RES;
    return (size_t)1U;
}

static bool daq_ready(tethys_xcp_state_t const* state)
{
    return (state->connected) && (state->daq != NULL);
}

static size_t handle_free_daq(
    tethys_xcp_state_t* state, uint8_t* response, size_t resp_cap)
{
    if (!daq_ready(state)) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_UNKNOWN);
    }
    (void)tethys_daq_free(state->daq);
    return write_res_only(response, resp_cap);
}

static size_t handle_alloc_daq(
    tethys_xcp_state_t* state, uint8_t const* request, size_t req_len,
    uint8_t* response, size_t resp_cap)
{
    if (!daq_ready(state)) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_UNKNOWN);
    }
    if (req_len < (size_t)4U) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_SYNTAX);
    }
    if (tethys_daq_alloc(state->daq, decode_u16_le(&request[2])) != 0) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_MEMORY_OVERFLOW);
    }
    return write_res_only(response, resp_cap);
}

static size_t handle_alloc_odt(
    tethys_xcp_state_t* state, uint8_t const* request, size_t req_len,
    uint8_t* response, size_t resp_cap)
{
    if (!daq_ready(state)) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_UNKNOWN);
    }
    if (req_len < (size_t)5U) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_SYNTAX);
    }
    if (tethys_daq_alloc_odt(state->daq, decode_u16_le(&request[2]), request[4]) != 0) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_MEMORY_OVERFLOW);
    }
    return write_res_only(response, resp_cap);
}

static size_t handle_alloc_odt_entry(
    tethys_xcp_state_t* state, uint8_t const* request, size_t req_len,
    uint8_t* response, size_t resp_cap)
{
    if (!daq_ready(state)) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_UNKNOWN);
    }
    if (req_len < (size_t)6U) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_SYNTAX);
    }
    if (tethys_daq_alloc_odt_entry(
            state->daq, decode_u16_le(&request[2]), request[4], request[5]) != 0) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_MEMORY_OVERFLOW);
    }
    return write_res_only(response, resp_cap);
}

static size_t handle_set_daq_ptr(
    tethys_xcp_state_t* state, uint8_t const* request, size_t req_len,
    uint8_t* response, size_t resp_cap)
{
    if (!daq_ready(state)) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_UNKNOWN);
    }
    if (req_len < (size_t)6U) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_SYNTAX);
    }
    if (tethys_daq_set_ptr(
            state->daq, decode_u16_le(&request[2]), request[4], request[5]) != 0) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_OUT_OF_RANGE);
    }
    return write_res_only(response, resp_cap);
}

static size_t handle_write_daq(
    tethys_xcp_state_t* state, uint8_t const* request, size_t req_len,
    uint8_t* response, size_t resp_cap)
{
    if (!daq_ready(state)) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_UNKNOWN);
    }
    if (req_len < (size_t)8U) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_SYNTAX);
    }
    if (tethys_daq_write_entry(
            state->daq, request[1], request[2], request[3],
            decode_u32_le(&request[4])) != 0) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_DAQ_CONFIG);
    }
    return write_res_only(response, resp_cap);
}

static size_t handle_write_daq_multiple(
    tethys_xcp_state_t* state, uint8_t const* request, size_t req_len,
    uint8_t* response, size_t resp_cap)
{
    if (!daq_ready(state)) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_UNKNOWN);
    }
    if (req_len < (size_t)2U) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_SYNTAX);
    }
    uint8_t const n = request[1];
    if (n == (uint8_t)0U) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_SYNTAX);
    }
    size_t const required = (size_t)2U + (size_t)n * (size_t)8U;
    if (req_len < required) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_SYNTAX);
    }
    for (uint8_t i = (uint8_t)0U; i < n; ++i) {
        size_t const base = (size_t)2U + (size_t)i * (size_t)8U;
        if (tethys_daq_write_entry(
                state->daq, request[base + 0U], request[base + 1U],
                request[base + 2U], decode_u32_le(&request[base + 4U])) != 0) {
            return write_error_response(response, resp_cap, TETHYS_XCP_ERR_DAQ_CONFIG);
        }
    }
    return write_res_only(response, resp_cap);
}

static size_t handle_set_daq_list_mode(
    tethys_xcp_state_t* state, uint8_t const* request, size_t req_len,
    uint8_t* response, size_t resp_cap)
{
    if (!daq_ready(state)) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_UNKNOWN);
    }
    if (req_len < (size_t)8U) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_SYNTAX);
    }
    if (tethys_daq_set_list_mode(
            state->daq, decode_u16_le(&request[2]), request[1],
            decode_u16_le(&request[4]), request[6], request[7]) != 0) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_OUT_OF_RANGE);
    }
    return write_res_only(response, resp_cap);
}

static size_t handle_get_daq_list_mode(
    tethys_xcp_state_t* state, uint8_t const* request, size_t req_len,
    uint8_t* response, size_t resp_cap)
{
    if (!daq_ready(state)) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_UNKNOWN);
    }
    if (req_len < (size_t)4U) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_SYNTAX);
    }
    uint8_t  mode      = (uint8_t)0U;
    uint16_t event_ch  = (uint16_t)0U;
    uint8_t  prescaler = (uint8_t)0U;
    uint8_t  priority  = (uint8_t)0U;
    if (tethys_daq_get_list_mode(
            state->daq, decode_u16_le(&request[2]), &mode, &event_ch,
            &prescaler, &priority) != 0) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_OUT_OF_RANGE);
    }
    if (resp_cap < (size_t)8U) {
        return (size_t)0U;
    }
    response[0] = TETHYS_XCP_PID_RES;
    response[1] = mode;
    response[2] = (uint8_t)0U;
    response[3] = (uint8_t)0U;
    response[4] = (uint8_t)( event_ch        & 0xFFU);
    response[5] = (uint8_t)((event_ch >> 8U) & 0xFFU);
    response[6] = prescaler;
    response[7] = priority;
    return (size_t)8U;
}

static size_t handle_start_stop_daq_list(
    tethys_xcp_state_t* state, uint8_t const* request, size_t req_len,
    uint8_t* response, size_t resp_cap)
{
    if (!daq_ready(state)) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_UNKNOWN);
    }
    if (req_len < (size_t)4U) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_SYNTAX);
    }
    uint8_t first_pid = (uint8_t)0U;
    if (tethys_daq_start_stop_list(
            state->daq, decode_u16_le(&request[2]), request[1], &first_pid) != 0) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_OUT_OF_RANGE);
    }
    if (resp_cap < (size_t)2U) {
        return (size_t)0U;
    }
    response[0] = TETHYS_XCP_PID_RES;
    response[1] = first_pid;
    return (size_t)2U;
}

static size_t handle_start_stop_synch(
    tethys_xcp_state_t* state, uint8_t const* request, size_t req_len,
    uint8_t* response, size_t resp_cap)
{
    if (!daq_ready(state)) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_UNKNOWN);
    }
    if (req_len < (size_t)2U) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_SYNTAX);
    }
    if (tethys_daq_start_stop_synch(state->daq, request[1]) != 0) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_OUT_OF_RANGE);
    }
    return write_res_only(response, resp_cap);
}

static size_t handle_get_daq_processor_info(
    tethys_xcp_state_t* state, uint8_t* response, size_t resp_cap)
{
    if (!daq_ready(state)) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_UNKNOWN);
    }
    if (resp_cap < (size_t)8U) {
        return (size_t)0U;
    }
    response[0] = TETHYS_XCP_PID_RES;
    response[1] = (uint8_t)0x41U;
    response[2] = (uint8_t)TETHYS_DAQ_MAX_LISTS;
    response[3] = (uint8_t)0U;
    response[4] = (uint8_t)0xFFU;
    response[5] = (uint8_t)0xFFU;
    response[6] = (uint8_t)0U;
    response[7] = (uint8_t)0U;
    return (size_t)8U;
}

static size_t handle_get_daq_resolution_info(
    tethys_xcp_state_t* state, uint8_t* response, size_t resp_cap)
{
    if (!daq_ready(state)) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_UNKNOWN);
    }
    if (resp_cap < (size_t)8U) {
        return (size_t)0U;
    }
    response[0] = TETHYS_XCP_PID_RES;
    response[1] = (uint8_t)1U;
    response[2] = (uint8_t)0xFFU;
    response[3] = (uint8_t)1U;
    response[4] = (uint8_t)0xFFU;
    response[5] = (uint8_t)0x34U;
    response[6] = (uint8_t)1U;
    response[7] = (uint8_t)0U;
    return (size_t)8U;
}

static size_t handle_get_daq_list_info(
    tethys_xcp_state_t* state, uint8_t const* request, size_t req_len,
    uint8_t* response, size_t resp_cap)
{
    if (!daq_ready(state)) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_UNKNOWN);
    }
    if (req_len < (size_t)4U) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_SYNTAX);
    }
    tethys_daq_list_t const* const list =
        tethys_daq_get_list(state->daq, decode_u16_le(&request[2]));
    if (list == NULL) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_OUT_OF_RANGE);
    }
    if (resp_cap < (size_t)6U) {
        return (size_t)0U;
    }
    response[0] = TETHYS_XCP_PID_RES;
    response[1] = (uint8_t)0x10U;
    if ((list->mode & TETHYS_DAQ_MODE_DIRECTION_STIM) != (uint8_t)0U) {
        response[1] |= (uint8_t)0x04U;
    }
    response[2] = list->odt_count;
    response[3] = (uint8_t)TETHYS_DAQ_MAX_ENTRIES_PER_ODT;
    response[4] = (uint8_t)( list->event_channel        & 0xFFU);
    response[5] = (uint8_t)((list->event_channel >> 8U) & 0xFFU);
    return (size_t)6U;
}

static size_t handle_get_daq_event_info(
    tethys_xcp_state_t* state, uint8_t const* request, size_t req_len,
    uint8_t* response, size_t resp_cap)
{
    if (!daq_ready(state)) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_UNKNOWN);
    }
    if (req_len < (size_t)4U) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_SYNTAX);
    }
    if (resp_cap < (size_t)7U) {
        return (size_t)0U;
    }
    response[0] = TETHYS_XCP_PID_RES;
    response[1] = (uint8_t)0x05U;
    response[2] = (uint8_t)TETHYS_DAQ_MAX_LISTS;
    response[3] = (uint8_t)11U;
    response[4] = (uint8_t)1U;
    response[5] = (uint8_t)6U;
    response[6] = (uint8_t)0U;
    return (size_t)7U;
}

static size_t handle_read_daq(
    tethys_xcp_state_t* state, uint8_t* response, size_t resp_cap)
{
    if (!daq_ready(state)) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_UNKNOWN);
    }
    if (resp_cap < (size_t)8U) {
        return (size_t)0U;
    }
    tethys_daq_entry_t e = {0};
    if (tethys_daq_read_entry(state->daq, &e) != 0) {
        return write_error_response(response, resp_cap, TETHYS_XCP_ERR_OUT_OF_RANGE);
    }
    response[0] = TETHYS_XCP_PID_RES;
    response[1] = e.bit_offset;
    response[2] = e.size_bytes;
    response[3] = e.addr_extension;
    response[4] = (uint8_t)( e.address        & 0xFFU);
    response[5] = (uint8_t)((e.address >>  8) & 0xFFU);
    response[6] = (uint8_t)((e.address >> 16) & 0xFFU);
    response[7] = (uint8_t)((e.address >> 24) & 0xFFU);
    return (size_t)8U;
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
    state->mta_address   = (uint32_t)0U;
    state->mta_extension = (uint8_t)0U;
    state->memory        = NULL;
    state->memory_size   = (size_t)0U;
    state->daq           = NULL;
}

void tethys_xcp_attach_memory(tethys_xcp_state_t* state, uint8_t* mem, size_t size)
{
    if (state == NULL) {
        return;
    }
    state->memory      = mem;
    state->memory_size = (mem == NULL) ? (size_t)0U : size;
    if (state->daq != NULL) {
        tethys_daq_attach_memory(state->daq, mem, state->memory_size);
    }
}

void tethys_xcp_attach_daq(tethys_xcp_state_t* state, tethys_daq_engine_t* engine)
{
    if (state == NULL) {
        return;
    }
    state->daq = engine;
    if (engine != NULL) {
        tethys_daq_attach_memory(engine, state->memory, state->memory_size);
    }
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
    else if (cmd == TETHYS_XCP_CMD_SET_MTA) {
        written = handle_set_mta(state, request, req_len, response, resp_cap);
    }
    else if (cmd == TETHYS_XCP_CMD_UPLOAD) {
        written = handle_upload(state, request, req_len, response, resp_cap);
    }
    else if (cmd == TETHYS_XCP_CMD_SHORT_UPLOAD) {
        written = handle_short_upload(state, request, req_len, response, resp_cap);
    }
    else if (cmd == TETHYS_XCP_CMD_DOWNLOAD) {
        written = handle_download(state, request, req_len, response, resp_cap);
    }
    else if (cmd == TETHYS_XCP_CMD_BUILD_CHECKSUM) {
        written = handle_build_checksum(state, request, req_len, response, resp_cap);
    }
    else if (cmd == TETHYS_XCP_CMD_SYNCH) {
        written = handle_synch(response, resp_cap);
    }
    else if (cmd == TETHYS_XCP_CMD_FREE_DAQ) {
        written = handle_free_daq(state, response, resp_cap);
    }
    else if (cmd == TETHYS_XCP_CMD_ALLOC_DAQ) {
        written = handle_alloc_daq(state, request, req_len, response, resp_cap);
    }
    else if (cmd == TETHYS_XCP_CMD_ALLOC_ODT) {
        written = handle_alloc_odt(state, request, req_len, response, resp_cap);
    }
    else if (cmd == TETHYS_XCP_CMD_ALLOC_ODT_ENTRY) {
        written = handle_alloc_odt_entry(state, request, req_len, response, resp_cap);
    }
    else if (cmd == TETHYS_XCP_CMD_SET_DAQ_PTR) {
        written = handle_set_daq_ptr(state, request, req_len, response, resp_cap);
    }
    else if (cmd == TETHYS_XCP_CMD_WRITE_DAQ) {
        written = handle_write_daq(state, request, req_len, response, resp_cap);
    }
    else if (cmd == TETHYS_XCP_CMD_WRITE_DAQ_MULTIPLE) {
        written = handle_write_daq_multiple(state, request, req_len, response, resp_cap);
    }
    else if (cmd == TETHYS_XCP_CMD_SET_DAQ_LIST_MODE) {
        written = handle_set_daq_list_mode(state, request, req_len, response, resp_cap);
    }
    else if (cmd == TETHYS_XCP_CMD_GET_DAQ_LIST_MODE) {
        written = handle_get_daq_list_mode(state, request, req_len, response, resp_cap);
    }
    else if (cmd == TETHYS_XCP_CMD_START_STOP_DAQ_LIST) {
        written = handle_start_stop_daq_list(state, request, req_len, response, resp_cap);
    }
    else if (cmd == TETHYS_XCP_CMD_START_STOP_SYNCH) {
        written = handle_start_stop_synch(state, request, req_len, response, resp_cap);
    }
    else if (cmd == TETHYS_XCP_CMD_GET_DAQ_PROCESSOR_INFO) {
        written = handle_get_daq_processor_info(state, response, resp_cap);
    }
    else if (cmd == TETHYS_XCP_CMD_GET_DAQ_RESOLUTION_INFO) {
        written = handle_get_daq_resolution_info(state, response, resp_cap);
    }
    else if (cmd == TETHYS_XCP_CMD_GET_DAQ_LIST_INFO) {
        written = handle_get_daq_list_info(state, request, req_len, response, resp_cap);
    }
    else if (cmd == TETHYS_XCP_CMD_GET_DAQ_EVENT_INFO) {
        written = handle_get_daq_event_info(state, request, req_len, response, resp_cap);
    }
    else if (cmd == TETHYS_XCP_CMD_READ_DAQ) {
        written = handle_read_daq(state, response, resp_cap);
    }
    else {
        written = write_error_response(response, resp_cap, TETHYS_XCP_ERR_CMD_UNKNOWN);
    }

    if (written == (size_t)0U) {
        return -1;
    }
    *resp_len = written;
    return 0;
}
