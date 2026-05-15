# Runbooks

Step-by-step recipes an external engineer can execute against the Tethys repository without further context. Each runbook is self-contained: prerequisites, commands for both PowerShell 7 and bash 5, expected outputs, rollback procedure.

| # | Runbook | Scope | Status |
| - | --- | --- | --- |
| 1 | [github-setup.md](github-setup.md) | Bootstrap GitHub surface - PAT, repo, branch protection, CODEOWNERS, Projects v2, milestones, labels, auto-add workflow, Phase-0 issues. | Drafted in PR-0a |
| 2 | [release-process.md](release-process.md) | Tag `v0.x.y` -> `release.yml` -> PyInstaller bundles + slave tarball + Docker image + CycloneDX SBOM + GitHub Release + PyPI. | Drafted in PR-6 |
| 3 | [hardware-setup-stm32.md](hardware-setup-stm32.md) | Parts list + wiring + flashing + serial setup for STM32F4/F7 Nucleo (marine) and STM32H7 Nucleo (space) boards. | Drafted in PR-6 |
| 4 | [hil-bench-setup.md](hil-bench-setup.md) | Closed-loop bench: master <-> STM32 slave <-> Simulink plant model via MATLAB `py.` interface. | Drafted in PR-6 |
| 5 | [traceability-matrix-maintenance.md](traceability-matrix-maintenance.md) | Editing `docs/traceability.csv`; regenerating `docs/standards-trace.md`; CI gate behaviour. | Drafted in PR-6 |
| 6 | [incident-and-defect.md](incident-and-defect.md) | Defect triage, MISRA deviation request lifecycle, security incident handling, post-incident review template. | Drafted in PR-6 |
| 7 | [supply-chain-and-sbom.md](supply-chain-and-sbom.md) | CycloneDX SBOM generation, Renovate/Dependabot review, PAT rotation, `pip-audit` + `osv-scanner` CVE triage, license audit. | Drafted in PR-6 |
| 8 | [demo-recording.md](demo-recording.md) | Recording the two end-to-end demos (marine common-rail + satellite reaction wheel) for README + docs site + case-study PDF. | Drafted in PR-6 |

## How runbooks are written

- Audience: an external engineer, future you, or a Cursor / Copilot agent.
- Length budget: aim for <=60 minutes wall-clock to execute end-to-end.
- Style: numbered sections, commands in both shells, expected output for every command, rollback table at the end.
- Cross-references: every runbook links to the parent plan section(s) and ADR(s) it implements.

## How runbooks are tested

Because runbooks describe live system interactions (provisioning GitHub, flashing STM32 boards, cutting releases), they can't be unit-tested in CI. Validation instead:

1. **Initial smoke**: the author of the runbook executes every step on a clean machine and confirms the expected outputs match.
2. **Quarterly re-validation**: any runbook untouched for >180 days is re-walked by the project owner; failures result in an issue with `type/docs` + `severity/medium`.
3. **Onboarding-driven validation**: when a new contributor follows the runbook, their feedback is gold; capture it in a PR that fixes any drift.

## How runbooks are added

1. Open an Issue with label `type/docs` + `area/docs` + the relevant `phase/*`.
2. Draft a sub-plan via `CreatePlan` (per parent-plan §6.8).
3. Land the runbook and a research note (`docs/research/phase-<N>-<topic>.md`) in the same PR.
4. Add the row above and tick "Status" once merged.

## Cross-references

- Parent plan section 16 (full runbooks list).
- Parent plan section 6.8 (sub-plan + status-sync workflow).
- [`.cursor/rules/research-note-per-phase.mdc`](../../.cursor/rules/research-note-per-phase.mdc).
- [`.cursor/rules/always-cite-standards.mdc`](../../.cursor/rules/always-cite-standards.mdc).
