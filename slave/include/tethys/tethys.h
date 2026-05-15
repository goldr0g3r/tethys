/*
 * tethys/tethys.h - top-level public header for the Tethys slave library.
 *
 * Module: tethys (top-level)
 * Profiles: all (marine, space, posix-sim)
 * Standards: ASAM XCP 1.4 Part 2 §1.1 (overview); MISRA C:2023 (coding gate)
 * Trace: docs/traceability.csv (header row TETHYS-DES-0001 lands in Phase 1)
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */
#ifndef TETHYS_TETHYS_H
#define TETHYS_TETHYS_H

#pragma once

#include "tethys/tethys_export.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Reports the library name + version string.
 *
 * Placeholder symbol kept from the cmake-init scaffold so downstream
 * link-tests have something to call. Phase 1 adds the real `tethys_init()` +
 * `tethys_xcp_*` surface.
 *
 * @return Constant string `"tethys"`.
 */
TETHYS_EXPORT char const* tethys_version(void);

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* TETHYS_TETHYS_H */
