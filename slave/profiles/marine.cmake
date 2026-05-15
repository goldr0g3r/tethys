# profiles/marine.cmake - marine profile real per-target flags + source list.
#
# Companion to slave/cmake/marine.cmake (thin wrapper). This file owns the
# marine-specific compile flags, source-file inclusion, and feature toggles
# documented in `.cursor/rules/marine-profile-invariants.mdc` and the parent
# plan §3.3 profile table.
#
# Standards trace:
#   - ADR-0002 - profile-based build system.
#   - IEC 60945 - maritime navigation equipment environmental (documented;
#     no compile effect - bench / lab verification covers this).
#   - IACS UR E22 Rev.3 - marine class society SW process anchor.
#   - .cursor/rules/marine-profile-invariants.mdc - feature invariants.
#
# Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.

# ---- Marine profile cache variables -----------------------------------------

option(TETHYS_MARINE_CAL_PAGE_CRC
    "Marine: enable optional CRC over CAL pages (recommended for production)"
    OFF)

option(TETHYS_MARINE_WATCHDOG_ON_DAQ_TICK
    "Marine: kick the watchdog on every DAQ tick (default OFF; XCP must never block the watchdog)"
    OFF)

# IEC 61162-450 default UDP port for Ethernet payload framing on shipboards.
# Documented here; the master tool's --transport udp connector defaults to
# this if no port is specified.
set(TETHYS_MARINE_DEFAULT_UDP_PORT "60001" CACHE STRING
    "Marine: default UDP port for the Ethernet transport (IEC 61162-450 baseline)")

# DAQ event-channel target rate hint (Hz). Drives static sizing of the ODT
# scratch buffers (per ADR-0005 no-dynamic-allocation).
set(TETHYS_MARINE_DAQ_EVENT_HZ "1000" CACHE STRING
    "Marine: target DAQ event-channel rate in Hz (1 kHz baseline)")

# ---- Endianness handling ----------------------------------------------------
#
# Per the profile invariants: marine = runtime-detect (network heterogeneous).
# space = compile-time-fixed.

add_compile_definitions(
    TETHYS_MARINE_ENDIAN_RUNTIME_DETECT=1
    TETHYS_MARINE_DAQ_EVENT_HZ=${TETHYS_MARINE_DAQ_EVENT_HZ})

if(TETHYS_MARINE_CAL_PAGE_CRC)
  add_compile_definitions(TETHYS_MARINE_CAL_PAGE_CRC=1)
else()
  add_compile_definitions(TETHYS_MARINE_CAL_PAGE_CRC=0)
endif()

if(TETHYS_MARINE_WATCHDOG_ON_DAQ_TICK)
  add_compile_definitions(TETHYS_MARINE_WATCHDOG_ON_DAQ_TICK=1)
else()
  add_compile_definitions(TETHYS_MARINE_WATCHDOG_ON_DAQ_TICK=0)
endif()

# ---- Marine seed-and-key ----------------------------------------------------
#
# Marine profile: seed-and-key is OPTIONAL and uses a 4-byte challenge by
# default (legacy hardware compatibility). When a marine deployment enables
# STIM in flight mode, the AES-128 16-byte scheme from ADR-0006 may be
# selected by setting `TETHYS_MARINE_SEED_AND_KEY=aes128` at cache time.

set(TETHYS_MARINE_SEED_AND_KEY "none" CACHE STRING
    "Marine: seed-and-key scheme (none | crc32 | aes128)")
set_property(CACHE TETHYS_MARINE_SEED_AND_KEY PROPERTY STRINGS
    "none" "crc32" "aes128")

if(TETHYS_MARINE_SEED_AND_KEY STREQUAL "aes128")
  add_compile_definitions(TETHYS_SEED_AND_KEY_AES128=1)
elseif(TETHYS_MARINE_SEED_AND_KEY STREQUAL "crc32")
  add_compile_definitions(TETHYS_SEED_AND_KEY_CRC32=1)
endif()

# ---- Marine profile sources -------------------------------------------------

target_sources(tethys_slave PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/src/profiles/marine/marine_init.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/profiles/marine/marine_workload.c"
)

target_include_directories(tethys_slave PUBLIC
    "$<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/src/profiles/marine>"
)

# ---- Marine-specific HAL sources (only when cross-compiling) ----------------

if(TETHYS_PLATFORM STREQUAL "stm32f4" OR TETHYS_PLATFORM STREQUAL "stm32f7")
  message(STATUS "Tethys/marine: STM32 HAL stubs enabled (TETHYS_PLATFORM=${TETHYS_PLATFORM})")
  add_compile_definitions(
      TETHYS_PLATFORM_STM32=1
      TETHYS_PLATFORM_STM32F4=$<STREQUAL:${TETHYS_PLATFORM},stm32f4>
      TETHYS_PLATFORM_STM32F7=$<STREQUAL:${TETHYS_PLATFORM},stm32f7>)
  target_sources(tethys_slave PRIVATE
      "${CMAKE_CURRENT_SOURCE_DIR}/src/platform/stm32/stm32_systick.c"
      "${CMAKE_CURRENT_SOURCE_DIR}/src/platform/stm32/stm32_uart.c"
      "${CMAKE_CURRENT_SOURCE_DIR}/src/platform/stm32/stm32_canfd.c"
      "${CMAKE_CURRENT_SOURCE_DIR}/src/platform/stm32/stm32_eth.c"
      "${CMAKE_CURRENT_SOURCE_DIR}/src/platform/stm32/stm32_watchdog.c"
      "${CMAKE_CURRENT_SOURCE_DIR}/src/platform/stm32/stm32_startup.c"
  )
endif()
