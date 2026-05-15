/*
 * src/security/aes128_seed_and_key.c - clean-room AES-128 (FIPS-197) for
 * the XCP authenticated service-mode unlock.
 *
 * Module: tethys::security::aes128_seed_and_key
 * Profiles: space (mandatory per ADR-0006), marine (optional).
 * Standards:
 *   - NIST FIPS-197 (AES) §5.1 (encryption), §5.2 (key expansion).
 *   - ASAM XCP 1.4 Part 2 §1.3 (seed-and-key generic mechanism).
 *   - ADR-0005 - no dynamic allocation; everything lives on caller's stack
 *     or in caller-owned arrays.
 *   - ADR-0006 - the wider seed-and-key scheme this primitive serves.
 *   - .cursor/rules/no-recursion-no-goto.mdc - all loops bounded; no goto.
 *
 * Why a clean-room implementation rather than vendor tiny-AES-c?
 *   1. Tighter ownership: every line traces directly into FIPS-197 §sections.
 *   2. No LICENSE-vendoring decision (tiny-AES-c is public domain, which is
 *      fine, but introduces an extra audit step at PR-time).
 *   3. The implementation is ~250 lines + tables; not a meaningful
 *      maintenance burden.
 *   4. tiny-AES-c remains the documented fallback per the worker brief's
 *      stop-condition 3: "AES impl fails MISRA = use tiny-AES-c vendor".
 *
 * The implementation follows FIPS-197 exactly:
 *   - SubBytes / InvSubBytes use the 256-byte tables from §5.1.1 (Figure 7).
 *   - ShiftRows is in-place row rotation per §5.1.2.
 *   - MixColumns uses xtime() per §4.2.1 (multiplication by x in GF(2^8)).
 *   - KeyExpansion follows §5.2 (Algorithm 1).
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */

#include "tethys/aes128_seed_and_key.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

/* ---- FIPS-197 §5.1.1 Figure 7: S-box --------------------------------------
 *
 * The forward substitution box (S-box). Inverse S-box is NOT included
 * because tethys does not need decrypt() per ADR-0006 (slave verifies the
 * master's encrypted response by encrypting its OWN seed with its OWN key
 * and comparing - no decrypt path).
 */
static uint8_t const tethys_aes_sbox_[256] = {
    0x63U, 0x7CU, 0x77U, 0x7BU, 0xF2U, 0x6BU, 0x6FU, 0xC5U,
    0x30U, 0x01U, 0x67U, 0x2BU, 0xFEU, 0xD7U, 0xABU, 0x76U,
    0xCAU, 0x82U, 0xC9U, 0x7DU, 0xFAU, 0x59U, 0x47U, 0xF0U,
    0xADU, 0xD4U, 0xA2U, 0xAFU, 0x9CU, 0xA4U, 0x72U, 0xC0U,
    0xB7U, 0xFDU, 0x93U, 0x26U, 0x36U, 0x3FU, 0xF7U, 0xCCU,
    0x34U, 0xA5U, 0xE5U, 0xF1U, 0x71U, 0xD8U, 0x31U, 0x15U,
    0x04U, 0xC7U, 0x23U, 0xC3U, 0x18U, 0x96U, 0x05U, 0x9AU,
    0x07U, 0x12U, 0x80U, 0xE2U, 0xEBU, 0x27U, 0xB2U, 0x75U,
    0x09U, 0x83U, 0x2CU, 0x1AU, 0x1BU, 0x6EU, 0x5AU, 0xA0U,
    0x52U, 0x3BU, 0xD6U, 0xB3U, 0x29U, 0xE3U, 0x2FU, 0x84U,
    0x53U, 0xD1U, 0x00U, 0xEDU, 0x20U, 0xFCU, 0xB1U, 0x5BU,
    0x6AU, 0xCBU, 0xBEU, 0x39U, 0x4AU, 0x4CU, 0x58U, 0xCFU,
    0xD0U, 0xEFU, 0xAAU, 0xFBU, 0x43U, 0x4DU, 0x33U, 0x85U,
    0x45U, 0xF9U, 0x02U, 0x7FU, 0x50U, 0x3CU, 0x9FU, 0xA8U,
    0x51U, 0xA3U, 0x40U, 0x8FU, 0x92U, 0x9DU, 0x38U, 0xF5U,
    0xBCU, 0xB6U, 0xDAU, 0x21U, 0x10U, 0xFFU, 0xF3U, 0xD2U,
    0xCDU, 0x0CU, 0x13U, 0xECU, 0x5FU, 0x97U, 0x44U, 0x17U,
    0xC4U, 0xA7U, 0x7EU, 0x3DU, 0x64U, 0x5DU, 0x19U, 0x73U,
    0x60U, 0x81U, 0x4FU, 0xDCU, 0x22U, 0x2AU, 0x90U, 0x88U,
    0x46U, 0xEEU, 0xB8U, 0x14U, 0xDEU, 0x5EU, 0x0BU, 0xDBU,
    0xE0U, 0x32U, 0x3AU, 0x0AU, 0x49U, 0x06U, 0x24U, 0x5CU,
    0xC2U, 0xD3U, 0xACU, 0x62U, 0x91U, 0x95U, 0xE4U, 0x79U,
    0xE7U, 0xC8U, 0x37U, 0x6DU, 0x8DU, 0xD5U, 0x4EU, 0xA9U,
    0x6CU, 0x56U, 0xF4U, 0xEAU, 0x65U, 0x7AU, 0xAEU, 0x08U,
    0xBAU, 0x78U, 0x25U, 0x2EU, 0x1CU, 0xA6U, 0xB4U, 0xC6U,
    0xE8U, 0xDDU, 0x74U, 0x1FU, 0x4BU, 0xBDU, 0x8BU, 0x8AU,
    0x70U, 0x3EU, 0xB5U, 0x66U, 0x48U, 0x03U, 0xF6U, 0x0EU,
    0x61U, 0x35U, 0x57U, 0xB9U, 0x86U, 0xC1U, 0x1DU, 0x9EU,
    0xE1U, 0xF8U, 0x98U, 0x11U, 0x69U, 0xD9U, 0x8EU, 0x94U,
    0x9BU, 0x1EU, 0x87U, 0xE9U, 0xCEU, 0x55U, 0x28U, 0xDFU,
    0x8CU, 0xA1U, 0x89U, 0x0DU, 0xBFU, 0xE6U, 0x42U, 0x68U,
    0x41U, 0x99U, 0x2DU, 0x0FU, 0xB0U, 0x54U, 0xBBU, 0x16U,
};

/* ---- FIPS-197 §5.2 Rcon array (round constants) -------------------------- */

static uint8_t const tethys_aes_rcon_[11] = {
    0x00U, 0x01U, 0x02U, 0x04U, 0x08U,
    0x10U, 0x20U, 0x40U, 0x80U, 0x1BU, 0x36U,
};

/* ---- Helpers ------------------------------------------------------------ */

/* Multiplication by x (i.e. {02}) in GF(2^8) using the AES reduction
 * polynomial m(x) = x^8 + x^4 + x^3 + x + 1 (0x1B). FIPS-197 §4.2.1. */
static inline uint8_t tethys_aes_xtime_(uint8_t b)
{
    uint8_t const mask = (uint8_t)(((b & 0x80U) != 0U) ? 0x1BU : 0x00U);
    return (uint8_t)(((uint8_t)(b << 1)) ^ mask);
}

/* ---- KeyExpansion (FIPS-197 §5.2) ---------------------------------------- */

void tethys_aes128_key_schedule(
    uint8_t const  key[TETHYS_AES128_KEY_SIZE],
    uint32_t       round_keys[TETHYS_AES128_ROUND_KEY_WORDS])
{
    /* First 4 words come straight from the key (big-endian 32-bit packing
     * per FIPS-197 §5.2). */
    for (size_t i = 0U; i < 4U; ++i)
    {
        round_keys[i] = ((uint32_t)key[(4U * i) + 0U] << 24)
                      | ((uint32_t)key[(4U * i) + 1U] << 16)
                      | ((uint32_t)key[(4U * i) + 2U] <<  8)
                      | ((uint32_t)key[(4U * i) + 3U]);
    }

    for (size_t i = 4U; i < TETHYS_AES128_ROUND_KEY_WORDS; ++i)
    {
        uint32_t temp = round_keys[i - 1U];
        if ((i % 4U) == 0U)
        {
            /*
             * RotWord: rotate left by one byte (FIPS-197 §5.2).
             * SubWord:   apply S-box to each byte.
             * XOR with Rcon[i/4] (only affects high byte).
             */
            uint32_t const rotated = ((temp << 8) | (temp >> 24));
            uint8_t const b0 = (uint8_t)((rotated >> 24) & 0xFFU);
            uint8_t const b1 = (uint8_t)((rotated >> 16) & 0xFFU);
            uint8_t const b2 = (uint8_t)((rotated >>  8) & 0xFFU);
            uint8_t const b3 = (uint8_t)(rotated         & 0xFFU);
            temp = ((uint32_t)tethys_aes_sbox_[b0] << 24)
                 | ((uint32_t)tethys_aes_sbox_[b1] << 16)
                 | ((uint32_t)tethys_aes_sbox_[b2] <<  8)
                 | ((uint32_t)tethys_aes_sbox_[b3]);
            temp ^= ((uint32_t)tethys_aes_rcon_[i / 4U]) << 24;
        }
        round_keys[i] = round_keys[i - 4U] ^ temp;
    }
}

/* ---- AddRoundKey (FIPS-197 §5.1.4) --------------------------------------- */

static void tethys_aes_add_round_key_(uint8_t state[16], uint32_t const* rk)
{
    for (size_t c = 0U; c < 4U; ++c)
    {
        state[(4U * c) + 0U] ^= (uint8_t)((rk[c] >> 24) & 0xFFU);
        state[(4U * c) + 1U] ^= (uint8_t)((rk[c] >> 16) & 0xFFU);
        state[(4U * c) + 2U] ^= (uint8_t)((rk[c] >>  8) & 0xFFU);
        state[(4U * c) + 3U] ^= (uint8_t)(rk[c]         & 0xFFU);
    }
}

/* ---- SubBytes (FIPS-197 §5.1.1) ------------------------------------------ */

static void tethys_aes_sub_bytes_(uint8_t state[16])
{
    for (size_t i = 0U; i < 16U; ++i)
    {
        state[i] = tethys_aes_sbox_[state[i]];
    }
}

/* ---- ShiftRows (FIPS-197 §5.1.2) ----------------------------------------- *
 *
 * State is stored column-major: byte (r, c) lives at state[4*c + r].
 * Row 0 unchanged; row r shifts left by r (cyclically) over the 4 columns.
 */
static void tethys_aes_shift_rows_(uint8_t state[16])
{
    uint8_t tmp;

    /* Row 1 left-shift by 1: (s[1], s[5], s[9], s[13]) -> (s[5], s[9], s[13], s[1]) */
    tmp      = state[1];
    state[1] = state[5];
    state[5] = state[9];
    state[9] = state[13];
    state[13]= tmp;

    /* Row 2 left-shift by 2: swap pairs */
    tmp      = state[2];
    state[2] = state[10];
    state[10]= tmp;
    tmp      = state[6];
    state[6] = state[14];
    state[14]= tmp;

    /* Row 3 left-shift by 3 (== right-shift by 1) */
    tmp      = state[15];
    state[15]= state[11];
    state[11]= state[7];
    state[7] = state[3];
    state[3] = tmp;
}

/* ---- MixColumns (FIPS-197 §5.1.3) ---------------------------------------- *
 *
 * For each column c, the new column is:
 *    s0' = 2*s0 ^ 3*s1 ^  s2 ^  s3
 *    s1' =  s0 ^ 2*s1 ^ 3*s2 ^  s3
 *    s2' =  s0 ^  s1 ^ 2*s2 ^ 3*s3
 *    s3' = 3*s0 ^  s1 ^  s2 ^ 2*s3
 * with all multiplications in GF(2^8).
 */
static void tethys_aes_mix_columns_(uint8_t state[16])
{
    for (size_t c = 0U; c < 4U; ++c)
    {
        uint8_t const s0 = state[(4U * c) + 0U];
        uint8_t const s1 = state[(4U * c) + 1U];
        uint8_t const s2 = state[(4U * c) + 2U];
        uint8_t const s3 = state[(4U * c) + 3U];
        uint8_t const t  = (uint8_t)(s0 ^ s1 ^ s2 ^ s3);

        state[(4U * c) + 0U] = (uint8_t)(s0 ^ t ^ tethys_aes_xtime_((uint8_t)(s0 ^ s1)));
        state[(4U * c) + 1U] = (uint8_t)(s1 ^ t ^ tethys_aes_xtime_((uint8_t)(s1 ^ s2)));
        state[(4U * c) + 2U] = (uint8_t)(s2 ^ t ^ tethys_aes_xtime_((uint8_t)(s2 ^ s3)));
        state[(4U * c) + 3U] = (uint8_t)(s3 ^ t ^ tethys_aes_xtime_((uint8_t)(s3 ^ s0)));
    }
}

/* ---- Encrypt one block (FIPS-197 §5.1) ----------------------------------- */

void tethys_aes128_encrypt_block(
    uint32_t const round_keys[TETHYS_AES128_ROUND_KEY_WORDS],
    uint8_t const  input[TETHYS_AES128_BLOCK_SIZE],
    uint8_t        output[TETHYS_AES128_BLOCK_SIZE])
{
    uint8_t state[16];

    /* Copy input to state. */
    for (size_t i = 0U; i < TETHYS_AES128_BLOCK_SIZE; ++i)
    {
        state[i] = input[i];
    }

    /* Initial round: AddRoundKey with round_keys[0..3]. */
    tethys_aes_add_round_key_(state, &round_keys[0]);

    /* 9 main rounds. */
    for (size_t round = 1U; round < 10U; ++round)
    {
        tethys_aes_sub_bytes_(state);
        tethys_aes_shift_rows_(state);
        tethys_aes_mix_columns_(state);
        tethys_aes_add_round_key_(state, &round_keys[round * 4U]);
    }

    /* Final round (no MixColumns). */
    tethys_aes_sub_bytes_(state);
    tethys_aes_shift_rows_(state);
    tethys_aes_add_round_key_(state, &round_keys[40]);

    /* Copy state to output. */
    for (size_t i = 0U; i < TETHYS_AES128_BLOCK_SIZE; ++i)
    {
        output[i] = state[i];
    }
}

/* ---- Constant-time verify_response --------------------------------------- */

bool tethys_aes128_verify_response(
    uint8_t const seed[TETHYS_AES128_BLOCK_SIZE],
    uint8_t const response[TETHYS_AES128_BLOCK_SIZE],
    uint8_t const local_key[TETHYS_AES128_KEY_SIZE])
{
    uint32_t round_keys[TETHYS_AES128_ROUND_KEY_WORDS];
    uint8_t  expected[TETHYS_AES128_BLOCK_SIZE];
    uint8_t  diff = 0U;

    tethys_aes128_key_schedule(local_key, round_keys);
    tethys_aes128_encrypt_block(round_keys, seed, expected);

    /*
     * Constant-time XOR-accumulate of the byte differences. We deliberately
     * do NOT short-circuit on the first mismatch (which would leak timing).
     * The `diff` accumulator is 0 iff every byte matched.
     */
    for (size_t i = 0U; i < TETHYS_AES128_BLOCK_SIZE; ++i)
    {
        diff = (uint8_t)(diff | (uint8_t)(expected[i] ^ response[i]));
    }

    /*
     * Wipe the local key schedule before returning. memset to a non-zero
     * pattern + then to zero would be more paranoid; for the academic dev
     * kit threat model (parent plan §1) a single zeroing is adequate.
     */
    (void)memset(round_keys, 0, sizeof(round_keys));
    (void)memset(expected,   0, sizeof(expected));

    return (diff == 0U);
}
