/*
 * src/core/xcp_odt.c - ODT (Object Descriptor Table) pack/unpack helpers.
 *
 * Module: tethys::core::xcp_odt
 * Profiles: all (marine, space, posix-sim)
 * Standards: ASAM XCP 1.4 Part 2 §1.4.1 (ODT model);
 *            MISRA C:2023 clean (mandatory + required);
 *            ECSS-E-ST-40C Rev.1 §5.4 (deterministic memory layout)
 * Trace: docs/traceability.csv (rows TETHYS-DES-0040..0044 land at PR-10)
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */
#include "tethys/xcp_odt.h"

#include <stddef.h>
#include <stdint.h>

/* ---- Bounds-check helper --------------------------------------------- */

/**
 * @brief True iff [address, address + length) lies fully inside memory.
 *
 * Defensive against u32 overflow at the high end of the address space.
 */
static bool span_in_memory(uint32_t address, size_t length, size_t memory_size)
{
    if (length == (size_t)0U) {
        return true;
    }
    if (address > (uint32_t)0xFFFFFFFFU - (uint32_t)length) {
        return false;
    }
    uint64_t const end = (uint64_t)address + (uint64_t)length;
    return end <= (uint64_t)memory_size;
}

/* ---- Public API ------------------------------------------------------- */

void tethys_odt_reset(tethys_odt_t* odt)
{
    if (odt == NULL) {
        return;
    }
    odt->entry_count = (uint8_t)0U;
    /* Bounded loop: TETHYS_DAQ_MAX_ENTRIES_PER_ODT is a compile-time constant. */
    for (uint8_t i = (uint8_t)0U; i < TETHYS_DAQ_MAX_ENTRIES_PER_ODT; ++i) {
        odt->entries[i].bit_offset     = TETHYS_DAQ_BIT_OFFSET_NONE;
        odt->entries[i].size_bytes     = (uint8_t)0U;
        odt->entries[i].addr_extension = (uint8_t)0U;
        odt->entries[i].in_use         = (uint8_t)0U;
        odt->entries[i].address        = (uint32_t)0U;
    }
}

int tethys_odt_pack(
    tethys_odt_t const* odt,
    uint8_t const*      memory,
    size_t              memory_size,
    uint8_t*            out_buffer,
    size_t              out_capacity,
    size_t*             out_offset)
{
    if ((odt == NULL) || (memory == NULL) || (out_buffer == NULL) || (out_offset == NULL)) {
        return -1;
    }
    if (odt->entry_count > TETHYS_DAQ_MAX_ENTRIES_PER_ODT) {
        return -1;
    }
    /* Bounded loop: entry_count <= TETHYS_DAQ_MAX_ENTRIES_PER_ODT (compile-time). */
    for (uint8_t i = (uint8_t)0U; i < odt->entry_count; ++i) {
        tethys_daq_entry_t const* const e = &odt->entries[i];
        if (e->in_use == (uint8_t)0U) {
            continue;
        }
        size_t const need = (size_t)e->size_bytes;
        if (!span_in_memory(e->address, need, memory_size)) {
            return -1;
        }
        if ((*out_offset > out_capacity) || ((out_capacity - *out_offset) < need)) {
            return -1;
        }
        /* Bounded copy: size_bytes <= 255 (u8). */
        for (uint8_t j = (uint8_t)0U; j < e->size_bytes; ++j) {
            out_buffer[*out_offset + (size_t)j] = memory[(size_t)e->address + (size_t)j];
        }
        *out_offset += need;
    }
    return 0;
}

int tethys_odt_unpack(
    tethys_odt_t const* odt,
    uint8_t*            memory,
    size_t              memory_size,
    uint8_t const*      in_buffer,
    size_t              in_size,
    size_t*             in_offset)
{
    if ((odt == NULL) || (memory == NULL) || (in_buffer == NULL) || (in_offset == NULL)) {
        return -1;
    }
    if (odt->entry_count > TETHYS_DAQ_MAX_ENTRIES_PER_ODT) {
        return -1;
    }
    for (uint8_t i = (uint8_t)0U; i < odt->entry_count; ++i) {
        tethys_daq_entry_t const* const e = &odt->entries[i];
        if (e->in_use == (uint8_t)0U) {
            continue;
        }
        size_t const need = (size_t)e->size_bytes;
        if (!span_in_memory(e->address, need, memory_size)) {
            return -1;
        }
        if ((*in_offset > in_size) || ((in_size - *in_offset) < need)) {
            return -1;
        }
        for (uint8_t j = (uint8_t)0U; j < e->size_bytes; ++j) {
            memory[(size_t)e->address + (size_t)j] = in_buffer[*in_offset + (size_t)j];
        }
        *in_offset += need;
    }
    return 0;
}
