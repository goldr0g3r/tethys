/*
 * tethys/xcp_dispatcher.h - XCP command dispatcher (Phase 1 + Phase 2 read path).
 *
 * Module: tethys::core::xcp_dispatcher
 * Profiles: all (marine, space, posix-sim)
 * Standards: ASAM XCP 1.4 Part 2 §1.3.2 + §1.3.3 + §1.4.2.1;
 *            MISRA C:2023; ECSS-E-ST-40C Rev.1 §5.4
 * Trace: docs/traceability.csv (rows TETHYS-DES-0001..0007 land at PR-10)
 *
 * Phase 1 commands:
 *   - CONNECT     (0xFF) - establish session
 *   - DISCONNECT  (0xFE) - tear down session
 *   - GET_STATUS  (0xFD) - session status / resource protection / state
 *   - GET_VERSION (0xC0) - protocol + transport version
 *
 * Phase 2 read-path commands (PR-28):
 *   - SET_MTA       (0xF6) - set Memory Transfer Address
 *   - UPLOAD        (0xF5) - upload N bytes from MTA (auto-increment)
 *   - SHORT_UPLOAD  (0xF4) - upload N bytes from given address (stateless)
 *
 * Out of scope (deferred):
 *   - DOWNLOAD / BUILD_CHECKSUM / SYNCH (Phase 2 PR-29)
 *   - A2L MEASUREMENT/CHARACTERISTIC parse (Phase 2 PR-30)
 *   - DAQ_LIST / STIM / CAL (Phase 3 + 4)
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */
#ifndef TETHYS_XCP_DISPATCHER_H
#define TETHYS_XCP_DISPATCHER_H

#pragma once

#include "tethys/tethys_export.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ---- Wire constants (XCP 1.4 Part 2) ----------------------------------- */

/** Maximum CTO size in bytes (XCP 1.4 default; configurable later). */
#define TETHYS_XCP_MAX_CTO   ((uint8_t)8U)

/** Maximum DTO size in bytes (XCP 1.4 default; configurable later). */
#define TETHYS_XCP_MAX_DTO   ((uint16_t)256U)

/** XCP Standard Command codes (subset; XCP 1.4 Part 2 Table 5). */
#define TETHYS_XCP_CMD_CONNECT       ((uint8_t)0xFFU)
#define TETHYS_XCP_CMD_DISCONNECT    ((uint8_t)0xFEU)
#define TETHYS_XCP_CMD_GET_STATUS    ((uint8_t)0xFDU)
#define TETHYS_XCP_CMD_SYNCH         ((uint8_t)0xFCU)
#define TETHYS_XCP_CMD_GET_VERSION   ((uint8_t)0xC0U)
#define TETHYS_XCP_CMD_SET_MTA       ((uint8_t)0xF6U)
#define TETHYS_XCP_CMD_UPLOAD        ((uint8_t)0xF5U)
#define TETHYS_XCP_CMD_SHORT_UPLOAD  ((uint8_t)0xF4U)

/** Packet IDs (first byte of any response packet; XCP 1.4 Part 2 §3.1). */
#define TETHYS_XCP_PID_RES   ((uint8_t)0xFFU)
#define TETHYS_XCP_PID_ERR   ((uint8_t)0xFEU)

/** Error codes (XCP 1.4 Part 2 Table 12; subset). */
#define TETHYS_XCP_ERR_CMD_SYNCH      ((uint8_t)0x00U)
#define TETHYS_XCP_ERR_CMD_UNKNOWN    ((uint8_t)0x20U)
#define TETHYS_XCP_ERR_CMD_SYNTAX     ((uint8_t)0x21U)
#define TETHYS_XCP_ERR_OUT_OF_RANGE   ((uint8_t)0x22U)
#define TETHYS_XCP_ERR_ACCESS_DENIED  ((uint8_t)0x24U)

/** CONNECT response resource availability bits (XCP 1.4 Part 2 §1.3.2.4). */
#define TETHYS_XCP_RES_CAL_PAG   ((uint8_t)0x01U)
#define TETHYS_XCP_RES_DAQ       ((uint8_t)0x04U)
#define TETHYS_XCP_RES_STIM      ((uint8_t)0x08U)
#define TETHYS_XCP_RES_PGM       ((uint8_t)0x10U)

/** Comm mode basic bits (XCP 1.4 Part 2 §1.3.2.4). */
#define TETHYS_XCP_COMM_OPTIONAL ((uint8_t)0x80U)

/** Protocol + transport version bytes (XCP 1.4). */
#define TETHYS_XCP_PROTO_VERSION ((uint8_t)0x01U)
#define TETHYS_XCP_XPRT_VERSION  ((uint8_t)0x01U)

/* ---- Session state ---------------------------------------------------- */

/**
 * @brief XCP session state (volatile; one instance per slave process / MCU).
 *
 * Caller owns the storage. tethys_xcp_init() must be called once before any
 * tethys_xcp_dispatch() call.
 *
 * Phase 2 additions (PR-28): mta_address, mta_extension, memory, memory_size.
 * The memory backend is caller-attached via tethys_xcp_attach_memory() so the
 * dispatcher has no module-level globals (per ADR-0005 and to enable parallel
 * test fixtures). memory == NULL implicitly disables UPLOAD / SHORT_UPLOAD.
 */
typedef struct
{
    bool     connected;
    uint8_t  session_status;
    uint8_t  resource_protection;
    uint8_t  state_number;
    uint16_t session_configuration_id;
    uint32_t mta_address;
    uint8_t  mta_extension;
    uint8_t* memory;
    size_t   memory_size;
} tethys_xcp_state_t;

/* ---- Public API ------------------------------------------------------- */

/**
 * @brief Reset the session state.
 *
 * @param[out] state Caller-owned state struct.
 *
 * @pre  state != NULL
 * @post state->connected == false
 * @post state->memory == NULL && state->memory_size == 0
 *
 * @note Memory is detached by init; call tethys_xcp_attach_memory() to
 *       enable UPLOAD / SHORT_UPLOAD.
 */
TETHYS_EXPORT void tethys_xcp_init(tethys_xcp_state_t* state);

/**
 * @brief Attach a caller-owned memory buffer for UPLOAD / DOWNLOAD.
 *
 * The dispatcher only reads/writes within @p mem[0 .. size).
 * Pass mem = NULL / size = 0 to detach and disable UPLOAD.
 *
 * @param[in,out] state Session state.
 * @param[in]     mem   Caller-owned buffer (lifetime exceeds state).
 * @param[in]     size  Buffer size in bytes.
 *
 * @pre state != NULL
 */
TETHYS_EXPORT void tethys_xcp_attach_memory(
    tethys_xcp_state_t* state,
    uint8_t*            mem,
    size_t              size);

/**
 * @brief Dispatch one inbound CTO request and write the response.
 *
 * Synchronous; does not block. Suitable to call from an ISR-free transport
 * polling loop (Phase 1).
 *
 * @param[in,out] state  Session state.
 * @param[in]  request   Inbound CTO bytes (first byte is the command code).
 * @param[in]  req_len   Length of @p request in bytes.
 * @param[out] response  Response buffer (caller-owned). Must be at least
 *                       TETHYS_XCP_MAX_CTO bytes.
 * @param[in]  resp_cap  Capacity of @p response in bytes.
 * @param[out] resp_len  On success the number of bytes written to @p response.
 *
 * @return 0 on success (response written), -1 on argument error.
 *
 * @pre  state != NULL && request != NULL && response != NULL && resp_len != NULL
 * @pre  resp_cap >= TETHYS_XCP_MAX_CTO
 *
 * @safety Marine + space profiles. No dynamic allocation. Bounded loops.
 *         MISRA C:2023 clean (mandatory + required).
 */
TETHYS_EXPORT int tethys_xcp_dispatch(
    tethys_xcp_state_t* state,
    uint8_t const*      request,
    size_t              req_len,
    uint8_t*            response,
    size_t              resp_cap,
    size_t*             resp_len);

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* TETHYS_XCP_DISPATCHER_H */
