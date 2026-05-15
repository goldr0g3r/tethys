/*
 * tethys/aes128_seed_and_key.h - AES-128 (FIPS-197) seed-and-key
 * primitives for the XCP authenticated service-mode unlock.
 *
 * Module: tethys::security::aes128_seed_and_key
 * Profiles: space (mandatory per ADR-0006); marine (optional via
 *           TETHYS_MARINE_SEED_AND_KEY=aes128).
 * Standards:
 *   - NIST FIPS-197 (AES) - <https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.197-upd1.pdf>.
 *   - ASAM XCP 1.4 Part 2 §1.3 - seed-and-key generic mechanism.
 *   - ADR-0006 - AES-128 16-byte seed-and-key (the deployment-wide choice).
 *   - ADR-0005 - no dynamic allocation; the key schedule lives on caller's
 *     stack or in static memory.
 *   - .cursor/rules/no-recursion-no-goto.mdc - bounded loops; no goto.
 *
 * Threat model: an attacker with bus access on the flight bus attempts to
 * elevate from quiescent mode to service mode. Mitigation: the slave issues
 * a fresh 16-byte seed; the master must respond with `AES-128(seed, key)`;
 * the slave's `verify_response` does a constant-time compare against its
 * locally-computed expected response.
 *
 * Side-channel scope: this implementation defends only against the timing
 * oracle on the verify step (constant-time compare). Power-analysis (DPA /
 * SPA) defences are explicitly out of scope per ADR-0006 §risk and are
 * documented as gap for any future flight-hardware deployment.
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */
#ifndef TETHYS_AES128_SEED_AND_KEY_H
#define TETHYS_AES128_SEED_AND_KEY_H

#pragma once

#include "tethys/tethys_export.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/** AES-128 block size in bytes. */
#define TETHYS_AES128_BLOCK_SIZE   ((size_t)16U)

/** AES-128 key size in bytes. */
#define TETHYS_AES128_KEY_SIZE     ((size_t)16U)

/** AES-128 expanded round-key word count (11 round keys × 4 words). */
#define TETHYS_AES128_ROUND_KEY_WORDS ((size_t)44U)

/**
 * @brief Expand a 16-byte AES-128 key into 44 round-key words (FIPS-197 §5.2).
 *
 * @param[in]  key         16-byte cipher key.
 * @param[out] round_keys  Buffer of 44 uint32_t round-key words.
 *
 * @pre key != NULL && round_keys != NULL
 *
 * @safety MISRA C:2023 clean. Bounded loops (44 iterations max). No dynamic
 *         allocation. Re-entrant (no module-level state).
 */
TETHYS_EXPORT void tethys_aes128_key_schedule(
    uint8_t const  key[TETHYS_AES128_KEY_SIZE],
    uint32_t       round_keys[TETHYS_AES128_ROUND_KEY_WORDS]);

/**
 * @brief Encrypt one 16-byte AES-128 block (FIPS-197 §5.1).
 *
 * @param[in]  round_keys  Round keys from `tethys_aes128_key_schedule`.
 * @param[in]  input       16-byte plaintext.
 * @param[out] output      16-byte ciphertext (may overlap input).
 *
 * @pre round_keys != NULL && input != NULL && output != NULL
 *
 * @safety MISRA C:2023 clean. Bounded loops (10 rounds + 4-byte SubBytes
 *         iterations only). No dynamic allocation. Re-entrant.
 *
 * @note Decryption is intentionally NOT exposed. The seed-and-key protocol
 *       per ADR-0006 only needs encrypt() on the slave side to verify the
 *       master's response.
 */
TETHYS_EXPORT void tethys_aes128_encrypt_block(
    uint32_t const round_keys[TETHYS_AES128_ROUND_KEY_WORDS],
    uint8_t const  input[TETHYS_AES128_BLOCK_SIZE],
    uint8_t        output[TETHYS_AES128_BLOCK_SIZE]);

/**
 * @brief Verify the master's seed-and-key response in constant time.
 *
 * Computes `expected = AES-128-encrypt(seed, local_key)` and compares it
 * against @p response. The compare is constant-time over the byte vector
 * length to defeat timing oracles per ADR-0006 §scheme.
 *
 * @param[in] seed       16-byte seed previously issued by `GET_SEED`.
 * @param[in] response   16-byte master response candidate.
 * @param[in] local_key  16-byte per-target key (lives in slave read-only
 *                       flash; never sent over the wire).
 *
 * @return true iff response matches the locally-computed expected response.
 *
 * @safety MISRA C:2023 clean. Constant-time over the input length.
 */
TETHYS_EXPORT bool tethys_aes128_verify_response(
    uint8_t const seed[TETHYS_AES128_BLOCK_SIZE],
    uint8_t const response[TETHYS_AES128_BLOCK_SIZE],
    uint8_t const local_key[TETHYS_AES128_KEY_SIZE]);

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* TETHYS_AES128_SEED_AND_KEY_H */
