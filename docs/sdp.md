# Software Development Plan (SDP)

> **Status:** living draft - Phase 0 seed. Each section currently
> points at the canonical Tethys artefact that already covers the
> required content; Phase 10 + Phase 11 expand the body to satisfy
> the full standard objectives.
> **Audience:** reviewers asking for the SDP under ECSS-Q-ST-80C
> §5.4 / NASA-STD-8739.8 §3.1 / IEC 61508-3 §6.
> **Length budget at v1.0:** 25-35 pages.

## 0. Document control

| Field | Value |
| --- | --- |
| Identifier | TETHYS-SDP-001 |
| Revision | 0.1 (seed) |
| Audit date | 2026-05-15 |
| Owner | Project owner (`AGENTS.md` §Owner) |
| Status | Living draft |

## 1. Scope

The Software Development Plan defines how Tethys is built, reviewed,
verified, and released. It is the **process-level** companion to the
[Software Architecture Description (SAD)](sad.md) which describes
*what* is built and the [Software Verification + Validation Plan
(SVCP)](svcp.md) which describes *how* the build is proved correct.

This document satisfies:

- ECSS-Q-ST-80C §5.4 (software development process planning).
- NASA-STD-8739.8 §3.1 (software development plan content).
- IEC 61508-3 §6 (software lifecycle process for SIL 2/3 targets).

## 2. Lifecycle model

Tethys uses an iterative, PR-driven lifecycle with twelve numbered
phases (Phase 0 - Phase 11). Each phase is a self-contained slice with:

- An Epic Issue.
- A research note (`docs/research/phase-<N>-<topic>.md`).
- A sub-plan (`.cursor/plans/<phase-id>_<topic>.plan.md`).
- One or more feature PRs.
- A Phase-Acceptance Issue closed when every child closes plus the
  demo recording is attached.

Phase definitions: [parent plan §8](../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md#8-phased-implementation-p1p11).

## 3. Team + roles

(seed; fill in at Phase 11)

- Project owner: signs off on architecture (ADR `accepted`).
- Reviewer pool: GitHub Copilot review (free for public repos) + at
  least one human approval per PR (branch protection rule).
- CI agents: every PR is validated by the 11 workflows in
  [`.github/workflows/`](../.github/workflows/).

## 4. Standards baseline

- ECSS-E-ST-40C Rev.1 (April 2025) - engineering process.
- ECSS-Q-ST-80C - software product assurance.
- NPR 7150.2D - NASA software engineering requirements (Class B target).
- IACS UR E22 Rev.3 (in force 1 Jul 2024) - marine class society SW.
- IEC 61508-3 - functional safety (SIL 2 default; SIL 3 design feasibility).
- DO-178C DAL-B (informational).
- MISRA C:2023 - coding standard (mandatory + required as CI gate).

Full matrix: [`docs/research/phase-0-standards-matrix.csv`](research/phase-0-standards-matrix.csv).

## 5. Development environment

Toolchain: parent plan §5. Every tool is OSI / free per
[ADR-0008 license-free toolchain](adr/0008-license-free-toolchain.md)
and [`.cursor/rules/free-tool-only.mdc`](../.cursor/rules/free-tool-only.mdc).

CI runs on the GitHub Actions free tier; image set: see
[`infrastructure/docker/`](../infrastructure/docker/).

## 6. Configuration management

See [Software Configuration Management Plan (SCMP)](scmp.md) for the
full lifecycle. Headline: SemVer + Conventional Commits +
branch-protected `main` + signed tags.

## 7. Verification + Validation

See [Software Verification + Validation Plan (SVCP)](svcp.md).
Coverage gates: `>= 95%` statement, `>= 90%` MC/DC on `slave/src/core/`
(parent plan §6.7 `coverage.yml`).

## 8. Quality assurance

See [Software Quality Assurance Plan (SQAP)](sqap.md).

## 9. Risk management

(seed; fill in at Phase 10)

- Tool-qualification gap (no qualified compiler / certified MISRA
  checker) - documented in ADR-0008.
- Hardware procurement risk (GR716A / RAD750 stand-in) -
  [parent plan §13 open question](../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md#13-open-questions-parked-for-the-relevant-phase-research-note).

## 10. Schedule

[Parent plan §8](../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md#8-phased-implementation-p1p11)
+ the Phase 0..11 milestones on GitHub. The schedule is
*phase-completion-driven*, not date-driven.

## 11. Status sync at PR merge

Every PR ends with the status-sync loop from parent plan §6.8:

1. Parent plan todo flipped `pending` → `in_progress` → `completed`.
2. Projects v2 item Status field updated.
3. Linked Issue closed `state_reason: completed`.
4. Research note records the PR URL + merge date.

## 12. Open items

- F1: Expand §3 (team + roles) at Phase 11 with the actual contributor
  set.
- F2: Expand §9 (risk register) at Phase 10 with the verification-pack
  output.
- F3: Add §13 (training plan) - waived for a one-owner academic project
  but listed for ECSS completeness.

## Cross-references

- Parent plan: [`xcp_extreme-env_tool_14019278.plan.md`](../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md).
- [SAD](sad.md), [SVCP](svcp.md), [SCMP](scmp.md), [SQAP](sqap.md).
- [Traceability matrix](traceability.csv).
- [ADR-0008 license-free toolchain](adr/0008-license-free-toolchain.md).
- ECSS-Q-ST-80C: https://ecss.nl/standard/ecss-q-st-80c-rev-1-software-product-assurance/.
- NASA-STD-8739.8: https://standards.nasa.gov/standard/nasa/nasa-std-87398.
- IEC 61508-3: https://webstore.iec.ch/publication/5519.
