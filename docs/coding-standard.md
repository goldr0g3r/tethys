# Tethys coding standard

> Authoritative source for naming, formatting, header guards, banned constructs,
> include order, and the MISRA deviation procedure across all Tethys C/C++ and
> Python source code.
>
> Cite: parent plan section 6.7 (CI gate matrix).
> Cite: [ADR-0003 - MISRA C:2023 as the coding gate](adr/0003-misra-c-2023-as-coding-gate.md).
> Cite: [ADR-0005 - No dynamic allocation](adr/0005-no-dynamic-allocation.md).
> Cite: [ADR-0008 - License-free toolchain](adr/0008-license-free-toolchain.md).
> Trace: [docs/traceability.csv](traceability.csv) - referenced from every traced module.

## Table of contents

1. [Scope and applicability](#1-scope-and-applicability)
2. [Style baseline](#2-style-baseline)
3. [Naming](#3-naming)
4. [Header guards and includes](#4-header-guards-and-includes)
5. [Banned constructs (C)](#5-banned-constructs-c)
6. [Banned constructs (Python)](#6-banned-constructs-python)
7. [File header template](#7-file-header-template)
8. [Test code conventions](#8-test-code-conventions)
9. [Commit and PR conventions](#9-commit-and-pr-conventions)
10. [MISRA C 2023 deviation procedure](#10-misra-c-2023-deviation-procedure)
11. [Tool configuration cross-reference](#11-tool-configuration-cross-reference)

---

## 1. Scope and applicability

| Code path | Standard tier | Tooling |
| --- | --- | --- |
| `slave/include/**`, `slave/src/**` | MISRA C:2023 mandatory + required (hard gate); advisory tracked | clang-format, clang-tidy, cppcheck-misra, gcc -fanalyzer |
| `slave/tests/**`, `slave/fuzz/**` | Same MISRA subset; deviations for test-only patterns allowed when documented | same + Unity / Ceedling / libFuzzer harnesses |
| `master/src/**`, `master/tests/**` | PEP-8 via `ruff format` + `ruff check`; type-checked via `mypy --strict` | ruff, mypy |
| `simulator/src/**`, `simulator/tests/**` | Same as master | ruff, mypy |
| `hil/**` (when added) | Same as master | ruff, mypy |
| `docs/**.md` | markdownlint rules in `.markdownlint.json` | markdownlint-cli2 |
| `docs/architecture/*.mmd` | Mermaid syntax | rendered via `docs-render.yml` |

The slave/ tree is the only place MISRA applies; Python tooling is the
counterpart anchor for master / simulator / hil.

## 2. Style baseline

### 2.1 C / C++ - root [`.clang-format`](../.clang-format)

- **Base style:** LLVM
- **Column limit:** 120
- **Indent:** 4 spaces (no tabs); `IndentCaseLabels: true`
- **Pointer alignment:** Left (`int* p`, not `int *p`)
- **Braces:** Custom (`AfterFunction: true`); always insert braces on control statements (`InsertBraces: true`); no short-block-on-one-line
- **Includes:** `IncludeBlocks: Regroup`, sorted CaseSensitive, with priority order documented in the file
- **Trailing comments:** aligned (`AlignTrailingComments: Always`)
- **Definition blocks:** separate (`SeparateDefinitionBlocks: Always`)

### 2.2 C / C++ - slave/ override [`slave/.clang-format`](../slave/.clang-format)

slave/ ships its own cmake-init-generated clang-format which is **stricter**
(`ColumnLimit: 80`, `IndentWidth: 2`, more aggressive include splitting). It
takes precedence inside `slave/` via clang-format's nearest-config rule. Both
configs ban tabs and require LF line endings.

### 2.3 Python - master, simulator, hil

- `ruff format` (Black-compatible defaults; 120 col)
- `ruff check` with the `E`, `F`, `I`, `B`, `UP`, `S`, `PL`, `RUF` rule families
- `mypy --strict`
- No `# noqa` without a rule code AND a one-line justification

### 2.4 EditorConfig

[`.editorconfig`](../.editorconfig) sets baseline indent + line-ending +
trailing-whitespace defaults so every editor (VS Code, vim, Visual Studio, IDEA
family) opens files at the right indentation regardless of clang-format /
ruff availability.

### 2.5 Line endings

- LF (Unix) everywhere except PowerShell / batch (CRLF). Enforced by
  [`.gitattributes`](../.gitattributes); files are re-normalised on first
  checkout.
- Final newline is mandatory; pre-commit hook `end-of-file-fixer` adds it
  automatically.

## 3. Naming

### 3.1 C identifiers (slave/)

| Kind | Convention | Example |
| --- | --- | --- |
| Public function | `tethys_<module>_<verb>` | `tethys_xcp_connect`, `tethys_daq_start` |
| Public type | `tethys_<module>_<name>_t` | `tethys_xcp_packet_t`, `tethys_daq_list_t` |
| Public macro / constant | `TETHYS_<MODULE>_<NAME>` | `TETHYS_XCP_MAX_CTO`, `TETHYS_DAQ_MAX_LISTS` |
| Public enum constant | `TETHYS_<MODULE>_<TAG>` | `TETHYS_XCP_STATE_DISCONNECTED` |
| Static (file-scope) function | `<verb>_<noun>` (no `tethys_` prefix; not exported) | `static void unlock_resource(void)` |
| Static (file-scope) variable | `<name>` (no prefix) | `static uint32_t request_counter` |
| Local variable | `lower_snake_case` | `frame_length`, `bytes_left` |
| Header guard | `TETHYS_<PATH>_<NAME>_H` | `TETHYS_INCLUDE_TETHYS_PROFILE_MARINE_H` |

### 3.2 Python identifiers (master, simulator)

| Kind | Convention | Example |
| --- | --- | --- |
| Module | `lower_snake_case` | `tethys_master.protocol.dispatcher` |
| Class | `UpperCamelCase` | `XcpDispatcher`, `A2lParser` |
| Function / method | `lower_snake_case` | `parse_command()`, `connect_slave()` |
| Constant | `UPPER_SNAKE_CASE` | `MAX_CTO`, `DEFAULT_TIMEOUT_MS` |
| Private | leading underscore | `_internal_state` |
| Type alias / TypeVar | `UpperCamelCase` | `BytesLike = bytes` |

### 3.3 Test / fuzz / fixture naming

- C: `test_<module>__<scenario>.c` (note double underscore between module and
  scenario) - matches Ceedling defaults.
- Python: `test_<module>__<scenario>.py` for pytest discovery.
- Fuzz harness: `fuzz_<module>.c`, single `LLVMFuzzerTestOneInput`.
- A2L / MDF / binary fixtures live in `**/tests/fixtures/` and are git-LFS-free
  (size-capped per `.pre-commit-config.yaml` `check-added-large-files` hook).

## 4. Header guards and includes

### 4.1 Header guard format

Every C header file has an `#ifndef` guard **and** a `#pragma once` belt-and-
braces marker:

```c
/*
 * tethys/profile_marine.h - marine profile feature flags.
 * Trace: docs/traceability.csv row TETHYS-DES-0007.
 */
#ifndef TETHYS_PROFILE_MARINE_H
#define TETHYS_PROFILE_MARINE_H

#pragma once

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ... declarations ... */

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* TETHYS_PROFILE_MARINE_H */
```

Guard name = `TETHYS_` + path-derived stem + `_H`. The repeated `pragma once`
prevents accidental double-inclusion when the guard macro is accidentally
redefined.

### 4.2 Include order

Per the root [`.clang-format`](../.clang-format) `IncludeCategories`:

1. Own header (the .c file's matching .h). Use `#include "tethys/xxx.h"`.
2. Project headers (`#include "tethys/..."`).
3. Standard library headers (`#include <stdbool.h>`, `<stdint.h>`, ...).
4. Third-party headers (`#include <unity.h>`, `<libfuzzer/...>`).
5. Internal helpers (`#include "src/core/internal.h"`).

clang-format regroups automatically; manual reordering is forbidden.

### 4.3 What lives in headers

- Declarations only - no definitions except `static inline` helpers.
- No `static` non-inline functions in headers (linker collisions).
- No global mutable state (`extern` constants OK with rationale).
- Always document the contract: `@brief`, `@param`, `@return`, `@pre`, `@post`,
  `@safety` (which profiles + standards apply).

## 5. Banned constructs (C)

### 5.1 Hard ban (cppcheck-misra + grep gate in CI)

| Construct | Reason | Tool catching it |
| --- | --- | --- |
| `malloc`, `calloc`, `realloc`, `free` | ADR-0005 / `no-dynamic-allocation.mdc` | grep + cppcheck-misra 21.3 |
| `alloca` | Stack-overflow risk; opaque to static analysis | clang-tidy `cert-arr39-c`, grep |
| Variable-length arrays | MISRA 18.8 + ADR-0005 | cppcheck-misra 18.8 |
| `goto` (slave/) | MISRA 15.1 + `no-recursion-no-goto.mdc` | cppcheck-misra 15.1 |
| Recursion (slave/) | MISRA 17.2 + `no-recursion-no-goto.mdc` | cppcheck-misra 17.2 |
| `setjmp` / `longjmp` | MISRA 21.4 | cppcheck-misra 21.4 |
| `signal.h` | MISRA 21.5 | cppcheck-misra 21.5 |
| `system()`, `getenv()`, `exit()`, `abort()` | MISRA 21.8 | cppcheck-misra 21.8 |
| `<tgmath.h>` | MISRA 21.11 | cppcheck-misra 21.11 |
| `gets()`, `scanf()`-family (unbounded) | CERT FIO34-C / FIO20-C | clang-tidy cert-fio |

### 5.2 Soft ban (allowed with deviation entry)

| Construct | Allowed scope | Required |
| --- | --- | --- |
| `printf` / `snprintf` (test code only) | `slave/tests/**`, `slave/fuzz/**` | Wrap in `#ifdef TETHYS_TEST_BUILD` |
| `assert(3)` (test code only) | `slave/tests/**` | Same |
| `union` (other than tagged unions for ASAM payloads) | none default | MISRA 19.2 advisory; deviation entry |
| Function-like macros over 3 lines | reluctantly | Prefer `static inline`; deviation if unavoidable |
| `_Atomic` / `<stdatomic.h>` | slave/src/core only, only when interrupts cross boundaries | Cite the use site in the deviation register |

### 5.3 Profile-specific extras (slave/)

- **Space profile** (`tethys/profile_space.h` active): also bans `volatile`
  unless paired with `_Atomic`, bans floating-point in DAQ tick (use scaled
  integer), requires ECC-checked memory access wrappers (`tethys_ecc_read()`,
  `tethys_ecc_write()`).
- **Marine profile** (`tethys/profile_marine.h` active): floating point allowed
  but capped at IEEE-754 single (`float`); `double` forbidden.

## 6. Banned constructs (Python)

| Construct | Reason | Tool catching it |
| --- | --- | --- |
| Bare `except:` | hides errors | ruff `E722` |
| `eval`, `exec` | Code-injection risk | ruff `S307`, `S102` |
| `pickle.loads` on untrusted input | RCE risk | ruff `S301` |
| `assert` on production paths | Removed by `-O` | ruff `S101` (allow under `tests/`) |
| `subprocess` with `shell=True` | Command injection | ruff `S602`, `S603` |
| Mutable default arguments | Easy bug | ruff `B006` |
| Print debugging in library code | Use `structlog` | ruff `T201` (allow in CLI entry-points only) |

## 7. File header template

### 7.1 C (slave/)

```c
/*
 * <filename> - <one-line description>.
 *
 * Module: tethys::<subsystem>
 * Profiles: marine, space (or marine-only / space-only)
 * Standards: <Cite: ASAM XCP 1.4 sec X.Y; ECSS-E-ST-40C Rev.1 sec ...>
 * Trace: docs/traceability.csv row <TETHYS-...>
 *
 * Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
 */
```

### 7.2 Python (master, simulator)

```python
"""<one-line summary>.

<paragraph body if needed>

Cite: <standard sec if applicable>
Trace: docs/traceability.csv row <TETHYS-...>
"""
from __future__ import annotations
```

## 8. Test code conventions

- Unit tests live next to their module in `slave/tests/test_<module>.c`
  (Ceedling default) or `master/tests/test_<module>.py` (pytest).
- One assertion concept per test name. No multi-scenario "test_everything".
- Fixtures are module-scope when expensive, function-scope otherwise.
- Hardware-in-the-loop tests live in `hil/` and are marked with the
  `@pytest.mark.hil` decorator (Python) or `#ifdef TETHYS_HIL_BUILD` (C).
- Coverage targets:
  - `slave/src/core/` (protocol core): >=95% statement, >=90% MC/DC (parent §6.7)
  - all other slave/ + simulator + master: >=85% statement
  - master GUI (`master/src/tethys_master/gui/`): smoke-tested headless via
    pytest-qt, coverage waiver documented in PR-6

## 9. Commit and PR conventions

See [`.cursor/rules/conventional-commits.mdc`](../.cursor/rules/conventional-commits.mdc).
Subject line format, allowed types, allowed scopes, body format
(`Cite:` / `Trace:` lines) are all enforced by `pr-title.yml` and
`always-cite-standards.mdc`.

## 10. MISRA C 2023 deviation procedure

### 10.1 When to file a deviation

- A required-tier rule is unavoidable for a specific code segment (e.g. ASAM
  payload `union` triggering MISRA 19.2 advisory).
- An advisory-tier rule was triaged and **chosen to ignore** project-wide.
- A new third-party dependency arrives that fails MISRA out-of-the-box and
  cannot be patched.

### 10.2 Mandatory rules

**Never.** A mandatory-rule violation blocks merge unconditionally. The fix is
always code change, not deviation.

### 10.3 Deviation entry format

Append to [`docs/misra-deviations.md`](misra-deviations.md):

```markdown
### MISRA C:2023 Rule N.M - <Mandatory | Required | Advisory>

- **Tier:** Required (or Advisory)
- **Files:** `slave/src/core/foo.c` lines 42-58
- **Rule text:** <one-line excerpt; full text in the MISRA C:2023 document>
- **Justification:** <why the violation is unavoidable>
- **Mitigation:** <what compensating control exists; e.g. extra runtime
  assertion, fuzz coverage, manual review by N>
- **Owner:** @goldr0g3r
- **PR introduced:** #NN
- **Approval status:** approved | pending | rejected
- **Review date:** 2026-MM-DD
- **Re-review by:** 2026-MM-DD (default +180 days)
```

### 10.4 Workflow

1. Author opens the PR with the violating code AND the deviation entry in the
   same commit.
2. `misra-gate.yml` runs cppcheck-misra; it will fail because of the rule
   violation.
3. Author updates `cppcheck-suppressions.txt` with the per-line suppression
   `misra-c2023-N.M:<file>:<line>` referencing the deviation entry.
4. `misra-gate.yml` re-runs; the workflow checks that every suppression has a
   matching entry in `docs/misra-deviations.md` and fails otherwise.
5. Review: at least one human reviewer signs off.
6. Merge; the deviation row is now part of history.

### 10.5 Periodic re-review

Every 180 days (configurable per entry), the owner re-reviews the deviation.
Outcomes:

- **Still valid:** bump the `Re-review by:` date.
- **No longer needed:** delete the entry + the suppression in the same PR.
- **Worse:** elevate to ADR, open a refactor issue.

## 11. Tool configuration cross-reference

| Concern | Configuration file | Owner |
| --- | --- | --- |
| C/C++ formatting | [`.clang-format`](../.clang-format) + [`slave/.clang-format`](../slave/.clang-format) | this PR + cmake-init slave default |
| C/C++ lint | [`.clang-tidy`](../.clang-tidy) + [`slave/.clang-tidy`](../slave/.clang-tidy) | this PR + cmake-init slave default |
| MISRA static analysis | [`cppcheck.cfg`](../cppcheck.cfg) + [`docs/misra-c-2023-rules.txt`](misra-c-2023-rules.txt) + [`cppcheck-suppressions.txt`](../cppcheck-suppressions.txt) | this PR |
| MISRA deviation register | [`docs/misra-deviations.md`](misra-deviations.md) | this PR |
| Editor baseline | [`.editorconfig`](../.editorconfig) | this PR |
| Line endings + binary marking | [`.gitattributes`](../.gitattributes) | this PR |
| Pre-commit hooks | [`.pre-commit-config.yaml`](../.pre-commit-config.yaml) | this PR |
| Python formatting + lint | per-package `pyproject.toml` `[tool.ruff]` section | Phase 1 |
| Python type-check | per-package `pyproject.toml` `[tool.mypy]` section | Phase 1 |
| Spellcheck | [`slave/.codespellrc`](../slave/.codespellrc) (cmake-init default) | scaffold PR-1 |
| CI gates | [`.github/workflows/`](../.github/workflows/) (13 workflows) | PR-4 |

## 12. References

- Parent plan section 4 (safety + standards mapping).
- Parent plan section 6.7 (CI/CD gate matrix).
- [ADR-0003 MISRA C:2023 as the coding gate](adr/0003-misra-c-2023-as-coding-gate.md).
- [ADR-0005 No dynamic allocation](adr/0005-no-dynamic-allocation.md).
- [ADR-0008 License-free toolchain](adr/0008-license-free-toolchain.md).
- [Cursor rule `misra-c-2023-gate.mdc`](../.cursor/rules/misra-c-2023-gate.mdc).
- [Cursor rule `no-dynamic-allocation.mdc`](../.cursor/rules/no-dynamic-allocation.mdc).
- [Cursor rule `no-recursion-no-goto.mdc`](../.cursor/rules/no-recursion-no-goto.mdc).
- [Cursor rule `xcp-protocol-discipline.mdc`](../.cursor/rules/xcp-protocol-discipline.mdc).
- MISRA C:2023 guidelines, available from the MISRA consortium
  (<https://www.misra.org.uk/>).
- cppcheck manual (<https://cppcheck.sourceforge.io/manual.html>).
- LLVM coding standards (<https://llvm.org/docs/CodingStandards.html>) - LLVM
  base style is the clang-format anchor.
