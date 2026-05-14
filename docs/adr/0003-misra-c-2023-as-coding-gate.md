# ADR-0003 - MISRA C:2023 as the coding gate

- **Status:** accepted
- **Date:** 2026-05-14
- **Deciders:** @goldr0g3r (project owner)
- **Consulted:** parent plan §4 (safety + standards mapping)
- **Informed:** all slave/ contributors; PR-5 (coding standards) implementer; PR-4 (CI) implementer
- **Supersedes:** —
- **Superseded by:** —
- **Accepted by:** PR-3 `docs(architecture)`

## Context and Problem Statement

Tethys-slave is portable C11 firmware that targets both marine (IACS UR E22 Rev.3, S11) and space (ECSS-E-ST-40C Rev.1, S18) profiles. Both standards expect a coding-standard regime; the closest market consensus is **MISRA C:2023** - the current revision of the MISRA C guidelines, published by the Motor Industry Software Reliability Association.

The question: which subset of MISRA do we enforce as a hard CI gate, what tool runs the check, and how do we handle documented deviations?

## Decision Drivers

- ECSS-E-ST-40C Rev.1 (S18) accepts MISRA C as a recognised coding standard.
- ISO 26262:2018 part 6 (S9) lists MISRA C among approved standards for ASIL-rated software.
- The free-tool constraint per [ADR-0008](0008-license-free-toolchain.md) rules out LDRA and Polyspace (paid).
- MISRA C:2023 is the latest revision; using older MISRA C:2012 would be a documentable but unnecessary regression.
- The [`misra-c-2023-gate.mdc`](../../.cursor/rules/misra-c-2023-gate.mdc) Cursor rule already documents the intent; this ADR records the architectural decision.

## Considered Options

1. **MISRA C:2012 + LDRA Testbed** (industry standard but paid).
2. **MISRA C:2023 mandatory only** as a CI gate (lighter scope; advisory and required ignored).
3. **MISRA C:2023 mandatory + required as a hard CI gate; advisory tracked but not blocking** (cppcheck-misra as the tool; deviations documented in `docs/misra-deviations.md`).

## Decision Outcome

Chose **Option 3** (MISRA C:2023 mandatory + required as a hard CI gate via cppcheck-misra).

### Gate semantics

- **Mandatory rules:** zero deviations. Ever. CI workflow `misra-gate.yml` (PR-4) runs `cppcheck --addon=misra` and fails on any violation.
- **Required rules:** zero open deviations on `main`. A PR may introduce a required-rule deviation only when accompanied by a corresponding entry in `docs/misra-deviations.md` with rationale, scope, mitigation, and an owner.
- **Advisory rules:** tracked in `docs/misra-deviations.md`; no PR-blocking gate, but documented violations are reviewed at phase-acceptance time.

The space profile additionally enforces a subset of advisory rules (see [`space-profile-invariants.mdc`](../../.cursor/rules/space-profile-invariants.mdc) and [`no-recursion-no-goto.mdc`](../../.cursor/rules/no-recursion-no-goto.mdc)).

### Tool chain

- **cppcheck** with `--addon=misra` as the primary gate (free; covers the MISRA C:2023 rule set).
- **clang-tidy** with `cert-*`, `bugprone-*`, `performance-*`, `readability-*` checks for additional CERT C coverage (security-sensitive code).
- **gcc -fanalyzer** for additional flow-sensitive analysis.
- **scan-build** for clang static analyser output.
- **Frama-C/WP** (optional) for ACSL-contract verification of `tethys_core/`.

### Deviation procedure (target: `docs/misra-deviations.md` - lands in PR-5)

```markdown
## MISRA C:2023 Rule N.M - <Mandatory | Required | Advisory>

- **Files:** slave/src/core/foo.c lines 42-58
- **Justification:** <why the violation is unavoidable>
- **Mitigation:** <what compensating control exists>
- **Owner:** @goldr0g3r
- **PR introduced:** #NN
- **Approval status:** approved / pending
```

## Consequences

- **Positive:** A free, repeatable, machine-checkable coding gate.
- **Positive:** Documented deviation process means every exception is auditable.
- **Positive:** MISRA C:2023 alignment positions Tethys for downstream certification reviews (DO-178C DAL-B reviewers know to look for MISRA evidence).
- **Negative:** cppcheck-misra rule coverage is not 100% identical to commercial tools (LDRA, Polyspace) per parent §9. Gap declared in [ADR-0008](0008-license-free-toolchain.md).
- **Negative:** Some legitimate patterns (e.g. printf-family in test code) trigger MISRA warnings; documented deviation is the answer rather than disabling the rule.
- **Risk:** cppcheck-misra addon updates may introduce new findings on previously-clean code. **Mitigation:** Renovate / Dependabot manages cppcheck version per [ADR-0008](0008-license-free-toolchain.md); any new findings get triaged in the bumping PR.

## Forward references

- `docs/coding-standard.md` - naming, header guards, banned constructs - lands in PR-5 `p0-coding-standards`.
- `docs/misra-deviations.md` - the deviation register - lands in PR-5; format above.
- `.github/workflows/misra-gate.yml` - the CI workflow - lands in PR-4 `p0-ci`.

## References

- Parent plan section 4 (safety + standards mapping); section 6.7 (CI gate matrix).
- [`misra-c-2023-gate.mdc`](../../.cursor/rules/misra-c-2023-gate.mdc) - machine-readable expression.
- MISRA C:2023 guidelines (no S-number; project-wide gate). Industry consensus on safety-critical C.
- ECSS-E-ST-40C Rev.1 (S18), ISO 26262:2018 (S9) - process anchors.
- [ADR-0007](0007-python-master-not-matlab.md) - master tool licensing (matches the free-tool constraint).
- [ADR-0008](0008-license-free-toolchain.md) - records the cppcheck-vs-LDRA coverage gap.
