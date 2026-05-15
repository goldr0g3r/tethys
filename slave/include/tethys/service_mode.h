/*
 * tethys/service_mode.h - authenticated service-mode unlock state machine
 * for the space profile.
 *
 * Module: tethys::security::service_mode
 * Profiles: space (mandatory per ADR-0006), marine (optional).
 * Standards:
 *   - ASAM XCP 1.4 Part 2 §1.3 - seed-and-key generic mechanism.
 *   - ADR-0006 - AES-128 seed-and-key §scheme: "match -> unlock service
 *     mode for 60 s inactivity timeout; mismatch -> increment failure
 *     counter; 3 failures in 10 min -> 10-min lockout; all attempts
 *     logged".
 *   - ADR-0005 - no dynamic allocation; state lives in a caller-owned
 *     struct (one per slave process / MCU).
 *   - .cursor/rules/space-profile-invariants.mdc - flight-mode default
 *     DAQ disabled; enable only via authenticated service-mode command.
 *   - .cursor/rules/no-recursion-no-goto.mdc - all transitions are
 *     straight-line table-driven.
 *
 * State machine (per ADR-0006):
 *
 *     [LOCKED] -- GET_SEED --> [SEED_ISSUED]
 *                                   |
 *                  UNLOCK(correct) -+--> [UNLOCKED]   (60 s inactivity)
 *                  UNLOCK(wrong)   -+--> [LOCKED + ++fail_count]
 *                                              |
 *                              fail_count >= 3
 *                              in <= 10 min ---+--> [LOCKED_OUT] (10 min)
 *
 *     [UNLOCKED] -- 60 s of inactivity --> [LOCKED]
 *                -- DISCONNECT          --> [LOCKED]
 *
 *     [LOCKED_OUT] -- 10 min wallclock --> [LOCKED]
 *
 * Wallclock is sourced from tethys_platform_now_us() so this header has no
 * direct dependency on the platform layer; the state machine takes the
 * current time as a parameter on every call.
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */
#ifndef TETHYS_SERVICE_MODE_H
#define TETHYS_SERVICE_MODE_H

#pragma once

#include "tethys/aes128_seed_and_key.h"
#include "tethys/tethys_export.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Service-mode state.
 *
 * Externally visible so a master tool can query via XCP `GET_STATUS` whether
 * the slave is in service mode.
 */
typedef enum
{
    /** Locked, no seed issued. Only `GET_SEED` allowed. */
    TETHYS_SERVICE_MODE_LOCKED = 0,
    /** Seed issued; awaiting `UNLOCK` response from the master. */
    TETHYS_SERVICE_MODE_SEED_ISSUED = 1,
    /** Unlocked. Service-mode commands accepted. Tracks inactivity. */
    TETHYS_SERVICE_MODE_UNLOCKED = 2,
    /** Locked out due to repeated failures. No `GET_SEED` accepted. */
    TETHYS_SERVICE_MODE_LOCKED_OUT = 3
} tethys_service_mode_state_t;

/**
 * @brief Service-mode state context.
 *
 * Caller owns the storage. One instance per slave process / MCU. All time
 * values are in microseconds (matching tethys_platform_now_us()).
 *
 * Field semantics:
 *   * state - current state.
 *   * seed - the 16-byte seed issued by the last GET_SEED. Only valid in
 *     SEED_ISSUED state.
 *   * seed_issued_at_us - wallclock when seed was issued. Used to bound
 *     the validity window (security; an attacker should not get unlimited
 *     time to brute-force).
 *   * last_activity_us - wallclock of the most recent valid service-mode
 *     command. Used to detect the 60-s inactivity timeout.
 *   * fail_count - number of unlock failures in the current sliding window.
 *   * first_fail_at_us - wallclock of the first failure in the current
 *     fail window (used to enforce the "3 in 10 min" rule).
 *   * lockout_until_us - wallclock when LOCKED_OUT expires.
 */
typedef struct
{
    tethys_service_mode_state_t state;
    uint8_t  seed[TETHYS_AES128_BLOCK_SIZE];
    uint64_t seed_issued_at_us;
    uint64_t last_activity_us;
    uint8_t  fail_count;
    uint64_t first_fail_at_us;
    uint64_t lockout_until_us;
} tethys_service_mode_ctx_t;

/* ---- Configurable thresholds (overridable at compile time) -------------- */

#ifndef TETHYS_SERVICE_MODE_SEED_VALIDITY_US
/** Seed is valid for 30 s once issued (cancels stale seeds). */
#  define TETHYS_SERVICE_MODE_SEED_VALIDITY_US  (30ULL * 1000000ULL)
#endif

#ifndef TETHYS_SERVICE_MODE_INACTIVITY_TIMEOUT_US
/** Unlock auto-relocks after 60 s of inactivity (per ADR-0006). */
#  define TETHYS_SERVICE_MODE_INACTIVITY_TIMEOUT_US  (60ULL * 1000000ULL)
#endif

#ifndef TETHYS_SERVICE_MODE_FAIL_WINDOW_US
/** Rolling 10-minute window for the "3 failures" rule (per ADR-0006). */
#  define TETHYS_SERVICE_MODE_FAIL_WINDOW_US  (600ULL * 1000000ULL)
#endif

#ifndef TETHYS_SERVICE_MODE_MAX_FAILS
/** 3 failures within FAIL_WINDOW_US triggers LOCKED_OUT (per ADR-0006). */
#  define TETHYS_SERVICE_MODE_MAX_FAILS  ((uint8_t)3U)
#endif

#ifndef TETHYS_SERVICE_MODE_LOCKOUT_DURATION_US
/** LOCKED_OUT lasts 10 minutes (per ADR-0006). */
#  define TETHYS_SERVICE_MODE_LOCKOUT_DURATION_US  (600ULL * 1000000ULL)
#endif

/* ---- Public API --------------------------------------------------------- */

/**
 * @brief Initialise the state machine to LOCKED.
 *
 * @param[out] ctx Caller-owned context. Must not be NULL.
 *
 * @safety MISRA C:2023 clean. Idempotent.
 */
TETHYS_EXPORT void tethys_service_mode_init(tethys_service_mode_ctx_t* ctx);

/**
 * @brief Handle XCP `GET_SEED`. Generates a fresh 16-byte seed and
 *        transitions the state machine to SEED_ISSUED.
 *
 * @param[in,out] ctx Context.
 * @param[in]  now_us Current wallclock from tethys_platform_now_us().
 * @param[in]  rng_seed 16-byte caller-supplied randomness (typically from
 *                      the platform's hardware RNG; pseudo-random fallback
 *                      acceptable per ADR-0006 §risk).
 * @param[out] out_seed Written with the 16-byte seed to send to the master.
 *
 * @return true on success (seed written, state -> SEED_ISSUED); false if
 *         the slave is currently LOCKED_OUT (no seed issued).
 *
 * @safety MISRA C:2023 clean. Bounded; no recursion; no allocation.
 */
TETHYS_EXPORT bool tethys_service_mode_get_seed(
    tethys_service_mode_ctx_t* ctx,
    uint64_t                   now_us,
    uint8_t const              rng_seed[TETHYS_AES128_BLOCK_SIZE],
    uint8_t                    out_seed[TETHYS_AES128_BLOCK_SIZE]);

/**
 * @brief Handle XCP `UNLOCK`. Verifies the master's response against the
 *        slave-computed expected response (AES-128(seed, local_key)) and
 *        transitions the state machine accordingly.
 *
 * @param[in,out] ctx Context.
 * @param[in] now_us Current wallclock.
 * @param[in] response 16-byte response from the master.
 * @param[in] local_key 16-byte per-target key (lives in slave protected
 *                      flash; never sent over the wire).
 *
 * @return true if the unlock succeeded (state -> UNLOCKED); false if it
 *         failed, the slave is LOCKED_OUT, or the seed has expired.
 *
 * @safety MISRA C:2023 clean. Constant-time response compare (delegates
 *         to tethys_aes128_verify_response()).
 */
TETHYS_EXPORT bool tethys_service_mode_unlock(
    tethys_service_mode_ctx_t* ctx,
    uint64_t                   now_us,
    uint8_t const              response[TETHYS_AES128_BLOCK_SIZE],
    uint8_t const              local_key[TETHYS_AES128_KEY_SIZE]);

/**
 * @brief Notify the state machine that a valid service-mode command was
 *        just processed. Refreshes the inactivity timer.
 *
 * @param[in,out] ctx Context.
 * @param[in] now_us Current wallclock.
 *
 * @return true if the slave is currently UNLOCKED (caller may proceed).
 *         false otherwise (caller should reject the command).
 *
 * @safety MISRA C:2023 clean. Also handles the lazy state transition
 *         UNLOCKED -> LOCKED on inactivity timeout.
 */
TETHYS_EXPORT bool tethys_service_mode_check_unlocked(
    tethys_service_mode_ctx_t* ctx,
    uint64_t                   now_us);

/**
 * @brief Explicit lock (e.g. on XCP DISCONNECT). Transitions UNLOCKED -> LOCKED.
 *
 * @param[in,out] ctx Context.
 *
 * @safety MISRA C:2023 clean. Safe in any state.
 */
TETHYS_EXPORT void tethys_service_mode_lock(tethys_service_mode_ctx_t* ctx);

/**
 * @brief Read-only state query.
 *
 * Lazily handles LOCKED_OUT -> LOCKED expiry and UNLOCKED -> LOCKED
 * inactivity expiry so callers always see the up-to-date state.
 *
 * @param[in,out] ctx Context (mutable so we can lazy-transition).
 * @param[in] now_us Current wallclock.
 *
 * @return Current state.
 *
 * @safety MISRA C:2023 clean.
 */
TETHYS_EXPORT tethys_service_mode_state_t tethys_service_mode_state(
    tethys_service_mode_ctx_t* ctx,
    uint64_t                   now_us);

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* TETHYS_SERVICE_MODE_H */
