/*
 * test_xcp_odt.c - Unity tests for the ODT pack/unpack helpers.
 *
 * Module: tests::test_xcp_odt
 * Profiles: posix-sim
 * Standards: ASAM XCP 1.4 Part 2 §1.4.1
 * Trace: docs/traceability.csv (rows TETHYS-TST-0050..0058 land at PR-10)
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */
#include "tethys/xcp_odt.h"

#include "unity.h"

#include <stddef.h>
#include <stdint.h>
#include <string.h>

TEST_SOURCE_FILE("xcp_odt.c")

#define TEST_MEM_SIZE  ((size_t)128U)

static tethys_odt_t g_odt;
static uint8_t      g_memory[TEST_MEM_SIZE];
static uint8_t      g_scratch[TETHYS_DAQ_MAX_DTO_BYTES];

static void seed_ramp(void)
{
    for (size_t i = (size_t)0U; i < TEST_MEM_SIZE; ++i) {
        g_memory[i] = (uint8_t)(i & 0xFFU);
    }
}

void setUp(void)
{
    tethys_odt_reset(&g_odt);
    seed_ramp();
    (void)memset(g_scratch, 0, sizeof g_scratch);
}

void tearDown(void) { /* no-op */ }

/* ---- Reset ---------------------------------------------------------- */

void test_reset_clears_entry_count(void)
{
    g_odt.entry_count = (uint8_t)5U;
    g_odt.entries[0].in_use = (uint8_t)1U;
    tethys_odt_reset(&g_odt);
    TEST_ASSERT_EQUAL_UINT8(0U, g_odt.entry_count);
    TEST_ASSERT_EQUAL_UINT8(0U, g_odt.entries[0].in_use);
}

void test_reset_null_safe(void)
{
    tethys_odt_reset(NULL); /* must not segfault */
    TEST_PASS();
}

/* ---- Pack: positive paths ------------------------------------------ */

void test_pack_two_entries_concatenates(void)
{
    g_odt.entry_count = (uint8_t)2U;
    g_odt.entries[0].in_use     = (uint8_t)1U;
    g_odt.entries[0].size_bytes = (uint8_t)4U;
    g_odt.entries[0].address    = (uint32_t)16U;
    g_odt.entries[1].in_use     = (uint8_t)1U;
    g_odt.entries[1].size_bytes = (uint8_t)2U;
    g_odt.entries[1].address    = (uint32_t)32U;

    size_t offset = (size_t)0U;
    int const rc = tethys_odt_pack(&g_odt, g_memory, TEST_MEM_SIZE, g_scratch, sizeof g_scratch, &offset);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_size_t((size_t)6U, offset);
    TEST_ASSERT_EQUAL_UINT8(16U, g_scratch[0]);
    TEST_ASSERT_EQUAL_UINT8(17U, g_scratch[1]);
    TEST_ASSERT_EQUAL_UINT8(18U, g_scratch[2]);
    TEST_ASSERT_EQUAL_UINT8(19U, g_scratch[3]);
    TEST_ASSERT_EQUAL_UINT8(32U, g_scratch[4]);
    TEST_ASSERT_EQUAL_UINT8(33U, g_scratch[5]);
}

void test_pack_skips_unused_entries(void)
{
    g_odt.entry_count = (uint8_t)3U;
    g_odt.entries[0].in_use     = (uint8_t)1U;
    g_odt.entries[0].size_bytes = (uint8_t)1U;
    g_odt.entries[0].address    = (uint32_t)1U;
    g_odt.entries[1].in_use     = (uint8_t)0U; /* skip */
    g_odt.entries[1].size_bytes = (uint8_t)4U;
    g_odt.entries[1].address    = (uint32_t)50U;
    g_odt.entries[2].in_use     = (uint8_t)1U;
    g_odt.entries[2].size_bytes = (uint8_t)1U;
    g_odt.entries[2].address    = (uint32_t)3U;

    size_t offset = (size_t)0U;
    TEST_ASSERT_EQUAL_INT(0, tethys_odt_pack(
        &g_odt, g_memory, TEST_MEM_SIZE, g_scratch, sizeof g_scratch, &offset));
    TEST_ASSERT_EQUAL_size_t((size_t)2U, offset);
    TEST_ASSERT_EQUAL_UINT8(1U, g_scratch[0]);
    TEST_ASSERT_EQUAL_UINT8(3U, g_scratch[1]);
}

void test_pack_respects_caller_offset_prefix(void)
{
    g_odt.entry_count = (uint8_t)1U;
    g_odt.entries[0].in_use     = (uint8_t)1U;
    g_odt.entries[0].size_bytes = (uint8_t)2U;
    g_odt.entries[0].address    = (uint32_t)0U;

    g_scratch[0] = (uint8_t)0xAAU;
    g_scratch[1] = (uint8_t)0xBBU;
    size_t offset = (size_t)2U;
    TEST_ASSERT_EQUAL_INT(0, tethys_odt_pack(
        &g_odt, g_memory, TEST_MEM_SIZE, g_scratch, sizeof g_scratch, &offset));
    TEST_ASSERT_EQUAL_size_t((size_t)4U, offset);
    TEST_ASSERT_EQUAL_UINT8(0xAAU, g_scratch[0]); /* prefix preserved */
    TEST_ASSERT_EQUAL_UINT8(0xBBU, g_scratch[1]);
    TEST_ASSERT_EQUAL_UINT8(0x00U, g_scratch[2]); /* memory[0] */
    TEST_ASSERT_EQUAL_UINT8(0x01U, g_scratch[3]); /* memory[1] */
}

/* ---- Pack: error paths --------------------------------------------- */

void test_pack_rejects_out_of_range_address(void)
{
    g_odt.entry_count = (uint8_t)1U;
    g_odt.entries[0].in_use     = (uint8_t)1U;
    g_odt.entries[0].size_bytes = (uint8_t)4U;
    g_odt.entries[0].address    = (uint32_t)(TEST_MEM_SIZE - 2U); /* spills past end */
    size_t offset = (size_t)0U;
    TEST_ASSERT_EQUAL_INT(-1, tethys_odt_pack(
        &g_odt, g_memory, TEST_MEM_SIZE, g_scratch, sizeof g_scratch, &offset));
}

void test_pack_rejects_buffer_overflow(void)
{
    g_odt.entry_count = (uint8_t)1U;
    g_odt.entries[0].in_use     = (uint8_t)1U;
    g_odt.entries[0].size_bytes = (uint8_t)8U;
    g_odt.entries[0].address    = (uint32_t)0U;
    size_t offset = (size_t)0U;
    TEST_ASSERT_EQUAL_INT(-1, tethys_odt_pack(
        &g_odt, g_memory, TEST_MEM_SIZE, g_scratch, /*out_capacity=*/ (size_t)4U, &offset));
}

void test_pack_null_arguments_rejected(void)
{
    size_t offset = (size_t)0U;
    TEST_ASSERT_EQUAL_INT(-1, tethys_odt_pack(NULL, g_memory, TEST_MEM_SIZE,
                                              g_scratch, sizeof g_scratch, &offset));
    TEST_ASSERT_EQUAL_INT(-1, tethys_odt_pack(&g_odt, NULL, TEST_MEM_SIZE,
                                              g_scratch, sizeof g_scratch, &offset));
    TEST_ASSERT_EQUAL_INT(-1, tethys_odt_pack(&g_odt, g_memory, TEST_MEM_SIZE,
                                              NULL, sizeof g_scratch, &offset));
    TEST_ASSERT_EQUAL_INT(-1, tethys_odt_pack(&g_odt, g_memory, TEST_MEM_SIZE,
                                              g_scratch, sizeof g_scratch, NULL));
}

/* ---- Unpack: STIM round-trip ---------------------------------------- */

void test_unpack_round_trip(void)
{
    g_odt.entry_count = (uint8_t)2U;
    g_odt.entries[0].in_use     = (uint8_t)1U;
    g_odt.entries[0].size_bytes = (uint8_t)4U;
    g_odt.entries[0].address    = (uint32_t)64U;
    g_odt.entries[1].in_use     = (uint8_t)1U;
    g_odt.entries[1].size_bytes = (uint8_t)2U;
    g_odt.entries[1].address    = (uint32_t)80U;

    /* Pack the ramp into scratch. */
    size_t offset = (size_t)0U;
    TEST_ASSERT_EQUAL_INT(0, tethys_odt_pack(
        &g_odt, g_memory, TEST_MEM_SIZE, g_scratch, sizeof g_scratch, &offset));
    TEST_ASSERT_EQUAL_size_t((size_t)6U, offset);

    /* Wipe memory; replay via unpack. */
    (void)memset(g_memory, 0, sizeof g_memory);
    size_t in_offset = (size_t)0U;
    TEST_ASSERT_EQUAL_INT(0, tethys_odt_unpack(
        &g_odt, g_memory, TEST_MEM_SIZE, g_scratch, offset, &in_offset));
    TEST_ASSERT_EQUAL_size_t((size_t)6U, in_offset);
    TEST_ASSERT_EQUAL_UINT8(64U, g_memory[64]);
    TEST_ASSERT_EQUAL_UINT8(65U, g_memory[65]);
    TEST_ASSERT_EQUAL_UINT8(80U, g_memory[80]);
    TEST_ASSERT_EQUAL_UINT8(81U, g_memory[81]);
}

void test_unpack_rejects_short_buffer(void)
{
    g_odt.entry_count = (uint8_t)1U;
    g_odt.entries[0].in_use     = (uint8_t)1U;
    g_odt.entries[0].size_bytes = (uint8_t)4U;
    g_odt.entries[0].address    = (uint32_t)0U;
    size_t in_offset = (size_t)0U;
    uint8_t too_short[2] = {0U};
    TEST_ASSERT_EQUAL_INT(-1, tethys_odt_unpack(
        &g_odt, g_memory, TEST_MEM_SIZE, too_short, sizeof too_short, &in_offset));
}
