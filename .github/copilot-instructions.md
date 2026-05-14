# GitHub Copilot - Tethys

These are the repo-wide instructions for GitHub Copilot Workspace and the Copilot review bot. File-pattern-scoped rules live in [`.github/instructions/*.instructions.md`](instructions/) and are auto-mirrored from [`.cursor/rules/*.mdc`](../.cursor/rules/) (do not hand-edit the mirror).

## Canonical conventions

Twelve rules cover: XCP protocol discipline, MISRA C:2023 gate, ECSS / NPR / IACS traceability, marine profile invariants, space profile invariants, no dynamic allocation, no recursion / no goto, always cite standards, research-note-per-phase, version pinning, free-tool only, Conventional Commits.

## Required per suggestion

- Cite the controlling standard in code comments and commit bodies (`always-cite-standards` rule).
- Follow Conventional Commits 1.0 (`conventional-commits` rule) for any PR title / commit subject suggestion.
- Static buffer sizing only in `slave/**/*.c` (`no-dynamic-allocation` rule).
- No recursion, no goto, bounded loops in `slave/**/*.c` (`no-recursion-no-goto` rule).
- Pin every new dependency exactly (`version-pinning` rule).
- No paid-license dependencies (`free-tool-only` rule).

## Reference docs

- Parent plan: [`.cursor/plans/xcp_extreme-env_tool_14019278.plan.md`](../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md)
- System requirements + packet-loss budget: [`docs/research/phase-0-system-requirements.md`](../docs/research/phase-0-system-requirements.md)
- Standards matrix: [`docs/research/phase-0-standards-matrix.csv`](../docs/research/phase-0-standards-matrix.csv)
- CODEOWNERS: [`.github/CODEOWNERS`](CODEOWNERS)
