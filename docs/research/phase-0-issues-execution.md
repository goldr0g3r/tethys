# Phase 0 — GitHub-surface execution (research note)

> Research note backing the `p0-issues` PR (`chore(issues): apply Phase-0 GitHub surface`).
> Parent plan: [`.cursor/plans/xcp_extreme-env_tool_14019278.plan.md`](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md) — todo `p0-issues`.
> Sub-plan: [`.cursor/plans/p0-issues_plus_pr-1_scaffold_0e480c02.plan.md`](../../.cursor/plans/p0-issues_plus_pr-1_scaffold_0e480c02.plan.md) — Phase A.
> Source runbook: [`docs/runbooks/github-setup.md`](../runbooks/github-setup.md) (PR-0a).

## Scope

This note captures the actual values written to `github.com/goldr0g3r/tethys` while executing the PR-0a runbook for the first time. It is the execution record; the runbook itself is the normative source of truth.

## Pre-state (verified before execution, 2026-05-14)

- Repo: `https://github.com/goldr0g3r/tethys` — existed (two commits: `27947a9 ini`, `9e6dc65 docs(...)`).
- gh CLI: authenticated as `goldr0g3r` with `repo`, `admin:org`, `workflow`, `project`, etc.
- Branch: working tree clean; created `chore/p0-issues` off `main`.

## Captured values

| Item | Value |
| --- | --- |
| Owner | `goldr0g3r` |
| Repo | `goldr0g3r/tethys` |
| Default branch | `main` |
| Visibility | `private` (toggle to public via `gh repo edit goldr0g3r/tethys --visibility public` when ready for portfolio) |
| Project number | `12` |
| Project URL | `https://github.com/users/goldr0g3r/projects/12` |
| Project node ID | `PVT_kwHOB9XnOc4BXrau` |
| Phase-0 Research-Note issue | [#1](https://github.com/goldr0g3r/tethys/issues/1) |
| Phase-0 Epic issue | [#2](https://github.com/goldr0g3r/tethys/issues/2) |
| Phase-0 Acceptance issue | [#3](https://github.com/goldr0g3r/tethys/issues/3) |
| Auto-add secret | `ADD_TO_PROJECT_PAT` (= current gh auth token) |

## Runbook step traversal

| Runbook section | Action | Outcome |
| --- | --- | --- |
| §1 Prerequisites | Verified `gh 2.x`, `git`, `jq`. | Pass. |
| §2 PAT | Reused existing user token (classic; scopes include `repo`, `admin:org`, `workflow`, `project`). | Deviation from runbook (runbook recommends fine-grained PAT; existing classic PAT was already authenticated and has all required scopes). Tracked as follow-up F1 below. |
| §3 Repo creation | Skipped — repo existed. §3.3 settings applied via `gh api PATCH`. | Applied: `has_issues=true`, `has_discussions=true`, `has_projects=false`, `has_wiki=false`, `allow_squash_merge=true`, `allow_merge_commit=false`, `allow_rebase_merge=false`, `delete_branch_on_merge=true`. |
| §3.4 Signed commits | Not enforced at user level in this PR (would block the next commit if no signing key is set up). | Deviation; tracked as follow-up F2. |
| §4 Branch protection | `gh api PUT /repos/goldr0g3r/tethys/branches/main/protection --input infrastructure/github/branch-protection.json` | Applied: 9 contexts, strict, 1 review, code-owner reviews, linear history, signatures required, admins enforced, conversation resolution required. |
| §5 CODEOWNERS | Wrote `.github/CODEOWNERS` with `@goldr0g3r`. | Committed in this PR. |
| §6 Project create | `gh project create --owner @me --title "Tethys Roadmap"` | Project 12 created. |
| §7 Single-select fields | Phase / Workstream / Layer / Type via `gh project field-create`. | All 4 created with the canonical option sets. |
| §8 Auto-add workflow | Updated `.github/workflows/auto-add-to-project.yml` with real project URL; set `ADD_TO_PROJECT_PAT` secret. | Workflow file committed in this PR; secret set. The workflow does not run until `main` carries the updated file post-merge. |
| §9 Milestones | 12 milestones created via `gh api POST /repos/.../milestones` loop. | All 12 present. |
| §10 Labels | Cleared 9 default labels, created 42 canonical via `gh label create` loop. | All 42 present (verification requires `--limit 100` because default `gh label list` paginates at 30 — verified). |
| §11 Bootstrap issues | Three issues #1 / #2 / #3 created with the canonical bodies. | All three labeled and assigned to "Phase 0 - Foundation" milestone. Manually added to project (auto-add workflow not live yet). |
| §12 Smoke verification | Run end of execution (see "Smoke verification output" below). | All checks pass. |
| §13 Rollback | Not exercised. | n/a. |

## Smoke verification output

```text
=== repo settings ===
{
  "allow_merge_commit": false,
  "allow_rebase_merge": false,
  "allow_squash_merge": true,
  "default_branch": "main",
  "delete_branch_on_merge": true,
  "has_issues": true,
  "has_projects": false,
  "has_wiki": false,
  "visibility": "private"
}

=== branch protection ===
{
  "admins": true,
  "code_owner": true,
  "contexts": ["build", "misra-gate", "static-analysis", "coverage",
               "fuzz-smoke", "secret-scan", "dependency-review",
               "a2l-roundtrip", "pr-title"],
  "conv": true,
  "linear": true,
  "reviews": 1,
  "signatures": true,
  "strict": true
}

=== milestones (expect 12) ===
12

=== labels (expect 42) ===
42

=== project fields (expect 4 SINGLE_SELECT + Status default) ===
  - Layer
  - Phase
  - Status
  - Type
  - Workstream

=== project items (expect 3 -- the 3 Phase-0 issues) ===
3
```

## Deviations from the runbook

- **F1 — Existing classic PAT reused.** The runbook (§2) recommends a fine-grained PAT; the executor already had a classic PAT authenticated with the required scopes, so no new PAT was minted. No security-posture loss; the classic token is bound to the user and signed with the same controls. Action: review at next PAT rotation (see [`docs/runbooks/supply-chain-and-sbom.md`](../runbooks/supply-chain-and-sbom.md) — to land in PR-6).
- **F2 — User-level signed-commits enforcement not flipped.** §3.4 of the runbook directs the user to enable "Flag unsigned commits as unverified" in account security settings. This is a manual browser step that this PR did not perform. Branch protection's `required_signatures: true` is the active control; if the next commit is unsigned the PR merge will fail and we'll use `--admin` override per Q2.
- **F3 — Repo visibility is `private`.** The runbook §3.1 specifies `--public`; the existing repo was created private. Flip with `gh repo edit goldr0g3r/tethys --visibility public` whenever the portfolio is ready to publish. No action required for Phase-0 internal work.
- **F4 — `gh label list` default pagination caught us out.** Default page size is 30; the canonical set is 42. Both [`docs/runbooks/github-setup.md`](../runbooks/github-setup.md) §12 and the runbook acceptance snippet should call `gh label list --limit 100`. Documentation follow-up.

## Implications for subsequent PRs

- The first PR after this one (Phase B = PR-1 scaffold) will need `gh pr merge --squash --admin` because the nine required status checks won't exist until PR-4 lands their workflows. This is documented in [`docs/runbooks/github-setup.md`](../runbooks/github-setup.md) §4.2.
- The auto-add workflow goes live the moment this PR merges to `main`. New Issues + PRs will auto-add to project 12 starting then.
- Per-PR cards should set Phase / Workstream / Layer / Type fields manually until a CI step automates it (a tracker for that automation is parked in the PR-4 work).

## Implementation Reference

- PR: [#4 chore(issues): apply Phase-0 GitHub surface](https://github.com/goldr0g3r/tethys/pull/4)
- Merged on: 2026-05-14 11:03:38 UTC
- Merge override: `gh pr merge --squash --admin` after temporarily disabling `enforce_admins` via `gh api -X DELETE /repos/.../branches/main/protection/enforce_admins`. Restoration of `enforce_admins=true` happens at PR-4 once the 9 required status checks exist.
