# Phase 0 - Rules execution (research note)

> Research note backing the `p0-rules` PR (`chore(rules): cursor rule set + agent mirrors + parent-plan status-sync`).
> Parent plan: [`.cursor/plans/xcp_extreme-env_tool_14019278.plan.md`](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md) - todo `p0-rules` (PR-2).
> Sub-plan: [`.cursor/plans/p0-rules_cursor_rules_+_mirrors_7b33dfed.plan.md`](../../.cursor/plans/p0-rules_cursor_rules_+_mirrors_7b33dfed.plan.md).

## Scope

This note captures the file inventory, glob decisions, mirror procedure, and the back-filled status-sync for the two stale-pending todos. The PR is pure-rules-and-stubs per the sub-plan Q1 resolution; layout reconciliation (PR-1 follow-up F2) becomes its own subsequent PR.

## Sources (retrieved 2026-05-14)

| ID | Title | URL | Used for |
| --- | --- | --- | --- |
| R1 | Cursor `.mdc` rule format | [`create-rule` skill](../../../skills-cursor/create-rule/SKILL.md) | YAML frontmatter `{description, globs, alwaysApply}`; ≤50-line guidance; one concern per rule. |
| R2 | GitHub Copilot custom instructions | <https://docs.github.com/en/copilot/customizing-copilot/about-customizing-github-copilot-chat-responses> | `.github/copilot-instructions.md` for repo-wide; `.github/instructions/*.instructions.md` with `applyTo` frontmatter for file-pattern-scoped. |
| R3 | Conventional Commits 1.0 | <https://www.conventionalcommits.org/en/v1.0.0/> | `conventional-commits` rule body. |
| R4 | Parent plan section 6.5 | [`.cursor/plans/xcp_extreme-env_tool_14019278.plan.md`](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md) | Authoritative list of the 12 rule names + their intent. |
| R5 | PR-0c research note | [`phase-0-system-requirements.md`](phase-0-system-requirements.md) | Standards cited inside rule bodies (S1, S7, S8, S9, S10, S11, S14, S15, S18). |
| R6 | PR-0c standards matrix | [`phase-0-standards-matrix.csv`](phase-0-standards-matrix.csv) | Cross-referenced from `always-cite-standards`. |

## File inventory

12 rule files under `.cursor/rules/` + 12 mirror files under `.github/instructions/` + 3 root/`.github` stubs = **27 new files**.

### `.cursor/rules/` (source of truth)

| # | File | Glob / always | Source standard |
| - | --- | --- | --- |
| 1 | `xcp-protocol-discipline.mdc` | `slave/src/core/**, slave/include/**, master/src/tethys_master/protocol/**` | ASAM XCP 1.4 (R5 S1) |
| 2 | `misra-c-2023-gate.mdc` | `slave/**/*.c, slave/**/*.h` | MISRA C:2023 |
| 3 | `ecss-traceability.mdc` | `slave/**, master/**, simulator/**, docs/traceability.csv, docs/adr/**, docs/research/**` | ECSS-E-ST-40C Rev.1 (R5 S18), NPR 7150.2D (R5 S20), IACS UR E22 Rev.3 (R5 S11) |
| 4 | `marine-profile-invariants.mdc` | `slave/profiles/marine.cmake, slave/src/profiles/marine/**, slave/include/tethys/profile_marine.h` | Parent plan section 3.3 |
| 5 | `space-profile-invariants.mdc` | `slave/profiles/space.cmake, slave/src/profiles/space/**, slave/include/tethys/profile_space.h` | Parent plan section 3.3 |
| 6 | `no-dynamic-allocation.mdc` | `slave/**/*.c, slave/**/*.h` | ECSS-E-ST-40C Rev.1, MISRA C:2023 advisory, ADR-0005 draft |
| 7 | `no-recursion-no-goto.mdc` | `slave/**/*.c, slave/**/*.h` | MISRA C:2023 Rule 15.1, parent plan section 3.3 (space profile) |
| 8 | `always-cite-standards.mdc` | alwaysApply: true | Process discipline; ties to `docs/traceability.csv` |
| 9 | `research-note-per-phase.mdc` | alwaysApply: true | Parent plan section 6.4 |
| 10 | `version-pinning.mdc` | `**/pyproject.toml, **/uv.lock, **/CMakeLists.txt, **/*.cmake, .github/workflows/**/*.yml, .pre-commit-config.yaml, **/requirements*.txt` | Parent plan section 6.1; GitHub third-party action hardening |
| 11 | `free-tool-only.mdc` | alwaysApply: true | Parent plan section 5; ADR-0008 (when PR-3 elevates) |
| 12 | `conventional-commits.mdc` | alwaysApply: true | Conventional Commits 1.0 (R3); parent plan section 6.1 |

### `.github/instructions/` (mirror for GitHub Copilot)

Twelve `<name>.instructions.md` files. Each has:

- Frontmatter `description:` and `applyTo:` (GitHub Copilot's term for the same concept as Cursor's `globs:`).
- A 1-line header pointing back at the source `.cursor/rules/<name>.mdc`.
- Verbatim body content.

### Root + `.github/` stubs

- [`AGENTS.md`](../../AGENTS.md) - 30 lines pointing all agents at `.cursor/rules/`.
- [`CLAUDE.md`](../../CLAUDE.md) - identical content to `AGENTS.md` (intentional duplicate for the Anthropic convention).
- [`.github/copilot-instructions.md`](../../.github/copilot-instructions.md) - points at `.github/instructions/`.

## Mirror procedure

The `.github/instructions/` tree is **regenerated** from `.cursor/rules/`, never hand-edited. The regeneration step was a PowerShell snippet that:

1. Lists `.cursor/rules/*.mdc`.
2. For each, parses frontmatter `{description, globs, alwaysApply}`.
3. Translates `globs:` -> `applyTo:` (or `applyTo: "**"` if `alwaysApply: true`).
4. Prepends a "Mirror of" header pointing back at the source.
5. Writes `.github/instructions/<name>.instructions.md` with the same body.

This snippet is captured as a follow-up artefact for **PR-5** (`p0-coding-standards`) which adds the pre-commit hook + the dedicated `infrastructure/rules/sync.ps1` + `sync.sh` script. **PR-4** (`p0-ci`) adds a CI check that re-runs the regeneration and fails the build if the working tree changes (catches drift between source and mirror).

## Decisions

| Q | Resolution |
| - | - |
| Q1 mirror file extension | `*.instructions.md` (GitHub Copilot current convention per R2) |
| Q2 `applyTo` for alwaysApply | `applyTo: '**'` (matches every file) |
| Q3 generator script | Documented now; committed script lands in PR-5; CI drift-check lands in PR-4 |
| Q4 conventional-commits scope list | Explicit list in the rule body (overlaps with `area/*` labels by design) |
| Sub-plan Q1 PR scope | Pure rules only; layout reconciliation deferred to its own follow-up PR |

## Status-sync back-fill

Two parent-plan todos were still marked `pending` despite their deliverables having been on `main` since commit `9e6dc65` (PR-0a runbook + PR-0c research note + ADR drafts + standards matrix). This PR flips them:

- `p0-github-setup-runbook`: `pending` -> `completed`
- `p0-system-requirements-research`: `pending` -> `completed`

`p0-rules` itself flips on this PR's merge via the standard post-merge status-sync PR.

## Open follow-ups

- **F1** - `infrastructure/rules/sync.ps1` + `sync.sh` + pre-commit hook entry - lands in PR-5 `p0-coding-standards`.
- **F2** - CI workflow that re-runs the mirror regeneration and fails on drift - lands in PR-4 `p0-ci`.
- **F3** - When PR-3 lands the accepted ADRs, the `marine-profile-invariants` and `space-profile-invariants` rules should cross-reference ADR-0002 (profile-based build system) directly instead of pointing only at parent §3.3.
- **F4** - Recheck GitHub Copilot's `applyTo` spec at PR-4 time; the field may have evolved.

## Implementation Reference

- PR: [#7 chore(rules): cursor rule set + agent mirrors + parent-plan status-sync](https://github.com/goldr0g3r/tethys/pull/7)
- Merged on: 2026-05-14 11:22:54 UTC
- Bootstrap window: same as PR #4 / #5 (`enforce_admins` off; PR-4 re-enables when status checks land).
