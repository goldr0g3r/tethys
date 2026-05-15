# MISRA C:2023 deviation register

> Living register of every project-approved deviation from MISRA C:2023.
> Mandatory deviations are not permitted. Required deviations require approval.
> Advisory deviations are logged for audit.
>
> Cite: [ADR-0003 - MISRA C:2023 as the coding gate](adr/0003-misra-c-2023-as-coding-gate.md).
> Cite: [docs/coding-standard.md - MISRA deviation procedure](coding-standard.md#10-misra-c2023-deviation-procedure).
> Cite: MISRA C:2023 (<https://www.misra.org.uk/>).
> Trace: [docs/traceability.csv](traceability.csv) - referenced by every
> deviation row.

## Status summary (current as of 2026-05-15)

| Tier | Open | Approved | Pending | Rejected | Closed |
| --- | --- | --- | --- | --- | --- |
| Mandatory | 0 | 0 | 0 | 0 | 0 |
| Required  | 0 | 0 | 0 | 0 | 0 |
| Advisory  | 0 | 0 | 0 | 0 | 0 |

Zero open deviations on day-zero. The slave/ source tree is empty; deviations
arrive incrementally as code lands in Phase 1 and onward.

## Workflow

1. New deviation arrives with the PR that requires it. Author appends an entry
   to the appropriate section below.
2. Author appends a per-line suppression to
   [`cppcheck-suppressions.txt`](../cppcheck-suppressions.txt) referencing the
   entry id.
3. `misra-gate.yml` cross-checks: every suppression must have a matching entry
   here.
4. Reviewer marks the entry `approved` or `rejected`. Rejected = the PR is
   either reworked or held.
5. Every 180 days the owner re-reviews. Outcome bumps the `Re-review by:` date
   or moves the entry into the `Closed` section.

## Entry id scheme

`MISRA-DEV-<NNNN>` where NNNN is a zero-padded monotonic counter. The next
available id appears at the bottom of the file.

## Mandatory deviations

**None permitted.** A mandatory-tier rule violation blocks merge unconditionally.

## Required deviations (approved)

*Empty on day-zero.*

## Required deviations (pending review)

*Empty on day-zero.*

## Advisory deviations (approved)

*Empty on day-zero.*

## Advisory deviations (logged - no fix planned)

*Empty on day-zero.*

## Closed deviations (history)

*Empty on day-zero.*

## Reference entry template (do NOT instantiate; copy when filing a new one)

```markdown
### MISRA-DEV-0001 - Rule N.M - <Mandatory | Required | Advisory>

- **Tier:** Required
- **Files:** `slave/src/core/foo.c` lines 42-58
- **Rule text:** <one-line excerpt from MISRA C:2023 - never copy the full
  rule body which is copyrighted by the MISRA consortium>
- **Justification:** <why the violation is unavoidable; reference the design
  constraint or external interface that forces it>
- **Mitigation:** <runtime assertion, fuzz coverage, manual review, formal
  proof - one or more>
- **Owner:** @goldr0g3r
- **PR introduced:** #NN
- **Approval status:** approved | pending | rejected
- **Review date:** 2026-MM-DD
- **Re-review by:** 2026-MM-DD (default +180 days)
- **Trace:** `docs/traceability.csv` row TETHYS-DEV-0001
- **Suppression:** `cppcheck-suppressions.txt` line N
```

## Next available id

`MISRA-DEV-0001`
