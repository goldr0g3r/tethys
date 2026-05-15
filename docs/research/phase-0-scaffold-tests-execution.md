# Phase 0 - Scaffold-tests execution (research note)

> Research note backing the `p0-scaffold-tests` PR
> (`chore(scaffold): Unity + Ceedling test harness under slave/tests/ + remove cmake-init CTest stub`).
> Parent plan: [`.cursor/plans/xcp_extreme-env_tool_14019278.plan.md`](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md) - PR-1a (companion to `p0-scaffold` PR #5).
> Companion: [`docs/research/phase-1-scaffold-execution.md`](phase-1-scaffold-execution.md) - the original cmake-init scaffold.

## Scope

Resolves PR-1 follow-up **F1** ("install Ruby + Ceedling; run `ceedling new
tests` inside `slave/`; document the CTest-vs-Ceedling split") and **F2**
("layout reconciliation - `slave/test/` -> `slave/tests/`") for the
tests/ subdirectory.

Layout reconciliation for `slave/include/slave/` -> `slave/include/tethys/`
and `slave/source/` -> `slave/src/core/` is owned by the parallel
`chore(layout)` PR.

## Sources (retrieved 2026-05-15)

| ID | Title | URL | Used for |
| --- | --- | --- | --- |
| R1 | Ceedling - "Test-Centered Build System for C" | <https://github.com/ThrowTheSwitch/Ceedling> | `ceedling new tests --docs --gitsupport` invocation. v1.0.1 SHA `fb1ce6c`. |
| R2 | Unity - test framework | <https://github.com/ThrowTheSwitch/Unity> | The `TEST_ASSERT_*` macros used in `test_scaffold_smoke.c`. v2.6.1. |
| R3 | CMock - mock generator | <https://github.com/ThrowTheSwitch/CMock> | Configuration in `project.yml :cmock` block. v2.6.0. |
| R4 | CException - C exception lib | <https://github.com/ThrowTheSwitch/CException> | Bundled with Ceedling; not directly used. v1.3.4. |
| R5 | RubyInstaller for Windows | <https://rubyinstaller.org/> | Ruby 3.3.11 via `winget install RubyInstallerTeam.Ruby.3.3`. |
| R6 | Parent plan section 14 | [`.cursor/plans/xcp_extreme-env_tool_14019278.plan.md`](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md) | Authoritative `slave/tests/` (plural) layout. |
| R7 | Parent plan section 6.7 | same | Unit-test row of the CI gate matrix. |
| R8 | PR-1 research note | [phase-1-scaffold-execution.md](phase-1-scaffold-execution.md) | Documented the CTest stub + the `tests/` follow-up. |
| R9 | Ceedling `project.yml` `:paths` documentation | <https://github.com/ThrowTheSwitch/Ceedling/blob/master/docs/CeedlingPacket.md#paths-configuration> | Configuring `:source` to point at `../src/**` instead of `tests/src/**`. |

## Tooling install

| Tool | Version | Install command |
| --- | --- | --- |
| Ruby (Windows) | 3.3.11 | `winget install RubyInstallerTeam.Ruby.3.3 --accept-package-agreements --accept-source-agreements --silent` |
| gem | 3.5.22 | bundled with Ruby |
| Ceedling | 1.0.1-fb1ce6c | `gem install ceedling --no-document` |
| Unity | 2.6.1 | bundled with Ceedling |
| CMock | 2.6.0 | bundled with Ceedling |
| CException | 1.3.4 | bundled with Ceedling |

Verify locally:

```powershell
$env:PATH = "C:\Ruby33-x64\bin;$env:PATH"
ruby --version    # ruby 3.3.11 (...)
ceedling version  # Ceedling => 1.0.1-fb1ce6c
```

## Generated tree

`ceedling new tests --docs --gitsupport` from inside `slave/` produces:

```text
slave/tests/
  project.yml            <- main Ceedling config (~400 lines, then edited for paths)
  .gitignore             <- /build/ ignored, /build/artifacts/ allowed
  src/                   <- empty default Ceedling source dir (not used; we point at ../src/)
  test/                  <- canonical Unity test home
    support/             <- mocks + shared fixtures (empty for now)
  docs/                  <- vendored Unity + CMock + CException + plugin docs
    unity/   cmock/   c_exception/   plugins/
```

Plus the hand-added:

- `slave/tests/test/test_scaffold_smoke.c` - 2-assertion Unity test proving
  the scaffold compiles and runs. Will be deleted at the first Phase-1+ PR
  that introduces real test coverage.
- `slave/tests/README.md` - quick-start, layout, naming convention,
  coverage targets.

## `project.yml` edits

Default vs Tethys patches:

```diff
- :source:
-   - src/**
- :include:
-   - src/**
+ :source:
+   - ../src/**
+ :include:
+   - ../include/**
+   - ../src/**
```

Rationale: parent §14 puts production code in `slave/src/{core,transport,
platform}` (NOT under `tests/src/`). Ceedling runs from inside `slave/tests/`
so relative `../src/**` reaches the parent dir.

Other config left at default: 8 test threads, `module_generator` plugin
enabled (for `ceedling module:create:foo`), `report_tests_pretty_stdout`
report format, Unity `UNITY_EXCLUDE_FLOAT` for slave bare-metal-friendliness.

## CTest stub removal

`slave/test/` (singular; cmake-init default) and its single file
`slave/test/source/slave_test.c` removed. The test was a 3-line `main()`
that linked against the cmake-init `exported_function()` stub, never to be
maintained.

`slave/cmake/dev-mode.cmake` correspondingly patched:

```diff
- include(CTest)
- if(BUILD_TESTING)
-   add_subdirectory(test)
- endif()
+ include(CTest)
+ # Tethys note: tests are owned by Ceedling under slave/tests/ (Phase-1+).
+ # CTest stays enabled in case future integration tests want it (e.g.
+ # Phase 9 HIL bench harness) but does not auto-add the legacy cmake-init
+ # CTest stub which has been removed in chore(scaffold-tests).
```

## Smoke test results

```text
TESTED:  2
PASSED:  2
FAILED:  0
IGNORED: 0
Ceedling operations completed in 15.2 seconds
```

Both assertions in `test_scaffold_smoke.c` pass. The scaffold is verified
working on Windows 11 + RubyInstaller 3.3.11 + Ceedling 1.0.1.

## Decisions

| Q | Resolution |
| - | - |
| Q1 Ruby install scope | Project-owner machine via `winget`. CI uses Ubuntu's `ruby-full` apt package + `gem install ceedling`. |
| Q2 Ceedling vs Catch2 vs Google Test | Ceedling (parent §5 + §6.7 enumerated it; Unity is bare-metal-friendly and matches DAL-B style). |
| Q3 Keep / delete cmake-init CTest stub | Delete. The two test frameworks would otherwise compete for `BUILD_TESTING`. PR-9 (HIL) reintroduces CTest if needed for integration tests. |
| Q4 Ceedling project.yml location | `slave/tests/project.yml` (parent §14 layout). |
| Q5 project.yml source paths | Edit defaults to point at `../src/**` and `../include/**` so production code lives where parent §14 says. |
| Q6 Smoke test scope | One file, two trivial assertions. Existence of any passing test proves the scaffold; real tests arrive in Phase 1+. |
| Q7 Coverage tool integration | gcov + gcovr via Ceedling's `:gcov` plugin (commented in `project.yml`; enable when slave/src/ has real code). |
| Q8 Pre-commit hook for Ceedling | Out of scope; CI handles. Local developers run `ceedling test:all` manually. |

## Open follow-ups

- **F1** - `slave/include/slave/` -> `slave/include/tethys/` and `slave/source/`
  -> `slave/src/core/` rename. Owned by the `chore(layout)` PR (parallel to
  this one in the same session).
- **F2** - When real slave code lands in Phase 1+, enable Ceedling's `:gcov`
  plugin (currently commented in `project.yml`) and wire the artefact to
  `coverage.yml`.
- **F3** - `ci.yml` job for slave/posix-sim currently uses cmake's `ctest`;
  add a parallel Ceedling job that runs `ceedling test:all` once real test
  files exist.
- **F4** - The vendored `slave/tests/docs/` tree is ~30 docs files / ~600 KB.
  Consider whether to keep (good for offline / no-internet developers) or to
  symlink to upstream after PR-11 docs-site lands. Keep for now; the
  `.gitattributes` + `text=auto eol=lf` rule from PR-5 normalises them.

## Implementation Reference

- PR: *to be filled at merge*
- Merged on: *to be filled at merge*
