---
name: Standards deviation
about: Document a MISRA C:2023 deviation (or other standards deviation) per ADR-0003
title: "standards-deviation: MISRA Rule <N.M> in <path>"
labels: standards-deviation, type/chore
assignees: ''
---

## Standard + rule

- Standard: (MISRA C:2023 | ISO 26262:2018 | ECSS-E-ST-40C Rev.1 | other)
- Rule / clause: (e.g. MISRA Rule 15.1)
- Severity: (Mandatory | Required | Advisory)

## Files affected

(File path + line range. Format matches `docs/misra-deviations.md` deviation register from ADR-0003.)

```text
slave/src/core/foo.c lines 42-58
```

## Justification

(Why is the deviation necessary? What prevents using the standard-compliant alternative?)

## Mitigation

(What compensating control exists? E.g. additional review, additional tests, runtime assertion.)

## Scope

- Profile affected: (marine | space | both)
- Phase introduced: (Phase 0..11)

## Owner + PR

- Owner: @goldr0g3r
- PR introducing the deviation: #
- Approval status: (proposed | approved | denied)

## References

- ADR-0003 - [MISRA C:2023 as the coding gate](../../docs/adr/0003-misra-c-2023-as-coding-gate.md)
- `docs/misra-deviations.md` - the canonical deviation register (lands in PR-5)
- [`.cursor/rules/misra-c-2023-gate.mdc`](../../.cursor/rules/misra-c-2023-gate.mdc)
