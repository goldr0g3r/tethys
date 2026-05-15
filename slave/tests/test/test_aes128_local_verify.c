/*
 * test_aes128_local_verify.c - tiny stand-alone main() that runs the AES KAT
 * + EDAC tests without Unity/Ceedling.
 *
 * NOT compiled by ceedling (it would conflict with the per-file test runners).
 * Built explicitly by the developer for a quick sanity check:
 *
 *   gcc -I include -I src/security -I src/profiles/space \
 *       src/security/aes128_seed_and_key.c \
 *       src/profiles/space/edac.c \
 *       tests/test/test_aes128_local_verify.c -o aes_verify
 *
 * Returns 0 on pass, non-zero on fail. CI does NOT run this; Ceedling
 * runs the real Unity tests in test_aes128_kat.c + test_edac.c.
 *
 * Excluded from ceedling via the `:files: :test:` exclude list in
 * slave/tests/project.yml (see PR-A diff).
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */

#include "tethys/aes128_seed_and_key.h"
#include "tethys/edac.h"

#include <stdint.h>
#include <stdio.h>
#include <string.h>

int main(void)
{
    int failures = 0;

    /* AES Appendix B KAT. */
    {
        static uint8_t const input[16] = {
            0x32U,0x43U,0xF6U,0xA8U,0x88U,0x5AU,0x30U,0x8DU,
            0x31U,0x31U,0x98U,0xA2U,0xE0U,0x37U,0x07U,0x34U
        };
        static uint8_t const key[16] = {
            0x2BU,0x7EU,0x15U,0x16U,0x28U,0xAEU,0xD2U,0xA6U,
            0xABU,0xF7U,0x15U,0x88U,0x09U,0xCFU,0x4FU,0x3CU
        };
        static uint8_t const expected[16] = {
            0x39U,0x25U,0x84U,0x1DU,0x02U,0xDCU,0x09U,0xFBU,
            0xDCU,0x11U,0x85U,0x97U,0x19U,0x6AU,0x0BU,0x32U
        };
        uint32_t round_keys[TETHYS_AES128_ROUND_KEY_WORDS];
        uint8_t  output[16] = {0};
        tethys_aes128_key_schedule(key, round_keys);
        tethys_aes128_encrypt_block(round_keys, input, output);
        if (memcmp(output, expected, 16) != 0)
        {
            (void)printf("FAIL AES Appendix B\n");
            for (int i = 0; i < 16; ++i) (void)printf("%02x ", output[i]);
            (void)printf("\n");
            failures += 1;
        }
        else
        {
            (void)printf("PASS AES Appendix B\n");
        }
    }

    /* EDAC roundtrip + single-bit correct. */
    {
        uint64_t const data   = 0x0123456789ABCDEFULL;
        uint8_t  const parity = (uint8_t)tethys_edac_encode_parity(data);
        uint64_t recovered = 0U;
        uint8_t  cb = 0U;
        if (tethys_edac_decode(data, parity, &recovered, &cb) != TETHYS_EDAC_OK
            || recovered != data)
        {
            (void)printf("FAIL EDAC roundtrip\n");
            failures += 1;
        }
        else
        {
            (void)printf("PASS EDAC roundtrip\n");
        }
        int sec_failures = 0;
        for (int bit = 0; bit < 64; ++bit)
        {
            uint64_t corrupted = data ^ ((uint64_t)1U << bit);
            uint64_t out = 0U;
            uint8_t  cbit = 0U;
            tethys_edac_decode_result_t r =
                tethys_edac_decode(corrupted, parity, &out, &cbit);
            if (r != TETHYS_EDAC_SINGLE_BIT_CORRECTED || out != data)
            {
                sec_failures += 1;
            }
        }
        int ded_failures = 0;
        for (int a = 0; a < 8; ++a)
        {
            for (int b = a + 1; b < 16; ++b)
            {
                uint64_t corrupted = data ^ ((uint64_t)1U << a) ^ ((uint64_t)1U << b);
                uint64_t out = 0U;
                uint8_t  cbit = 0U;
                tethys_edac_decode_result_t r =
                    tethys_edac_decode(corrupted, parity, &out, &cbit);
                if (r != TETHYS_EDAC_DOUBLE_BIT_DETECTED)
                {
                    ded_failures += 1;
                }
            }
        }
        if (sec_failures > 0)
        {
            (void)printf("FAIL EDAC SEC (%d failures)\n", sec_failures);
            failures += sec_failures;
        }
        else
        {
            (void)printf("PASS EDAC SEC (all 64 positions)\n");
        }
        if (ded_failures > 0)
        {
            (void)printf("FAIL EDAC DED (%d failures)\n", ded_failures);
            failures += ded_failures;
        }
        else
        {
            (void)printf("PASS EDAC DED (8x16 representative pairs)\n");
        }
    }

    return failures;
}
