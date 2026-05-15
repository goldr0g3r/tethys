cmake_minimum_required(VERSION 3.14)

include(cmake/prelude.cmake)

project(
    tethys
    VERSION 0.1.0
    DESCRIPTION "Tethys slave - portable C11 XCP slave library (marine + space profiles)"
    HOMEPAGE_URL "https://github.com/goldr0g3r/tethys"
    LANGUAGES C
)

include(cmake/project-is-top-level.cmake)
include(cmake/variables.cmake)

# ---- Profile + platform selection ----
#
# Compile-time profile selection per ADR-0002. Empty default (host posix-sim
# build via `cmake --preset=dev` works with no profile - useful for the XCP
# core unit tests that are profile-agnostic).
#
# Profiles:
#   marine - STM32F4/F7 + CAN-FD + Ethernet (W5500); MISRA mandatory+required.
#   space  - STM32H7 + UART/SxI + 1-wire FT CAN; MISRA mandatory+required+advisory.
#
# Platforms:
#   posix  - host-side simulator (Phase 1+ CI); default when no platform set.
#   stm32f4, stm32f7, stm32h7 - cross-compile via slave/cmake/arm-none-eabi.cmake.
set(TETHYS_PROFILE "" CACHE STRING "Profile (marine|space|<empty for posix-sim>)")
set_property(CACHE TETHYS_PROFILE PROPERTY STRINGS "" "marine" "space")

set(TETHYS_PLATFORM "posix" CACHE STRING "Platform (posix|stm32f4|stm32f7|stm32h7)")
set_property(CACHE TETHYS_PLATFORM PROPERTY STRINGS
    "posix" "stm32f4" "stm32f7" "stm32h7")

# ---- Declare library ----
#
# Source files live under src/{core,transport,platform}/ per parent plan §14.
# Phase 1 adds the XCP dispatcher under src/core/; Phase 2+ adds DAQ, CAL,
# transport modules. Phase 7+8 (foundation) adds the platform sources via the
# profile cmake files.
add_library(
    tethys_slave
    src/core/tethys.c
    src/core/xcp_dispatcher.c
)
add_library(tethys::slave ALIAS tethys_slave)

# Platform abstraction sources: posix host-side build pulls in posix.c; STM32
# builds (selected by the marine/space profile cmake) pull in the stm32/*.c
# stubs. The host posix.c source compiles on Ubuntu / macOS / Windows and is
# used by Phase 1+ CI's slave-posix job.
if(TETHYS_PLATFORM STREQUAL "posix")
  target_sources(tethys_slave PRIVATE
      src/platform/posix.c
  )
endif()

# ---- Profile inclusion ----
#
# `include(cmake/<profile>.cmake)` delegates to a thin per-profile wrapper
# that pulls in `slave/profiles/<profile>.cmake` (the real flags + source
# list per ADR-0002).
if(TETHYS_PROFILE STREQUAL "marine")
  include(cmake/marine.cmake)
elseif(TETHYS_PROFILE STREQUAL "space")
  include(cmake/space.cmake)
elseif(TETHYS_PROFILE STREQUAL "")
  message(STATUS "Tethys: no profile selected (posix-sim build - protocol-core only)")
else()
  message(FATAL_ERROR
      "Tethys: TETHYS_PROFILE='${TETHYS_PROFILE}' is not recognised; "
      "expected 'marine', 'space', or empty (posix-sim).")
endif()

include(GenerateExportHeader)
generate_export_header(
    tethys_slave
    BASE_NAME tethys
    EXPORT_FILE_NAME export/tethys/tethys_export.h
)

if(NOT BUILD_SHARED_LIBS)
  target_compile_definitions(tethys_slave PUBLIC TETHYS_STATIC_DEFINE)
endif()

set_target_properties(
    tethys_slave PROPERTIES
    C_VISIBILITY_PRESET hidden
    VERSION "${PROJECT_VERSION}"
    SOVERSION "${PROJECT_VERSION_MAJOR}"
    EXPORT_NAME slave
    OUTPUT_NAME tethys_slave
)

target_include_directories(
    tethys_slave ${warning_guard}
    PUBLIC
    "\$<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>"
)

target_include_directories(
    tethys_slave SYSTEM
    PUBLIC
    "\$<BUILD_INTERFACE:${PROJECT_BINARY_DIR}/export>"
)

# `target_compile_features(... c_std_11)` walks CMake's compiler-feature
# database which is unpopulated for arm-none-eabi-gcc (CMake only ships
# feature tables for hosted compilers). Use the direct property pair instead;
# semantically identical for our use - C11 is required, no GNU extensions.
set_target_properties(tethys_slave PROPERTIES
    C_STANDARD 11
    C_STANDARD_REQUIRED ON
    C_EXTENSIONS OFF)

# ---- Install rules ----
#
# Install rules are host-side concerns (lib + headers go under
# CMAKE_INSTALL_PREFIX). Skip them when cross-compiling for STM32 - we ship
# the cross-built libtethys_slave.a as a CI artefact, not as a system install.
if(NOT CMAKE_SKIP_INSTALL_RULES AND NOT CMAKE_CROSSCOMPILING)
  include(cmake/install-rules.cmake)
endif()

# ---- Developer mode ----

if(NOT tethys_DEVELOPER_MODE)
  return()
elseif(NOT PROJECT_IS_TOP_LEVEL)
  message(
      AUTHOR_WARNING
      "Developer mode is intended for developers of tethys"
  )
endif()

include(cmake/dev-mode.cmake)
