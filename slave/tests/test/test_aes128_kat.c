/*
 * test_aes128_kat.c - Unity tests for AES-128 against NIST FIPS-197
 * Appendix B + C known-answer vectors.
 *
 * Verifies:
 *   - Key expansion matches FIPS-197 Appendix A.1 round-keys for the
 *     standard AES-128 key.
 *   - Encrypt-block matches FIPS-197 Appendix B (the worked example).
 *   - Encrypt-block matches FIPS-197 Appendix C.1 (additional KAT).
 *   - verify_response returns true for the correct response, false for
 *     any single-byte modification.
 *
 * Standards trace:
 *   - NIST FIPS-197 §A.1 (key expansion example).
 *   - NIST FIPS-197 §B (cipher example).
 *   - NIST FIPS-197 §C.1 (AES-128 monte-carlo seed).
 *   - tethys/aes128_seed_and_key.h public contract.
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */

#include "tethys/aes128_seed_and_key.h"
#include "unity.h"

#include <stdbool.h>
#include <stdint.h>
#include <string.h>

void setUp(void)    { /* no-op */ }
void tearDown(void) { /* no-op */ }

/* ---- FIPS-197 Appendix A.1: AES-128 key expansion ----------------------- *
 *
 * Key:     2b 7e 15 16 28 ae d2 a6 ab f7 15 88 09 cf 4f 3c
 *
 * Expected first 4 + last 4 round-key words (big-endian; matches FIPS-197
 * §A.1 Figure 6):
 *   w[0]=2b7e1516 w[1]=28aed2a6 w[2]=abf71588 w[3]=09cf4f3c
 *   w[40]=d014f9a8 w[41]=c9ee2589 w[42]=e13f0cc8 w[43]=b6630ca6
 */

void test_aes128_key_expansion_matches_fips197_appendix_a1(void)
{
    static uint8_t const key[16] = {
        0x2BU, 0x7EU, 0x15U, 0x16U, 0x28U, 0xAEU, 0xD2U, 0xA6U,
        0xABU, 0xF7U, 0x15U, 0x88U, 0x09U, 0xCFU, 0x4FU, 0x3CU
    };
    uint32_t round_keys[TETHYS_AES128_ROUND_KEY_WORDS];

    tethys_aes128_key_schedule(key, round_keys);

    TEST_ASSERT_EQUAL_HEX32(0x2B7E1516U, round_keys[0]);
    TEST_ASSERT_EQUAL_HEX32(0x28AED2A6U, round_keys[1]);
    TEST_ASSERT_EQUAL_HEX32(0xABF71588U, round_keys[2]);
    TEST_ASSERT_EQUAL_HEX32(0x09CF4F3CU, round_keys[3]);

    TEST_ASSERT_EQUAL_HEX32(0xD014F9A8U, round_keys[40]);
    TEST_ASSERT_EQUAL_HEX32(0xC9EE2589U, round_keys[41]);
    TEST_ASSERT_EQUAL_HEX32(0xE13F0CC8U, round_keys[42]);
    TEST_ASSERT_EQUAL_HEX32(0xB6630CA6U, round_keys[43]);
}

/* ---- FIPS-197 Appendix B: cipher example -------------------------------- *
 *
 * Input:      32 43 f6 a8 88 5a 30 8d 31 31 98 a2 e0 37 07 34
 * Cipher key: 2b 7e 15 16 28 ae d2 a6 ab f7 15 88 09 cf 4f 3c
 * Output:     39 25 84 1d 02 dc 09 fb dc 11 85 97 19 6a 0b 32
 */
void test_aes128_encrypt_block_matches_fips197_appendix_b(void)
{
    static uint8_t const input[16] = {
        0x32U, 0x43U, 0xF6U, 0xA8U, 0x88U, 0x5AU, 0x30U, 0x8DU,
        0x31U, 0x31U, 0x98U, 0xA2U, 0xE0U, 0x37U, 0x07U, 0x34U
    };
    static uint8_t const key[16] = {
        0x2BU, 0x7EU, 0x15U, 0x16U, 0x28U, 0xAEU, 0xD2U, 0xA6U,
        0xABU, 0xF7U, 0x15U, 0x88U, 0x09U, 0xCFU, 0x4FU, 0x3CU
    };
    static uint8_t const expected[16] = {
        0x39U, 0x25U, 0x84U, 0x1DU, 0x02U, 0xDCU, 0x09U, 0xFBU,
        0xDCU, 0x11U, 0x85U, 0x97U, 0x19U, 0x6AU, 0x0BU, 0x32U
    };

    uint32_t round_keys[TETHYS_AES128_ROUND_KEY_WORDS];
    uint8_t  output[16] = {0};

    tethys_aes128_key_schedule(key, round_keys);
    tethys_aes128_encrypt_block(round_keys, input, output);

    TEST_ASSERT_EQUAL_HEX8_ARRAY(expected, output, 16);
}

/* ---- FIPS-197 Appendix C.1: AES-128 KAT --------------------------------- *
 *
 * Input:      00 11 22 33 44 55 66 77 88 99 aa bb cc dd ee ff
 * Cipher key: 00 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f
 * Output:     69 c4 e0 d8 6a 7b 04 30 d8 cd b7 80 70 b4 c5 5a
 */
void test_aes128_encrypt_block_matches_fips197_appendix_c1(void)
{
    static uint8_t const input[16] = {
        0x00U, 0x11U, 0x22U, 0x33U, 0x44U, 0x55U, 0x66U, 0x77U,
        0x88U, 0x99U, 0xAAU, 0xBBU, 0xCCU, 0xDDU, 0xEEU, 0xFFU
    };
    static uint8_t const key[16] = {
        0x00U, 0x01U, 0x02U, 0x03U, 0x04U, 0x05U, 0x06U, 0x07U,
        0x08U, 0x09U, 0x0AU, 0x0BU, 0x0CU, 0x0DU, 0x0EU, 0x0FU
    };
    static uint8_t const expected[16] = {
        0x69U, 0xC4U, 0xE0U, 0xD8U, 0x6AU, 0x7BU, 0x04U, 0x30U,
        0xD8U, 0xCDU, 0xB7U, 0x80U, 0x70U, 0xB4U, 0xC5U, 0x5AU
    };

    uint32_t round_keys[TETHYS_AES128_ROUND_KEY_WORDS];
    uint8_t  output[16] = {0};

    tethys_aes128_key_schedule(key, round_keys);
    tethys_aes128_encrypt_block(round_keys, input, output);

    TEST_ASSERT_EQUAL_HEX8_ARRAY(expected, output, 16);
}

/* ---- verify_response acceptance ----------------------------------------- */

void test_aes128_verify_response_accepts_correct_response(void)
{
    static uint8_t const seed[16] = {
        0x32U, 0x43U, 0xF6U, 0xA8U, 0x88U, 0x5AU, 0x30U, 0x8DU,
        0x31U, 0x31U, 0x98U, 0xA2U, 0xE0U, 0x37U, 0x07U, 0x34U
    };
    static uint8_t const key[16] = {
        0x2BU, 0x7EU, 0x15U, 0x16U, 0x28U, 0xAEU, 0xD2U, 0xA6U,
        0xABU, 0xF7U, 0x15U, 0x88U, 0x09U, 0xCFU, 0x4FU, 0x3CU
    };
    /* Master would compute this; we hard-code the FIPS-197 Appendix B answer. */
    static uint8_t const correct_response[16] = {
        0x39U, 0x25U, 0x84U, 0x1DU, 0x02U, 0xDCU, 0x09U, 0xFBU,
        0xDCU, 0x11U, 0x85U, 0x97U, 0x19U, 0x6AU, 0x0BU, 0x32U
    };
    TEST_ASSERT_TRUE(tethys_aes128_verify_response(seed, correct_response, key));
}

void test_aes128_verify_response_rejects_modified_byte(void)
{
    static uint8_t const seed[16] = {
        0x32U, 0x43U, 0xF6U, 0xA8U, 0x88U, 0x5AU, 0x30U, 0x8DU,
        0x31U, 0x31U, 0x98U, 0xA2U, 0xE0U, 0x37U, 0x07U, 0x34U
    };
    static uint8_t const key[16] = {
        0x2BU, 0x7EU, 0x15U, 0x16U, 0x28U, 0xAEU, 0xD2U, 0xA6U,
        0xABU, 0xF7U, 0x15U, 0x88U, 0x09U, 0xCFU, 0x4FU, 0x3CU
    };
    static uint8_t const correct_response[16] = {
        0x39U, 0x25U, 0x84U, 0x1DU, 0x02U, 0xDCU, 0x09U, 0xFBU,
        0xDCU, 0x11U, 0x85U, 0x97U, 0x19U, 0x6AU, 0x0BU, 0x32U
    };

    /*
     * Flip one bit in each byte position and verify the slave rejects.
     * The constant-time loop in verify_response means every byte position
     * gets the same execution path; a timing-side-channel attacker cannot
     * distinguish.
     */
    for (size_t pos = 0U; pos < 16U; ++pos)
    {
        uint8_t bad[16];
        (void)memcpy(bad, correct_response, sizeof(bad));
        bad[pos] = (uint8_t)(bad[pos] ^ 0x01U);
        TEST_ASSERT_FALSE_MESSAGE(
            tethys_aes128_verify_response(seed, bad, key),
            "verify_response must reject any single-byte modification");
    }
}

void test_aes128_verify_response_rejects_wrong_key(void)
{
    static uint8_t const seed[16] = {
        0x32U, 0x43U, 0xF6U, 0xA8U, 0x88U, 0x5AU, 0x30U, 0x8DU,
        0x31U, 0x31U, 0x98U, 0xA2U, 0xE0U, 0x37U, 0x07U, 0x34U
    };
    static uint8_t const wrong_key[16] = {
        0xFFU, 0xFFU, 0xFFU, 0xFFU, 0xFFU, 0xFFU, 0xFFU, 0xFFU,
        0xFFU, 0xFFU, 0xFFU, 0xFFU, 0xFFU, 0xFFU, 0xFFU, 0xFFU
    };
    static uint8_t const response_for_real_key[16] = {
        0x39U, 0x25U, 0x84U, 0x1DU, 0x02U, 0xDCU, 0x09U, 0xFBU,
        0xDCU, 0x11U, 0x85U, 0x97U, 0x19U, 0x6AU, 0x0BU, 0x32U
    };
    TEST_ASSERT_FALSE(tethys_aes128_verify_response(seed,
                                                     response_for_real_key,
                                                     wrong_key));
}
