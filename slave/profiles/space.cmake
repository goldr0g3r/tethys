# profiles/space.cmake - space profile real per-target flags + source list.
#
# Companion to slave/cmake/space.cmake (thin wrapper). This file owns the
# space-specific compile flags, source-file inclusion, and feature toggles
# documented in `.cursor/rules/space-profile-invariants.mdc` and the parent
# plan §3.3 profile table.
#
# Standards trace:
#   - ADR-0002 - profile-based build system.
#   - ADR-0005 - no dynamic allocation.
#   - ADR-0006 - AES-128 16-byte seed-and-key (mandatory).
#   - ADR-0010 - packet-loss tolerance budget (space rows 8-11).
#   - ECSS-E-ST-40C Rev.1 - SW engineering process (DAL-B-equivalent).
#   - NPR 7150.2D - NASA SW engineering requirements.
#   - DO-178C DAL-B - aviation crossover (target).
#   - CCSDS 232.1-B-2 - COP-1 (transport-layer note; Worker B wires it).
#   - CCSDS 132.0-B-3 - Telemetry Space Data Link Protocol (transport).
#   - .cursor/rules/space-profile-invariants.mdc - all invariants below.
#   - .cursor/rules/no-recursion-no-goto.mdc - applied everywhere; doubly
#     enforced here (space profile mandates).
#
# Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.

# ---- Space profile cache variables (all mandatory; no off switch) ----------

# Endianness: space profile is compile-time-fixed per mission target. Default
# little (matches STM32 Cortex-M); override with -DTETHYS_SPACE_ENDIAN=big for
# heritage big-endian targets (e.g. PowerPC RAD750).
set(TETHYS_SPACE_ENDIAN "little" CACHE STRING
    "Space: compile-time fixed endianness (little|big)")
set_property(CACHE TETHYS_SPACE_ENDIAN PROPERTY STRINGS "little" "big")

# AES-128 key burn slot in flash. Real per-target key bytes are NOT committed
# to git; this is a placeholder address that the bring-up procedure overwrites
# with the per-target key per docs/runbooks/hardware-setup-stm32.md (§6).
set(TETHYS_SPACE_AES_KEY_FLASH_ADDR "0x080E0000" CACHE STRING
    "Space: flash address of the 16-byte per-target AES-128 key (read-protected sector)")

# Watchdog timeout: space profile defaults to a tight 32 ms - tighter than
# marine's 1 s baseline - because the deterministic ODT scheduling guarantees
# DAQ ticks land at <10 ms intervals.
set(TETHYS_IWDG_TIMEOUT_MS "32" CACHE STRING
    "Space: IWDG watchdog timeout in ms (default 32; marine default 1000)")

# ---- Compile-time invariants ------------------------------------------------
#
# Mirror the .cursor/rules/space-profile-invariants.mdc invariants as compile
# defines so the protocol core can branch on them where needed.

add_compile_definitions(
    TETHYS_SPACE_ENDIAN_FIXED=1
    TETHYS_SPACE_EDAC_MANDATORY=1
    TETHYS_SPACE_WATCHDOG_ON_DAQ_TICK=1
    TETHYS_SPACE_SEED_AND_KEY_AES128=1
    TETHYS_SPACE_NO_RECURSION_NO_GOTO=1
    TETHYS_SPACE_DETERMINISTIC_ODT=1
    TETHYS_SPACE_FLIGHT_MODE_DAQ_DEFAULT_OFF=1
    TETHYS_IWDG_TIMEOUT_MS=${TETHYS_IWDG_TIMEOUT_MS})

if(TETHYS_SPACE_ENDIAN STREQUAL "big")
  add_compile_definitions(TETHYS_SPACE_BIG_ENDIAN=1)
else()
  add_compile_definitions(TETHYS_SPACE_LITTLE_ENDIAN=1)
endif()

# ---- Space profile sources -------------------------------------------------

target_sources(tethys_slave PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/src/profiles/space/space_init.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/profiles/space/space_workload.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/profiles/space/edac.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/profiles/space/service_mode.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/security/aes128_seed_and_key.c"
)

target_include_directories(tethys_slave PUBLIC
    "$<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/src/profiles/space>"
    "$<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/src/security>"
)

# ---- Space-specific HAL sources (only when cross-compiling) ----------------

if(TETHYS_PLATFORM STREQUAL "stm32h7")
  message(STATUS "Tethys/space: STM32H7 HAL stubs enabled")
  add_compile_definitions(
      TETHYS_PLATFORM_STM32=1
      TETHYS_PLATFORM_STM32H7=1)
  target_sources(tethys_slave PRIVATE
      "${CMAKE_CURRENT_SOURCE_DIR}/src/platform/stm32/stm32_systick.c"
      "${CMAKE_CURRENT_SOURCE_DIR}/src/platform/stm32/stm32_uart.c"
      "${CMAKE_CURRENT_SOURCE_DIR}/src/platform/stm32/stm32_canfd.c"
      "${CMAKE_CURRENT_SOURCE_DIR}/src/platform/stm32/stm32_watchdog.c"
      "${CMAKE_CURRENT_SOURCE_DIR}/src/platform/stm32/stm32_startup.c"
  )
  # Note: no W5500 Ethernet on the space profile; UART/SxI + 1-wire FT CAN
  # only per the profile invariants.
endif()
