# space.cmake - thin wrapper that engages the space profile.
#
# Invoked by `slave/CMakeLists.txt` when `TETHYS_PROFILE=space`. Delegates the
# real work to `slave/profiles/space.cmake` per ADR-0002 (file-glob matching
# of the `space-profile-invariants.mdc` Cursor rule).
#
# Standards trace:
#   - ADR-0002 - profile-based build system.
#   - ADR-0006 - AES-128 16-byte seed-and-key (mandatory space).
#   - parent plan §3.3 - profile table.
#   - .cursor/rules/space-profile-invariants.mdc - feature invariants.
#
# Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.

message(STATUS "Tethys: space profile selected")

# Compile-time define visible to every C source.
add_compile_definitions(
    TETHYS_PROFILE_SPACE=1
    TETHYS_PROFILE_NAME="space"
)

include("${CMAKE_CURRENT_SOURCE_DIR}/profiles/space.cmake")
