/*
 * src/core/xcp_daq.c - DAQ engine implementation.
 *
 * Module: tethys::core::xcp_daq
 * Profiles: all (marine, space, posix-sim)
 * Standards: ASAM XCP 1.4 Part 2 §1.4 (DAQ commands + DTO emission);
 *            MISRA C:2023 clean (mandatory + required);
 *            ECSS-E-ST-40C Rev.1 §5.4 (deterministic memory layout);
 *            ADR-0005 (no dynamic allocation); ADR-0010 row 2 (DAQ CTR)
 * Trace: docs/traceability.csv (rows TETHYS-DES-0050..0064 land at PR-10)
 *
 * Phase 3 PR-3a: configuration-side commands + helpers + DTO pack/unpack
 * surface. PR-3b adds the event-tick fan-out + TAL emission. PR-3e adds
 * STIM direction.
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */
#include "tethys/xcp_daq.h"

#include "tethys/tethys_transport.h"
#include "tethys/xcp_odt.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* ---- Helpers --------------------------------------------------------- */

/**
 * @brief Reset every list slot to the unallocated state.
 *
 * Called from tethys_daq_init and tethys_daq_free. Bounded loop;
 * deterministic per ECSS-E-ST-40C §5.4.
 */
static void reset_all_lists(tethys_daq_engine_t* engine)
{
    for (uint8_t i = (uint8_t)0U; i < TETHYS_DAQ_MAX_LISTS; ++i) {
        tethys_daq_list_t* const list = &engine->lists[i];
        for (uint8_t j = (uint8_t)0U; j < TETHYS_DAQ_MAX_ODT_PER_LIST; ++j) {
            tethys_odt_reset(&list->odts[j]);
        }
        list->odt_count          = (uint8_t)0U;
        list->first_pid          = (uint8_t)0U;
        list->mode               = (uint8_t)0U;
        list->priority           = (uint8_t)0U;
        list->event_channel      = (uint16_t)0U;
        list->prescaler          = (uint8_t)1U;
        list->prescaler_counter  = (uint8_t)0U;
        list->allocated          = false;
        list->running            = false;
        list->selected           = false;
    }
    engine->list_count  = (uint8_t)0U;
    engine->ptr_valid   = false;
    engine->ptr_daq     = (uint8_t)0U;
    engine->ptr_odt     = (uint8_t)0U;
    engine->ptr_entry   = (uint8_t)0U;
}

/**
 * @brief Re-compute FIRST_PID across all allocated lists.
 *
 * XCP 1.4 Part 2 §1.4.2.1 specifies the PID range 0x00..0xFB for DAQ DTOs.
 * Tethys assigns them by walking allocated lists in order and summing
 * each list's ODT count: list 0 gets PIDs [0, odt_count_0); list 1 gets
 * [odt_count_0, odt_count_0 + odt_count_1); and so on.
 */
static void recompute_first_pids(tethys_daq_engine_t* engine)
{
    uint8_t next = (uint8_t)0U;
    for (uint8_t i = (uint8_t)0U; i < engine->list_count; ++i) {
        tethys_daq_list_t* const list = &engine->lists[i];
        if (!list->allocated) {
            continue;
        }
        list->first_pid = next;
        /* Bounded: odt_count <= TETHYS_DAQ_MAX_ODT_PER_LIST. */
        if ((uint16_t)next + (uint16_t)list->odt_count <= (uint16_t)0xFCU) {
            next = (uint8_t)((uint16_t)next + (uint16_t)list->odt_count);
        }
    }
}

/* ---- Public API: lifecycle ------------------------------------------- */

void tethys_daq_init(tethys_daq_engine_t* engine)
{
    if (engine == NULL) {
        return;
    }
    reset_all_lists(engine);
    engine->dto_counter      = (uint16_t)0U;
    engine->timestamp_now_us = (uint32_t)0U;
    engine->memory           = NULL;
    engine->memory_size      = (size_t)0U;
}

void tethys_daq_attach_memory(tethys_daq_engine_t* engine, uint8_t* mem, size_t size)
{
    if (engine == NULL) {
        return;
    }
    engine->memory      = mem;
    engine->memory_size = (mem == NULL) ? (size_t)0U : size;
}

/* ---- Public API: command-level helpers ------------------------------- */

int tethys_daq_free(tethys_daq_engine_t* engine)
{
    if (engine == NULL) {
        return -1;
    }
    reset_all_lists(engine);
    engine->dto_counter = (uint16_t)0U;
    return 0;
}

int tethys_daq_alloc(tethys_daq_engine_t* engine, uint16_t list_count)
{
    if (engine == NULL) {
        return -1;
    }
    if ((list_count == (uint16_t)0U) || (list_count > (uint16_t)TETHYS_DAQ_MAX_LISTS)) {
        return -1;
    }
    reset_all_lists(engine);
    engine->list_count = (uint8_t)list_count;
    for (uint8_t i = (uint8_t)0U; i < engine->list_count; ++i) {
        engine->lists[i].allocated = true;
        engine->lists[i].prescaler = (uint8_t)1U;
    }
    recompute_first_pids(engine);
    return 0;
}

int tethys_daq_alloc_odt(
    tethys_daq_engine_t* engine,
    uint16_t             daq_list_num,
    uint8_t              odt_count)
{
    if (engine == NULL) {
        return -1;
    }
    if (daq_list_num >= (uint16_t)engine->list_count) {
        return -1;
    }
    if ((odt_count == (uint8_t)0U) || (odt_count > TETHYS_DAQ_MAX_ODT_PER_LIST)) {
        return -1;
    }
    tethys_daq_list_t* const list = &engine->lists[daq_list_num];
    if (!list->allocated) {
        return -1;
    }
    list->odt_count = odt_count;
    for (uint8_t i = (uint8_t)0U; i < TETHYS_DAQ_MAX_ODT_PER_LIST; ++i) {
        tethys_odt_reset(&list->odts[i]);
    }
    recompute_first_pids(engine);
    return 0;
}

int tethys_daq_alloc_odt_entry(
    tethys_daq_engine_t* engine,
    uint16_t             daq_list_num,
    uint8_t              odt_num,
    uint8_t              entry_count)
{
    if (engine == NULL) {
        return -1;
    }
    if (daq_list_num >= (uint16_t)engine->list_count) {
        return -1;
    }
    if ((entry_count == (uint8_t)0U) || (entry_count > TETHYS_DAQ_MAX_ENTRIES_PER_ODT)) {
        return -1;
    }
    tethys_daq_list_t* const list = &engine->lists[daq_list_num];
    if ((!list->allocated) || (odt_num >= list->odt_count)) {
        return -1;
    }
    tethys_odt_t* const odt = &list->odts[odt_num];
    tethys_odt_reset(odt);
    odt->entry_count = entry_count;
    return 0;
}

int tethys_daq_set_ptr(
    tethys_daq_engine_t* engine,
    uint16_t             daq_list_num,
    uint8_t              odt_num,
    uint8_t              entry_idx)
{
    if (engine == NULL) {
        return -1;
    }
    if (daq_list_num >= (uint16_t)engine->list_count) {
        return -1;
    }
    tethys_daq_list_t const* const list = &engine->lists[daq_list_num];
    if ((!list->allocated) || (odt_num >= list->odt_count)) {
        return -1;
    }
    tethys_odt_t const* const odt = &list->odts[odt_num];
    if (entry_idx >= odt->entry_count) {
        return -1;
    }
    engine->ptr_daq   = (uint8_t)daq_list_num;
    engine->ptr_odt   = odt_num;
    engine->ptr_entry = entry_idx;
    engine->ptr_valid = true;
    return 0;
}

int tethys_daq_write_entry(
    tethys_daq_engine_t* engine,
    uint8_t              bit_offset,
    uint8_t              size_bytes,
    uint8_t              addr_extension,
    uint32_t             address)
{
    if (engine == NULL) {
        return -1;
    }
    if (!engine->ptr_valid) {
        return -1;
    }
    if (size_bytes == (uint8_t)0U) {
        return -1;
    }
    tethys_daq_list_t* const list = &engine->lists[engine->ptr_daq];
    tethys_odt_t* const odt = &list->odts[engine->ptr_odt];
    if (engine->ptr_entry >= odt->entry_count) {
        return -1;
    }
    tethys_daq_entry_t* const e = &odt->entries[engine->ptr_entry];
    e->bit_offset     = bit_offset;
    e->size_bytes     = size_bytes;
    e->addr_extension = addr_extension;
    e->address        = address;
    e->in_use         = (uint8_t)1U;
    /* Advance the pointer; wrap stays within the ODT so the master can
     * keep writing entries with a single SET_DAQ_PTR. WRITE_DAQ on a
     * wrapped pointer would just refill from entry 0; the master is
     * expected to SET_DAQ_PTR again before crossing an ODT boundary. */
    if (engine->ptr_entry < (uint8_t)(odt->entry_count - 1U)) {
        engine->ptr_entry = (uint8_t)(engine->ptr_entry + (uint8_t)1U);
    }
    return 0;
}

int tethys_daq_read_entry(
    tethys_daq_engine_t const* engine,
    tethys_daq_entry_t*        out_entry)
{
    if ((engine == NULL) || (out_entry == NULL)) {
        return -1;
    }
    if (!engine->ptr_valid) {
        return -1;
    }
    tethys_daq_list_t const* const list = &engine->lists[engine->ptr_daq];
    tethys_odt_t const* const odt = &list->odts[engine->ptr_odt];
    if (engine->ptr_entry >= odt->entry_count) {
        return -1;
    }
    *out_entry = odt->entries[engine->ptr_entry];
    return 0;
}

int tethys_daq_set_list_mode(
    tethys_daq_engine_t* engine,
    uint16_t             daq_list_num,
    uint8_t              mode,
    uint16_t             event_channel,
    uint8_t              prescaler,
    uint8_t              priority)
{
    if (engine == NULL) {
        return -1;
    }
    if (daq_list_num >= (uint16_t)engine->list_count) {
        return -1;
    }
    tethys_daq_list_t* const list = &engine->lists[daq_list_num];
    if (!list->allocated) {
        return -1;
    }
    list->mode              = mode;
    list->event_channel     = event_channel;
    list->prescaler         = (prescaler == (uint8_t)0U) ? (uint8_t)1U : prescaler;
    list->priority          = priority;
    list->prescaler_counter = (uint8_t)0U;
    return 0;
}

int tethys_daq_get_list_mode(
    tethys_daq_engine_t const* engine,
    uint16_t                   daq_list_num,
    uint8_t*                   out_mode,
    uint16_t*                  out_event_channel,
    uint8_t*                   out_prescaler,
    uint8_t*                   out_priority)
{
    if ((engine == NULL) || (out_mode == NULL) || (out_event_channel == NULL)
            || (out_prescaler == NULL) || (out_priority == NULL)) {
        return -1;
    }
    if (daq_list_num >= (uint16_t)engine->list_count) {
        return -1;
    }
    tethys_daq_list_t const* const list = &engine->lists[daq_list_num];
    if (!list->allocated) {
        return -1;
    }
    *out_mode          = list->mode;
    *out_event_channel = list->event_channel;
    *out_prescaler     = list->prescaler;
    *out_priority      = list->priority;
    return 0;
}

int tethys_daq_start_stop_list(
    tethys_daq_engine_t* engine,
    uint16_t             daq_list_num,
    uint8_t              mode,
    uint8_t*             out_first_pid)
{
    if ((engine == NULL) || (out_first_pid == NULL)) {
        return -1;
    }
    if (daq_list_num >= (uint16_t)engine->list_count) {
        return -1;
    }
    tethys_daq_list_t* const list = &engine->lists[daq_list_num];
    if (!list->allocated) {
        return -1;
    }
    if (mode == TETHYS_DAQ_START_STOP_STOP) {
        list->running  = false;
        list->selected = false;
    }
    else if (mode == TETHYS_DAQ_START_STOP_START) {
        list->running           = true;
        list->selected          = false;
        list->prescaler_counter = (uint8_t)0U;
    }
    else if (mode == TETHYS_DAQ_START_STOP_SELECT) {
        list->selected = true;
    }
    else {
        return -1;
    }
    *out_first_pid = list->first_pid;
    return 0;
}

int tethys_daq_start_stop_synch(tethys_daq_engine_t* engine, uint8_t mode)
{
    if (engine == NULL) {
        return -1;
    }
    bool start_selected = false;
    bool stop_selected  = false;
    bool stop_all       = false;
    if (mode == TETHYS_DAQ_SYNCH_STOP_ALL) {
        stop_all = true;
    }
    else if (mode == TETHYS_DAQ_SYNCH_START_SELECTED) {
        start_selected = true;
    }
    else if (mode == TETHYS_DAQ_SYNCH_STOP_SELECTED) {
        stop_selected = true;
    }
    else if (mode == TETHYS_DAQ_SYNCH_PREPARE_START_SELECTED) {
        /* "Prepare to start selected" - per XCP 1.4 §1.4.2.5 this primes
         * the lists but does not flip `running`. The next call with
         * START_SELECTED commits. Tethys treats it as a no-op (the
         * selected flag is already set) so the engine is race-fix-safe
         * by construction. */
        return 0;
    }
    else {
        return -1;
    }
    for (uint8_t i = (uint8_t)0U; i < engine->list_count; ++i) {
        tethys_daq_list_t* const list = &engine->lists[i];
        if (!list->allocated) {
            continue;
        }
        if (stop_all) {
            list->running  = false;
            list->selected = false;
        }
        else if (start_selected && list->selected) {
            list->running           = true;
            list->selected          = false;
            list->prescaler_counter = (uint8_t)0U;
        }
        else if (stop_selected && list->selected) {
            list->running  = false;
            list->selected = false;
        }
        else {
            /* leave alone */
        }
    }
    return 0;
}

/* ---- DTO emission ---------------------------------------------------- */

int tethys_daq_pack_dto(
    tethys_daq_engine_t* engine,
    uint16_t             daq_list_num,
    uint8_t              odt_num,
    uint8_t*             out_buffer,
    size_t               out_capacity,
    size_t*              out_len)
{
    if ((engine == NULL) || (out_buffer == NULL) || (out_len == NULL)) {
        return -1;
    }
    if (daq_list_num >= (uint16_t)engine->list_count) {
        return -1;
    }
    tethys_daq_list_t const* const list = &engine->lists[daq_list_num];
    if ((!list->allocated) || (odt_num >= list->odt_count)) {
        return -1;
    }
    if (engine->memory == NULL) {
        return -1;
    }
    size_t offset = (size_t)0U;
    /* PID = first_pid + odt_num unless PID_OFF is set (XCP 1.4 §1.4.2.6). */
    bool const pid_off = (list->mode & TETHYS_DAQ_MODE_PID_OFF) != (uint8_t)0U;
    if (!pid_off) {
        if (out_capacity == (size_t)0U) {
            return -1;
        }
        out_buffer[offset] = (uint8_t)((uint16_t)list->first_pid + (uint16_t)odt_num);
        offset = (size_t)1U;
    }
    /* Optional 4-byte little-endian timestamp prefix. */
    bool const timestamped = (list->mode & TETHYS_DAQ_MODE_TIMESTAMP) != (uint8_t)0U;
    if (timestamped) {
        if (out_capacity < (offset + (size_t)4U)) {
            return -1;
        }
        uint32_t const ts = engine->timestamp_now_us;
        out_buffer[offset + (size_t)0U] = (uint8_t)( ts        & 0xFFU);
        out_buffer[offset + (size_t)1U] = (uint8_t)((ts >>  8) & 0xFFU);
        out_buffer[offset + (size_t)2U] = (uint8_t)((ts >> 16) & 0xFFU);
        out_buffer[offset + (size_t)3U] = (uint8_t)((ts >> 24) & 0xFFU);
        offset += (size_t)4U;
    }
    /* Payload. */
    if (tethys_odt_pack(
            &list->odts[odt_num],
            engine->memory,
            engine->memory_size,
            out_buffer,
            out_capacity,
            &offset) != 0) {
        return -1;
    }
    *out_len = offset;
    engine->dto_counter = (uint16_t)((uint16_t)engine->dto_counter + (uint16_t)1U);
    return 0;
}

int tethys_daq_apply_stim_dto(
    tethys_daq_engine_t* engine,
    uint16_t             daq_list_num,
    uint8_t              odt_num,
    uint8_t const*       in_buffer,
    size_t               in_size)
{
    if ((engine == NULL) || (in_buffer == NULL)) {
        return -1;
    }
    if (daq_list_num >= (uint16_t)engine->list_count) {
        return -1;
    }
    tethys_daq_list_t const* const list = &engine->lists[daq_list_num];
    if ((!list->allocated) || (odt_num >= list->odt_count)) {
        return -1;
    }
    if (engine->memory == NULL) {
        return -1;
    }
    /* STIM-direction lists strip the same prefix the master prepended. */
    size_t offset = (size_t)0U;
    bool const pid_off = (list->mode & TETHYS_DAQ_MODE_PID_OFF) != (uint8_t)0U;
    if (!pid_off) {
        if (in_size == (size_t)0U) {
            return -1;
        }
        uint8_t const want_pid = (uint8_t)((uint16_t)list->first_pid + (uint16_t)odt_num);
        if (in_buffer[0] != want_pid) {
            return -1;
        }
        offset = (size_t)1U;
    }
    bool const timestamped = (list->mode & TETHYS_DAQ_MODE_TIMESTAMP) != (uint8_t)0U;
    if (timestamped) {
        if (in_size < (offset + (size_t)4U)) {
            return -1;
        }
        offset += (size_t)4U;
    }
    return tethys_odt_unpack(
        &list->odts[odt_num],
        engine->memory,
        engine->memory_size,
        in_buffer,
        in_size,
        &offset);
}

/* ---- Event tick (Phase 3 PR-3b) -------------------------------------- */

uint16_t tethys_daq_tick(
    tethys_daq_engine_t* engine,
    uint16_t             event_channel,
    uint32_t             timestamp_us)
{
    if (engine == NULL) {
        return (uint16_t)0U;
    }
    engine->timestamp_now_us = timestamp_us;
    uint16_t emitted = (uint16_t)0U;
    uint8_t scratch[TETHYS_DAQ_MAX_DTO_BYTES];

    /* Bounded outer loop (compile-time constant). */
    for (uint8_t i = (uint8_t)0U; i < engine->list_count; ++i) {
        tethys_daq_list_t* const list = &engine->lists[i];
        if ((!list->allocated) || (!list->running)) {
            continue;
        }
        /* STIM-direction lists are master-driven; the slave's tick
         * doesn't emit anything for them. */
        if ((list->mode & TETHYS_DAQ_MODE_DIRECTION_STIM) != (uint8_t)0U) {
            continue;
        }
        if (list->event_channel != event_channel) {
            continue;
        }
        /* Prescaler: only fire every Nth matching tick (XCP 1.4
         * §1.4.2.6 prescaler field). */
        list->prescaler_counter = (uint8_t)(list->prescaler_counter + (uint8_t)1U);
        if (list->prescaler_counter < list->prescaler) {
            continue;
        }
        list->prescaler_counter = (uint8_t)0U;

        /* Bounded inner loop (compile-time constant). */
        for (uint8_t j = (uint8_t)0U; j < list->odt_count; ++j) {
            size_t len = (size_t)0U;
            if (tethys_daq_pack_dto(
                    engine, (uint16_t)i, j, scratch, sizeof scratch, &len) != 0) {
                /* Packing error - skip this DTO. The master will see
                 * the CTR gap and recover via its DAQ_GAP policy. */
                continue;
            }
            tethys_tr_status_t const tr =
                tethys_tr_send(scratch, len);
            if (tr != TETHYS_TR_OK) {
                /* TAL refused the frame. Stop emitting for this tick;
                 * the TAL has emitted its own LOSS event already. */
                return emitted;
            }
            emitted = (uint16_t)(emitted + (uint16_t)1U);
        }
    }
    return emitted;
}

/* ---- Diagnostic helpers ---------------------------------------------- */

tethys_daq_list_t const* tethys_daq_get_list(
    tethys_daq_engine_t const* engine,
    uint16_t                   daq_list_num)
{
    if (engine == NULL) {
        return NULL;
    }
    if (daq_list_num >= (uint16_t)engine->list_count) {
        return NULL;
    }
    return &engine->lists[daq_list_num];
}
