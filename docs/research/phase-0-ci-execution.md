# Phase 0 - CI execution (research note)

> Research note backing the `p0-ci` PR (`ci: 11 workflows + templates + rule-mirror + dep-graph render + enforce_admins re-enable`).
> Parent plan: [`.cursor/plans/xcp_extreme-env_tool_14019278.plan.md`](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md) - todo `p0-ci` (PR-4).

## Scope

This note captures the workflow inventory, action SHA pin procedure, scaffold-vs-engaged status per workflow, the resolution of three prior PR follow-ups (PR-3 F1, PR-7 F1+F2), and the bootstrap-window closure.

## Sources (retrieved 2026-05-14)

| ID | Title | URL | Used for |
| --- | --- | --- | --- |
| R1 | Parent plan section 6.7 | [`.cursor/plans/xcp_extreme-env_tool_14019278.plan.md`](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md) | The 11-workflow enumeration + gate semantics |
| R2 | GitHub Actions third-party hardening | <https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions#using-third-party-actions> | SHA-pinning requirement |
| R3 | Conventional Commits 1.0 | <https://www.conventionalcommits.org/en/v1.0.0/> | `pr-title.yml` type + scope list |
| R4 | `amannn/action-semantic-pull-request` | <https://github.com/amannn/action-semantic-pull-request> | PR-title validator |
| R5 | TruffleHog GitHub Action | <https://github.com/trufflesecurity/trufflehog> | Secret scanning |
| R6 | GitHub Dependency Review | <https://docs.github.com/en/code-security/supply-chain-security/understanding-your-software-supply-chain/dependency-review> | License / vulnerability gating |
| R7 | CycloneDX gh-python-generate-sbom | <https://github.com/CycloneDX/gh-python-generate-sbom> | Python SBOM generation |
| R8 | cppcheck MISRA addon | <https://cppcheck.sourceforge.io/manual.html> | C static analysis |
| R9 | `@mermaid-js/mermaid-cli` | <https://github.com/mermaid-js/mermaid-cli> | `dep-graph.svg` render (PR-3 F1) |
| R10 | Dependabot config v2 | <https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/configuration-options-for-the-dependabot.yml-file> | `.github/dependabot.yml` |
| R11 | Renovate config | <https://docs.renovatebot.com/configuration-options/> | `.github/renovate.json` |

## Workflow inventory (13 total)

| # | File | Trigger | Status | Resolves |
| - | --- | --- | --- | --- |
| 1 | `ci.yml` | push + PR | scaffolded (matrix runs trivially; engages at Phase-1+) | parent Â§6.7 |
| 2 | `misra-gate.yml` | PR on `slave/**` | scaffolded (empty C tree; engages at Phase-2) | parent Â§6.7 + ADR-0003 |
| 3 | `static-analysis.yml` | push + PR | scaffolded; zero new warnings rule engages with code | parent Â§6.7 |
| 4 | `coverage.yml` | push + PR + nightly | scaffolded; `--print-summary` only today; thresholds engage at PR-2+ | parent Â§6.7 + ADR-0010 |
| 5 | `fuzz-nightly.yml` | nightly cron + manual | scaffolded; harness lands in Phase-2 | parent Â§6.7 + ADR-0010 |
| 6 | `a2l-roundtrip.yml` | PR on A2L paths | scaffolded; fixtures land in Phase-1 | parent Â§6.7 |
| 7 | `pr-title.yml` | PR | **engaged today** | rule `conventional-commits` |
| 8 | `secret-scan.yml` | push + PR | **engaged today** | parent Â§6.7 |
| 9 | `dependency-review.yml` | PR | **engaged today** | parent Â§6.7 + rule `free-tool-only` |
| 10 | `sbom.yml` | tag `v*` | scaffolded; first release at v0.1.0 | parent Â§6.7 + ADR-0008 |
| 11 | `release.yml` | tag `v*` | scaffolded; full content at PR-11 | parent Â§6.7 + section 11 |
| 12 | `docs-render.yml` | PR/push touching `dep-graph.mmd` | **engaged today** | **PR-3 F1** |
| 13 | `rules-mirror-drift.yml` | PR touching rule paths | **engaged today** | **PR-7 F2** |

Status legend:

- **engaged today**: workflow runs against current main and gates real behaviour.
- **scaffolded**: workflow is wired correctly and runs; substantive checks engage when relevant source/tests/fixtures arrive in later phases.

## Action SHA pin procedure

Per [`version-pinning.mdc`](../../.cursor/rules/version-pinning.mdc) every third-party action is pinned by commit SHA with a `# vX.Y.Z` trailing comment. The SHAs used in this PR:

| Action | SHA | Tag |
| --- | --- | --- |
| `actions/checkout` | `11bd71901bbe5b1630ceea73d27597364c9af683` | v4.2.2 |
| `actions/setup-python` | `0b93645e9fea7318ecaed2b359559ac225c90a2b` | v5.3.0 |
| `astral-sh/setup-uv` | `38f3f104447c67c051c4a08e39b64a148898af3a` | v4.2.0 |
| `amannn/action-semantic-pull-request` | `0723387faaf9b38adef4775cd42cfd5155ed6017` | v5.5.3 |
| `trufflesecurity/trufflehog` | `af3e68261fa87568031f65161577cc2ebe1ca669` | v3.83.7 |
| `actions/dependency-review-action` | `3b139cfc5fae8b618d3eae3675e383bb1769c019` | v4.5.0 |
| `CycloneDX/gh-python-generate-sbom` | `39fe80937489538e12de5a7b427e078649ec44bb` | v2.0.0 |
| `actions/upload-artifact` | `b4b15b8c7c6ac21ea08fcf65892d2ee8f75cf882` | v4.4.3 |
| `actions/download-artifact` | `fa0a91b85d4f404e444e00e005971372dc801d16` | v4.1.8 |
| `actions/setup-node` | `39370e3970a6d050c480ffad4ff0ed4d3fdee5af` | v4.1.0 |

Renovate (`.github/renovate.json`) + Dependabot (`.github/dependabot.yml`) both manage SHA bumps via PR.

Lookup procedure:

```bash
gh api "repos/<owner>/<repo>/git/ref/tags/<tag>" --jq '.object.sha'
```

## Issue + PR templates

- `.github/ISSUE_TEMPLATE/feature.md` - title + problem + proposed solution + acceptance + traceability hooks.
- `.github/ISSUE_TEMPLATE/bug.md` - environment + repro + expected + actual + severity + affected profile.
- `.github/ISSUE_TEMPLATE/standards-deviation.md` - MISRA rule + files + justification + mitigation + owner; format matches ADR-0003 deviation register.
- `.github/PULL_REQUEST_TEMPLATE.md` - summary + related issues/ADRs + test-plan checklist + standards citations + sub-plan/research-note links.

The three originally-shipped templates (`research-note.md`, `epic.md`, `phase-acceptance.md`) from PR-4 (#4 `p0-issues`) remain; combined the issue-template set is 6 files.

## Rule-mirror sync (PR-7 follow-up F1)

`infrastructure/rules/sync.{sh,ps1}` + `_convert.py`:

- `sync.sh` (bash) / `sync.ps1` (PowerShell) - thin wrappers that iterate `.cursor/rules/*.mdc` and call the Python helper.
- `_convert.py` - parses frontmatter; translates `globs:` â†’ `applyTo:` (or `applyTo: '**'` if `alwaysApply: true`); prepends a "Mirror of" header; writes `.github/instructions/<name>.instructions.md`.
- Idempotent; running twice produces the same output.
- The CI workflow `rules-mirror-drift.yml` runs `sync.sh` on every PR touching rule paths and fails on diff. Resolves PR-7 F2.

## Dep-graph SVG render (PR-3 follow-up F1)

`docs-render.yml`:

- On push to `main` touching `dep-graph.mmd`: render SVG via `npx -y @mermaid-js/mermaid-cli mmdc`, commit + push if changed (with `[skip ci]` to avoid loops).
- On PR touching `dep-graph.mmd` or `dep-graph.svg`: drift check; fail if committed SVG disagrees with regenerated.
- Puppeteer runs in Ubuntu container with `--no-sandbox` flags; bypasses the Windows local install issue documented in PR-3.

## Dependabot + Renovate

Both ship; configurations are equivalent. Dependabot is the GitHub-native baseline (no PAT needed); Renovate offers grouped updates + lock-file maintenance. Repository owner can disable either if desired.

## Bootstrap-window closure

After PR-4 merges:

```bash
gh api -X POST "/repos/goldr0g3r/tethys/branches/main/protection/enforce_admins"
```

Verifies via:

```bash
gh api "/repos/goldr0g3r/tethys/branches/main/protection" --jq '.enforce_admins.enabled'
# â†’ true
```

Future PRs go through:

- 9 required status checks (`build`, `misra-gate`, `static-analysis`, `coverage`, `fuzz-smoke`, `secret-scan`, `dependency-review`, `a2l-roundtrip`, `pr-title`) plus 2 new (`docs-render`, `rules-mirror-drift`) where path-applicable.
- 1 review required (code-owner reviews required).
- Linear history.
- Signed commits required.
- Conversation resolution required.

The `--admin` override is no longer available; subsequent PRs must pass all gates organically.

## Decisions

| Q | Resolution |
| - | - |
| Q1 PR scope | all 13 workflows + templates + scripts in one PR per parent Â§7 |
| Q2 enforce_admins re-enable | as final step inside PR-4 after merge |
| Q3 Dependabot vs Renovate | ship both; Dependabot is the GitHub-native baseline |
| Q4 Missing-feature stubs | scaffold workflows trivially today; engage when code arrives |
| Q5 Third-party action pins | resolved at execution time via `gh api`; recorded above |

## Open follow-ups

- **F1** - Once Phase-1+ code lands, revisit each `scaffolded` workflow and add proper threshold engagement (coverage 95%, MISRA zero deviations, fuzz crash issue automation).
- **F2** - `docs-render.yml` regenerates `dep-graph.svg` on every push; will run on first push to main after this PR lands and commit the canonical SVG.
- **F3** - `release.yml` and `sbom.yml` are scaffolded; PR-11 finalises the Docker image content, semantic-release config, and full FetchContent dependency enumeration in the slave SBOM.
- **F4** - `pr-title.yml` scope list is duplicated in `.cursor/rules/conventional-commits.mdc`; a future PR could generate one from the other to prevent drift.

## Implementation Reference

- PR: [#11 ci: 11 workflows + templates + rule-mirror + dep-graph render + enforce_admins re-enable](https://github.com/goldr0g3r/tethys/pull/11)
- Merged on: 2026-05-14 (PR #11)
- Bootstrap window closed: 2026-05-14 - `enforce_admins=true` restored on `main` immediately after PR #11 merge via `gh api -X POST /repos/.../branches/main/protection/enforce_admins`; this status-sync PR (PR #12) is the first PR exercising the full gate organically (no `--admin` override).
