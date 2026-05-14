# Architecture Decision Records (ADRs)

Tethys uses [MADR v3.0](https://adr.github.io/madr/) for Architecture Decision Records. Each ADR captures one architecturally significant decision with its context, drivers, considered options, outcome, and consequences.

## Index

| # | Title | Status | Date | Accepted by |
| - | --- | --- | --- | --- |
| [0001](0001-xcp-as-development-protocol.md) | XCP as a development-time protocol | accepted | 2026-05-14 | PR-3 |
| [0002](0002-profile-based-build-system.md) | Profile-based build system (marine, space) | accepted | 2026-05-14 | PR-3 |
| [0003](0003-misra-c-2023-as-coding-gate.md) | MISRA C:2023 as the coding gate | accepted | 2026-05-14 | PR-3 |
| [0004](0004-transport-abstraction-layer.md) | Transport-abstraction-layer interface | accepted | 2026-05-14 | PR-3 |
| [0005](0005-no-dynamic-allocation.md) | No dynamic allocation in the slave | accepted | 2026-05-14 | PR-3 |
| [0006](0006-aes-128-seed-and-key.md) | AES-128 derived seed-and-key (space profile) | accepted | 2026-05-14 | PR-3 |
| [0007](0007-python-master-not-matlab.md) | Python master tool, MATLAB is consumer not driver | accepted | 2026-05-14 | PR-3 |
| [0008](0008-license-free-toolchain.md) | License-free toolchain + repo license | accepted | 2026-05-14 | PR-3 |
| [0009](0009-rulesets-migration.md) | Migrate `main` from classic branch protection to a Repository Ruleset | proposed | 2026-05-14 | *(deferred)* |
| [0010](0010-packet-loss-tolerance-budget.md) | Packet-loss tolerance budget | accepted | 2026-05-14 | PR-3 |

## ADR workflow

1. **Identify** an architecturally significant decision (something that's hard to reverse, affects many components, or has non-obvious trade-offs).
2. **Open a research note** under `docs/research/phase-N-<topic>.md` per the [`research-note-per-phase`](../../.cursor/rules/research-note-per-phase.mdc) rule.
3. **Draft the ADR** under `docs/adr/drafts/adr-NNNN-<slug>.md` with status `proposed`.
4. **Promote** the draft to `docs/adr/NNNN-<slug>.md` with status `accepted` in the PR that lands the corresponding code (or the architecture-only PR that formalises the decision).
5. **Supersede** an accepted ADR by writing a new one and setting the old one's `Superseded by:` field.

## MADR v3.0 template

See [MADR v3.0](https://adr.github.io/madr/) for the canonical template. The frontmatter Tethys uses:

```markdown
# ADR-NNNN - <Short title>

- **Status:** proposed | accepted | superseded
- **Date:** YYYY-MM-DD
- **Deciders:** @owner
- **Consulted:** ...
- **Informed:** ...
- **Supersedes:** ADR-NNNN
- **Superseded by:** ADR-NNNN
- **Accepted by:** PR-N description

## Context and Problem Statement
## Decision Drivers
## Considered Options
## Decision Outcome
## Consequences
## References
```

## Related rules

- [`always-cite-standards`](../../.cursor/rules/always-cite-standards.mdc) - every ADR cites the standards it consumes (S1-S35 in [`docs/research/phase-0-standards-matrix.csv`](../research/phase-0-standards-matrix.csv)).
- [`ecss-traceability`](../../.cursor/rules/ecss-traceability.mdc) - every new ADR gets a row in `docs/traceability.csv` (lands in PR-10).
- [`research-note-per-phase`](../../.cursor/rules/research-note-per-phase.mdc) - every ADR is backed by a research note.
