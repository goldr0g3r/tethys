/*
 * test_service_mode.c - Unity tests for the authenticated service-mode
 * unlock state machine.
 *
 * Verifies the state-machine transitions documented in
 * docs/adr/0006-aes-128-seed-and-key.md §scheme and
 * .cursor/rules/space-profile-invariants.mdc.
 *
 * Standards trace:
 *   - ADR-0006 §scheme.
 *   - tethys/service_mode.h public contract.
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */

#include "tethys/service_mode.h"
#include "unity.h"

#include <stdint.h>
#include <string.h>

/* Fixed test key + seed for deterministic AES verification. */
static uint8_t const TEST_KEY[16] = {
    0x2BU, 0x7EU, 0x15U, 0x16U, 0x28U, 0xAEU, 0xD2U, 0xA6U,
    0xABU, 0xF7U, 0x15U, 0x88U, 0x09U, 0xCFU, 0x4FU, 0x3CU
};

static uint8_t const TEST_SEED[16] = {
    0x32U, 0x43U, 0xF6U, 0xA8U, 0x88U, 0x5AU, 0x30U, 0x8DU,
    0x31U, 0x31U, 0x98U, 0xA2U, 0xE0U, 0x37U, 0x07U, 0x34U
};

/* FIPS-197 Appendix B answer: AES-128(TEST_SEED, TEST_KEY). */
static uint8_t const CORRECT_RESPONSE[16] = {
    0x39U, 0x25U, 0x84U, 0x1DU, 0x02U, 0xDCU, 0x09U, 0xFBU,
    0xDCU, 0x11U, 0x85U, 0x97U, 0x19U, 0x6AU, 0x0BU, 0x32U
};

static tethys_service_mode_ctx_t ctx_;

void setUp(void)
{
    tethys_service_mode_init(&ctx_);
}

void tearDown(void) { /* no-op */ }

/* ---- Initial state ------------------------------------------------------ */

void test_service_mode_init_state_is_locked(void)
{
    TEST_ASSERT_EQUAL_INT(TETHYS_SERVICE_MODE_LOCKED,
                          tethys_service_mode_state(&ctx_, 1000U));
}

/* ---- Happy-path unlock --------------------------------------------------- */

void test_service_mode_get_seed_then_unlock_with_correct_response(void)
{
    uint8_t issued_seed[16] = {0};
    bool const got = tethys_service_mode_get_seed(
        &ctx_, 1000U, TEST_SEED, issued_seed);
    TEST_ASSERT_TRUE(got);
    TEST_ASSERT_EQUAL_HEX8_ARRAY(TEST_SEED, issued_seed, 16);
    TEST_ASSERT_EQUAL_INT(TETHYS_SERVICE_MODE_SEED_ISSUED,
                          tethys_service_mode_state(&ctx_, 2000U));

    bool const unlocked = tethys_service_mode_unlock(
        &ctx_, 3000U, CORRECT_RESPONSE, TEST_KEY);
    TEST_ASSERT_TRUE(unlocked);
    TEST_ASSERT_EQUAL_INT(TETHYS_SERVICE_MODE_UNLOCKED,
                          tethys_service_mode_state(&ctx_, 4000U));
}

void test_service_mode_check_unlocked_after_successful_unlock(void)
{
    uint8_t issued_seed[16] = {0};
    (void)tethys_service_mode_get_seed(&ctx_, 1000U, TEST_SEED, issued_seed);
    (void)tethys_service_mode_unlock(&ctx_, 2000U, CORRECT_RESPONSE, TEST_KEY);
    TEST_ASSERT_TRUE(tethys_service_mode_check_unlocked(&ctx_, 3000U));
}

/* ---- Wrong response ----------------------------------------------------- */

void test_service_mode_wrong_response_returns_to_locked(void)
{
    uint8_t issued_seed[16] = {0};
    (void)tethys_service_mode_get_seed(&ctx_, 1000U, TEST_SEED, issued_seed);

    uint8_t wrong[16];
    (void)memcpy(wrong, CORRECT_RESPONSE, sizeof(wrong));
    wrong[7] = (uint8_t)(wrong[7] ^ 0x01U);
    bool const unlocked = tethys_service_mode_unlock(
        &ctx_, 2000U, wrong, TEST_KEY);
    TEST_ASSERT_FALSE(unlocked);
    TEST_ASSERT_EQUAL_INT(TETHYS_SERVICE_MODE_LOCKED,
                          tethys_service_mode_state(&ctx_, 3000U));
}

void test_service_mode_three_wrong_responses_triggers_lockout(void)
{
    uint8_t wrong[16];
    (void)memcpy(wrong, CORRECT_RESPONSE, sizeof(wrong));
    wrong[0] = (uint8_t)(wrong[0] ^ 0x01U);

    uint64_t t = 1000U;
    for (uint8_t i = 0U; i < 3U; ++i)
    {
        uint8_t seed_out[16] = {0};
        (void)tethys_service_mode_get_seed(&ctx_, t, TEST_SEED, seed_out);
        (void)tethys_service_mode_unlock(&ctx_, t + 100U, wrong, TEST_KEY);
        t += 200U;
    }
    TEST_ASSERT_EQUAL_INT(TETHYS_SERVICE_MODE_LOCKED_OUT,
                          tethys_service_mode_state(&ctx_, t));
}

void test_service_mode_lockout_rejects_get_seed(void)
{
    /* Trigger lockout. */
    uint8_t wrong[16];
    (void)memcpy(wrong, CORRECT_RESPONSE, sizeof(wrong));
    wrong[0] = (uint8_t)(wrong[0] ^ 0x01U);
    uint64_t t = 1000U;
    for (uint8_t i = 0U; i < 3U; ++i)
    {
        uint8_t s[16] = {0};
        (void)tethys_service_mode_get_seed(&ctx_, t, TEST_SEED, s);
        (void)tethys_service_mode_unlock(&ctx_, t + 100U, wrong, TEST_KEY);
        t += 200U;
    }

    /* GET_SEED must now refuse. */
    uint8_t seed_out[16] = {0};
    bool const got = tethys_service_mode_get_seed(
        &ctx_, t + 1000U, TEST_SEED, seed_out);
    TEST_ASSERT_FALSE(got);
}

void test_service_mode_lockout_expires_after_10_minutes(void)
{
    /* Trigger lockout at t=1000us. */
    uint8_t wrong[16];
    (void)memcpy(wrong, CORRECT_RESPONSE, sizeof(wrong));
    wrong[0] = (uint8_t)(wrong[0] ^ 0x01U);
    uint64_t t = 1000U;
    for (uint8_t i = 0U; i < 3U; ++i)
    {
        uint8_t s[16] = {0};
        (void)tethys_service_mode_get_seed(&ctx_, t, TEST_SEED, s);
        (void)tethys_service_mode_unlock(&ctx_, t + 100U, wrong, TEST_KEY);
        t += 200U;
    }

    /* Advance just past 10 minutes + lockout-start time. The lockout was
     * armed on the 3rd unlock attempt at t = 1000 + 2*200 + 100 = 1500us;
     * lockout_until = 1500us + 600_000_000us. Add a little slack. */
    uint64_t const after_lockout = 1500U + 600000000ULL + 1000U;
    TEST_ASSERT_EQUAL_INT(TETHYS_SERVICE_MODE_LOCKED,
                          tethys_service_mode_state(&ctx_, after_lockout));

    /* And GET_SEED works again. */
    uint8_t seed_out[16] = {0};
    bool const got = tethys_service_mode_get_seed(
        &ctx_, after_lockout + 1U, TEST_SEED, seed_out);
    TEST_ASSERT_TRUE(got);
}

/* ---- Inactivity timeout ------------------------------------------------- */

void test_service_mode_unlocked_relocks_after_60s_inactivity(void)
{
    uint8_t seed_out[16] = {0};
    (void)tethys_service_mode_get_seed(&ctx_, 1000U, TEST_SEED, seed_out);
    (void)tethys_service_mode_unlock(&ctx_, 2000U, CORRECT_RESPONSE, TEST_KEY);
    /* 61 s later: must be LOCKED again. */
    uint64_t const t_after_60s = 2000U + (61ULL * 1000000ULL);
    TEST_ASSERT_EQUAL_INT(TETHYS_SERVICE_MODE_LOCKED,
                          tethys_service_mode_state(&ctx_, t_after_60s));
}

void test_service_mode_activity_refreshes_inactivity_timer(void)
{
    uint8_t seed_out[16] = {0};
    (void)tethys_service_mode_get_seed(&ctx_, 1000U, TEST_SEED, seed_out);
    (void)tethys_service_mode_unlock(&ctx_, 2000U, CORRECT_RESPONSE, TEST_KEY);
    /*
     * Successive check_unlocked calls each within 60 s of the previous
     * should keep us UNLOCKED indefinitely.
     */
    uint64_t t = 2000U;
    for (uint8_t i = 0U; i < 5U; ++i)
    {
        t += 30ULL * 1000000ULL; /* 30 s steps */
        TEST_ASSERT_TRUE(tethys_service_mode_check_unlocked(&ctx_, t));
    }
}

/* ---- Explicit lock + seed expiry ---------------------------------------- */

void test_service_mode_lock_returns_to_locked(void)
{
    uint8_t seed_out[16] = {0};
    (void)tethys_service_mode_get_seed(&ctx_, 1000U, TEST_SEED, seed_out);
    (void)tethys_service_mode_unlock(&ctx_, 2000U, CORRECT_RESPONSE, TEST_KEY);
    tethys_service_mode_lock(&ctx_);
    TEST_ASSERT_EQUAL_INT(TETHYS_SERVICE_MODE_LOCKED,
                          tethys_service_mode_state(&ctx_, 3000U));
}

void test_service_mode_stale_seed_rejected_on_unlock(void)
{
    uint8_t seed_out[16] = {0};
    (void)tethys_service_mode_get_seed(&ctx_, 1000U, TEST_SEED, seed_out);
    /* Wait 31 s (past TETHYS_SERVICE_MODE_SEED_VALIDITY_US = 30 s). */
    uint64_t const t_late = 1000U + (31ULL * 1000000ULL);
    bool const unlocked = tethys_service_mode_unlock(
        &ctx_, t_late, CORRECT_RESPONSE, TEST_KEY);
    TEST_ASSERT_FALSE(unlocked);
    TEST_ASSERT_EQUAL_INT(TETHYS_SERVICE_MODE_LOCKED,
                          tethys_service_mode_state(&ctx_, t_late + 1U));
}

void test_service_mode_unlock_without_seed_fails(void)
{
    /* Skip GET_SEED. UNLOCK should fail. */
    bool const unlocked = tethys_service_mode_unlock(
        &ctx_, 2000U, CORRECT_RESPONSE, TEST_KEY);
    TEST_ASSERT_FALSE(unlocked);
}
