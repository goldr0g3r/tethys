# Software Verification + Validation Plan (SVCP)

> **Status:** living draft - Phase 0 seed. The bulk of V&V mechanics
> already exists in the CI workflows (parent plan §6.7); this document
> is the **standards-referenced view** of those workflows.
> **Length budget at v1.0:** 25-40 pages.

## 0. Document control

| Field | Value |
| --- | --- |
| Identifier | TETHYS-SVCP-001 |
| Revision | 0.1 (seed) |
| Audit date | 2026-05-15 |
| Owner | Project owner |
| Status | Living draft |

## 1. Scope

The SVCP describes how Tethys verifies that the software is built
correctly (verification) and that it does what it should (validation).
Companion document: the Software Quality Assurance Plan
[(SQAP)](sqap.md), which audits the *process* rather than the
*product*.

Satisfies:

- ECSS-E-ST-40C Rev.1 §5.6 (software verification) + §5.8 (software validation).
- IEC 61508-3 §7.7 (software verification) + §7.8 (software safety validation).
- DO-178C §6.4 (software verification process, informational).
- NPR 7150.2D §3.6 + §3.7 (Class B software verification).

## 2. Verification techniques

### 2.1 Static analysis

| Tool | Workflow | Gate |
| --- | --- | --- |
| `cppcheck --addon=misra` | [`misra-gate.yml`](../.github/workflows/misra-gate.yml) | Zero open mandatory/required deviations. |
| `clang-tidy` | [`static-analysis.yml`](../.github/workflows/static-analysis.yml) | Zero new warnings. |
| `gcc -fanalyzer` | [`static-analysis.yml`](../.github/workflows/static-analysis.yml) | Zero new warnings. |
| `scan-build` | [`static-analysis.yml`](../.github/workflows/static-analysis.yml) | Zero new findings. |
| `ruff` | [`ci.yml`](../.github/workflows/ci.yml) | Zero violations. |
| `mypy --strict` | [`ci.yml`](../.github/workflows/ci.yml) | Zero type errors. |

### 2.2 Unit + integration test

| Suite | Tool | Workflow |
| --- | --- | --- |
| Slave unit tests | Unity + Ceedling | [`ci.yml`](../.github/workflows/ci.yml) slave matrix |
| Master unit tests | pytest | [`ci.yml`](../.github/workflows/ci.yml) master matrix |
| GUI smoke | pytest-qt (offscreen) | [`ci.yml`](../.github/workflows/ci.yml) master matrix |
| Differential test vs pyxcp | pytest + `[diff-test]` extra | [`ci.yml`](../.github/workflows/ci.yml) Phase 2 acceptance |
| Transport conformance | pytest | [`master/tests/test_transport_conformance.py`](../master/tests/test_transport_conformance.py) |

### 2.3 Coverage

| Gate | Target | Workflow |
| --- | --- | --- |
| Slave statement coverage | `>= 95%` on `slave/src/core/` | [`coverage.yml`](../.github/workflows/coverage.yml) |
| Slave MC/DC coverage | `>= 90%` on `slave/src/core/` (`>= 95%` by P8) | [`coverage.yml`](../.github/workflows/coverage.yml) |
| Master coverage | `>= 90%` on `protocol` + `transport` | [`ci.yml`](../.github/workflows/ci.yml) |

### 2.4 Fuzzing

| Harness | Tool | Workflow | Cadence |
| --- | --- | --- | --- |
| CTO dispatcher | libFuzzer (Clang) | [`fuzz-nightly.yml`](../.github/workflows/fuzz-nightly.yml) | Nightly. Corpus growth tracked. |
| A2L parser | AFL++ / libFuzzer | [`fuzz-nightly.yml`](../.github/workflows/fuzz-nightly.yml) | Nightly. |

Corpus: [`slave/fuzz/corpus/`](../slave/fuzz/corpus/).

### 2.5 Robustness suite (Phase 10)

Dropped / reordered / duplicated frames, A2L drift, timeout edge cases,
malformed CTO, AES seed-and-key tamper. Tracked by parent §6.7 +
Phase 10 acceptance.

### 2.6 A2L round-trip

[`a2l-roundtrip.yml`](../.github/workflows/a2l-roundtrip.yml). Parse +
emit + re-parse equivalence; drift = failure.

## 3. Validation techniques

### 3.1 Acceptance bench (Phase 1+)

Master ↔ simulator over UDP loopback (parent §8 Phase 1 acceptance).
Reproducible via [`infrastructure/docker/compose.yml`](../infrastructure/docker/compose.yml).

### 3.2 HIL bench (Phase 9)

Closed-loop on real STM32 hardware with a Simulink plant model.
[`docs/runbooks/hil-bench-setup.md`](runbooks/hil-bench-setup.md);
scenarios under [`hil/scenarios/`](../hil/scenarios/).

### 3.3 Demo recordings

Two end-to-end recordings per Phase 9 + parent §11 + the
[`demo-recording.md`](runbooks/demo-recording.md) runbook.

## 4. Traceability

Single living matrix: [`docs/traceability.csv`](traceability.csv).
Format per [`.cursor/rules/ecss-traceability.mdc`](../.cursor/rules/ecss-traceability.mdc):

```text
id, kind, parent, description, implemented_by, verified_by, standard_objective, phase, profile
```

Generated view: [`docs/traceability.md`](traceability.md) (rendered
from the CSV by a Sphinx build).

## 5. Independence + reviewer roles

- CI = independent verification (machine, no operator).
- Human review = mandatory per branch protection (`require_code_owner_reviews`).
- GitHub Copilot review = secondary reviewer (free for public repos).

## 6. Tool qualification (DO-178C §11.22, informational)

Tethys is academic / demonstrator-grade today. Tool qualification
gaps:

- No certified MISRA checker (cppcheck-misra is open-source, not
  qualified). Polyspace Bug Finder waived per ADR-0008.
- No qualified compiler (GCC / Clang free toolchain; Green Hills /
  IAR Safety waived).
- gcovr is not qualified for DAL-B MC/DC evidence in a flight-grade
  audit; documented gap.

Each gap is recorded in [ADR-0008 license-free toolchain](adr/0008-license-free-toolchain.md).

## 7. Defect tracking

[`docs/runbooks/incident-and-defect.md`](runbooks/incident-and-defect.md).
GitHub Issues with the [`type/bug`](https://github.com/goldr0g3r/tethys/labels/type%2Fbug)
label; severity matrix in the runbook.

## 8. Open items

- F1: Phase 10 produces the full verification PDF bundle - including a
  consolidated MC/DC trace, a fuzz corpus summary, and a robustness
  report.
- F2: Phase 11 publishes the verification artefacts under
  [`docs/site/_static/`](../docs/site/_static/) and links them from the
  README scorecard.

## Cross-references

- [SDP](sdp.md), [SAD](sad.md), [SCMP](scmp.md), [SQAP](sqap.md).
- Parent plan §6.7 (CI gate matrix).
- Parent plan §12 (standards compliance scorecard).
- [`docs/traceability.csv`](traceability.csv).
- [`docs/runbooks/traceability-matrix-maintenance.md`](runbooks/traceability-matrix-maintenance.md).
- ECSS-E-ST-40C Rev.1 §5.6 + §5.8.
- IEC 61508-3 §7.7 + §7.8.
- DO-178C §6.4.
- NPR 7150.2D §3.6 + §3.7.
