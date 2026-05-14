# Phase 1 — Scaffold execution (research note)

> Research note backing the `p0-scaffold` PR (`chore(scaffold): monorepo bootstrap via CLI`).
> Parent plan: [`.cursor/plans/xcp_extreme-env_tool_14019278.plan.md`](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md) — todo `p0-scaffold` (PR-1).
> Sub-plan: [`.cursor/plans/p0-issues_plus_pr-1_scaffold_0e480c02.plan.md`](../../.cursor/plans/p0-issues_plus_pr-1_scaffold_0e480c02.plan.md) — Phase B.

## Scope

This note captures the actual CLI invocations and emitted artefacts during the first monorepo scaffold. Per the strict parent-plan rule — *"NO hand-rolled pyproject.toml / CMakeLists.txt edits beyond what the CLIs emit"* — every file under `master/`, `simulator/`, and `slave/` is verbatim what the CLI wrote.

## Tool versions

| Tool | Version | Source | Install command |
| --- | --- | --- | --- |
| uv | 0.9.26 | Already present (Astral) | n/a |
| Python | 3.10.6 | QTronic Silver 2023.03-1 mingw32 bundle | n/a |
| CMake | 4.3.2 | Kitware via winget | `winget install Kitware.CMake -e` |
| cmake-init | 0.41.1 | Astral uv tool registry | `uv tool install cmake-init` |
| Ruby + Ceedling | not installed | — | Deferred to PR-1a per sub-plan Q1 (b) |

## CLI invocations and emitted artefacts

### `uv init master --package --name tethys-master --no-readme --no-workspace`

Stdout: `Initialized project 'tethys-master' at 'C:\Code\tethys\master'`

Emitted:

```text
master/.python-version
master/pyproject.toml
master/src/tethys_master/__init__.py
```

### `uv init simulator --package --name tethys-sim --no-readme --no-workspace`

Stdout: `Initialized project 'tethys-sim' at 'C:\Code\tethys\simulator'`

Emitted:

```text
simulator/.python-version
simulator/pyproject.toml
simulator/src/tethys_sim/__init__.py
```

### `cmake-init --c -s --std 11 --no-clang-tidy --no-cppcheck slave`

Stdout: success message pointing at HACKING.md / BUILDING.md and CMake 3.20+ requirement.

Emitted (36 files):

```text
slave/.clang-format               (cmake-init default - kept as-is per rule)
slave/.clang-tidy                 (cmake-init default - kept as-is per rule)
slave/.clangd
slave/.codespellrc
slave/.gitignore                  (slave-scoped; root .gitignore in this PR)
slave/.github/workflows/ci.yml    (slave-scoped; GitHub Actions only reads root .github)
slave/BUILDING.md
slave/CMakeLists.txt              (parent-rule: no edits beyond what CLI emits)
slave/CMakePresets.json
slave/CMakeUserPresets.json
slave/CODE_OF_CONDUCT.md          (slave-scoped; root file lands in PR-3)
slave/CONTRIBUTING.md             (slave-scoped; root file lands in PR-3)
slave/HACKING.md
slave/README.md                   (slave-scoped; root README lands in PR-3)
slave/env.bat
slave/env.ps1
slave/cmake/coverage.cmake
slave/cmake/dev-mode.cmake
slave/cmake/docs-ci.cmake
slave/cmake/docs.cmake
slave/cmake/folders.cmake
slave/cmake/install-config.cmake
slave/cmake/install-rules.cmake
slave/cmake/lint-targets.cmake
slave/cmake/lint.cmake
slave/cmake/prelude.cmake
slave/cmake/project-is-top-level.cmake
slave/cmake/spell-targets.cmake
slave/cmake/spell.cmake
slave/cmake/variables.cmake
slave/docs/conf.py.in
slave/docs/Doxyfile.in
slave/docs/pages/about.dox
slave/include/slave/slave.h       (note: slave/slave/ namespace; parent §14 wants tethys/)
slave/source/slave.c              (note: source/ not src/; parent §14 wants src/{core,transport,platform})
slave/test/CMakeLists.txt         (note: test/ not tests/; parent §14 wants tests/)
slave/test/source/slave_test.c    (CTest-based stub; PR-1a replaces with Unity+Ceedling)
```

### Empty-directory stubs (`.gitkeep`)

Added 10 `.gitkeep` files for parent-§14 directories the CLIs did not create:

```text
master/tests/.gitkeep
master/docs/.gitkeep
slave/include/tethys/.gitkeep
slave/src/core/.gitkeep
slave/src/transport/.gitkeep
slave/src/platform/.gitkeep
slave/profiles/.gitkeep
slave/fuzz/.gitkeep
hil/.gitkeep
infrastructure/docker/.gitkeep
```

### Root `.gitignore`

Written: `.gitignore` at repo root with 30 lines (Python, C/C++ build, editor/OS, Ceedling placeholder, commit-message temp files). Per-component ignores (e.g. `slave/.gitignore`) remain.

## Divergences from parent §14 layout

cmake-init's opinions diverge from parent-plan §14 in three places:

| Parent §14 | cmake-init emitted | Reconciliation |
| --- | --- | --- |
| `slave/include/tethys/` | `slave/include/slave/slave.h` | `.gitkeep` placed in `slave/include/tethys/`. PR-1a (or PR-2) migrates `slave/slave.h` to `tethys/tethys.h` once we are allowed to touch CLI output. |
| `slave/src/{core,transport,platform}/` | `slave/source/slave.c` | `.gitkeep` placed in each `src/<sub>/`. PR-2 (or PR-7 when actual code arrives) migrates `slave/source/slave.c` to the proper module. |
| `slave/tests/` | `slave/test/` | `.gitkeep` not added (PR-1a `ceedling new` will write into `slave/tests/`). Two parallel test dirs is documented as a follow-up. |

The strict "no edits beyond what CLIs emit" rule blocks reconciliation in this PR. PR-2 (`chore(rules)`) is the natural place to add rename-only migration commits because it does not change semantics.

## Pre-emption of later PRs

cmake-init shipped files that overlap with later PR scope. Per the strict rule we keep them as cmake-init emitted; PR-5 will reconcile:

- `slave/.clang-format`, `slave/.clang-tidy` — PR-5 `p0-coding-standards` was going to write project-wide variants. Decision: keep cmake-init defaults under `slave/`; PR-5 writes the **root** `.clang-format` / `.clang-tidy` that cascade to the rest of the tree.
- `slave/.codespellrc` — PR-5 owns project-wide config; same pattern.
- `slave/.github/workflows/ci.yml` — slave-scoped, never executed by GitHub Actions (which reads only root `.github/workflows/`). Documented as a no-op artefact. PR-4 `p0-ci` writes the real workflows at the root.

## Open follow-ups

- **F1 — PR-1a `chore(scaffold-tests)`** — install Ruby + Ceedling, run `ceedling new tests` inside `slave/`, document the CTest-vs-Ceedling split. Open issue after merge.
- **F2 — Layout reconciliation** — slave/include/slave -> slave/include/tethys; slave/source -> slave/src/core; slave/test -> slave/tests. Either ship as PR-2 (`chore(rules)`) follow-on or open a dedicated `chore(layout)` PR.
- **F3 — slave/.github/workflows/ci.yml** — delete in PR-4 once root workflows exist, or leave as a slave-only consumer-of-CMake reference. Decide at PR-4.
- **F4 — master + simulator pinning** — uv emitted minimal `pyproject.toml` with no dependency pins. Per parent §8 Phase-1, pinning + structlog/pydantic-settings/click happens in Phase 1 (todo `p1`), not here.

## Implementation Reference

<!-- status-sync step appends the merged PR URL here once the PR is merged. -->

- PR: *to be filled at merge*
- Merged on: *to be filled at merge*
