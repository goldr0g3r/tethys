# Runbooks

Step-by-step recipes an external engineer can execute against the Tethys repository without further context. Each runbook is self-contained: prerequisites, commands for both PowerShell 7 and bash 5, expected outputs, rollback procedure.

| # | Runbook | Scope | Status |
| - | --- | --- | --- |
| 1 | [github-setup.md](github-setup.md) | Bootstrap GitHub surface — PAT, repo, branch protection, CODEOWNERS, Projects v2, milestones, labels, auto-add workflow, Phase-0 issues. | Drafted in PR-0a |
| 2 | release-process.md | Tag → `release.yml` → PyInstaller bundles + slave tarball + Docker image + SBOM + GitHub Release. | Planned for PR-6 |
| 3 | hardware-setup-stm32.md | Wiring + flashing + serial setup for STM32F4/F7 (marine) and STM32H7 (space) Nucleo boards. | Planned for PR-6 |
| 4 | hil-bench-setup.md | Closed-loop bench: master ↔ STM32 slave ↔ Simulink plant model. | Planned for PR-6 |
| 5 | traceability-matrix-maintenance.md | Editing `docs/traceability.csv`; regenerating `docs/standards-trace.md`; CI gate behaviour. | Planned for PR-6 |
| 6 | incident-and-defect.md | Defect triage, MISRA deviation request, security incident handling. | Planned for PR-6 |
| 7 | supply-chain-and-sbom.md | CycloneDX SBOM generation, Renovate/Dependabot review, PAT rotation, `pip-audit` + `osv-scanner` triage. | Planned for PR-6 |
| 8 | demo-recording.md | Recording the two end-to-end demos (marine common-rail + satellite reaction wheel) for the README + docs site. | Planned for PR-6 |

## How runbooks are written

- Audience: an external engineer, future you, or a Cursor / Copilot agent.
- Length budget: aim for ≤ 60 minutes wall-clock to execute end-to-end.
- Style: numbered sections, commands in both shells, expected output for every command, rollback table at the end.
- Cross-references: every runbook links to the parent plan section(s) and ADR(s) it implements.

## How runbooks are added

1. Open an Issue with label `type/docs` + `area/docs` + the relevant `phase/*`.
2. Draft a sub-plan via `CreatePlan` (per parent-plan §6.8).
3. Land the runbook and a research note (`docs/research/phase-<N>-<topic>.md`) in the same PR.
4. Add the row above and tick "Status" once merged.
