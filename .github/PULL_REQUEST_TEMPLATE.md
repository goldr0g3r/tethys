<!--
PR title must follow Conventional Commits 1.0 per .cursor/rules/conventional-commits.mdc.
Format: <type>(<scope>): <imperative-mood subject, lowercase, no period>
Types: feat | fix | chore | docs | ci | refactor | test | perf | build | revert
Scopes: master | slave | transport | profile-marine | profile-space | docs | ci | standards |
        scaffold | rules | issues | runbook | research | status-sync | release | branch-protection
-->

## Summary

(1-2 sentences explaining the WHY. Cite the parent-plan todo + sub-plan + research note.)

## Related issues + ADRs

- Closes #
- ADR: [ADR-NNNN](docs/adr/NNNN-*.md)
- Sub-plan: `.cursor/plans/<id>.plan.md`
- Research note: `docs/research/phase-N-<topic>.md`

## What this PR does

- (Concrete deliverable 1)
- (Concrete deliverable 2)

## Test plan

- [ ] Tests added or updated (or N/A documented)
- [ ] `markdownlint-cli2` clean
- [ ] MISRA clean (if `slave/` touched)
- [ ] Coverage delta acceptable (if test code touched)
- [ ] Docs updated (README, runbooks, architecture)
- [ ] `docs/traceability.csv` row added (if requirement-touching - per `ecss-traceability` rule)
- [ ] Sub-plan + research note attached
- [ ] Status-sync update planned (flip parent-plan todo on merge)

## Standards citations

(Required by `always-cite-standards` rule when touching traced code. Multiple `Cite:` lines allowed.)

```text
Cite: ASAM XCP 1.4 Part 2 §...
Cite: ECSS-E-ST-40C Rev.1 §...
Cite: MISRA C:2023 Rule X.Y
Trace: docs/traceability.csv row TETHYS-REQ-NNNN
```

## Decisions baked in (if sub-plan asked open questions)

- Q1: ...
- Q2: ...

## Notes for reviewers

(Anything reviewers should pay extra attention to: surprises, deferred follow-ups, gaps from the parent plan.)
