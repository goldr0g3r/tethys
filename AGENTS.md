# AGENTS.md - Tethys

This file is a short stub for **any AI agent** (Cursor, Claude, generic) working on this repository. It intentionally duplicates [`CLAUDE.md`](CLAUDE.md) so each agent finds its expected entry point.

## Canonical conventions

The **single source of truth** for project conventions is [`.cursor/rules/`](.cursor/rules/). GitHub Copilot reads the same rules from [`.github/instructions/`](.github/instructions/) (auto-mirrored; do not hand-edit).

Twelve rule files cover: XCP protocol discipline, MISRA C:2023 gate, ECSS / NPR / IACS traceability, marine profile invariants, space profile invariants, no dynamic allocation, no recursion / no goto, always cite standards, research-note-per-phase, version pinning, free-tool only, Conventional Commits.

## PR workflow (parent plan section 6.2)

1. Open or pick an issue.
2. Branch off `main` as `<type>/<short-name>` (e.g. `chore/p0-rules`).
3. Open a draft PR; CI runs on every push.
4. Self-review against the rule mirror in [`.github/instructions/`](.github/instructions/).
5. Address review comments; mark "Ready for review".
6. Squash-merge with the Conventional Commit title.

## Required per PR

- Sub-plan under [`.cursor/plans/`](.cursor/plans/) before execution.
- Research note under [`docs/research/`](docs/research/) with retrieval-dated sources.
- Status-sync edits on merge (flip parent-plan todo to `completed`).

## Reference docs

- Parent plan: [`.cursor/plans/xcp_extreme-env_tool_14019278.plan.md`](.cursor/plans/xcp_extreme-env_tool_14019278.plan.md)
- System requirements + packet-loss budget: [`docs/research/phase-0-system-requirements.md`](docs/research/phase-0-system-requirements.md)
- Standards matrix: [`docs/research/phase-0-standards-matrix.csv`](docs/research/phase-0-standards-matrix.csv)
- GitHub runbook: [`docs/runbooks/github-setup.md`](docs/runbooks/github-setup.md)
