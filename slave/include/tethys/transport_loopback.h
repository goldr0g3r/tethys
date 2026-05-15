/*
 * tethys/transport_loopback.h - In-process loopback transport (universal baseline).
 *
 * Module: tethys::transport::loopback
 * Profiles: posix-sim, all (used by conformance + scaffold tests)
 * Standards: ADR-0004 (transport-abstraction-layer interface);
 *            ADR-0010 row 12 (loopback zero-loss budget)
 * Trace: docs/traceability.csv (TETHYS-DES-0031 loopback transport)
 *
 * Provides a single-frame ring-buffer pair where send writes the head and
 * recv consumes the tail. transport_id = TETHYS_TR_LOOPBACK; reliable;
 * zero-loss; mtu = 256 bytes (matches the XCP MAX_DTO).
 *
 * Used by the Phase-5 conformance suite as the universal baseline: every
 * other transport is asserted against the same shape of test that loopback
 * passes.
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */
#ifndef TETHYS_TRANSPORT_LOOPBACK_H
#define TETHYS_TRANSPORT_LOOPBACK_H

#pragma once

#include "tethys/tethys_export.h"
#include "tethys/tethys_transport.h"

#ifdef __cplusplus
extern "C" {
#endif

/** Loopback MTU - 256 bytes matches the default XCP MAX_DTO. */
#define TETHYS_LOOPBACK_MTU   ((uint16_t)256U)

/** Depth of the ring buffer (frames). 8 is enough for the conformance suite's
 *  burst scenarios. Statically sized per ADR-0005. */
#define TETHYS_LOOPBACK_DEPTH ((size_t)8U)

/**
 * @brief Get the loopback transport descriptor.
 *
 * Returns a pointer to a `static const` descriptor. Pass to
 * `tethys_tr_register_transport()` to make loopback the active transport.
 *
 * @return Non-NULL descriptor pointer.
 */
TETHYS_EXPORT const tethys_tr_descriptor_t *tethys_tr_loopback_descriptor(void);

/**
 * @brief Reset the loopback ring buffer.
 *
 * Tests call this between cases. Idempotent.
 */
TETHYS_EXPORT void tethys_tr_loopback_reset(void);

/**
 * @brief Inject a synthetic loss event (advances `count` slots in the ring).
 *
 * Used by the conformance suite to verify the event-callback path without
 * needing a real lossy transport.
 *
 * @param[in] count How many frames to declare lost (1..TETHYS_LOOPBACK_DEPTH).
 */
TETHYS_EXPORT void tethys_tr_loopback_inject_loss(uint16_t count);

/**
 * @brief Report how many frames are currently queued (testing-only).
 *
 * @return 0..TETHYS_LOOPBACK_DEPTH.
 */
TETHYS_EXPORT size_t tethys_tr_loopback_pending(void);

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* TETHYS_TRANSPORT_LOOPBACK_H */
