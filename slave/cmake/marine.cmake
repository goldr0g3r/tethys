# marine.cmake - thin wrapper that engages the marine profile.
#
# Invoked by `slave/CMakeLists.txt` when `TETHYS_PROFILE=marine`. Delegates the
# real work to `slave/profiles/marine.cmake` (per ADR-0002 the profile-specific
# CMake lives under `slave/profiles/` so that file-glob enforcement of the
# `marine-profile-invariants.mdc` Cursor rule matches cleanly).
#
# Standards trace:
#   - ADR-0002 - profile-based build system.
#   - parent plan §3.3 - profile table.
#   - .cursor/rules/marine-profile-invariants.mdc - feature invariants.
#
# Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.

message(STATUS "Tethys: marine profile selected")

# Compile-time define visible to every C source.
# Profile-specific source files use this to guard their per-profile bodies
# (e.g. CAL page CRC vs EDAC).
add_compile_definitions(
    TETHYS_PROFILE_MARINE=1
    TETHYS_PROFILE_NAME="marine"
)

include("${CMAKE_CURRENT_SOURCE_DIR}/profiles/marine.cmake")
