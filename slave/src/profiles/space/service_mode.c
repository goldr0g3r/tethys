/*
 * src/profiles/space/service_mode.c - authenticated service-mode unlock
 * state machine.
 *
 * Module: tethys::security::service_mode
 * Profiles: space (mandatory), marine (optional).
 * Standards:
 *   - ADR-0006 - AES-128 seed-and-key §scheme (the canonical reference).
 *   - .cursor/rules/space-profile-invariants.mdc - flight-mode default OFF.
 *   - .cursor/rules/no-recursion-no-goto.mdc - all transitions are flat
 *     conditionals; no recursion; no goto.
 *
 * Why a state machine here rather than scattered checks across the
 * dispatcher? Three reasons:
 *   1. The "3 fails in 10 min -> 10 min lockout" rule needs persistent
 *      state across calls; that state belongs in one place.
 *   2. Constant-time semantics (the unlock path always runs
 *      AES_verify_response in full, even after the seed-validity check
 *      fails) are easier to audit when concentrated here.
 *   3. Unit-testable: the state machine takes wallclock as a parameter
 *      so tests can simulate the full 10-minute lockout in microseconds.
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */

#include "tethys/service_mode.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

/* ---- Internal helpers ---------------------------------------------------- */

/* Lazy LOCKED_OUT -> LOCKED expiry. Called from every public entry point. */
static void tethys_service_mode_expire_lockout_(
    tethys_service_mode_ctx_t* ctx,
    uint64_t                   now_us)
{
    if ((ctx->state == TETHYS_SERVICE_MODE_LOCKED_OUT)
        && (now_us >= ctx->lockout_until_us))
    {
        ctx->state            = TETHYS_SERVICE_MODE_LOCKED;
        ctx->fail_count       = 0U;
        ctx->first_fail_at_us = 0U;
        ctx->lockout_until_us = 0U;
    }
}

/* Lazy UNLOCKED -> LOCKED expiry on inactivity. */
static void tethys_service_mode_expire_inactivity_(
    tethys_service_mode_ctx_t* ctx,
    uint64_t                   now_us)
{
    if (ctx->state == TETHYS_SERVICE_MODE_UNLOCKED)
    {
        uint64_t const delta = now_us - ctx->last_activity_us;
        if (delta >= TETHYS_SERVICE_MODE_INACTIVITY_TIMEOUT_US)
        {
            ctx->state = TETHYS_SERVICE_MODE_LOCKED;
        }
    }
}

/* Lazy SEED_ISSUED -> LOCKED on seed-validity expiry. */
static void tethys_service_mode_expire_seed_(
    tethys_service_mode_ctx_t* ctx,
    uint64_t                   now_us)
{
    if (ctx->state == TETHYS_SERVICE_MODE_SEED_ISSUED)
    {
        uint64_t const delta = now_us - ctx->seed_issued_at_us;
        if (delta >= TETHYS_SERVICE_MODE_SEED_VALIDITY_US)
        {
            ctx->state = TETHYS_SERVICE_MODE_LOCKED;
            (void)memset(ctx->seed, 0, sizeof(ctx->seed));
        }
    }
}

/* Reset the failure-counter window when the rolling 10-min window expires. */
static void tethys_service_mode_age_fail_window_(
    tethys_service_mode_ctx_t* ctx,
    uint64_t                   now_us)
{
    if ((ctx->fail_count > 0U) && (ctx->first_fail_at_us != 0U))
    {
        uint64_t const delta = now_us - ctx->first_fail_at_us;
        if (delta >= TETHYS_SERVICE_MODE_FAIL_WINDOW_US)
        {
            ctx->fail_count       = 0U;
            ctx->first_fail_at_us = 0U;
        }
    }
}

/* Composite lazy-expiry sweep: call before processing every event. */
static void tethys_service_mode_age_(
    tethys_service_mode_ctx_t* ctx,
    uint64_t                   now_us)
{
    tethys_service_mode_expire_lockout_(ctx, now_us);
    tethys_service_mode_expire_inactivity_(ctx, now_us);
    tethys_service_mode_expire_seed_(ctx, now_us);
    tethys_service_mode_age_fail_window_(ctx, now_us);
}

/* ---- Public API --------------------------------------------------------- */

void tethys_service_mode_init(tethys_service_mode_ctx_t* ctx)
{
    if (ctx == NULL)
    {
        return;
    }
    (void)memset(ctx, 0, sizeof(*ctx));
    ctx->state = TETHYS_SERVICE_MODE_LOCKED;
}

bool tethys_service_mode_get_seed(
    tethys_service_mode_ctx_t* ctx,
    uint64_t                   now_us,
    uint8_t const              rng_seed[TETHYS_AES128_BLOCK_SIZE],
    uint8_t                    out_seed[TETHYS_AES128_BLOCK_SIZE])
{
    if ((ctx == NULL) || (rng_seed == NULL) || (out_seed == NULL))
    {
        return false;
    }
    tethys_service_mode_age_(ctx, now_us);
    if (ctx->state == TETHYS_SERVICE_MODE_LOCKED_OUT)
    {
        return false;
    }
    /* Accept GET_SEED from any other state - the new seed supersedes any
     * prior in-flight one. */
    for (size_t i = 0U; i < TETHYS_AES128_BLOCK_SIZE; ++i)
    {
        ctx->seed[i] = rng_seed[i];
        out_seed[i]  = rng_seed[i];
    }
    ctx->seed_issued_at_us = now_us;
    ctx->state             = TETHYS_SERVICE_MODE_SEED_ISSUED;
    return true;
}

bool tethys_service_mode_unlock(
    tethys_service_mode_ctx_t* ctx,
    uint64_t                   now_us,
    uint8_t const              response[TETHYS_AES128_BLOCK_SIZE],
    uint8_t const              local_key[TETHYS_AES128_KEY_SIZE])
{
    if ((ctx == NULL) || (response == NULL) || (local_key == NULL))
    {
        return false;
    }
    tethys_service_mode_age_(ctx, now_us);

    /*
     * Constant-time policy: always run AES_verify_response and only then
     * apply state-based gating, so an attacker cannot distinguish "seed
     * expired" from "wrong response" via timing. The slight CPU cost is
     * acceptable on the academic dev kit.
     */
    bool const aes_ok = tethys_aes128_verify_response(
        ctx->seed, response, local_key);

    if (ctx->state == TETHYS_SERVICE_MODE_LOCKED_OUT)
    {
        return false;
    }
    if (ctx->state != TETHYS_SERVICE_MODE_SEED_ISSUED)
    {
        /* No seed in flight; reject without changing failure counters
         * (this is a protocol error, not a credential failure). */
        return false;
    }

    if (aes_ok)
    {
        ctx->state            = TETHYS_SERVICE_MODE_UNLOCKED;
        ctx->last_activity_us = now_us;
        ctx->fail_count       = 0U;
        ctx->first_fail_at_us = 0U;
        (void)memset(ctx->seed, 0, sizeof(ctx->seed));
        return true;
    }

    /* Wrong response: increment failure counter; maybe escalate to lockout. */
    if (ctx->fail_count == 0U)
    {
        ctx->first_fail_at_us = now_us;
    }
    ctx->fail_count = (uint8_t)(ctx->fail_count + 1U);
    ctx->state      = TETHYS_SERVICE_MODE_LOCKED;
    (void)memset(ctx->seed, 0, sizeof(ctx->seed));

    if (ctx->fail_count >= TETHYS_SERVICE_MODE_MAX_FAILS)
    {
        ctx->state            = TETHYS_SERVICE_MODE_LOCKED_OUT;
        ctx->lockout_until_us = now_us + TETHYS_SERVICE_MODE_LOCKOUT_DURATION_US;
    }
    return false;
}

bool tethys_service_mode_check_unlocked(
    tethys_service_mode_ctx_t* ctx,
    uint64_t                   now_us)
{
    if (ctx == NULL)
    {
        return false;
    }
    tethys_service_mode_age_(ctx, now_us);
    if (ctx->state == TETHYS_SERVICE_MODE_UNLOCKED)
    {
        ctx->last_activity_us = now_us;
        return true;
    }
    return false;
}

void tethys_service_mode_lock(tethys_service_mode_ctx_t* ctx)
{
    if (ctx == NULL)
    {
        return;
    }
    ctx->state = TETHYS_SERVICE_MODE_LOCKED;
    (void)memset(ctx->seed, 0, sizeof(ctx->seed));
    /* Preserve fail_count + first_fail_at_us + lockout_until_us so a
     * malicious DISCONNECT cannot reset the lockout window. */
}

tethys_service_mode_state_t tethys_service_mode_state(
    tethys_service_mode_ctx_t* ctx,
    uint64_t                   now_us)
{
    if (ctx == NULL)
    {
        return TETHYS_SERVICE_MODE_LOCKED;
    }
    tethys_service_mode_age_(ctx, now_us);
    return ctx->state;
}
