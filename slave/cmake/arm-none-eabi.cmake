# arm-none-eabi.cmake - cross-compile toolchain for ARM Cortex-M targets.
#
# Used by the per-MCU CMake presets (`marine-stm32f4`, `marine-stm32f7`,
# `space-stm32h7`) to build the Tethys slave library for STM32 Nucleo boards
# without running native code on the host.
#
# Profiles: marine + space.
# Standards trace:
#   - ADR-0002 - profile-based build system (cross-compile is part of the
#     profile substrate).
#   - Parent plan §5 (toolchain - arm-none-eabi-gcc 14.x).
#   - Parent plan §7 (Phase 7 - marine STM32F4/F7).
#   - Parent plan §8 (Phase 8 - space STM32H7 ECC RAM).
#
# Per-MCU flags are layered ON TOP of this file via the presets'
# `cacheVariables` (`TETHYS_MCU_FLAGS`). This file sets only the bits that are
# common to every Cortex-M target.
#
# Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.

# CMake refuses to load a toolchain file twice. Guard against that.
if(DEFINED TETHYS_ARM_NONE_EABI_TOOLCHAIN_LOADED)
  return()
endif()
set(TETHYS_ARM_NONE_EABI_TOOLCHAIN_LOADED TRUE)

# ---- System identification --------------------------------------------------

# `Generic` tells CMake we are building for a freestanding environment.
# Skips host-OS-specific feature checks (e.g. POSIX clock_gettime).
set(CMAKE_SYSTEM_NAME      Generic)
set(CMAKE_SYSTEM_PROCESSOR arm)

# ---- Compiler discovery -----------------------------------------------------
#
# We use a fixed `arm-none-eabi-` prefix. CI installs the toolchain via
# `sudo apt-get install gcc-arm-none-eabi` (Ubuntu 24.04 ships 14.x).
# Windows dev uses `winget install ArmGnuToolchain` per
# docs/runbooks/hardware-setup-stm32.md §2.1.

set(TETHYS_ARM_PREFIX "arm-none-eabi-" CACHE STRING
    "Prefix for the ARM cross toolchain binaries")

set(CMAKE_C_COMPILER     "${TETHYS_ARM_PREFIX}gcc")
set(CMAKE_CXX_COMPILER   "${TETHYS_ARM_PREFIX}g++")
set(CMAKE_ASM_COMPILER   "${TETHYS_ARM_PREFIX}gcc")
set(CMAKE_AR             "${TETHYS_ARM_PREFIX}ar")
set(CMAKE_RANLIB         "${TETHYS_ARM_PREFIX}ranlib")
set(CMAKE_LINKER         "${TETHYS_ARM_PREFIX}ld")
set(CMAKE_OBJCOPY        "${TETHYS_ARM_PREFIX}objcopy" CACHE FILEPATH "objcopy")
set(CMAKE_OBJDUMP        "${TETHYS_ARM_PREFIX}objdump" CACHE FILEPATH "objdump")
set(CMAKE_SIZE           "${TETHYS_ARM_PREFIX}size"    CACHE FILEPATH "size")

# CMake's `try_compile` of an executable would need a startup file + linker
# script we do not have at the foundation-PR stage. Static library is enough to
# satisfy CMake's compiler-detection probe.
set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)

# ---- Sysroot + find-root semantics -----------------------------------------
#
# Standard cross-compile pattern: only search the toolchain's bundled libs
# (NEVER look up host /usr/lib at link time). Programs (cmake's `find_program`)
# still resolve from the host so tools like `cmake`, `ninja`, `python`, etc.
# remain available.

set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)

# ---- Common compile + link flags -------------------------------------------
#
# These apply to EVERY Cortex-M build. Per-MCU `-mcpu` / `-mfpu` /
# `-mfloat-abi` / device defines come from the preset via `TETHYS_MCU_FLAGS`.
#
# Rationale:
#   * `-ffunction-sections -fdata-sections` + `-Wl,--gc-sections` strips
#     unused code (matters on 192 KB SRAM STM32F4).
#   * `--specs=nano.specs` selects newlib-nano (smaller stdlib).
#   * `--specs=nosys.specs` stubs out system calls (POSIX syscall layer
#     unused on bare metal; calls like `_write` return -1 instead of linking
#     in libgloss).
#   * `-fstack-usage` emits `.su` files alongside `.o` for static stack
#     analysis (ECSS-E-ST-40C Rev.1 §5.4 worst-case stack analysis).
#   * Strict warnings come from the project-level preset (`flags-gcc-clang`),
#     not the toolchain file, so the host POSIX build sees the same gates.

set(TETHYS_ARM_COMMON_FLAGS
    "-ffunction-sections -fdata-sections -fno-common -fstack-usage")

set(CMAKE_C_FLAGS_INIT
    "${TETHYS_ARM_COMMON_FLAGS} ${TETHYS_MCU_FLAGS}")
set(CMAKE_CXX_FLAGS_INIT
    "${TETHYS_ARM_COMMON_FLAGS} ${TETHYS_MCU_FLAGS} -fno-exceptions -fno-rtti")
set(CMAKE_ASM_FLAGS_INIT
    "${TETHYS_MCU_FLAGS}")

set(CMAKE_EXE_LINKER_FLAGS_INIT
    "${TETHYS_MCU_FLAGS} --specs=nano.specs --specs=nosys.specs -Wl,--gc-sections -Wl,--print-memory-usage")

# Release defaults: -Os for code-size (STM32F4 = 1 MB flash but marine
# profile drags in W5500 SPI + FDCAN ring buffers; -O3 inflates by ~15 %).
# Override with -DCMAKE_BUILD_TYPE=MinSizeRel or pass -O2 / -O3 explicitly.
set(CMAKE_C_FLAGS_RELEASE_INIT   "-Os -DNDEBUG")
set(CMAKE_CXX_FLAGS_RELEASE_INIT "-Os -DNDEBUG")

# ---- Skip non-applicable host checks ---------------------------------------
#
# CMake's compiler-introspection step probes for shared library + dynamic
# loader support. Both are nonsensical on Cortex-M. Disabling them speeds up
# configure by ~2 s in CI.

set(CMAKE_C_COMPILER_FORCED   TRUE)
set(CMAKE_CXX_COMPILER_FORCED TRUE)
