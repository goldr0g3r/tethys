# Runbook - Incident and defect handling

> Audience: any engineer triaging a bug, MISRA deviation request, or security
> incident.
> Goal: from "I found a problem" or "user reported X" to "issue filed,
> severity assigned, fix in flight, post-mortem complete". Wall-clock target:
> **30 minutes for triage**, **<24 hours for first response on Critical /
> Security**.
> Style: severity matrix first, then per-flow runbook.
>
> Implements parent plan §6.6 (issue + label system) and ADR-0003 MISRA
> deviation procedure. Companion to
> [`docs/runbooks/traceability-matrix-maintenance.md`](traceability-matrix-maintenance.md)
> for DEV row creation.

## Table of contents

1. [Severity matrix](#1-severity-matrix)
2. [Defect triage](#2-defect-triage)
3. [MISRA deviation lifecycle](#3-misra-deviation-lifecycle)
4. [Security incident handling](#4-security-incident-handling)
5. [Post-incident review](#5-post-incident-review)
6. [Hotfix release flow](#6-hotfix-release-flow)
7. [Templates](#7-templates)
8. [Cross-references](#8-cross-references)

---

## 1. Severity matrix

| Severity | Definition | Response SLA | Label |
| --- | --- | --- | --- |
| **Critical** | Data corruption, safety hazard, slave does not respond to CONNECT, master crashes the bench, security CVE exploit demonstrated | First response < 24 h; fix or workaround within 7 days; hotfix release | `prio/p0` + `severity/critical` |
| **High** | DAQ drops > 1% under nominal load, CAL writes silently rejected, A2L round-trip drift, MISRA mandatory rule violation discovered post-merge | First response < 72 h; fix in next minor release | `prio/p1` + `severity/high` |
| **Medium** | Documentation bug, UI cosmetic issue, deprecation warning in CI, performance regression < 10% | First response < 2 weeks; fix in next minor release | `prio/p2` + `severity/medium` |
| **Low** | Typo, nice-to-have, sub-millisecond latency wobble, suggestion | Best effort | `prio/p3` + `severity/low` |

Severity is set on the issue at triage time; it can be re-classified once
diagnosis is complete.

## 2. Defect triage

### 2.1 Receive the report

Bugs arrive via:

- GitHub issue (preferred; label `type/bug`).
- Direct message / email (the maintainer files the issue on the reporter's
  behalf).
- CI failure on `main` (the workflow auto-files an issue when a nightly job
  fails).

### 2.2 Reproduce

```bash
# Run the failing test in isolation
cd slave
cmake --build build --target test_<failing_module>
ctest --test-dir build -R test_<failing_module> -V
```

```powershell
cd slave
cmake --build build --target test_<failing_module>
ctest --test-dir build -R test_<failing_module> -V
```

Expected: reproduce locally; if it does not reproduce, mark the issue
`needs-info` and ask for the reporter's environment.

### 2.3 Diagnose

Tag the issue with one of:

- `area/master`, `area/slave`, `area/transport`, `area/profile-marine`,
  `area/profile-space`, `area/ci`, `area/docs`, `area/standards` (from
  `.cursor/rules/conventional-commits.mdc` scope list).
- The relevant `phase/N` label.
- The relevant `severity/*` label.

Comment on the issue with:

- Reproduction steps used.
- Root cause hypothesis.
- Proposed fix (or "needs ADR" if architectural).

### 2.4 Assign + size

```powershell
gh issue edit <NN> --add-assignee @goldr0g3r --milestone "Phase X"
gh project item-add <project-num> --owner goldr0g3r --url "https://github.com/goldr0g3r/tethys/issues/<NN>"
```

```bash
gh issue edit <NN> --add-assignee @goldr0g3r --milestone "Phase X"
gh project item-add <project-num> --owner goldr0g3r --url "https://github.com/goldr0g3r/tethys/issues/<NN>"
```

Set Status=`In progress`, Type=`Bug`.

### 2.5 Fix + verify

- Open a branch `fix/<scope>-<short>`.
- Add a regression test FIRST that fails.
- Write the fix; the regression test passes.
- PR per the standard flow (sub-plan optional for `severity/low` and
  `severity/medium`; required for `severity/high` and above).
- If the bug traces to a missed requirement, add the missing trace row per
  [`traceability-matrix-maintenance.md`](traceability-matrix-maintenance.md).

### 2.6 Close

Close the issue with `state_reason: completed`. Comment with the merge SHA
and the next release that contains the fix.

## 3. MISRA deviation lifecycle

Per [ADR-0003](../adr/0003-misra-c-2023-as-coding-gate.md) and
[`docs/coding-standard.md`](../coding-standard.md#10-misra-c-2023-deviation-procedure):

### 3.1 Mandatory rule violation

**Never accepted.** A mandatory rule violation blocks merge unconditionally.
The fix is always a code change. There is no deviation request flow for
mandatory rules.

### 3.2 Required or advisory rule violation

1. Author commits the violating code AND the deviation entry in
   `docs/misra-deviations.md` in the same PR (per coding-standard.md §10.4).
2. Author adds the per-line suppression in
   [`cppcheck-suppressions.txt`](../../cppcheck-suppressions.txt) referencing
   the deviation id.
3. `misra-gate.yml` runs; the workflow checks that every suppression has a
   matching entry in `docs/misra-deviations.md` and fails otherwise.
4. Reviewer marks the entry `approved` or `rejected` (rejection requires
   another rework cycle).
5. Author also adds a `kind=DEV` row to `docs/traceability.csv` per
   [`traceability-matrix-maintenance.md`](traceability-matrix-maintenance.md).
6. Merge.

### 3.3 Periodic re-review

Every 180 days the owner of each deviation entry re-reviews. Outcomes:

- **Still valid:** bump `Re-review by:` date.
- **No longer needed:** delete the entry + the suppression + the trace row in
  the same PR.
- **Worse:** elevate to ADR; open a refactor issue with `severity/high`.

`release.yml` opens a quarterly re-review issue automatically.

## 4. Security incident handling

### 4.1 Receive

Security reports arrive via:

- **Public GitHub issue** with label `security` (rare; reporter is usually
  asked to switch to private).
- **Private security advisory** (GitHub built-in; PREFERRED) at
  <https://github.com/goldr0g3r/tethys/security/advisories/new>.
- **Email** to the maintainer's published address (see `SECURITY.md`).

### 4.2 Triage (within 24 hours)

- Acknowledge the reporter.
- Assess severity using CVSS v3.1 calculator
  (<https://www.first.org/cvss/calculator/3.1>).
- If exploitable in default config: severity `critical`. Else `high`.
- Open private security advisory; invite the reporter as a collaborator.

### 4.3 Develop the fix in private

- Branch off in a private fork OR use a private security advisory branch.
- Tests stay private until disclosure.
- Code review happens in the security advisory; gate normal CI does not see
  the branch.

### 4.4 Coordinate disclosure

- Pick a public disclosure date (default: 90 days after triage, sooner if the
  vulnerability is widely known).
- Notify dependents (downstream forks, known users).
- File a CVE via GitHub's CVE-numbering integration on the security advisory.

### 4.5 Release the fix

Per [`release-process.md`](release-process.md) §9.4 - hotfix release with
the security note in the CHANGELOG. The CVE is published simultaneously.

### 4.6 Post-disclosure

- Public security advisory becomes visible.
- The security label is added to the public issue (if one existed).
- Post-mortem (see §5) is required for `critical` vulnerabilities.

## 5. Post-incident review

For every Critical-severity defect or security incident, within 7 days of fix
shipping:

### 5.1 Create the PIR document

```text
docs/incidents/<YYYY-MM-DD>-<short-slug>.md
```

### 5.2 PIR template

```markdown
# Post-incident review - <slug>

## Summary
<one-paragraph>

## Timeline (UTC)
- T+0:00  - first symptom observed
- T+0:15  - issue filed
- T+1:00  - root cause hypothesised
- T+...   - PR opened
- T+...   - PR merged
- T+...   - hotfix release shipped
- T+...   - users notified

## Root cause
<one or two paragraphs; cite the code/config involved>

## Impact
- Users affected: <N or estimate>
- Data loss: <yes/no/uncertain>
- Safety hazard: <yes/no>

## Detection
How was it detected? CI? user report? automated alert? Could detection have
been earlier?

## Resolution
- Workaround offered: <yes/no; details>
- Fix shipped in: vX.Y.Z

## Lessons learned
- What went well
- What went badly
- What we will change

## Action items
| # | Action | Owner | Due |
| - | --- | --- | --- |
| 1 | ... | ... | ... |
```

### 5.3 Publish

Commit to `main` via PR (not direct; PIR PRs get the same review discipline as
any docs change). Label `type/docs` + `area/docs` + `phase/<phase>`. Link from
`docs/runbooks/README.md` index.

## 6. Hotfix release flow

Hot-fix releases follow the [release-process.md](release-process.md) flow but
with the following overrides:

1. Branch off the **last release tag**, not `main` (`git checkout v0.4.7`).
2. Cherry-pick the fix commit(s) from `main`.
3. Bump PATCH only (`0.4.7` -> `0.4.8`).
4. Skip the CHANGELOG semantic-release step; write the CHANGELOG entry by
   hand referencing the CVE or PIR.
5. Tag + push as normal; `release.yml` runs.

## 7. Templates

### 7.1 Bug report issue (`.github/ISSUE_TEMPLATE/bug.md`)

```yaml
---
name: Bug report
about: Something is broken or wrong
labels: type/bug
---

## Environment
- OS:
- tethys-master version:
- tethys-slave commit:
- Transport (UDP / CAN / UART):
- Profile (marine / space):

## Reproduction steps
1. ...
2. ...
3. ...

## Expected behaviour

## Actual behaviour

## Logs / screenshots

## Suggested severity
- [ ] Critical
- [ ] High
- [ ] Medium
- [ ] Low
```

### 7.2 Security advisory comment template

```markdown
Thank you for the responsible disclosure.

We have:
- Acknowledged the report on <DATE>.
- Assigned CVSS v3.1 score: <BASE_SCORE> (<VECTOR>).
- Opened private fix branch: <link>.
- Target disclosure date: <DATE>.

You will be credited in the security advisory unless you prefer anonymity.
```

## 8. Cross-references

- Parent plan section 6.6 (issue + label system; severity / type / area
  labels).
- [ADR-0003 MISRA C:2023 as the coding gate](../adr/0003-misra-c-2023-as-coding-gate.md).
- [docs/coding-standard.md §10 MISRA deviation procedure](../coding-standard.md#10-misra-c-2023-deviation-procedure).
- [docs/misra-deviations.md](../misra-deviations.md) - the register.
- [Runbook: traceability-matrix-maintenance.md](traceability-matrix-maintenance.md)
  for DEV row creation.
- [Runbook: release-process.md](release-process.md) §9 - hotfix flow.
- [GitHub private security advisories docs](https://docs.github.com/en/code-security/security-advisories/working-with-repository-security-advisories/about-repository-security-advisories).
- [CVSS v3.1 calculator](https://www.first.org/cvss/calculator/3.1).
