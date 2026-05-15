/*
 * tethys/xcp_daq.h - DAQ (Data AcQuisition) engine public API.
 *
 * Module: tethys::core::xcp_daq
 * Profiles: all (marine, space, posix-sim)
 * Standards: ASAM XCP 1.4 Part 2 §1.4 (DAQ command set + DTO emission);
 *            MISRA C:2023; ECSS-E-ST-40C Rev.1 §5.4;
 *            ADR-0005 (no dynamic allocation); ADR-0010 (loss budget)
 * Trace: docs/traceability.csv (rows TETHYS-DES-0050..0064 land at PR-10)
 *
 * The DAQ engine owns:
 *   - up to TETHYS_DAQ_MAX_LISTS DAQ lists (each = up to MAX_ODT_PER_LIST
 *     ODTs of MAX_ENTRIES_PER_ODT entries each);
 *   - a 16-bit DTO counter (CTR) per ADR-0010 row 2 + XCP 1.4 §3.1.5;
 *   - the mode bits (DIRECTION = DAQ|STIM, TIMESTAMP enable, PID_OFF);
 *   - a static DTO scratch buffer the dispatcher hands to the TAL on
 *     each event tick.
 *
 * The XCP command dispatcher (xcp_dispatcher.c) forwards every DAQ
 * command (XCP codes 0xD3..0xDF + 0xE0..0xE2 + 0xC7) to the helpers
 * declared below. The dispatcher remains the only public entry point for
 * inbound CTOs; this header exists so the dispatcher's branch handlers
 * + the tests can talk to the engine without poking its internals.
 *
 * Phase 3 PR-3b adds the event-tick fan-out + DTO emission; PR-3e adds
 * the STIM direction. PR-3a (this PR) ships the engine surface, the 11
 * configuration-side dispatcher commands, and zero DTO transmission.
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */
#ifndef TETHYS_XCP_DAQ_H
#define TETHYS_XCP_DAQ_H

#pragma once

#include "tethys/tethys_export.h"
#include "tethys/xcp_odt.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ---- DAQ command codes (XCP 1.4 Part 2 §1.4 Table 5; subset) --------- */

#define TETHYS_XCP_CMD_FREE_DAQ              ((uint8_t)0xD6U)
#define TETHYS_XCP_CMD_ALLOC_DAQ             ((uint8_t)0xD5U)
#define TETHYS_XCP_CMD_ALLOC_ODT             ((uint8_t)0xD4U)
#define TETHYS_XCP_CMD_ALLOC_ODT_ENTRY       ((uint8_t)0xD3U)
#define TETHYS_XCP_CMD_SET_DAQ_PTR           ((uint8_t)0xE2U)
#define TETHYS_XCP_CMD_WRITE_DAQ             ((uint8_t)0xE1U)
#define TETHYS_XCP_CMD_WRITE_DAQ_MULTIPLE    ((uint8_t)0xC7U)
#define TETHYS_XCP_CMD_SET_DAQ_LIST_MODE     ((uint8_t)0xE0U)
#define TETHYS_XCP_CMD_GET_DAQ_LIST_MODE     ((uint8_t)0xDFU)
#define TETHYS_XCP_CMD_START_STOP_DAQ_LIST   ((uint8_t)0xDEU)
#define TETHYS_XCP_CMD_START_STOP_SYNCH      ((uint8_t)0xDDU)
#define TETHYS_XCP_CMD_GET_DAQ_PROCESSOR_INFO ((uint8_t)0xDAU)
#define TETHYS_XCP_CMD_GET_DAQ_RESOLUTION_INFO ((uint8_t)0xD9U)
#define TETHYS_XCP_CMD_GET_DAQ_LIST_INFO     ((uint8_t)0xD8U)
#define TETHYS_XCP_CMD_GET_DAQ_EVENT_INFO    ((uint8_t)0xD7U)
#define TETHYS_XCP_CMD_READ_DAQ              ((uint8_t)0xDBU)

/* ---- SET_DAQ_LIST_MODE mode bits (XCP 1.4 Part 2 §1.4.2.6 Table 22) -- */

#define TETHYS_DAQ_MODE_ALTERNATING    ((uint8_t)0x01U) /**< alternating display */
#define TETHYS_DAQ_MODE_DIRECTION_STIM ((uint8_t)0x02U) /**< 1 = STIM, 0 = DAQ */
#define TETHYS_DAQ_MODE_TIMESTAMP      ((uint8_t)0x04U) /**< prepend timestamp */
#define TETHYS_DAQ_MODE_PID_OFF        ((uint8_t)0x10U) /**< suppress PID byte */

/* ---- START_STOP_DAQ_LIST modes (XCP 1.4 Part 2 §1.4.2.4) ------------- */

#define TETHYS_DAQ_START_STOP_STOP      ((uint8_t)0x00U)
#define TETHYS_DAQ_START_STOP_START     ((uint8_t)0x01U)
#define TETHYS_DAQ_START_STOP_SELECT    ((uint8_t)0x02U)

/* ---- START_STOP_SYNCH modes (XCP 1.4 Part 2 §1.4.2.5) ---------------- */

#define TETHYS_DAQ_SYNCH_STOP_ALL          ((uint8_t)0x00U)
#define TETHYS_DAQ_SYNCH_START_SELECTED    ((uint8_t)0x01U)
#define TETHYS_DAQ_SYNCH_STOP_SELECTED     ((uint8_t)0x02U)
#define TETHYS_DAQ_SYNCH_PREPARE_START_SELECTED ((uint8_t)0x03U)

/* ---- Error codes specific to DAQ (XCP 1.4 Part 2 Table 12) ----------- */

#define TETHYS_XCP_ERR_MEMORY_OVERFLOW   ((uint8_t)0x30U)
#define TETHYS_XCP_ERR_DAQ_CONFIG        ((uint8_t)0x32U)

/* ---- Engine state ----------------------------------------------------- */

/**
 * @brief Per-DAQ-list state (configuration + runtime).
 *
 * Held inline in @ref tethys_daq_engine_t so the whole engine is one
 * contiguous struct. All ODT storage is statically sized per ADR-0005.
 */
typedef struct
{
    tethys_odt_t odts[TETHYS_DAQ_MAX_ODT_PER_LIST];
    uint8_t      odt_count;            /**< ALLOC_ODT */
    uint8_t      first_pid;            /**< absolute PID of ODT 0 */
    uint8_t      mode;                 /**< SET_DAQ_LIST_MODE bits */
    uint8_t      priority;             /**< SET_DAQ_LIST_MODE prio */
    uint16_t     event_channel;        /**< SET_DAQ_LIST_MODE event */
    uint8_t      prescaler;            /**< SET_DAQ_LIST_MODE prescaler */
    uint8_t      prescaler_counter;    /**< runtime tick prescaling */
    bool         allocated;            /**< ALLOC_DAQ allocated this slot */
    bool         running;              /**< START_STOP_DAQ_LIST set */
    bool         selected;             /**< SELECT mode marker */
} tethys_daq_list_t;

/**
 * @brief DAQ engine state (one instance per slave process / MCU).
 *
 * Lives on the caller's stack / .bss; no allocation done internally.
 * Use @ref tethys_daq_init to wipe it before use.
 *
 * `memory` / `memory_size` MUST point at the same backend the xcp
 * dispatcher uses for UPLOAD/DOWNLOAD (call tethys_daq_attach_memory).
 *
 * The `ptr_*` fields hold the current "SET_DAQ_PTR" selection that
 * subsequent WRITE_DAQ / READ_DAQ commands operate on.
 */
typedef struct
{
    tethys_daq_list_t lists[TETHYS_DAQ_MAX_LISTS];
    uint8_t           list_count;        /**< ALLOC_DAQ */
    uint8_t           ptr_daq;           /**< SET_DAQ_PTR selected list */
    uint8_t           ptr_odt;           /**< SET_DAQ_PTR selected ODT */
    uint8_t           ptr_entry;         /**< SET_DAQ_PTR selected entry idx */
    bool              ptr_valid;         /**< SET_DAQ_PTR set since last reset */
    uint16_t          dto_counter;       /**< rolling CTR (ADR-0010 §3) */
    uint32_t          timestamp_now_us;  /**< master-injected tick clock */
    uint8_t*          memory;
    size_t            memory_size;
} tethys_daq_engine_t;

/* ---- Public API ------------------------------------------------------- */

/**
 * @brief Reset the DAQ engine to the disconnected state.
 *
 * Equivalent to a fresh FREE_DAQ + DISCONNECT: clears every list, every
 * ODT, every entry; detaches memory; resets the CTR.
 *
 * @param[out] engine Caller-owned engine.
 *
 * @pre engine != NULL
 */
TETHYS_EXPORT void tethys_daq_init(tethys_daq_engine_t* engine);

/**
 * @brief Attach the XCP memory backend.
 *
 * Same buffer the xcp dispatcher uses for UPLOAD/DOWNLOAD. The engine
 * does NOT take ownership; the caller keeps the buffer alive past every
 * tethys_daq_* call.
 *
 * @param[in,out] engine Engine state.
 * @param[in]     mem    Caller-owned buffer (or NULL to detach).
 * @param[in]     size   Buffer size in bytes (0 when mem == NULL).
 *
 * @pre engine != NULL
 */
TETHYS_EXPORT void tethys_daq_attach_memory(
    tethys_daq_engine_t* engine,
    uint8_t*             mem,
    size_t               size);

/* ---- Command-level helpers (called from xcp_dispatcher.c) ------------ */

/**
 * @brief Handle FREE_DAQ (0xD6).
 *
 * @return 0 on success.
 */
TETHYS_EXPORT int tethys_daq_free(tethys_daq_engine_t* engine);

/**
 * @brief Handle ALLOC_DAQ (0xD5).
 *
 * @param[in,out] engine Engine state.
 * @param[in]  list_count Number of DAQ lists to allocate (1..MAX_LISTS).
 *
 * @return 0 on success, -1 on out-of-range (returns ERR_MEMORY_OVERFLOW
 *         to the master).
 */
TETHYS_EXPORT int tethys_daq_alloc(
    tethys_daq_engine_t* engine,
    uint16_t             list_count);

/**
 * @brief Handle ALLOC_ODT (0xD4).
 *
 * @param[in,out] engine    Engine state.
 * @param[in]  daq_list_num Target DAQ list (0..list_count-1).
 * @param[in]  odt_count    Number of ODTs to allocate (1..MAX_ODT_PER_LIST).
 *
 * @return 0 on success; -1 on list-not-allocated / count out-of-range.
 */
TETHYS_EXPORT int tethys_daq_alloc_odt(
    tethys_daq_engine_t* engine,
    uint16_t             daq_list_num,
    uint8_t              odt_count);

/**
 * @brief Handle ALLOC_ODT_ENTRY (0xD3).
 *
 * @param[in,out] engine     Engine state.
 * @param[in]  daq_list_num  Target DAQ list.
 * @param[in]  odt_num       Target ODT within the list.
 * @param[in]  entry_count   Number of entries to allocate (1..MAX_ENTRIES_PER_ODT).
 *
 * @return 0 on success; -1 on ODT-not-allocated / count out-of-range.
 */
TETHYS_EXPORT int tethys_daq_alloc_odt_entry(
    tethys_daq_engine_t* engine,
    uint16_t             daq_list_num,
    uint8_t              odt_num,
    uint8_t              entry_count);

/**
 * @brief Handle SET_DAQ_PTR (0xE2).
 *
 * @return 0 on success; -1 if any index is out of allocated range.
 */
TETHYS_EXPORT int tethys_daq_set_ptr(
    tethys_daq_engine_t* engine,
    uint16_t             daq_list_num,
    uint8_t              odt_num,
    uint8_t              entry_idx);

/**
 * @brief Handle WRITE_DAQ (0xE1).
 *
 * Writes one entry at the current SET_DAQ_PTR position and advances the
 * pointer to the next entry index.
 *
 * @return 0 on success; -1 on no-pointer / out-of-range / overflow.
 */
TETHYS_EXPORT int tethys_daq_write_entry(
    tethys_daq_engine_t* engine,
    uint8_t              bit_offset,
    uint8_t              size_bytes,
    uint8_t              addr_extension,
    uint32_t             address);

/**
 * @brief Handle READ_DAQ (0xDB) - read the entry at the current pointer.
 *
 * @return 0 on success; -1 on no-pointer / out-of-range. On success the
 *         caller fills its response packet from @p out_entry.
 */
TETHYS_EXPORT int tethys_daq_read_entry(
    tethys_daq_engine_t const* engine,
    tethys_daq_entry_t*        out_entry);

/**
 * @brief Handle SET_DAQ_LIST_MODE (0xE0).
 *
 * @return 0 on success; -1 if @p daq_list_num is unallocated.
 */
TETHYS_EXPORT int tethys_daq_set_list_mode(
    tethys_daq_engine_t* engine,
    uint16_t             daq_list_num,
    uint8_t              mode,
    uint16_t             event_channel,
    uint8_t              prescaler,
    uint8_t              priority);

/**
 * @brief Handle GET_DAQ_LIST_MODE (0xDF) - inverse of set_list_mode.
 *
 * @return 0 on success; -1 if @p daq_list_num is unallocated.
 */
TETHYS_EXPORT int tethys_daq_get_list_mode(
    tethys_daq_engine_t const* engine,
    uint16_t                   daq_list_num,
    uint8_t*                   out_mode,
    uint16_t*                  out_event_channel,
    uint8_t*                   out_prescaler,
    uint8_t*                   out_priority);

/**
 * @brief Handle START_STOP_DAQ_LIST (0xDE).
 *
 * `mode` is one of TETHYS_DAQ_START_STOP_*.
 *
 * @param[out] out_first_pid On START/SELECT mode the absolute FIRST_PID of
 *                          the list (PID range 0x00..0xFB per XCP 1.4
 *                          Part 2 §1.4.2.1). The slave assigns FIRST_PID
 *                          consecutively across allocated lists.
 *
 * @return 0 on success; -1 if @p daq_list_num is unallocated or @p mode
 *         is unknown.
 */
TETHYS_EXPORT int tethys_daq_start_stop_list(
    tethys_daq_engine_t* engine,
    uint16_t             daq_list_num,
    uint8_t              mode,
    uint8_t*             out_first_pid);

/**
 * @brief Handle START_STOP_SYNCH (0xDD) - all-lists race-fix variant.
 *
 * `mode` is one of TETHYS_DAQ_SYNCH_*.
 *
 * @return 0 on success; -1 on unknown mode.
 */
TETHYS_EXPORT int tethys_daq_start_stop_synch(
    tethys_daq_engine_t* engine,
    uint8_t              mode);

/* ---- DTO emission (Phase 3 PR-3b) ------------------------------------ */

/**
 * @brief Pack one ODT into a DTO frame ready for the TAL.
 *
 * Layout in @p out_buffer:
 *   [0]     PID = first_pid + odt_num
 *   [1..4]  optional 4-byte little-endian timestamp (if SET_DAQ_LIST_MODE
 *           mode bit 0x04 is set on the list)
 *   [rest]  payload bytes (see tethys_odt_pack)
 *
 * @param[in]  engine        Engine state.
 * @param[in]  daq_list_num  Target list (must be allocated and running).
 * @param[in]  odt_num       Target ODT within the list.
 * @param[out] out_buffer    Caller-owned scratch buffer.
 * @param[in]  out_capacity  Capacity of @p out_buffer in bytes.
 * @param[out] out_len       Number of bytes written.
 *
 * @return 0 on success; -1 on inactive list / out-of-range / overflow.
 *
 * @note PR-3a ships the function but no caller yet; PR-3b wires it into
 *       the event-tick fan-out. Tested in PR-3a as a unit test only.
 */
TETHYS_EXPORT int tethys_daq_pack_dto(
    tethys_daq_engine_t* engine,
    uint16_t             daq_list_num,
    uint8_t              odt_num,
    uint8_t*             out_buffer,
    size_t               out_capacity,
    size_t*              out_len);

/**
 * @brief Unpack one STIM DTO into the memory backend.
 *
 * Inverse of @ref tethys_daq_pack_dto for STIM direction. The caller has
 * already validated @p in_buffer[0] as a valid STIM PID (= first_pid +
 * odt_num for a STIM-direction list) and supplies @p daq_list_num /
 * @p odt_num.
 *
 * @return 0 on success; -1 on configuration / overflow error.
 *
 * @note PR-3e ships the wiring; PR-3a defines the surface so tests can
 *       exercise the round-trip.
 */
TETHYS_EXPORT int tethys_daq_apply_stim_dto(
    tethys_daq_engine_t* engine,
    uint16_t             daq_list_num,
    uint8_t              odt_num,
    uint8_t const*       in_buffer,
    size_t               in_size);

/* ---- Diagnostic helpers (test-only) ---------------------------------- */

/**
 * @brief Look up the @p daq_list_num list pointer (NULL if unallocated).
 *
 * Read-only: the engine retains ownership. Tests use this to inspect
 * mode bits, FIRST_PID, prescaler, etc. without going through the full
 * dispatcher path.
 */
TETHYS_EXPORT tethys_daq_list_t const* tethys_daq_get_list(
    tethys_daq_engine_t const* engine,
    uint16_t                   daq_list_num);

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* TETHYS_XCP_DAQ_H */
