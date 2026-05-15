/*
 * src/profiles/space/edac.c - SEC-DED Hamming(72,64) implementation.
 *
 * Module: tethys::edac
 * Profiles: space.
 * Standards:
 *   - R. W. Hamming, "Error detecting and error correcting codes," Bell
 *     System Technical Journal, vol. 29, pp. 147-160, 1950.
 *   - ECSS-E-ST-40C Rev.1 §5.4.
 *   - ADR-0005 - no dynamic allocation.
 *   - .cursor/rules/no-recursion-no-goto.mdc - bounded loops; no goto.
 *
 * Scheme - shortened SEC-DED Hamming(72,64) with separate-storage parity:
 *
 *   Logical codeword positions: 1..71 (position 0 unused, used to zero the
 *   syndrome on the clean case).
 *
 *   Positions 1, 2, 4, 8, 16, 32, 64 hold the seven Hamming parity bits
 *   P0..P6. Position 7 is unused (would be P3 in a wider code; we use only
 *   7 parity bits for 64 data bits).
 *
 *   Hmm wait - 2^7 - 1 = 127 codeword positions; 7 of those are parity =>
 *   120 data positions max. We only need 64 of those 120; the rest are
 *   "shortened" out (treated as zero data). So our 64 data bits map to the
 *   first 64 non-power-of-two positions in 1..71. That is positions:
 *   3, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15, 17, 18, 19, 20, 21, 22, 23, 24,
 *   25, 26, 27, 28, 29, 30, 31, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43,
 *   44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61,
 *   62, 63, 65, 66, 67, 68, 69, 70, 71. (64 positions)
 *
 *   For each parity bit p in {0..6}, parity_p XORs all data bits whose
 *   codeword position has bit p set.
 *
 *   The 8th parity bit (P7 in the parity byte) is the overall-parity bit,
 *   the XOR of all data bits XOR all 7 Hamming parity bits. Promotes
 *   SEC to SEC-DED (single-error correction + double-error detection).
 *
 *   Decoding:
 *     1. Recompute the 8 parity bits from `data`.
 *     2. XOR with received parity -> 8-bit syndrome (7-bit Hamming
 *        syndrome + 1-bit overall syndrome).
 *     3. If syndrome == 0: TETHYS_EDAC_OK.
 *     4. If hamming_syndrome != 0 AND overall_syndrome != 0:
 *        TETHYS_EDAC_SINGLE_BIT_CORRECTED. hamming_syndrome IS the
 *        codeword position of the flipped bit. If that codeword position
 *        is one of {1,2,4,8,16,32,64} the flipped bit is a parity bit
 *        (data unchanged). Otherwise look up the data-bit index via the
 *        `codeword_to_data_idx` reverse map.
 *     5. Else (hamming_syndrome != 0 AND overall_syndrome == 0, or
 *        hamming_syndrome == 0 AND overall_syndrome != 0):
 *        TETHYS_EDAC_DOUBLE_BIT_DETECTED.
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */

#include "tethys/edac.h"

#include <stdbool.h>
#include <stdint.h>

/* ---- Codeword-position table for the 64 data bits ----------------------- *
 *
 * data_to_codeword_[k] = logical codeword position of data bit k.
 * Sequence: skip codeword positions that are powers of two (1, 2, 4, 8, 16,
 * 32, 64); the rest map in order to data bits 0..63.
 */
static uint8_t const tethys_edac_data_to_codeword_[64] = {
    /*  0 */  3,  5,  6,  7,  9, 10, 11, 12,
    /*  8 */ 13, 14, 15, 17, 18, 19, 20, 21,
    /* 16 */ 22, 23, 24, 25, 26, 27, 28, 29,
    /* 24 */ 30, 31, 33, 34, 35, 36, 37, 38,
    /* 32 */ 39, 40, 41, 42, 43, 44, 45, 46,
    /* 40 */ 47, 48, 49, 50, 51, 52, 53, 54,
    /* 48 */ 55, 56, 57, 58, 59, 60, 61, 62,
    /* 56 */ 63, 65, 66, 67, 68, 69, 70, 71,
};

/* Reverse map: codeword position (1..71) -> data-bit index (0..63), or 0xFF
 * if the codeword position is a parity-bit slot. Indexed by codeword
 * position directly (size 72; position 0 + parity-bit slots use 0xFF). */
static uint8_t const tethys_edac_codeword_to_data_idx_[72] = {
    /* cw 0..7   */ 0xFFU, 0xFFU, 0xFFU,    0U,   0xFFU,    1U,    2U,    3U,
    /* cw 8..15  */ 0xFFU,    4U,    5U,    6U,      7U,    8U,    9U,   10U,
    /* cw 16..23 */ 0xFFU,   11U,   12U,   13U,     14U,   15U,   16U,   17U,
    /* cw 24..31 */   18U,   19U,   20U,   21U,     22U,   23U,   24U,   25U,
    /* cw 32..39 */ 0xFFU,   26U,   27U,   28U,     29U,   30U,   31U,   32U,
    /* cw 40..47 */   33U,   34U,   35U,   36U,     37U,   38U,   39U,   40U,
    /* cw 48..55 */   41U,   42U,   43U,   44U,     45U,   46U,   47U,   48U,
    /* cw 56..63 */   49U,   50U,   51U,   52U,     53U,   54U,   55U,   56U,
    /* cw 64..71 */ 0xFFU,   57U,   58U,   59U,     60U,   61U,   62U,   63U,
};

/* ---- Helpers ------------------------------------------------------------ */

static inline uint8_t tethys_edac_xor_parity64_(uint64_t v)
{
    v ^= v >> 32;
    v ^= v >> 16;
    v ^= v >> 8;
    v ^= v >> 4;
    v ^= v >> 2;
    v ^= v >> 1;
    return (uint8_t)(v & 1U);
}

/* Compute the 7 Hamming parity bits from `data`. Returns a 7-bit value in
 * the low bits of the result. */
static uint8_t tethys_edac_compute_hamming_(uint64_t data)
{
    uint8_t hamming = 0U;
    for (uint8_t p = 0U; p < 7U; ++p)
    {
        uint64_t mask = 0U;
        /* Build the mask of data bits whose codeword position has bit p set. */
        for (uint8_t k = 0U; k < 64U; ++k)
        {
            uint8_t const cwpos = tethys_edac_data_to_codeword_[k];
            if (((cwpos >> p) & 1U) != 0U)
            {
                mask |= ((uint64_t)1U << k);
            }
        }
        uint8_t const bit = tethys_edac_xor_parity64_(data & mask);
        hamming = (uint8_t)(hamming | (uint8_t)(bit << p));
    }
    return hamming;
}

/* ---- Encode ------------------------------------------------------------- */

uint64_t tethys_edac_encode_parity(uint64_t data)
{
    uint8_t const hamming = tethys_edac_compute_hamming_(data);
    /* Overall parity bit = XOR of all data + all 7 Hamming bits. */
    uint8_t const overall =
        (uint8_t)(tethys_edac_xor_parity64_(data)
                ^ tethys_edac_xor_parity64_((uint64_t)hamming));
    return (uint64_t)((uint8_t)(hamming | (uint8_t)(overall << 7)));
}

/* ---- Decode ------------------------------------------------------------- */

tethys_edac_decode_result_t tethys_edac_decode(
    uint64_t   data,
    uint8_t    parity,
    uint64_t*  out_data,
    uint8_t*   out_corrected_bit)
{
    if (out_data == NULL)
    {
        return TETHYS_EDAC_OK;
    }

    /*
     * Hamming syndrome: XOR of the 7 Hamming parity bits computed from the
     * received data with the 7 Hamming parity bits received in storage. If
     * any single bit (data or Hamming) flipped, this syndrome equals the
     * codeword position of that bit (0 if no flip).
     */
    uint8_t  const expected_hamming = tethys_edac_compute_hamming_(data);
    uint8_t  const received_hamming = (uint8_t)(parity & 0x7FU);
    uint8_t  const hamming_syndrome = (uint8_t)(received_hamming ^ expected_hamming);

    /*
     * Overall syndrome T: XOR of ALL 72 received bits (64 data + 8 parity).
     * Encoder set the overall-parity bit (bit 7 of `parity`) so this XOR
     * equals 0 for an unchanged codeword. Therefore:
     *   T = 0 if 0 or 2 bits flipped
     *   T = 1 if 1 bit flipped (anywhere - data, Hamming, or overall)
     */
    uint8_t const overall_syndrome =
        (uint8_t)(tethys_edac_xor_parity64_(data)
                ^ tethys_edac_xor_parity64_((uint64_t)parity));

    if ((hamming_syndrome == 0U) && (overall_syndrome == 0U))
    {
        *out_data = data;
        return TETHYS_EDAC_OK;
    }

    if (overall_syndrome != 0U)
    {
        /*
         * Single bit flipped.
         *   - hamming_syndrome == 0 -> the overall-parity bit itself flipped.
         *     Data + Hamming bits unchanged.
         *   - hamming_syndrome != 0 -> the bit at codeword position
         *     `hamming_syndrome` flipped. If that names a data-bit slot
         *     (per codeword_to_data_idx_), flip the corresponding data bit.
         *     Otherwise (parity-bit slot) data is unchanged.
         */
        uint64_t corrected = data;
        uint8_t  bit_idx   = (uint8_t)(0x80U); /* sentinel "parity-bit flip" */
        if (hamming_syndrome != 0U && hamming_syndrome < 72U)
        {
            uint8_t const data_idx = tethys_edac_codeword_to_data_idx_[hamming_syndrome];
            if (data_idx != 0xFFU)
            {
                corrected ^= ((uint64_t)1U << data_idx);
                bit_idx = data_idx;
            }
        }
        *out_data = corrected;
        if (out_corrected_bit != NULL)
        {
            *out_corrected_bit = bit_idx;
        }
        return TETHYS_EDAC_SINGLE_BIT_CORRECTED;
    }

    /* hamming_syndrome != 0 AND overall_syndrome == 0 -> double-bit. */
    *out_data = data;
    return TETHYS_EDAC_DOUBLE_BIT_DETECTED;
}
