# ADR-0002 - Profile-based build system (marine, space)

- **Status:** accepted
- **Date:** 2026-05-14
- **Deciders:** @goldr0g3r (project owner)
- **Consulted:** parent plan §3.3 profile table
- **Informed:** Phase 1 / 7 / 8 implementers
- **Supersedes:** —
- **Superseded by:** —
- **Accepted by:** PR-3 `docs(architecture)`

## Context and Problem Statement

Tethys targets two environments with diverging invariants (parent plan §3.3): **marine** (CAN-FD + Ethernet, optional CAL CRC, optional 4-byte seed-and-key, full MDF4 logging, MISRA mandatory+required) and **space** (UART/SxI wrapped in CCSDS COP-1 + 1-wire FT CAN, mandatory EDAC, mandatory 16-byte AES-128 seed-and-key, watermarked ring-buffer logging, MISRA mandatory+required+advisory, no recursion, no goto).

The two profiles share most of the protocol core but differ on:

- Transport set (per [ADR-0004](0004-transport-abstraction-layer.md)).
- CAL page protection (CRC vs EDAC).
- Seed-and-key (4-byte optional vs 16-byte AES-128 mandatory; see [ADR-0006](0006-aes-128-seed-and-key.md)).
- Coding rules strictness (mandatory+required vs +advisory; see [ADR-0003](0003-misra-c-2023-as-coding-gate.md)).
- Endianness (runtime vs compile-time).
- Buffer sizing (per [ADR-0005](0005-no-dynamic-allocation.md)).

How should Tethys express these divergences without duplicating code or creating runtime overhead?

## Decision Drivers

- ECSS-E-ST-40C Rev.1 (S18) and IACS UR E22 Rev.3 (S11) both prefer compile-time over runtime profile selection: smaller flight binary, no dead code, deterministic memory layout.
- Slave runs on memory-constrained MCUs (STM32F4 = 192 KB SRAM); runtime profile flags would bloat both code (both paths compiled in) and RAM (worst-case sized for both).
- Drift between two forks is a known maintenance hazard for safety-critical software.
- The [`marine-profile-invariants.mdc`](../../.cursor/rules/marine-profile-invariants.mdc) and [`space-profile-invariants.mdc`](../../.cursor/rules/space-profile-invariants.mdc) Cursor rules express the invariants but need a corresponding build-time mechanism.

## Considered Options

1. **Runtime profile flag** (`tethys_set_profile(MARINE)` at boot). Both code paths compiled in; switch at runtime.
2. **Separate forks** of the codebase (`tethys-marine` + `tethys-space` repositories). Independent evolution.
3. **Compile-time profile selection via CMake** (`cmake -DTETHYS_PROFILE=marine|space`). One source tree, two build outputs.

## Decision Outcome

Chose **Option 3** (compile-time CMake selection).

- The single CMake build flag `TETHYS_PROFILE` accepts `marine` or `space` (no default; build fails on missing value).
- Profile-specific code lives under `slave/src/profiles/<profile>/` and `slave/profiles/<profile>.cmake`.
- Profile-specific configuration headers live under `slave/include/tethys/profile_<profile>.h`.
- The `tethys_profile.h` aggregator picks the right per-profile header via `#ifdef TETHYS_PROFILE_MARINE` / `TETHYS_PROFILE_SPACE`.
- The `tethys_static_memory.h` header (per [ADR-0005](0005-no-dynamic-allocation.md)) is regenerated per profile.

## Consequences

- **Positive:** Smaller flight binaries (no dead code from the other profile); RAM layout exactly matches the selected profile; no runtime branching on profile flags in the hot path.
- **Positive:** A single source tree avoids fork drift. PRs touch one set of files; both profiles get tested in CI (the matrix in `ci.yml` builds both).
- **Positive:** The per-profile Cursor rules ([`marine-profile-invariants.mdc`](../../.cursor/rules/marine-profile-invariants.mdc), [`space-profile-invariants.mdc`](../../.cursor/rules/space-profile-invariants.mdc)) gate at file-glob level, which maps cleanly onto `slave/src/profiles/<profile>/` paths.
- **Negative:** Profile-aware ifdefs need disciplined use; cppcheck's coverage of each profile must be invoked twice (once per profile) in CI.
- **Negative:** Adding a new profile (e.g. `automotive`) is a substantial change: new directory tree, new Cursor rule, new CI matrix row, new `tethys_static_memory.h` generation.

## References

- Parent plan §3.3 (profile table).
- [`marine-profile-invariants.mdc`](../../.cursor/rules/marine-profile-invariants.mdc), [`space-profile-invariants.mdc`](../../.cursor/rules/space-profile-invariants.mdc).
- [ADR-0003](0003-misra-c-2023-as-coding-gate.md), [ADR-0004](0004-transport-abstraction-layer.md), [ADR-0005](0005-no-dynamic-allocation.md), [ADR-0006](0006-aes-128-seed-and-key.md) - all reference the profile mechanism.
- ECSS-E-ST-40C Rev.1 (S18 in [`phase-0-standards-matrix.csv`](../research/phase-0-standards-matrix.csv)) and IACS UR E22 Rev.3 (S11) - process anchors.
