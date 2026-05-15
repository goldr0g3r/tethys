# Phase 0 - Layout execution (research note)

> Research note backing the `p0-layout` PR
> (`chore(layout): rebrand slave -> tethys; slave/include/slave -> slave/include/tethys; slave/source -> slave/src/core; add dev preset`).
> Parent plan: [`.cursor/plans/xcp_extreme-env_tool_14019278.plan.md`](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md) - todo `p0-layout` (PR-1b).
> Sub-plan: [`.cursor/plans/p0-layout_pr-1b_d2af9911.plan.md`](../../.cursor/plans/p0-layout_pr-1b_d2af9911.plan.md).
> Companion: [`docs/research/phase-1-scaffold-execution.md`](phase-1-scaffold-execution.md) - the original cmake-init scaffold that left this F2 follow-up.

## Scope

Resolves PR-1 follow-up F2: rename slave/include/slave -> slave/include/tethys,
slave/source -> slave/src/core, and rebrand the CMake `slave` project and
target names to `tethys` throughout. Also adds a `dev` configure preset to
`slave/CMakePresets.json` matching `ci-ubuntu` to fix the F5 CI clang-tidy +
gcc-fanalyzer workflow failures (`No such preset: dev`).

## Sources (retrieved 2026-05-15)

| ID | Title | URL | Used for |
| --- | --- | --- | --- |
| R1 | Parent plan section 14 | [`.cursor/plans/xcp_extreme-env_tool_14019278.plan.md`](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md) | Authoritative `slave/include/tethys/`, `slave/src/{core,transport,platform}/` layout. |
| R2 | cmake-init v0.41.1 | <https://github.com/friendlyanon/cmake-init> | Origin of the existing `slave` namespace; this PR renames it to `tethys`. |
| R3 | CMake preset spec v2 | <https://cmake.org/cmake/help/latest/manual/cmake-presets.7.html> | `dev` preset additions. |
| R4 | docs/coding-standard.md | [../coding-standard.md](../coding-standard.md) | §7.1 file header template + §4.1 header guard format. |
| R5 | PR-1 research note | [phase-1-scaffold-execution.md](phase-1-scaffold-execution.md) | F2 follow-up identification. |

## Renames performed (git-tracked)

| Before | After |
| --- | --- |
| `slave/include/slave/slave.h` | `slave/include/tethys/tethys.h` |
| `slave/source/slave.c` | `slave/src/core/tethys.c` |

Both renames done via `git mv` to preserve git blame / log history. The
`slave/include/tethys/.gitkeep` and `slave/src/core/.gitkeep` placeholders
were deleted because the renamed real files now occupy those paths.
`slave/source/` and `slave/include/slave/` dirs are gone.

## CMake project rebranding

`slave/CMakeLists.txt`:

- `project(slave ...)` -> `project(tethys ...)`.
- Library target `slave_slave` -> `tethys_slave`.
- Alias `slave::slave` -> `tethys::slave` (with `EXPORT_NAME slave` so the
  `tethys::slave` namespace separator works with the `slave` short name).
- `generate_export_header` output `export/slave/slave_export.h` ->
  `export/tethys/tethys_export.h`.
- `SLAVE_STATIC_DEFINE` -> `TETHYS_STATIC_DEFINE`.
- `slave_DEVELOPER_MODE` -> `tethys_DEVELOPER_MODE`.

`slave/cmake/install-rules.cmake`:

- All `slave` -> `tethys`; `slaveTargets` -> `tethysTargets`;
  `slave_Development` / `slave_Runtime` components -> `tethys_Development` /
  `tethys_Runtime`.

`slave/cmake/install-config.cmake`:

- `slaveTargets.cmake` -> `tethysTargets.cmake`.

`slave/cmake/variables.cmake`:

- `slave_DEVELOPER_MODE` -> `tethys_DEVELOPER_MODE`.
- `slave_INCLUDES_WITH_SYSTEM` -> `tethys_INCLUDES_WITH_SYSTEM`.

`slave/CMakePresets.json`:

- `slave_DEVELOPER_MODE` cache var -> `tethys_DEVELOPER_MODE`.
- Added new configure preset `dev` aliasing `ci-ubuntu` (inherits
  `["ci-build", "ci-linux", "clang-tidy", "cppcheck", "dev-mode"]`) so the
  static-analysis.yml + clang-tidy + gcc-fanalyzer workflows can call
  `cmake --preset=dev`. The CMakeUserPresets.json `dev` preset (gitignored)
  was Windows-only; this project-side `dev` is Linux-first (matches CI).

`slave/cmake/dev-mode.cmake`:

- Removed `add_subdirectory(test)` (the deleted CTest stub) - already done in
  PR-1a (#17). The variable substitution `slave` -> `tethys` here was
  also done in PR-1a (covered by the dev-mode CTest comment).

`slave/README.md`:

- Rewritten as the Tethys subtree introduction with layout table + license +
  cross-references.

## Symbol rename

- `exported_function()` -> `tethys_version()` (returns `"tethys"`, was
  `"slave"`).
- File header rewritten per `docs/coding-standard.md` §7.1 template:
  module, profiles, standards, trace, SPDX-License-Identifier.

## Pre-existing tests

`slave/tests/test/test_scaffold_smoke.c` (PR-1a) does NOT reference
`exported_function`; the smoke test is content-free Unity asserts. So Ceedling
test:all still passes (TESTED 2 / PASSED 2).

## Decisions

| Q | Resolution |
| - | - |
| Q1 git mv vs delete-then-create | git mv preserves blame; chose git mv for both files. |
| Q2 CMake target name | `tethys_slave` (matches `tethys-slave` Python-style package name from parent §1). |
| Q3 Public symbol name | `tethys_version()` (one-line shim; replaces the placeholder `exported_function()`). |
| Q4 `dev` preset target OS | Linux (matches CI). CMakeUserPresets.json `dev` is local-Windows; gitignored; no conflict. |
| Q5 Profile presets (marine.cmake / space.cmake) | Deferred to Phase 7 + 8. PR-1b stays scoped to layout. |
| Q6 SOVERSION + EXPORT_NAME | EXPORT_NAME stays as `slave` so `find_package(tethys)` consumers see `tethys::slave` (alias semantics). |

## Open follow-ups

- **F1** - When Phase 1 first source files land in `slave/src/core/dispatcher.c`,
  add `target_sources(tethys_slave PRIVATE ...)` lines (or globs) to the
  top-level CMakeLists.txt.
- **F2** - Phase 7 + 8 add `slave/profiles/marine.cmake` + `space.cmake` +
  `slave/cmake/toolchains/arm-cortex-m{4,7,33}.cmake`.
- **F3** - The `BUILDING.md` + `HACKING.md` files in slave/ still reference
  `slave_DEVELOPER_MODE` in their commands. Update at next docs PR (low
  priority - the slave_ prefix won't be parsed by CMake but the docs example
  commands will silently fail). PR-6 docs(runbook) was the closest natural
  place but those runbooks are operational, not contributor-facing. The
  contributor-facing CONTRIBUTING.md update lands at Phase 11.

## Implementation Reference

- PR: *to be filled at merge*
- Merged on: *to be filled at merge*
