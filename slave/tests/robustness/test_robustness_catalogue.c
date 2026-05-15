/*
 * test_robustness_catalogue.c - Unity scaffold for the 16-row fault-injection
 *                                catalogue from ADR-0010 §10.1
 *                                (phase-0-system-requirements.md §10.1).
 *
 * Module: tests::robustness::catalogue
 * Profiles: all (marine, space, posix-sim)
 * Standards: ASAM XCP 1.4 Part 2 §3 (CTR + packet structure); IEC 61784-3 ed.4
 *            §6 (safe-comm residual); AUTOSAR PRS E2E §4.3.3 (fault classes);
 *            DO-178C §6.4.2 (requirements-based testing on equivalence classes);
 *            ISO 11898-1:2024 §10 (CAN bus-off recovery); MISRA C:2023.
 * Trace: docs/traceability.csv rows TETHYS-REQ-FAULT-001..016 +
 *        TETHYS-REQ-VER-003.
 *
 * Layout: one Unity test function per catalogue row. Rows 14 + 15 run today
 * against the existing tethys_xcp_dispatch surface (Phase-1 + Phase-2 read
 * path landed in PR #22 + PR #28). The remaining 14 rows are TEST_IGNORE'd
 * with a phase / PR marker so the owning worker finds them by id when
 * their phase lands and flips the macro to the real assertion.
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */
#include "tethys/xcp_dispatcher.h"

#include "unity.h"

#include <stddef.h>
#include <stdint.h>
#include <string.h>

/* Ceedling source discovery: explicit because the dispatcher .c is nested
 * under src/core/. Same idiom as slave/tests/test/test_xcp_dispatcher.c.
 */
TEST_SOURCE_FILE("xcp_dispatcher.c")

/* ---- Per-test fixture state (static; no dynamic allocation per ADR-0005) - */

#define ROBUST_RESP_CAP  ((size_t)TETHYS_XCP_MAX_CTO)
#define ROBUST_MEM_SIZE  ((size_t)256U)

static tethys_xcp_state_t g_state;
static uint8_t            g_response[ROBUST_RESP_CAP];
static size_t             g_response_len;
static uint8_t            g_memory[ROBUST_MEM_SIZE];

static void connect_session(void)
{
    uint8_t connect_req[2] = {TETHYS_XCP_CMD_CONNECT, 0U};
    (void)tethys_xcp_dispatch(
        &g_state, connect_req, sizeof connect_req,
        g_response, sizeof g_response, &g_response_len);
}

void setUp(void)
{
    tethys_xcp_init(&g_state);
    for (size_t i = 0U; i < ROBUST_MEM_SIZE; ++i) {
        g_memory[i] = (uint8_t)(i & 0xFFU);
    }
    tethys_xcp_attach_memory(&g_state, g_memory, ROBUST_MEM_SIZE);
    (void)memset(g_response, 0, sizeof g_response);
    g_response_len = (size_t)0U;
}

void tearDown(void)
{
    /* No-op. */
}

/* ---- Row 1 - Drop 1 of every N DTO packets ---------------------------- */

void test_row01_drop_1_of_n_dto_packets(void)
{
    /* Catalogue: master emits DAQ_GAP event; pass when
     * count(DAQ_GAP) == ceil(total/N) and MDF4 stays valid.
     * Depends on: Phase-3 master DAQ engine + Phase-5 transport stub that can
     * inject dropped frames. Flip TEST_IGNORE_MESSAGE -> real assertions when
     * tethys_master.protocol.ctr_tracker + the lossy transport stub land.
     */
    TEST_IGNORE_MESSAGE("Pending Phase-3 master DAQ engine + Phase-5 lossy transport stub");
}

/* ---- Row 2 - Burst-K consecutive DTO loss ----------------------------- */

void test_row02_burst_k_dto_loss(void)
{
    /* Catalogue: one DAQ_GAP per burst; packets_lost == K;
     * duration_us within +/- 1 ms of expected.
     */
    TEST_IGNORE_MESSAGE("Pending Phase-3 master DAQ engine + Phase-5 burst-loss injector");
}

/* ---- Row 3 - Reorder DTO at distance D -------------------------------- */

void test_row03_reorder_dto_at_distance_d(void)
{
    /* Catalogue: out-of-order packets rejected via CTR; MDF4 valid.
     * AUTOSAR E2E §4.3.3 fault class: Insertion.
     */
    TEST_IGNORE_MESSAGE("Pending Phase-3 master ctr_tracker + Phase-5 UDP transport");
}

/* ---- Row 4 - Duplicate DTO at rate R ---------------------------------- */

void test_row04_duplicate_dto_at_rate_r(void)
{
    /* Catalogue: duplicates dropped; count(duplicate) ~ R x total.
     * AUTOSAR E2E §4.3.3 fault class: Repetition.
     */
    TEST_IGNORE_MESSAGE("Pending Phase-3 master ctr_tracker + Phase-5 UDP transport");
}

/* ---- Row 5 - Single-bit corruption on DTO payload --------------------- */

void test_row05_single_bit_corruption_on_dto(void)
{
    /* Catalogue: transport CRC drops the frame; reduces to row 1 (loss).
     * AUTOSAR E2E §4.3.3 fault class: Corruption.
     */
    TEST_IGNORE_MESSAGE("Pending Phase-5 transport CRC + bit-flip injector stub");
}

/* ---- Row 6 - Single-bit corruption on CTO payload --------------------- */

void test_row06_single_bit_corruption_on_cto(void)
{
    /* Catalogue: transport CRC drops; master retries once; final command
     * succeeds. Master observes exactly one retry counter increment.
     */
    TEST_IGNORE_MESSAGE("Pending Phase-5 master cto_retry + Phase-5 corrupting transport stub");
}

/* ---- Row 7 - CTO timeout (no slave response) -------------------------- */

void test_row07_cto_timeout_no_response(void)
{
    /* Catalogue: master retries 3 then declares connection lost.
     * AUTOSAR E2E §4.3.3 fault class: Delay.
     */
    TEST_IGNORE_MESSAGE("Pending Phase-5 master cto_retry + null transport stub");
}

/* ---- Row 8 - Slave reboot mid-DAQ ------------------------------------- */

void test_row08_slave_reboot_mid_daq(void)
{
    /* Catalogue: CONNECT mismatch detected on reconnect; master resets CTR
     * and restarts DAQ; MDF4 has explicit reboot marker.
     */
    TEST_IGNORE_MESSAGE("Pending Phase-3 master DAQ + Phase-3 reboot-marker MDF4 schema");
}

/* ---- Row 9 - A2L drift (hash mismatch) -------------------------------- */

void test_row09_a2l_drift_hash_mismatch(void)
{
    /* Catalogue: master refuses to start DAQ; requires A2L re-fetch.
     * Slave reports its A2L hash in the CONNECT response (currently the
     * dispatcher returns a fixed comm-mode-basic byte; Phase-2 PR-30 adds
     * the hash field per ASAM MCD-2 MC v1.7 binary-hash extension).
     */
    TEST_IGNORE_MESSAGE("Pending Phase-2 PR-30 A2L parser + Phase-5 master hash compare on CONNECT");
}

/* ---- Row 10 - CRC mismatch on CAL write ------------------------------- */

void test_row10_crc_mismatch_on_cal_write(void)
{
    /* Catalogue: master rolls back the write; old value preserved; error
     * surfaced. Depends on DOWNLOAD + BUILD_CHECKSUM (Phase-2 PR-29) +
     * master rollback policy (Phase-4).
     */
    TEST_IGNORE_MESSAGE("Pending Phase-2 PR-29 DOWNLOAD+BUILD_CHECKSUM + Phase-4 master CAL rollback");
}

/* ---- Row 11 - Bus-off on CAN-FD --------------------------------------- */

void test_row11_bus_off_on_can_fd(void)
{
    /* Catalogue: master observes connection-lost event; auto-reconnect
     * within 5s of bus recovery (ISO 11898-1:2024 §10 - 128x 11 recessive
     * bits).
     */
    TEST_IGNORE_MESSAGE("Pending Phase-5 SocketCAN transport + bus-off injector");
}

/* ---- Row 12 - ECC double-bit error on CAL page (space) ---------------- */

void test_row12_ecc_double_bit_error_on_cal_page(void)
{
    /* Catalogue: EDAC raises EV_FAULT; slave reloads CAL from flash mirror;
     * no operator action required. Space profile only.
     */
    TEST_IGNORE_MESSAGE("Pending Phase-8 space EDAC SEC-DED + flash-mirror reload");
}

/* ---- Row 13 - Service-mode auth failure (wrong key) ------------------- */

void test_row13_service_mode_auth_failure(void)
{
    /* Catalogue: after 3 failed unlocks slave locks for 10 minutes.
     * Space profile only; AES-128 16-byte challenge / response.
     */
    TEST_IGNORE_MESSAGE("Pending Phase-8 AES-128 seed-and-key + service-mode lockout timer");
}

/* ---- Row 14 - MTU overflow (CTO > MAX_CTO) ---------------------------- */

void test_row14_mtu_overflow_cto_oversize(void)
{
    /* Catalogue: reject malformed CTO with ERR_CMD_SYNTAX; no slave state
     * change.
     *
     * The current Phase-1+2-read-path dispatcher does NOT enforce a
     * req_len <= MAX_CTO check. It dispatches based on request[0] and
     * ignores any bytes beyond what the per-command handler reads. So
     * sending a 16-byte request with request[0]==CONNECT would still set
     * state->connected = true. That violates the "no slave state change"
     * pass criterion.
     *
     * Robustness verified TODAY: the dispatcher does not read past req_len
     * for any handler; address-sanitiser + UBSan stay clean when we feed
     * an oversize input. That is the conservative MISRA-C:2023 invariant
     * the dispatcher already enforces.
     *
     * Pending: explicit oversize-CTO rejection. Owning PR: Phase-2 PR-29
     * (or a dedicated dispatcher-hardening PR).
     */
    TEST_IGNORE_MESSAGE("Pending Phase-2 PR-29 dispatcher explicit MAX_CTO size check");
}

/* ---- Row 15 - Malformed CTO PID byte ---------------------------------- */

/* Helper for row 15: dispatch one byte with the given PID, assert that the
 * dispatcher returns ERR_CMD_UNKNOWN with no state change beyond what the
 * unknown-PID path is permitted to touch.
 */
static void assert_unknown_pid_rejected(uint8_t pid)
{
    bool const     was_connected     = g_state.connected;
    uint8_t const  was_session_state = g_state.session_status;
    uint8_t const  request[1]        = {pid};
    int const      rc                = tethys_xcp_dispatch(
        &g_state, request, sizeof request, g_response, sizeof g_response, &g_response_len);

    TEST_ASSERT_EQUAL_INT_MESSAGE(0, rc, "Dispatcher returned -1 for unknown PID");
    TEST_ASSERT_EQUAL_size_t_MESSAGE((size_t)2U, g_response_len,
        "Unknown PID response should be PID + error code (2 bytes)");
    TEST_ASSERT_EQUAL_HEX8_MESSAGE(TETHYS_XCP_PID_ERR, g_response[0],
        "Unknown PID response PID byte should be ERR");
    TEST_ASSERT_EQUAL_HEX8_MESSAGE(TETHYS_XCP_ERR_CMD_UNKNOWN, g_response[1],
        "Unknown PID response should carry ERR_CMD_UNKNOWN (0x20)");
    /* The unknown-PID path is not permitted to mutate session state. */
    TEST_ASSERT_EQUAL_MESSAGE(was_connected, g_state.connected,
        "Unknown PID handler must not mutate state->connected");
    TEST_ASSERT_EQUAL_UINT8_MESSAGE(was_session_state, g_state.session_status,
        "Unknown PID handler must not mutate state->session_status");
}

void test_row15_malformed_cto_pid_byte_low_range(void)
{
    /* Catalogue: every unknown PID is rejected with ERR_CMD_UNKNOWN;
     * no crash; ASan / UBSan clean.
     *
     * The dispatcher's known-PID set today is:
     *   CONNECT (0xFF), DISCONNECT (0xFE), GET_STATUS (0xFD),
     *   GET_VERSION (0xC0), SET_MTA (0xF6), UPLOAD (0xF5),
     *   SHORT_UPLOAD (0xF4).
     * Every other byte falls through the else branch and returns
     * ERR_CMD_UNKNOWN.
     *
     * We sample the entire low half (0x00..0x7F) plus a handful of
     * mid-range and high-range unknowns. Iterating every byte 0x00..0xFF
     * would double-count the known PIDs above; we skip those explicitly.
     */
    for (uint16_t pid = 0x00U; pid <= 0x7FU; ++pid) {
        setUp(); /* reset state per iteration so each PID lands in a clean session */
        assert_unknown_pid_rejected((uint8_t)pid);
    }
}

void test_row15_malformed_cto_pid_byte_high_range_unknowns(void)
{
    /* Spot-check unknown PIDs in the 0x80..0xFF band (XCP reserves
     * 0xC0..0xFF for standard commands; this catches the gaps).
     * Skip the known commands above.
     */
    static uint8_t const unknown_high_pids[] = {
        0x80U, 0xA0U, 0xBFU,                                      /* below the standard-cmd band */
        0xC1U, 0xC2U, 0xC3U, 0xCFU,                               /* gaps just above GET_VERSION */
        0xD0U, 0xD4U, 0xDFU,
        0xE0U, 0xEFU,
        0xF0U, 0xF1U, 0xF2U, 0xF3U,                               /* gaps below SHORT_UPLOAD */
        0xF7U, 0xF8U, 0xF9U, 0xFAU, 0xFBU, 0xFCU                  /* SYNCH 0xFC defined but unimplemented today */
    };
    for (size_t i = 0U; i < (sizeof unknown_high_pids / sizeof unknown_high_pids[0]); ++i) {
        setUp();
        assert_unknown_pid_rejected(unknown_high_pids[i]);
    }
}

void test_row15_malformed_cto_pid_byte_after_connect(void)
{
    /* Stronger property: even after a CONNECT (state is now connected),
     * an unknown PID must not silently flip state back to disconnected.
     * (DISCONNECT 0xFE is the only path that does that.)
     */
    connect_session();
    TEST_ASSERT_TRUE(g_state.connected);

    static uint8_t const unknowns[] = {0x00U, 0x42U, 0xCDU, 0xF7U};
    for (size_t i = 0U; i < (sizeof unknowns / sizeof unknowns[0]); ++i) {
        assert_unknown_pid_rejected(unknowns[i]);
        TEST_ASSERT_TRUE_MESSAGE(g_state.connected,
            "Unknown PID handler must not silently disconnect the session");
    }
}

/* ---- Row 16 - Continuous loss > blackout bound ------------------------ */

void test_row16_continuous_loss_above_blackout_bound(void)
{
    /* Catalogue: master alert fires within +/- 100 ms of the bound;
     * halts DAQ if per-ODT policy = halt. Marine 1 kHz DAQ bound is
     * 100 ms (ADR-0010 §6.2 table row 1).
     */
    TEST_IGNORE_MESSAGE("Pending Phase-3 master DAQ blackout timer + per-ODT policy enum");
}
