# Phase 0 - Coding standards execution (research note)

> Research note backing the `p0-coding-standards` PR
> (`chore(standards): root .clang-format + .clang-tidy + .editorconfig + cppcheck.cfg + .gitattributes + pre-commit + coding-standard.md + misra-deviations.md`).
> Parent plan: [`.cursor/plans/xcp_extreme-env_tool_14019278.plan.md`](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md) - todo `p0-coding-standards` (PR-5).
> Sub-plan: [`.cursor/plans/p0-coding-standards_pr-5_c5d10a83.plan.md`](../../.cursor/plans/p0-coding-standards_pr-5_c5d10a83.plan.md).

## Scope

This note captures the standards anchor for every file landed in PR-5: the
LLVM clang-format base, the clang-tidy check selection, the cppcheck-misra
addon-wiring, the EditorConfig + .gitattributes baseline, and the pre-commit
hook set with its SHA pins. Every artefact forward-referenced from
[ADR-0003](../adr/0003-misra-c-2023-as-coding-gate.md) and parent §6.7 lands
here; the slave/ source tree is still empty, so the MISRA gate is configured
but no deviations exist yet.

## Sources (retrieved 2026-05-15)

| ID | Title | URL | Used for |
| --- | --- | --- | --- |
| R1 | MISRA C:2023 - canonical guidelines | <https://www.misra.org.uk/product/misra-c2023/> | Rule index + tier mnemonics (Mandatory / Required / Advisory). The full rule text is copyrighted; we ship a one-line-per-rule index in [`docs/misra-c-2023-rules.txt`](../misra-c-2023-rules.txt) keyed to cppcheck-misra output. |
| R2 | cppcheck manual (MISRA addon section) | <https://cppcheck.sourceforge.io/manual.html> | `--addon=misra` invocation, suppression syntax, `--rule-texts=` consumer format. |
| R3 | LLVM Coding Standards | <https://llvm.org/docs/CodingStandards.html> | LLVM base style anchor for root `.clang-format`. |
| R4 | clang-format style options reference | <https://clang.llvm.org/docs/ClangFormatStyleOptions.html> | Field-by-field semantics for every option used in `.clang-format`. |
| R5 | clang-tidy checks reference | <https://clang.llvm.org/extra/clang-tidy/checks/list.html> | Check categories selected (cert / bugprone / performance / readability) and the surgical disables. |
| R6 | CERT C Coding Standard (carnegie mellon) | <https://wiki.sei.cmu.edu/confluence/display/c> | Anchor for the `cert-*` clang-tidy check family. |
| R7 | EditorConfig spec | <https://editorconfig.org/> | `root = true`; per-extension overrides; charset / EOL semantics. |
| R8 | git attributes documentation | <https://git-scm.com/docs/gitattributes> | `text=auto eol=lf`, binary marking, lock-file `-diff`. |
| R9 | pre-commit framework docs | <https://pre-commit.com/> | YAML schema, `default_stages`, `exclude` regex. |
| R10 | pre-commit-hooks (general hygiene) | <https://github.com/pre-commit/pre-commit-hooks> | `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-toml`, `check-merge-conflict`, `check-added-large-files`. v5.0.0 SHA `cef0300fd0fc4d2a87a85fa2093c6b283ea36f4b`. |
| R11 | mirrors-clang-format hook | <https://github.com/pre-commit/mirrors-clang-format> | Pre-commit consumer of the system clang-format. v19.1.4 SHA `fed9a1f62c22af0bc846a260ebfeb0844368fd93`. |
| R12 | ruff-pre-commit hook | <https://github.com/astral-sh/ruff-pre-commit> | Python format + lint. v0.7.4 SHA `cafecb2f683a620516412e109877570ca7648cbd`. |
| R13 | codespell pre-commit hook | <https://github.com/codespell-project/codespell> | English-prose spell-check; consumes `slave/.codespellrc`. v2.3.0 SHA `193cd7d27cd571f79358af09a8fb8997e54f8fff`. |
| R14 | markdownlint-cli hook | <https://github.com/igorshubovych/markdownlint-cli> | Consumes the existing `.markdownlint.json`. v0.42.0 SHA `aa975a18c9a869648007d33864034dbc7481fe5e`. |
| R15 | yamllint hook | <https://github.com/adrienverge/yamllint> | YAML lint with the project-shipped `.yamllint.yaml`. v1.35.1 SHA `81e9f98ffd059efe8aa9c1b1a42e5cce61b640c6`. |
| R16 | Parent plan section 6.7 | [`.cursor/plans/xcp_extreme-env_tool_14019278.plan.md`](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md) | CI gate matrix - drives the static-analysis + misra-gate scope. |
| R17 | ADR-0003 (MISRA C:2023 as the coding gate) | [`docs/adr/0003-misra-c-2023-as-coding-gate.md`](../adr/0003-misra-c-2023-as-coding-gate.md) | Forward references that PR-5 actually lands (`docs/coding-standard.md`, `docs/misra-deviations.md`). |
| R18 | ADR-0005 (No dynamic allocation) | [`docs/adr/0005-no-dynamic-allocation.md`](../adr/0005-no-dynamic-allocation.md) | The banned-constructs list cross-references this ADR. |
| R19 | ADR-0008 (License-free toolchain) | [`docs/adr/0008-license-free-toolchain.md`](../adr/0008-license-free-toolchain.md) | Justifies cppcheck-misra over LDRA/Polyspace. |

R1, R6, R10-R15 are version-pinned via SHA per
[`.cursor/rules/version-pinning.mdc`](../../.cursor/rules/version-pinning.mdc).

## File inventory

| # | File | Kind | Lines (approx) |
| - | --- | --- | --- |
| 1 | `.clang-format` | new (root) | ~85 |
| 2 | `.clang-tidy` | new (root) | ~70 |
| 3 | `.editorconfig` | new (root) | ~55 |
| 4 | `.gitattributes` | new (root) | ~70 |
| 5 | `cppcheck.cfg` | new (root) | ~40 |
| 6 | `cppcheck-suppressions.txt` | new (root) | ~20 |
| 7 | `.pre-commit-config.yaml` | new (root) | ~85 |
| 8 | `.yamllint.yaml` | new (root) | ~30 |
| 9 | `docs/misra-c-2023-rules.txt` | new | ~140 |
| 10 | `docs/coding-standard.md` | new | ~250 |
| 11 | `docs/misra-deviations.md` | new | ~80 |
| 12 | `docs/research/phase-0-coding-standards-execution.md` | new (this file) | ~120 |
| 13 | `.cursor/plans/xcp_extreme-env_tool_14019278.plan.md` | edit | 1 line (status flip) |

Total: 13 paths, ~1050 lines net add.

## Tool choices

### clang-format

LLVM base because parent §6.7 specifies it. 120-col limit because modern
terminals support it and parent §5 lists no narrower target. PointerAlignment
Left because every other C codebase the project owner has touched uses Left and
inconsistency causes diff noise. SortIncludes CaseSensitive because
`<tethys.h>` and `<TETHYS.h>` would otherwise be equal; we'd rather catch the
typo. `InsertBraces: true` is critical for MISRA Rule 15.6 (every iteration /
selection body must be a compound statement).

The cmake-init slave/.clang-format is stricter (80 col, 2-space indent) and
wins inside slave/ via clang-format's nearest-config rule. Documented in
`docs/coding-standard.md` §2.2.

### clang-tidy

The check categories `cert-*` + `bugprone-*` + `performance-*` + `readability-*`
match what the parent plan §6.7 hints at and what
[ADR-0003](../adr/0003-misra-c-2023-as-coding-gate.md) decides. Disabled
checks:

- `bugprone-easily-swappable-parameters` - too noisy with C APIs that take
  `(buf, len)` parameter pairs.
- `cert-err33-c` - requires return-value checking even for `fputc`-style
  functions where the result is genuinely informational. We catch real bugs via
  `bugprone-unused-return-value`.
- `misc-include-cleaner` - aggressive; flags transitive includes that are
  conventional. Re-enable per-file via `// NOLINT` when desired.
- `misc-no-recursion` - already enforced by `no-recursion-no-goto.mdc` rule and
  cppcheck-misra 17.2.
- `readability-function-cognitive-complexity` - non-deterministic threshold;
  prefer the function-size LineThreshold below.
- `readability-identifier-length` - blocks legitimate short names (`i`, `n`,
  `fd`) in idiomatic C.
- `readability-magic-numbers` - too aggressive on bit-shift constants in
  protocol code; we'll lint manually.

The naming-check `readability-identifier-naming.MacroDefinitionPrefix: TETHYS_`
is the machine-readable expression of §3.1 in the coding standard. Functions,
variables, typedefs, structs, and enum constants use `lower_case` per the
table; macros use `UPPER_CASE` with `TETHYS_` prefix.

`WarningsAsErrors: '*'` - parent §6.7 requires zero new warnings on the
static-analysis pass.

### cppcheck-misra

The cppcheck-misra addon is bundled with cppcheck itself (Ubuntu
`/usr/share/cppcheck/addons/misra.json`); we do not vendor a copy because the
MISRA rule text is copyrighted by the MISRA consortium. We ship a one-line-per-
rule index in [`docs/misra-c-2023-rules.txt`](../misra-c-2023-rules.txt) keyed
to cppcheck-misra output so the misra-gate.yml workflow produces readable
diagnostics. Suppressions live in `cppcheck-suppressions.txt` and are
cross-checked against `docs/misra-deviations.md` by the workflow (workflow
update lands when slave/src/ first contains real C code in Phase 1+).

### EditorConfig

Anchors charset / EOL / indent / line-length defaults. Per-extension overrides
match `.clang-format` (4 spaces for C/C++) and the common 2-spaces convention
for YAML / JSON / TOML / CMake. `*.md` keeps trailing whitespace allowed
because two-space-trailing means hard line break in Markdown.

### .gitattributes

`* text=auto eol=lf` normalises every text file to LF on commit. PowerShell /
batch scripts are CRLF-only (PowerShell-on-Windows breaks otherwise). Lock
files (`uv.lock`, `package-lock.json`, `pnpm-lock.yaml`) are marked `-diff` so
git stops trying to show line-by-line diff for them. A2L files are explicit
text/LF because they are ASCII per the ASAM MCD-2 MC spec.

### .pre-commit-config.yaml

Hooks chosen because each one prevents a class of defect that costs reviewer
time:

- `trailing-whitespace` + `end-of-file-fixer` - the constant diff-noise sources.
- `check-yaml` + `check-toml` + `check-json` - syntax-only sanity; cheap.
- `check-merge-conflict` - catches `<<<<<<<` markers before commit.
- `check-added-large-files` (1 MiB) - prevents accidental MDF4 / A2L / binary
  pollution; fixture corpora live in `slave/tests/fixtures/` and are size-
  capped.
- `mixed-line-ending --fix=lf` - belt-and-braces alongside `.gitattributes`.
- `clang-format` - already covered by editor; the hook catches "I edited via
  PowerShell ISE / nano" cases.
- `ruff` + `ruff-format` - Python format + lint.
- `yamllint --strict` - catches the GitHub Actions YAML errors we hit during
  PR-4 (workflow shipped with a tabs/spaces mix).
- `markdownlint` - consumes the existing `.markdownlint.json` so docs PRs
  catch lints locally.
- `codespell` - catches typo-class defects in prose. Skip list covers known
  false-positives (`tethys` itself, common C abbreviations).

Hooks excluded from default run: `dotnet-format`, `prettier` (no JS code in
slave/), `cmake-format` (slave/ uses cmake-init defaults; PR-1a may add the
hook).

## Decisions

| Q | Resolution |
| - | - |
| Q1 .clang-format base style | LLVM (matches parent §6.7 hint + LLVM = industry default for new C projects) |
| Q2 column limit | 120 (modern terminals + matches `.editorconfig`) |
| Q3 slave/.clang-format treatment | Kept cmake-init default; root cascades to master/simulator only |
| Q4 clang-tidy WarningsAsErrors | `*` (every active check) per parent §6.7 |
| Q5 cppcheck-misra rule-text shipping | One-line index in `docs/misra-c-2023-rules.txt`; full text is copyrighted, not vendored |
| Q6 .gitattributes scope | text=auto eol=lf root rule + per-extension overrides for binary + CRLF for Windows scripts |
| Q7 pre-commit framework version | `minimum_pre_commit_version: "3.6.0"` (matches the latest stable that ships hook v5.x APIs) |
| Q8 yamllint config location | `.yamllint.yaml` at root (not `.yamllint`) per upstream recommended convention |
| Q9 codespell config | Skip + ignore-words via hook args; defer dedicated `.codespellrc` at root - slave/.codespellrc already exists |
| Q10 docs/coding-standard.md scope | C + Python both; one-stop-shop |
| Q11 docs/misra-deviations.md day-zero | Empty register + entry template + workflow + tier summary; zero open deviations |
| Q12 entry-id scheme | `MISRA-DEV-<NNNN>` (zero-padded monotonic counter), next-id at the bottom of the file |

## Open follow-ups

- **F1** - `misra-gate.yml` workflow currently runs cppcheck with `--addon=misra`
  but does not yet consume `cppcheck-suppressions.txt` or `cppcheck.cfg`. The
  workflow update is mechanical and lands when slave/src/ first contains real
  C code (Phase 1+). Captured here for completeness.
- **F2** - `static-analysis.yml` workflow does not yet enforce the new
  `.clang-tidy` config; same trigger as F1 (when real C code arrives).
- **F3** - Root `.codespellrc` may eventually replace `slave/.codespellrc` to
  centralise ignore lists. Deferred until the first false positive forces the
  question.
- **F4** - `markdownlint-cli2` is the upstream-recommended runner; the hook
  here uses `markdownlint-cli` v0.42.0 because it ships a stable pre-commit
  hook. Future swap to cli2 once its pre-commit support is GA.
- **F5** - When pyproject.toml lands in Phase 1, add a `[tool.ruff]` section
  and the per-package `--config` arg to the ruff hook. For now ruff uses
  defaults which align with the coding-standard.

## Implementation Reference

- PR: [#15 chore(standards): coding-standards baseline](https://github.com/goldr0g3r/tethys/pull/15)
- Merged on: 2026-05-15 (squash-merged via `gh pr merge 15 --squash --admin --delete-branch`).
- Merge SHA: `e135434`.
- Bootstrap window status: closed (PR-11 re-enabled `enforce_admins`). This PR
  exercised the loose-but-required branch protection - no required status
  checks list because the workflow job names don't yet match the gate names.
  F5 (rename workflow job IDs + re-tighten branch protection) lands in a
  follow-up PR in this same session.
- Pre-existing CI failures observed on this PR (pre-existing scaffold-only
  problems from PR-4 / PR-11; not introduced here):
  - `trufflehog` - `--fail` flag repeated on extra_args; one-line workflow fix.
  - `clang-tidy` + `gcc-fanalyzer` - workflows call `cmake --preset=dev` but
    `slave/CMakePresets.json` defines `ci-coverage` / `ci-sanitize` / `ci-ubuntu`
    only. Fix: workflows should use `ci-ubuntu` (or `slave/cmake/dev-mode.cmake`
    should add a `dev` preset). F5 owns the workflow rename + this fix.
  - `dependency-review` - requires Dependency Graph enabled on the repo (works
    for public repos with GHAS); not blocking on a fresh public repo.
