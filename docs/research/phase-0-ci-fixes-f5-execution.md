# Phase 0 - CI fixes (F5) execution (research note)

> Research note backing the `ci/p0-workflow-fixes-f5` PR
> (`ci: workflow job rename to canonical contexts + trufflehog --fail fix + dependency-review hardening + ci.yml YAML fix + branch protection re-tighten`).
> Parent plan: [`.cursor/plans/xcp_extreme-env_tool_14019278.plan.md`](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md) - resolves the F5 follow-up from PR #14 (the loosened branch-protection state).
> Companion: [`phase-0-ci-execution.md`](phase-0-ci-execution.md) (PR-4).

## Scope

Five tightly-related issues, addressed together because they all affect the
CI-context-to-branch-protection contract:

1. **trufflehog --fail double**: TruffleHog 3.x adds `--fail` by default;
   passing it via `extra_args: --only-verified --fail` causes `flag 'fail'
   cannot be repeated`. Remove the trailing `--fail`.
2. **ci.yml YAML parse error**: shell `run:` lines containing `|| echo "...:
   ..."` triggered `mapping values are not allowed here` in PyYAML (and in
   GitHub Actions' YAML parser - the workflow runs completed in 0 s with
   "workflow file issue"). Fix by quoting each `run:` value in single quotes
   AND removing the colon after `<tool>:` in the echo string. Applies to
   ci.yml + coverage.yml.
3. **dependency-review on private repos**: the action errors `Dependency
   review is not supported on this repository` when run on private repos
   without GHAS. Fix by switching the repo to public (already done) +
   adding a `if: github.event_name == 'pull_request'` guard + clearer comment.
4. **Workflow job ID rename**: parent §6.7 lists protection contexts
   `build`, `misra-gate`, `static-analysis`, `coverage`, `fuzz-smoke`,
   `secret-scan`, `dependency-review`, `a2l-roundtrip`, `pr-title`. The
   workflow files shipped with different job IDs (`master`, `cppcheck-misra`,
   `clang-tidy`, `slave-coverage`, `libfuzzer`, `trufflehog`, `review`,
   `roundtrip`, `conventional-commits`). Rename per the table below.
5. **Branch protection re-tighten**: with renamed contexts in place,
   re-apply the parent §6.7 required-status-checks list via `gh api PUT
   /repos/.../branches/main/protection`.

## Sources (retrieved 2026-05-15)

| ID | Title | URL | Used for |
| --- | --- | --- | --- |
| R1 | TruffleHog v3.83.7 docs | <https://github.com/trufflesecurity/trufflehog#octocat-trufflehog-github-action> | `--fail` is now default; remove from `extra_args`. |
| R2 | `dependency-review-action` v4.5.0 docs | <https://github.com/actions/dependency-review-action> | `if: github.event_name == 'pull_request'` guard; `comment-summary-in-pr: on-failure` semantics. |
| R3 | GitHub branch protection REST API | <https://docs.github.com/en/rest/branches/branch-protection> | `required_status_checks.contexts` and `required_status_checks.checks` payload shape. |
| R4 | GitHub Actions workflow syntax: `jobs.<job_id>.name` | <https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions#jobsjob_idname> | Job ID -> status-check context name mapping. |
| R5 | YAML 1.2 spec - flow scalar `:` handling | <https://yaml.org/spec/1.2.2/#733-plain-style> | Why `echo "foo: bar"` inside an unquoted `run:` value triggers ScannerError. |
| R6 | Parent plan §6.7 (CI/CD gate matrix) | [`.cursor/plans/xcp_extreme-env_tool_14019278.plan.md`](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md) | Authoritative list of required-status-check contexts. |
| R7 | PR #14 + PR #11 IR | [phase-0-ci-execution.md](phase-0-ci-execution.md) | Documented the loose-protection state F5 unwinds. |

## Workflow job ID rename map

| Workflow file | Before (job id) | After (job id) | After (display name) |
| --- | --- | --- | --- |
| `ci.yml` | `master`, `simulator`, `slave-posix`, `slave-stm32` | unchanged + new umbrella job `build` | `build (summary)` (needs all 4 above) |
| `misra-gate.yml` | `cppcheck-misra` | `misra-gate` | `misra-gate (cppcheck-misra)` |
| `static-analysis.yml` | `clang-tidy`, `gcc-fanalyzer`, `scan-build` | unchanged + new umbrella `static-analysis` | `static-analysis (summary)` (needs all 3) |
| `coverage.yml` | `slave-coverage`, `master-coverage` | unchanged + new umbrella `coverage` | `coverage (summary)` (needs both) |
| `fuzz-nightly.yml` | `libfuzzer` | `fuzz-smoke` | `fuzz-smoke (libfuzzer)` |
| `secret-scan.yml` | `trufflehog` | `secret-scan` | `secret-scan (trufflehog)` |
| `dependency-review.yml` | `review` | `dependency-review` | `dependency-review (licenses + CVEs)` |
| `a2l-roundtrip.yml` | `roundtrip` | `a2l-roundtrip` | `a2l-roundtrip (parse-emit-parse)` |
| `pr-title.yml` | `conventional-commits` | `pr-title` | `pr-title (conventional-commits)` |

The umbrella-job pattern (`build`, `static-analysis`, `coverage`) is the
standard GitHub Actions idiom for matrix workflows where branch protection
wants a single check name. Each umbrella `needs: [...]` all the matrix legs
and has an aggregator step that exits non-zero if any leg failed or was
cancelled.

## Branch protection apply

Final protection payload (after this PR merges):

```json
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "build",
      "misra-gate",
      "static-analysis",
      "coverage",
      "secret-scan",
      "dependency-review",
      "pr-title"
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": null,
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
```

Notes:

- `fuzz-smoke` not required (nightly only; per parent §6.7).
- `a2l-roundtrip` not required by default (path-conditional - only runs on
  A2L touches; making it required would block non-A2L PRs).
- `required_pull_request_reviews` stays `null` per single-maintainer mode;
  re-enable when a second reviewer joins.
- `required_signatures` stays disabled per the loose mode set in PR #14
  (re-enable when local GPG signing is back).

## Repo visibility flip

The repo was created as `private` (per the original `github-setup.md`
default). Per parent §6.1 + §11 ("public mono-repo on GitHub") + ADR-0008
(license-free toolchain), the repo is now **public**. Flipped via
`gh repo edit goldr0g3r/tethys --visibility public
--accept-visibility-change-consequences` as part of this PR.

Secondary security toggles enabled in the same step:

- `secret_scanning` -> enabled
- `secret_scanning_push_protection` -> enabled
- `dependabot_security_updates` -> enabled

Cost: 0 USD (GitHub free tier on public repos).

## Decisions

| Q | Resolution |
| - | - |
| Q1 Umbrella job pattern vs rename one matrix leg | Umbrella job. Lets branch protection require one canonical context per workflow without losing the matrix leg granularity in the UI. |
| Q2 trufflehog --fail | Remove from extra_args; let the action's default behaviour drive the failure exit code. |
| Q3 dependency-review on a fresh repo | Adding `if: github.event_name == 'pull_request'` is a soft guard. Combined with the repo-public flip, the action runs cleanly on PRs. |
| Q4 Re-enabling signed commits | Defer. Requires local GPG setup; project owner not currently GPG-signing. |
| Q5 Re-enabling required reviews | Defer. Single-maintainer mode; PR #14 documented the rationale. |
| Q6 fuzz-smoke as required context | Not required (nightly only). Listed as scaffolded in parent §6.7 status table. |
| Q7 a2l-roundtrip as required context | Not required (path-conditional). |
| Q8 PR title scope `layout` | Not in the allowed scope list; chore(layout) used `chore(scaffold)` instead. PR-1b retrospectively. |

## Open follow-ups

- **F1** - When Phase 1 lands real Python deps in master/pyproject.toml,
  dependency-review will start surfacing meaningful license-check output.
  Today there are no deps to review so the action runs and exits clean.
- **F2** - When Phase 2 lands first slave C code, the misra-gate.yml gate
  starts producing real violation reports.
- **F3** - When Phase 9 HIL lands real A2L fixtures under `master/tests/`,
  a2l-roundtrip stops being a no-op.
- **F4** - When Phase 1 wires Unity + Ceedling test runs into `ci.yml` (the
  `slave-posix` leg), CTest will run real tests and the umbrella `build`
  job will reflect real test status.
- **F5** - Add `fuzz-smoke` and `a2l-roundtrip` to required contexts once
  Phase 2 + Phase 3 land their first concrete fixtures.

## Implementation Reference

- PR: [#19 ci: workflow job rename to canonical contexts + trufflehog fix + ci.yml YAML fix + dependency-review hardening](https://github.com/goldr0g3r/tethys/pull/19)
- Merged on: 2026-05-15 (squash-merged via `gh pr merge 19 --squash --admin --delete-branch`).
- Merge SHA: see `main` log immediately after PR #19.
- Branch protection state after PR merge: **7 required contexts** -
  `build (summary)`, `misra-gate (cppcheck-misra)`,
  `static-analysis (summary)`, `coverage (summary)`,
  `secret-scan (trufflehog)`, `dependency-review (licenses + CVEs)`,
  `pr-title (conventional-commits)`. `enforce_admins=true`. Linear-history +
  conversation-resolution required. Force-push + deletion blocked.
- Repo visibility: **public** (flipped earlier in the same session via
  `gh repo edit --visibility public`).
- Secondary security toggles enabled in the same step: `secret_scanning`,
  `secret_scanning_push_protection`, `dependabot_security_updates`.
- CI green on the PR: 19/19 checks pass after the follow-up fix commit
  (`ci: fix master/windows ruff/mypy/pytest install + slave/posix dev build preset`)
  added `uv run --with <tool>` patterns for master/simulator/coverage.py
  jobs and added `buildPresets` + `testPresets` aliases to
  `slave/CMakePresets.json`.
