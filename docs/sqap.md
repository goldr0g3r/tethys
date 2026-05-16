# Software Quality Assurance Plan (SQAP)

> **Status:** living draft - Phase 0 seed. The QA mechanics live in the
> CI workflows + the Cursor rule set; this document is the
> **standards-referenced view**.
> **Length budget at v1.0:** 15-25 pages.

## 0. Document control

| Field | Value |
| --- | --- |
| Identifier | TETHYS-SQAP-001 |
| Revision | 0.1 (seed) |
| Audit date | 2026-05-15 |
| Owner | Project owner |
| Status | Living draft |

## 1. Scope

The SQAP describes how Tethys assures that the development process
itself meets the controlling standards. Companion documents:

- [SDP](sdp.md) - how the work gets done.
- [SVCP](svcp.md) - how the *product* is proved correct.
- [SCMP](scmp.md) - how the configuration is managed.
- [SAD](sad.md) - what the architecture is.

Satisfies:

- ECSS-Q-ST-80C §5.2 (software quality assurance).
- NASA-STD-8739.8 §3.2 (software quality assurance plan content).
- DO-178C §11.6 (software quality assurance, informational).
- IEC 61508-3 §6.2.4 (quality management).

## 2. Quality goals

| # | Goal | Source of truth |
| --- | --- | --- |
| 1 | Zero open MISRA mandatory + required deviations on `main`. | [`misra-gate.yml`](../.github/workflows/misra-gate.yml) artefact. |
| 2 | `>= 95%` statement + `>= 90%` MC/DC on slave protocol core. | [`coverage.yml`](../.github/workflows/coverage.yml) badge. |
| 3 | Zero new static-analysis warnings per PR. | [`static-analysis.yml`](../.github/workflows/static-analysis.yml). |
| 4 | Conventional Commits on every commit + PR title. | [`pr-title.yml`](../.github/workflows/pr-title.yml). |
| 5 | Every traced code change cites the controlling standard section. | [`.cursor/rules/always-cite-standards.mdc`](../.cursor/rules/always-cite-standards.mdc). |
| 6 | Every phase PR ships with a research note. | [`.cursor/rules/research-note-per-phase.mdc`](../.cursor/rules/research-note-per-phase.mdc). |
| 7 | Every dependency pinned exactly. | [`.cursor/rules/version-pinning.mdc`](../.cursor/rules/version-pinning.mdc). |
| 8 | No paid-license-required dependency. | [`.cursor/rules/free-tool-only.mdc`](../.cursor/rules/free-tool-only.mdc). |
| 9 | Secret-scan clean on every push. | [`secret-scan.yml`](../.github/workflows/secret-scan.yml). |
| 10 | SBOM 100% dependency coverage on every tag. | [`sbom.yml`](../.github/workflows/sbom.yml). |

The full scorecard lives in parent plan §12.

## 3. QA activities

### 3.1 Per-PR

- CI runs every check on every push (parent §6.7).
- At least one human reviewer + GitHub Copilot review.
- PR template enforces a checklist: tests added, MISRA clean, coverage
  delta, docs updated, ADR added if architectural, traceability matrix
  updated if requirement-touching.

### 3.2 Per-phase

- Phase Epic Issue tracks all child issues + PRs.
- Phase-Acceptance Issue closes only when:
  - Every child Issue + PR closes;
  - The demo recording is attached;
  - The research note records merged-on dates.

### 3.3 Per-release

[`docs/runbooks/release-process.md`](runbooks/release-process.md) §2
pre-flight checklist:

- `main` green on every required-status-check.
- Zero open `phase-acceptance` issues.
- Zero open `security`-labelled issues.
- Zero open MISRA mandatory/required deviations.
- Traceability CSV validates.
- Coverage thresholds met.
- Renovate / Dependabot PRs reviewed; no unresolved CVEs.

### 3.4 Quarterly

- Re-walk any runbook untouched for >180 days
  ([`docs/runbooks/README.md`](runbooks/README.md) §How runbooks are tested).
- Re-audit ADR statuses (proposed -> accepted, superseded by ADR-NNNN).

## 4. Audit reporting

QA non-conformances surface as:

- CI-detected: GitHub Actions failure on the PR.
- Reviewer-detected: PR comment with `type/quality` label.
- Periodic-audit: `type/quality` issue with severity.

Severity:

| Severity | Action | SLA |
| --- | --- | --- |
| Critical | Block release; hotfix branch. | <= 24 h |
| High | Block phase acceptance. | <= 1 week |
| Medium | Tracked at phase rollover. | next phase |
| Low | Backlog. | best-effort |

## 5. Standards compliance check

| Standard | How we comply | Evidence |
| --- | --- | --- |
| ECSS-Q-ST-80C | This SQAP + the SDP/SCMP/SVCP + the rules + the runbooks. | [`docs/research/phase-0-standards-matrix.csv`](research/phase-0-standards-matrix.csv) rows. |
| IEC 61508-3 | SIL 2 default with SIL 3 design feasibility (parent §4). | ADR-0003 + ADR-0005 + SVCP §2 + §3. |
| NPR 7150.2D | Class B targeting; documentation set per parent §4. | This SQAP + SVCP. |
| IACS UR E22 Rev.3 | Marine profile invariants + traceability rows + IEC 60945 reference. | [`marine-profile-invariants.mdc`](../.cursor/rules/marine-profile-invariants.mdc). |
| MISRA C:2023 | mandatory + required as hard gate; advisory documented. | [`misra-gate.yml`](../.github/workflows/misra-gate.yml) + [`docs/misra-deviations.md`](misra-deviations.md). |

## 6. Tool qualification posture

Per ADR-0008: Tethys is a license-free academic / demonstrator project.
The gaps (qualified compiler, certified MISRA checker, qualified
coverage tool) are explicitly named and waived for the public
demonstrator path. A real flight programme reading these documents
needs to overlay the qualified tool set; this SQAP names the gaps so
that overlay is auditable.

## 7. Open items

- F1: Add a `qa-review.yml` workflow (Phase 11) that scrapes the rule
  set + the CI gate matrix and emits a one-page QA summary PDF for the
  Release.
- F2: Quarterly QA review cadence - first review scheduled Phase 11
  close +90 days.

## Cross-references

- [SDP](sdp.md), [SAD](sad.md), [SVCP](svcp.md), [SCMP](scmp.md).
- Parent plan §6.5 (Cursor rules) + §6.6 (GitHub project management) +
  §6.7 (CI gate matrix) + §12 (scorecard).
- [`docs/runbooks/release-process.md`](runbooks/release-process.md).
- [`docs/runbooks/incident-and-defect.md`](runbooks/incident-and-defect.md).
- ECSS-Q-ST-80C §5.2.
- NASA-STD-8739.8 §3.2: https://standards.nasa.gov/standard/nasa/nasa-std-87398.
- DO-178C §11.6: https://www.rtca.org/products/do-178c.
- IEC 61508-3 §6.2.4: https://webstore.iec.ch/publication/5519.
