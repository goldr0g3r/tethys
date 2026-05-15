/*
 * fuzz_cto_dispatcher.c - libFuzzer harness for tethys_xcp_dispatch().
 *
 * Module: tests::fuzz::cto_dispatcher
 * Profiles: all (marine, space, posix-sim)
 * Standards: ASAM XCP 1.4 Part 2 §1.3.2 (CONNECT); §1.3.3 (SET_MTA/UPLOAD/
 *            SHORT_UPLOAD); Table 12 (error codes); MISRA C:2023;
 *            ECSS-E-ST-40C Rev.1 §5.5 (robustness verification);
 *            DO-178C §6.4.4.1 (robustness testing).
 * Trace: docs/traceability.csv rows TETHYS-REQ-VER-002 + TETHYS-REQ-FAULT-015.
 *
 * What it does:
 *   - libFuzzer mutates random byte sequences and calls
 *     LLVMFuzzerTestOneInput(data, size) for each.
 *   - The harness clamps size to a bounded RX window, builds a CTO from
 *     the input, dispatches it through tethys_xcp_dispatch(), and
 *     discards the response. No crash, no UB, no OOB read or write.
 *   - The first byte of the input drives the dispatcher's PID switch;
 *     subsequent bytes act as command-body fuzz. SET_MTA / UPLOAD /
 *     SHORT_UPLOAD with attached memory exercises the address-bounds
 *     checks inside the dispatcher.
 *
 * No dynamic allocation (ADR-0005). No recursion. No goto. All buffers
 * static; the dispatcher state and the memory window are file-scope
 * globals re-initialised per invocation.
 *
 * Build (local):
 *   clang -fsanitize=fuzzer,address,undefined -O1 -g \
 *     -I slave/include -I slave/tests/test/support \
 *     slave/fuzz/fuzz_cto_dispatcher.c slave/src/core/xcp_dispatcher.c \
 *     -o fuzz_cto_dispatcher
 *   ./fuzz_cto_dispatcher slave/fuzz/corpus/cto/ -max_total_time=600
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */
#include "tethys/xcp_dispatcher.h"

#include <stddef.h>
#include <stdint.h>
#include <string.h>

/* ---- Bounded RX / response / memory windows (static; ADR-0005) -------- */

/* The dispatcher's MAX_CTO is 8 today. We feed up to 64 bytes so the harness
 * exercises both the in-spec band AND the oversize band (the future explicit
 * size-check path; see slave/tests/robustness/test_robustness_catalogue.c
 * row 14). libFuzzer mutations beyond this length are truncated.
 */
#define FUZZ_MAX_RX     ((size_t)64U)
#define FUZZ_RESP_CAP   ((size_t)TETHYS_XCP_MAX_CTO)
#define FUZZ_MEM_SIZE   ((size_t)256U)

static uint8_t            g_request[FUZZ_MAX_RX];
static uint8_t            g_response[FUZZ_RESP_CAP];
static uint8_t            g_memory[FUZZ_MEM_SIZE];
static tethys_xcp_state_t g_state;

/* ---- libFuzzer entry point ------------------------------------------- */

/**
 * @brief Called by libFuzzer for each mutated input.
 *
 * @param data Mutated input bytes.
 * @param size Length of @p data in bytes (0..N).
 *
 * @return 0 always. libFuzzer interprets non-zero as "interesting" hinting,
 *         not as failure. Crashes / sanitiser hits are detected by the
 *         runtime, not by the return value.
 */
int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size);

int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size)
{
    /* Clamp to the bounded RX window. */
    size_t const req_len = (size > FUZZ_MAX_RX) ? FUZZ_MAX_RX : size;

    /* MISRA-friendly bounded copy. */
    for (size_t i = (size_t)0U; i < req_len; ++i) {
        g_request[i] = data[i];
    }

    /* Re-init dispatcher state per invocation so each mutation hits a
     * deterministic starting point. The memory window stays attached so
     * SET_MTA / UPLOAD / SHORT_UPLOAD have a non-NULL memory backend to
     * exercise the address-bounds path.
     */
    tethys_xcp_init(&g_state);
    /* Seed memory as a 0..255 ramp so out-of-bounds reads would surface
     * as visible byte values if the dispatcher ever returned data from
     * outside the attached window. */
    for (size_t i = (size_t)0U; i < FUZZ_MEM_SIZE; ++i) {
        g_memory[i] = (uint8_t)(i & 0xFFU);
    }
    tethys_xcp_attach_memory(&g_state, g_memory, FUZZ_MEM_SIZE);

    /* Pre-CONNECT mutations: ~50% of inputs (data[0] & 0x80 == 0) skip the
     * CONNECT, exercising the access-denied paths for stateful commands.
     * ~50% (data[0] & 0x80 != 0) do a CONNECT first so the stateful paths
     * are reachable. This doubles per-mutation coverage with zero extra
     * mutation budget. */
    if ((req_len > (size_t)0U) && ((data[0] & (uint8_t)0x80U) != (uint8_t)0U)) {
        uint8_t const connect_req[2] = {TETHYS_XCP_CMD_CONNECT, (uint8_t)0U};
        size_t        connect_resp_len = (size_t)0U;
        (void)tethys_xcp_dispatch(
            &g_state, connect_req, sizeof connect_req,
            g_response, sizeof g_response, &connect_resp_len);
    }

    /* The actual mutation. Response buffer is sized exactly MAX_CTO so the
     * dispatcher's resp_cap check is enforced; any handler that tries to
     * write past resp_cap will trigger ASan / UBSan.
     */
    size_t resp_len = (size_t)0U;
    (void)tethys_xcp_dispatch(
        &g_state, g_request, req_len, g_response, sizeof g_response, &resp_len);

    /* No crash, no UB, no OOB. libFuzzer treats reaching this return as
     * success for this input. */
    return 0;
}
