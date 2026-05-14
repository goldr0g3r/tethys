# Phase 0 - Docs execution (research note)

> Research note backing the `p0-docs` PR (`docs(architecture): rewrite README + system-context + dep-graph + 10 ADRs`).
> Parent plan: [`.cursor/plans/xcp_extreme-env_tool_14019278.plan.md`](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md) - todo `p0-docs` (PR-3).
> Sub-plan: [`.cursor/plans/p0-docs_architecture_+_adrs_58de05db.plan.md`](../../.cursor/plans/p0-docs_architecture_+_adrs_58de05db.plan.md).

## Scope

This note captures the deliverable inventory, the ADR elevation procedure, the dep-graph generation procedure, and the forward references for the next three Phase-0 PRs.

## Sources (retrieved 2026-05-14)

| ID | Title | URL | Used for |
| --- | --- | --- | --- |
| R1 | MADR v3.0 | <https://adr.github.io/madr/> | Frontmatter + section structure for all 10 ADRs |
| R2 | Michael Nygard - "Documenting architecture decisions" (2011) | <https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions> | Original ADR pattern |
| R3 | Parent plan section 6.3 | [`.cursor/plans/xcp_extreme-env_tool_14019278.plan.md`](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md) | Originally enumerated 8 ADRs and their titles |
| R4 | Parent plan section 11 | same | README deliverable list (badges + indexes) |
| R5 | Parent plan section 12 | same | Standards-compliance scorecard table (embedded verbatim into README) |
| R6 | Parent plan section 2 | same | System-architecture mermaid diagram |
| R7 | NIST FIPS-197 (AES) | <https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.197-upd1.pdf> | ADR-0006 cipher choice |
| R8 | ASAM XCP 1.4 Part 2 §1.3 seed-and-key | (paywalled; cited via [`phase-0-system-requirements.md`](phase-0-system-requirements.md) S1) | ADR-0006 protocol-level scheme |
| R9 | `@mermaid-js/mermaid-cli` | <https://github.com/mermaid-js/mermaid-cli> | dep-graph.svg generation |
| R10 | GitHub Rulesets | <https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets> | ADR-0009 migration target |
| R11 | MIT License text | <https://opensource.org/license/mit/> | ADR-0008 repo licence |

Standards consumed by individual ADRs are cited via the matrix at [`phase-0-standards-matrix.csv`](phase-0-standards-matrix.csv) (S1-S35).

## Deliverable inventory

| # | File | Kind | Lines (approx) |
| - | --- | --- | --- |
| 1 | `README.md` | rewrite | ~150 |
| 2 | `docs/architecture/system-context.md` | new | ~230 |
| 3 | `docs/architecture/dep-graph.mmd` | new | ~70 |
| 4 | `docs/architecture/dep-graph.svg` | DEFERRED to PR-4 (see Decisions table) | — |
| 5 | `docs/adr/0001-xcp-as-development-protocol.md` | elevated | ~80 |
| 6 | `docs/adr/0002-profile-based-build-system.md` | new | ~65 |
| 7 | `docs/adr/0003-misra-c-2023-as-coding-gate.md` | new | ~85 |
| 8 | `docs/adr/0004-transport-abstraction-layer.md` | elevated | ~120 |
| 9 | `docs/adr/0005-no-dynamic-allocation.md` | elevated | ~110 |
| 10 | `docs/adr/0006-aes-128-seed-and-key.md` | new | ~80 |
| 11 | `docs/adr/0007-python-master-not-matlab.md` | new | ~85 |
| 12 | `docs/adr/0008-license-free-toolchain.md` | new | ~100 |
| 13 | `docs/adr/0009-rulesets-migration.md` | new (proposed stub) | ~70 |
| 14 | `docs/adr/0010-packet-loss-tolerance-budget.md` | elevated | ~80 |
| 15 | `docs/adr/README.md` | new | ~50 |
| 16 | `docs/research/phase-0-docs-execution.md` | new (this file) | ~120 |
| 17 | `.cursor/plans/xcp_extreme-env_tool_14019278.plan.md` | edit | 1 line |

Plus: deletion of `docs/adr/drafts/` (4 files removed via `git mv`).

## ADR elevation procedure

The 4 drafts at `docs/adr/drafts/adr-{0001,0004,0005,0010}-*.md` were elevated by:

1. `git mv docs/adr/drafts/adr-NNNN-*.md docs/adr/NNNN-*.md` - preserves git history of the draft.
2. Rewrite the frontmatter to MADR v3.0:
   - Status: `proposed` → `accepted`
   - Add `Consulted`, `Informed`, `Accepted by` fields
   - Remove `Source PR` and `Promoted by` fields (replaced by `Accepted by`)
   - Add or update `Supersedes` and `Superseded by` fields
3. Add `Decision Drivers` and `Considered Options` sections (MADR v3.0 mandatory; the drafts had a less-structured `Alternatives considered` heading).
4. Restructure `Consequences` into `Positive` / `Negative` / `Risks` bullets.
5. Update internal cross-links: `[ADR-0010 draft](adr-0010-...)` → `[ADR-0010](0010-...)` (paths simplified because no more `drafts/` prefix; same dir).
6. Update outbound paths: `../../research/...` → `../research/...` and `../../../.cursor/rules/...` → `../../.cursor/rules/...` (relative-path shift from `docs/adr/drafts/` to `docs/adr/`).
7. Remove the "(draft)" suffix from the title and the "> This is a draft..." blockquote disclaimer.

## Dep-graph generation procedure

Source-of-truth: `docs/architecture/dep-graph.mmd` (Mermaid `flowchart LR`).

SVG generation **deferred to PR-4** because the local Windows toolchain blocks the `npx -y @mermaid-js/mermaid-cli` puppeteer install (an `EPERM rmdir` cleanup error on `node_modules\puppeteer-core` repeats across attempts; likely an antivirus / Windows file-lock interaction with `npm-cache\_npx`). The intended command:

```bash
npx -y @mermaid-js/mermaid-cli mmdc \
  -i docs/architecture/dep-graph.mmd \
  -o docs/architecture/dep-graph.svg
```

GitHub renders Mermaid inline, so the SVG is a convenience for non-GitHub viewers (and the future Sphinx docs site at PR-11). PR-4's `ci.yml` (or a dedicated `docs.yml`) workflow runs `mmdc` in a clean Ubuntu runner and commits the resulting SVG. This deferral is tracked as follow-up F1 below.

## Decisions

| Q | Resolution |
| - | - |
| Q1 sub-plan PR scope | single PR with all 13 docs together (per parent §7) |
| Q2 dep-graph format | Mermaid source + generated SVG via mermaid-cli |
| Q3 ADR-0009 status | proposed; migration deferred until PR-4 status checks stabilise |
| Q4 README badges | concrete URLs assuming PR-4 workflows; render broken until then by design |
| Q5 git mv vs copy-then-delete | git mv (preserves history) |
| Q6 docs/coding-standard.md | forward-noted in ADR-0003; lands in PR-5 |
| Q7 mermaid-cli install | npx one-shot (no global install) |
| Q8 ADR-0010 numbering | kept as 0010 per the PR-0c decision; ADR-0009 reserved for Rulesets migration |

## Open follow-ups

- **F1** - `docs/architecture/dep-graph.svg` generation. Blocked locally by Windows npx puppeteer install. PR-4 ships `docs.yml` (or extends `ci.yml`) to run `mmdc` in an Ubuntu container and commit the SVG. Add a CI drift-check that re-runs `mmdc` on every PR touching `dep-graph.mmd` and fails if the committed SVG is stale.

## Forward references

- **PR-4 `p0-ci`** - implements `.github/workflows/{ci,misra-gate,coverage,fuzz-nightly,a2l-roundtrip,pr-title,secret-scan,dependency-review,sbom,release}.yml`. Real CI badges in README start rendering. Re-enables `enforce_admins=true` on `main` branch protection (ending the bootstrap-window override pattern used by PR-4 / PR-5 / PR-7 / this PR). **Also generates `docs/architecture/dep-graph.svg` from the .mmd source per F1 above.**
- **PR-5 `p0-coding-standards`** - lands `docs/coding-standard.md` (referenced by ADR-0003) and `docs/misra-deviations.md` (the deviation register).
- **PR-6 `p0-runbooks`** - 7 additional runbooks per parent §16.
- **PR-11 `p11-release`** - Sphinx + GitHub Pages docs site renders the architecture + ADRs.
- **Future ADR-0011** - will supersede ADR-0009 with the Rulesets migration once PR-4 stabilises.

## Implementation Reference

- PR: [#9 docs(architecture): rewrite README + system-context + dep-graph + 10 ADRs](https://github.com/goldr0g3r/tethys/pull/9)
- Merged on: 2026-05-14 11:43:36 UTC
- Bootstrap window: same as PR #4 / #5 / #7 (`enforce_admins` off; PR-4 re-enables when status checks land).
