/*
 * test_edac.c - Unity tests for SEC-DED Hamming(72,64) EDAC.
 *
 * Verifies:
 *   - Encode/decode round-trip with no flipped bits returns OK.
 *   - Single-bit flip is corrected for every bit position in the codeword.
 *   - Representative double-bit flips are detected (not corrected).
 *
 * Standards trace:
 *   - tethys/edac.h public contract.
 *   - ADR-0005 - no dynamic allocation in test code either.
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */

#include "tethys/edac.h"
#include "unity.h"

#include <stdint.h>

void setUp(void)    { /* no-op */ }
void tearDown(void) { /* no-op */ }

/* A few representative data patterns to drive the round-trip tests. The
 * choice covers all-zeros, all-ones, alternating, and a "typical" payload. */
static uint64_t const tethys_edac_test_patterns_[] = {
    0x0000000000000000ULL,
    0xFFFFFFFFFFFFFFFFULL,
    0xAAAAAAAAAAAAAAAAULL,
    0x5555555555555555ULL,
    0x0123456789ABCDEFULL,
    0xDEADBEEFCAFEBABEULL,
    0x8000000000000001ULL,
};

#define TETHYS_EDAC_TEST_PATTERN_COUNT_  \
    (sizeof(tethys_edac_test_patterns_)/sizeof(tethys_edac_test_patterns_[0]))

void test_edac_roundtrip_no_errors_returns_ok(void)
{
    for (size_t p = 0U; p < TETHYS_EDAC_TEST_PATTERN_COUNT_; ++p)
    {
        uint64_t const data   = tethys_edac_test_patterns_[p];
        uint8_t  const parity = (uint8_t)tethys_edac_encode_parity(data);

        uint64_t recovered = 0U;
        uint8_t  corrected_bit = 0xFFU;
        tethys_edac_decode_result_t const r =
            tethys_edac_decode(data, parity, &recovered, &corrected_bit);

        TEST_ASSERT_EQUAL_HEX64(data, recovered);
        TEST_ASSERT_EQUAL_INT(TETHYS_EDAC_OK, r);
    }
}

void test_edac_single_bit_flip_in_data_is_corrected(void)
{
    /*
     * Flip every one of the 64 data-bit positions and verify the decoder
     * recovers the original data + reports SEC.
     */
    uint64_t const data   = 0x0123456789ABCDEFULL;
    uint8_t  const parity = (uint8_t)tethys_edac_encode_parity(data);

    for (uint8_t bit = 0U; bit < 64U; ++bit)
    {
        uint64_t corrupted = data ^ ((uint64_t)1U << bit);

        uint64_t recovered = 0U;
        uint8_t  corrected_bit = 0U;
        tethys_edac_decode_result_t const r =
            tethys_edac_decode(corrupted, parity, &recovered, &corrected_bit);

        TEST_ASSERT_EQUAL_INT_MESSAGE(TETHYS_EDAC_SINGLE_BIT_CORRECTED, r,
            "expected SEC for a single-bit data flip");
        TEST_ASSERT_EQUAL_HEX64_MESSAGE(data, recovered,
            "SEC corrected data does not match original");
    }
}

void test_edac_single_bit_flip_in_parity_is_corrected(void)
{
    /*
     * Flip each of the 7 Hamming parity bits + the overall-parity bit
     * (bit 7) and verify the decoder reports SEC and recovers data
     * unchanged.
     */
    uint64_t const data   = 0xDEADBEEFCAFEBABEULL;
    uint8_t  const parity = (uint8_t)tethys_edac_encode_parity(data);

    for (uint8_t bit = 0U; bit < 8U; ++bit)
    {
        uint8_t const corrupted_parity = (uint8_t)(parity ^ (uint8_t)(1U << bit));

        uint64_t recovered = 0U;
        uint8_t  corrected_bit = 0U;
        tethys_edac_decode_result_t const r =
            tethys_edac_decode(data, corrupted_parity, &recovered, &corrected_bit);

        TEST_ASSERT_EQUAL_INT_MESSAGE(TETHYS_EDAC_SINGLE_BIT_CORRECTED, r,
            "expected SEC for a single-bit parity flip");
        TEST_ASSERT_EQUAL_HEX64_MESSAGE(data, recovered,
            "SEC parity flip should not change data");
    }
}

void test_edac_double_bit_flip_is_detected(void)
{
    /*
     * Representative pairs: two data bits, two parity bits, one data + one
     * parity. All should report TETHYS_EDAC_DOUBLE_BIT_DETECTED.
     */
    uint64_t const data   = 0xDEADBEEFCAFEBABEULL;
    uint8_t  const parity = (uint8_t)tethys_edac_encode_parity(data);

    struct double_flip
    {
        uint8_t bit_a; /* 0..71: 0..63 data, 64..71 parity */
        uint8_t bit_b;
    };
    static struct double_flip const cases[] = {
        { 0U, 1U },    /* two data bits, adjacent */
        { 5U, 50U },   /* two data bits, far apart */
        { 64U, 65U },  /* two parity bits */
        { 3U, 66U },   /* one data + one parity */
        { 31U, 32U },  /* boundary */
    };
    size_t const n = sizeof(cases) / sizeof(cases[0]);

    for (size_t i = 0U; i < n; ++i)
    {
        uint64_t corrupted_data   = data;
        uint8_t  corrupted_parity = parity;
        uint8_t const a = cases[i].bit_a;
        uint8_t const b = cases[i].bit_b;

        if (a < 64U) { corrupted_data ^= ((uint64_t)1U << a); }
        else         { corrupted_parity = (uint8_t)(corrupted_parity ^ (uint8_t)(1U << (a - 64U))); }

        if (b < 64U) { corrupted_data ^= ((uint64_t)1U << b); }
        else         { corrupted_parity = (uint8_t)(corrupted_parity ^ (uint8_t)(1U << (b - 64U))); }

        uint64_t recovered = 0U;
        uint8_t  corrected_bit = 0U;
        tethys_edac_decode_result_t const r =
            tethys_edac_decode(corrupted_data, corrupted_parity,
                                &recovered, &corrected_bit);

        TEST_ASSERT_EQUAL_INT_MESSAGE(TETHYS_EDAC_DOUBLE_BIT_DETECTED, r,
            "expected DED for a representative two-bit flip");
    }
}
