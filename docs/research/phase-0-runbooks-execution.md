# Phase 0 - Runbooks execution (research note)

> Research note backing the `p0-runbooks` PR
> (`docs(runbook): 7 runbooks per parent §16 + README index update`).
> Parent plan: [`.cursor/plans/xcp_extreme-env_tool_14019278.plan.md`](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md) - todo `p0-runbooks` (PR-6).
> Sub-plan: [`.cursor/plans/p0-runbooks_pr-6_b8e90d72.plan.md`](../../.cursor/plans/p0-runbooks_pr-6_b8e90d72.plan.md).

## Scope

Authors the 7 runbooks parent §16 enumerates plus the README index update so
the runbooks tree matches the parent-plan layout. The runbooks are intentionally
narrative + step-by-step; they exist so an external engineer (or future me) can
go from "I have nothing" to "I can run this" in <60 minutes per topic.

## Sources (retrieved 2026-05-15)

| ID | Title | URL | Used for |
| --- | --- | --- | --- |
| R1 | Parent plan section 16 | [`.cursor/plans/xcp_extreme-env_tool_14019278.plan.md`](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md) | Authoritative list of the 7 runbooks + their scope. |
| R2 | CycloneDX specification overview | <https://cyclonedx.org/specification/overview/> | `supply-chain-and-sbom.md` SBOM generation. |
| R3 | CycloneDX cli | <https://github.com/CycloneDX/cyclonedx-cli> | SBOM merge + validate commands. |
| R4 | cyclonedx-py (Python lib) | <https://github.com/CycloneDX/cyclonedx-python> | `uvx cyclonedx-py environment` invocation pattern. |
| R5 | pip-audit | <https://github.com/pypa/pip-audit> | CVE triage workflow in supply-chain runbook. |
| R6 | osv-scanner | <https://github.com/google/osv-scanner> | Same. |
| R7 | semantic-release docs | <https://semantic-release.gitbook.io/semantic-release/> | release-process runbook §4 CHANGELOG generation. |
| R8 | GitHub Container Registry | <https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry> | Docker image publishing in release-process. |
| R9 | PyPI publishing best practices | <https://packaging.python.org/en/latest/guides/distributing-packages-using-setuptools/> | Same. |
| R10 | ST RM0410 Reference Manual | <https://www.st.com/resource/en/reference_manual/rm0410-stm32f76xxx-and-stm32f77xxx-advanced-armbased-32bit-mcus-stmicroelectronics.pdf> | STM32F767ZI pinout for hardware-setup-stm32 §3.1. |
| R11 | ST RM0433 Reference Manual | <https://www.st.com/resource/en/reference_manual/rm0433-stm32h742-stm32h743753-and-stm32h750-value-line-advanced-armbased-32bit-mcus-stmicroelectronics.pdf> | STM32H753ZI pinout for hardware-setup-stm32 §4.1. |
| R12 | CANable 2.0 getting started | <https://canable.io/getting-started.html> | hardware-setup-stm32 §2.4 + §7.2 transport setup. |
| R13 | stlink-org/stlink | <https://github.com/stlink-org/stlink> | hardware-setup-stm32 §2.2 ST-Link tools install. |
| R14 | st-link udev rules (Linux) | inferred from R13 manual | hardware-setup-stm32 §2.3 permissions. |
| R15 | OBS Studio docs | <https://obsproject.com/wiki/> | demo-recording §5.1 OBS setup. |
| R16 | DaVinci Resolve free | <https://www.blackmagicdesign.com/products/davinciresolve/> | demo-recording §6.1 editing. |
| R17 | MATLAB py.* interface docs | <https://www.mathworks.com/help/matlab/call-python-libraries.html> | hil-bench-setup §3.2 MATLAB <-> Python bridge. |
| R18 | asammdf MDF4 toolkit | <https://github.com/danielhrisca/asammdf> | hil-bench-setup §8 + release-process §7.1 MDF4 artefact. |
| R19 | CVSS v3.1 calculator | <https://www.first.org/cvss/calculator/3.1> | incident-and-defect §4.2 severity assignment. |
| R20 | GitHub private security advisories | <https://docs.github.com/en/code-security/security-advisories/working-with-repository-security-advisories/about-repository-security-advisories> | incident-and-defect §4.3-4.4 disclosure flow. |
| R21 | GitHub Dependency Review API | <https://docs.github.com/en/code-security/supply-chain-security/understanding-your-software-supply-chain/dependency-review> | supply-chain-and-sbom CI gate behaviour. |
| R22 | Conventional Commits 1.0 | <https://www.conventionalcommits.org/en/v1.0.0/> | release-process §4 CHANGELOG generation depends on conventional subjects. |
| R23 | Parent plan §6.6 | [`.cursor/plans/xcp_extreme-env_tool_14019278.plan.md`](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md) | PAT rotation cadence in supply-chain runbook §5. |

## Deliverable inventory

| # | File | Lines (approx) |
| - | --- | --- |
| 1 | `docs/runbooks/release-process.md` | ~320 |
| 2 | `docs/runbooks/hardware-setup-stm32.md` | ~330 |
| 3 | `docs/runbooks/hil-bench-setup.md` | ~285 |
| 4 | `docs/runbooks/traceability-matrix-maintenance.md` | ~210 |
| 5 | `docs/runbooks/incident-and-defect.md` | ~290 |
| 6 | `docs/runbooks/supply-chain-and-sbom.md` | ~280 |
| 7 | `docs/runbooks/demo-recording.md` | ~240 |
| 8 | `docs/runbooks/README.md` | edit (flip 7 status rows, add "how runbooks are tested" subsection) |
| 9 | `docs/research/phase-0-runbooks-execution.md` | new (this file) |
| 10 | `.cursor/plans/xcp_extreme-env_tool_14019278.plan.md` | edit (status flip) |

Total: 7 new runbooks (~1955 lines) + index update + research note + 1-line
status sync.

## Format anchor

Every runbook follows the `github-setup.md` template from PR-0a:

- Plain Markdown heading + blockquote header with audience / goal / style.
- Numbered top-level sections (1, 2, ...).
- Code blocks tagged `powershell` AND `bash` when both shells are relevant
  (the runbook tells the reader which shell each tagged block targets).
- "Expected output" annotation under every command.
- Final section: "Cross-references" pointing at parent plan + ADRs + adjacent
  runbooks.

`release-process.md` and `hardware-setup-stm32.md` additionally have a
dedicated "Rollback and re-run" or "Troubleshooting" section because
operational runbooks need an unhappy-path option.

## Decisions

| Q | Resolution |
| - | - |
| Q1 PR scope | All 7 runbooks in one PR per parent §7. The runbooks are independent of each other (cross-link only); writing them together amortises the format discipline. |
| Q2 Hardware-specific commands without hardware in hand | Written from vendor docs (R10, R11, R12). Smoke verification deferred until project owner has hardware (tracked as follow-up F3). |
| Q3 Demo-recording runbook scope | Pre-Phase-9 scaffold: the actual videos land in Phase 11. The runbook documents the recording procedure so Phase 9 / Phase 11 work has a clear recipe. |
| Q4 PowerShell + bash duplication | Required for parent-plan §16 audience reach. The github-setup.md precedent has both for every command. |
| Q5 Length | Runbooks aim for <=60 minutes wall-clock to execute. Each runbook estimates its target in the header blockquote. |
| Q6 Cross-references | Every runbook ends with a §N "Cross-references" section linking parent plan §X.Y + relevant ADRs + adjacent runbooks. This is the discovery surface that lets a reader graph the runbook set quickly. |
| Q7 Incident runbook coverage | Includes defect triage + MISRA deviation lifecycle + security incident handling + post-incident review template. One runbook because they share the same severity / labelling vocabulary. |
| Q8 Supply chain runbook coverage | Includes SBOM regeneration + Renovate triage + CVE workflow + PAT rotation + license audit. One runbook because they all share the dependency-management mental model. |
| Q9 Templates | Bug report template + security advisory comment + PIR template are inline in the incident runbook §7 rather than under `.github/ISSUE_TEMPLATE/` (which already has the bug.md from PR-4). The runbook documents the template shape; the issue templates remain the executable surface. |
| Q10 Verification of SBOM tool versions | `cyclonedx-py` + `cyclonedx-cli` versions not pinned in this runbook because they live under `master/pyproject.toml` + Renovate cadence per `version-pinning.mdc`. Runbook references the tool name only. |

## Open follow-ups

- **F1** - Phase 11 Sphinx + MyST-Parser docs site renders these runbooks; cross-check link rendering at that time. Runbook prose uses standard Markdown so any Sphinx renderer should consume them cleanly.
- **F2** - Once Phase 11 ships `docs/case-study.pdf`, `demo-recording.md` §7.5 gets a concrete artefact link.
- **F3** - `hardware-setup-stm32.md` command verification deferred until the project owner has hardware in hand. Tracking issue opens at the start of Phase 7. Vendor-docs-derived commands are best-effort accurate but should be re-validated on real silicon.
- **F4** - The traceability matrix scripts (`scripts/trace_check.py`, `scripts/trace_orphans.py`) referenced from `traceability-matrix-maintenance.md` §4 + §6 are scaffolded in this runbook as inline code; full implementation lands in PR-10 `p10-verification`.
- **F5** - `release.yml` workflow currently scaffolded only; `release-process.md` §6 lists the expected jobs which the workflow content needs to match at PR-11.
- **F6** - `supply-chain-and-sbom.md` §5 PAT rotation calendar is a template; first row populated from PR-0a (`tethys-bootstrap-2026-05`). Project owner maintains.
- **F7** - `incident-and-defect.md` §4.5 hot-fix release flow references `release-process.md` §9.4; the latter is a brief paragraph because Phase 11 work formalises it.

## Implementation Reference

- PR: *to be filled at merge*
- Merged on: *to be filled at merge*
- Bootstrap window status: closed (PR-11 re-enabled `enforce_admins`).
- CI status on this PR: pre-existing scaffold-only workflow failures the same
  as PR-5 (PR #15) - `trufflehog --fail` flag double-up, `clang-tidy` +
  `gcc-fanalyzer` `cmake --preset=dev` mismatch, `dependency-review` waiting on
  GHAS / dependency-graph enabled on the public repo. F5 (workflow rename +
  branch-protection re-tighten) addresses them all in a follow-up PR in this
  same session.
