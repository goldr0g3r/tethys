/*
 * tethys/xcp_odt.h - ODT (Object Descriptor Table) static container.
 *
 * Module: tethys::core::xcp_odt
 * Profiles: all (marine, space, posix-sim)
 * Standards: ASAM XCP 1.4 Part 2 §1.4.1 (ODT model);
 *            MISRA C:2023; ECSS-E-ST-40C Rev.1 §5.4
 * Trace: docs/traceability.csv (rows TETHYS-DES-0040..0044 land at PR-10)
 *
 * An ODT (Object Descriptor Table) is a fixed-size list of element
 * references. Each entry binds (address, address-extension, size_bytes)
 * so the DAQ engine can pack the referenced bytes into one DTO frame on
 * each event-channel tick.
 *
 * Static sizing per ADR-0005 (no dynamic allocation):
 *   - TETHYS_DAQ_MAX_ENTRIES_PER_ODT entries per ODT (compile-time).
 *   - Storage lives in tethys_daq_engine_t (xcp_daq.h); this header
 *     declares the element-level types and the bounded helpers.
 *
 * Out of scope (deferred):
 *   - BIT_OFFSET-based packing of sub-byte signals (XCP 1.4 §1.4.2.2
 *     bit_offset field). Phase 3 stores the field on entries but the
 *     packer treats it as 0xFF "no bit packing" - per A2L MEASUREMENT
 *     BIT_MASK semantics already enforced master-side. Sub-byte
 *     packing lands when the first MEASUREMENT with BIT_MASK enters
 *     the marine workload (Phase 7).
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */
#ifndef TETHYS_XCP_ODT_H
#define TETHYS_XCP_ODT_H

#pragma once

#include "tethys/tethys_export.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ---- Static sizing constants (ADR-0005) ------------------------------- */

/** Max entries per ODT (compile-time). */
#define TETHYS_DAQ_MAX_ENTRIES_PER_ODT    ((uint8_t)16U)

/** Max ODTs per DAQ list (compile-time). */
#define TETHYS_DAQ_MAX_ODT_PER_LIST       ((uint8_t)8U)

/** Max DAQ lists per engine instance (compile-time). */
#define TETHYS_DAQ_MAX_LISTS              ((uint8_t)4U)

/** Max DTO payload bytes (PID + data) emitted by the engine. */
#define TETHYS_DAQ_MAX_DTO_BYTES          ((uint16_t)64U)

/** Sentinel BIT_OFFSET: no sub-byte packing (XCP 1.4 §1.4.2.2). */
#define TETHYS_DAQ_BIT_OFFSET_NONE        ((uint8_t)0xFFU)

/* ---- Per-entry types -------------------------------------------------- */

/**
 * @brief One ODT entry (element reference).
 *
 * Wire layout consumed by WRITE_DAQ (XCP 1.4 Part 2 §1.4.2.2):
 *   bit_offset (1B)  - 0xFF = no sub-byte packing
 *   size       (1B)  - element size in bytes (1..255)
 *   ext        (1B)  - address extension
 *   addr       (4B)  - element address (LE)
 *
 * In-memory layout is the same fields plus an `in_use` flag the engine
 * uses to skip unallocated entries. Total: 8 bytes per entry incl.
 * padding so the engine's static array packs predictably on
 * 32-bit + 64-bit hosts.
 */
typedef struct
{
    uint8_t  bit_offset;
    uint8_t  size_bytes;
    uint8_t  addr_extension;
    uint8_t  in_use;
    uint32_t address;
} tethys_daq_entry_t;

/**
 * @brief One ODT (Object Descriptor Table) - fixed array of entries.
 *
 * Static sizing per ADR-0005: the array length is
 * TETHYS_DAQ_MAX_ENTRIES_PER_ODT. ALLOC_ODT_ENTRY trims `entry_count`
 * down to the value the master sets; entries beyond `entry_count` are
 * always `in_use = false` and skipped during packing.
 */
typedef struct
{
    tethys_daq_entry_t entries[TETHYS_DAQ_MAX_ENTRIES_PER_ODT];
    uint8_t            entry_count;
} tethys_odt_t;

/* ---- Public API ------------------------------------------------------- */

/**
 * @brief Reset one ODT to the unallocated state.
 *
 * Clears `entry_count` and zeroes every entry's `in_use` flag. Idempotent.
 *
 * @param[out] odt Caller-owned ODT (typically inside a DAQ list).
 *
 * @pre odt != NULL
 */
TETHYS_EXPORT void tethys_odt_reset(tethys_odt_t* odt);

/**
 * @brief Pack the live entries of one ODT into a DTO scratch buffer.
 *
 * Iterates `entry_count` entries in order, reading `size_bytes` bytes
 * from the attached memory backend starting at each entry's address,
 * and concatenating into `out_buffer` after `out_offset` bytes already
 * written. The PID + optional timestamp prefix are NOT written by this
 * function - the DAQ engine handles those.
 *
 * @param[in]  odt        ODT to pack.
 * @param[in]  memory     Caller-owned memory backend (XCP RAM region).
 * @param[in]  memory_size Size of `memory` in bytes.
 * @param[in,out] out_buffer Scratch DTO buffer.
 * @param[in]  out_capacity Capacity of @p out_buffer in bytes.
 * @param[in,out] out_offset Number of bytes already written; advanced by
 *                            the number of payload bytes packed.
 *
 * @return 0 on success.
 * @return -1 if any entry's [address, address+size_bytes) lies outside
 *         the attached memory range or if @p out_buffer overflows.
 *         On error @p out_offset is left at whatever value it reached
 *         before the offending entry; the caller MUST discard the partial
 *         frame.
 *
 * @pre odt != NULL && memory != NULL && out_buffer != NULL && out_offset != NULL
 *
 * @safety Bounded loop (TETHYS_DAQ_MAX_ENTRIES_PER_ODT). No dynamic alloc.
 */
TETHYS_EXPORT int tethys_odt_pack(
    tethys_odt_t const* odt,
    uint8_t const*      memory,
    size_t              memory_size,
    uint8_t*            out_buffer,
    size_t              out_capacity,
    size_t*             out_offset);

/**
 * @brief Unpack a STIM DTO payload back into the attached memory backend.
 *
 * Inverse of @ref tethys_odt_pack. Walks the same entries in order and
 * writes the corresponding bytes from @p in_buffer (after `in_offset`)
 * into the memory backend at each entry's address.
 *
 * @param[in]  odt          ODT describing the packing layout (must match
 *                          the sender's DAQ-list configuration).
 * @param[in,out] memory    Caller-owned memory backend (XCP RAM region).
 * @param[in]  memory_size  Size of `memory` in bytes.
 * @param[in]  in_buffer    DTO payload (PID + optional timestamp already
 *                          stripped by the engine).
 * @param[in]  in_size      Length of @p in_buffer in bytes.
 * @param[in,out] in_offset Number of bytes already consumed; advanced by
 *                          the number of payload bytes unpacked.
 *
 * @return 0 on success, -1 on memory-range violation or buffer underrun.
 *
 * @pre odt != NULL && memory != NULL && in_buffer != NULL && in_offset != NULL
 *
 * @safety Bounded loop. No dynamic alloc.
 */
TETHYS_EXPORT int tethys_odt_unpack(
    tethys_odt_t const* odt,
    uint8_t*            memory,
    size_t              memory_size,
    uint8_t const*      in_buffer,
    size_t              in_size,
    size_t*             in_offset);

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* TETHYS_XCP_ODT_H */
