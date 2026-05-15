/*
 * tethys/edac.h - SEC-DED Hamming(72,64) error-detection-and-correction
 * wrapper for the space profile.
 *
 * Module: tethys::edac
 * Profiles: space (mandatory per .cursor/rules/space-profile-invariants.mdc);
 *           marine (advisory; not used by default).
 * Standards:
 *   - R. W. Hamming, "Error detecting and error correcting codes," Bell
 *     System Technical Journal, vol. 29, pp. 147-160, 1950 (the original
 *     paper).
 *   - ECSS-E-ST-40C Rev.1 §5.4 - safety-critical SW process (the EDAC
 *     mechanism is one of the SEU-mitigation measures referenced).
 *   - NPR 7150.2D §SWE-080 - software safety analysis (SEU is one of the
 *     environmental hazards).
 *   - ADR-0002 - profile-based build system.
 *   - ADR-0005 - no dynamic allocation; EDAC operates on stack-passed values.
 *   - ADR-0010 §space rows - the EDAC bound feeds the CAL-page loss budget.
 *
 * Scheme: Hamming(72,64) SEC-DED.
 *   - 64 data bits (1 uint64_t word).
 *   - 8 parity bits in the high byte of a uint64_t codeword (when paired
 *     with the data uint64_t, the storage cost is 72 bits per 64 -> 12.5 %
 *     overhead per ADR-0005 §consequences).
 *   - 7 Hamming parity bits provide single-bit correction.
 *   - 1 overall parity bit promotes the scheme from SEC to SEC-DED (single-
 *     error correction + double-error detection).
 *
 * Why 64-bit words? Matches the natural CAL-page granularity on STM32H7's
 * 64-bit-wide flash (RM0433 §3 - flash organisation is 32 quad-word lines).
 * Each CAL page is a vector of uint64_t data + uint64_t parity stored
 * side-by-side; the decode loop is bounded by `CAL_PAGE_WORDS`.
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */
#ifndef TETHYS_EDAC_H
#define TETHYS_EDAC_H

#pragma once

#include "tethys/tethys_export.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Decode-result code returned by `tethys_edac_decode`.
 */
typedef enum
{
    /** Codeword passed both Hamming + overall-parity check. */
    TETHYS_EDAC_OK = 0,
    /** One bit flipped; corrected; out_data + out_corrected_bit valid. */
    TETHYS_EDAC_SINGLE_BIT_CORRECTED = 1,
    /** Two bits flipped; cannot correct; out_data is the raw best-effort. */
    TETHYS_EDAC_DOUBLE_BIT_DETECTED = 2
} tethys_edac_decode_result_t;

/**
 * @brief Compute the 8-bit Hamming SEC-DED parity for @p data.
 *
 * @param[in] data Caller's 64-bit datum.
 * @return Parity byte to store alongside @p data (only the low 8 bits matter;
 *         the upper 56 bits of the returned uint64_t are always zero).
 *
 * @safety MISRA C:2023 clean. Constant-time over @p data (bounded `for`
 *         loop; no data-dependent branches).
 */
TETHYS_EXPORT uint64_t tethys_edac_encode_parity(uint64_t data);

/**
 * @brief Decode a (data, parity) pair and report single/double-bit errors.
 *
 * @param[in]  data            64-bit datum read from storage.
 * @param[in]  parity          8-bit parity byte read alongside @p data
 *                             (low 8 bits used; upper bits ignored).
 * @param[out] out_data        Corrected datum on success / single-bit
 *                             correct. On double-bit detection it is the
 *                             un-corrected input (so caller can log it).
 *                             Must not be NULL.
 * @param[out] out_corrected_bit  On single-bit correct, the 0..71 bit
 *                                index that was flipped. Ignored on OK /
 *                                DOUBLE_BIT_DETECTED. May be NULL.
 *
 * @return One of `tethys_edac_decode_result_t`.
 *
 * @safety MISRA C:2023 clean. Bounded loops (max 8 iterations per parity
 *         column). No dynamic allocation.
 */
TETHYS_EXPORT tethys_edac_decode_result_t tethys_edac_decode(
    uint64_t   data,
    uint8_t    parity,
    uint64_t*  out_data,
    uint8_t*   out_corrected_bit);

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* TETHYS_EDAC_H */
