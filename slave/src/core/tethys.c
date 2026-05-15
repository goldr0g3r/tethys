/*
 * src/core/tethys.c - top-level library entry point.
 *
 * Module: tethys (top-level)
 * Profiles: all (marine, space, posix-sim)
 * Standards: ASAM XCP 1.4 Part 2 §1.1 (overview); MISRA C:2023
 * Trace: docs/traceability.csv (lands in Phase 1)
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */
#include "tethys/tethys.h"

char const* tethys_version(void)
{
    return "tethys";
}
