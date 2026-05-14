# Phase 0 — GitHub Setup (research note)

> Research note backing PR-0a `docs(runbook): add github setup runbook`.
> Parent plan: [`.cursor/plans/xcp_extreme-env_tool_14019278.plan.md`](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md) — todo `p0-github-setup-runbook`.
> Sub-plan: [`.cursor/plans/p0_github_setup_runbook_643e9e0e.plan.md`](../../.cursor/plans/p0_github_setup_runbook_643e9e0e.plan.md).

## Scope

This note backs the runbook [`docs/runbooks/github-setup.md`](../runbooks/github-setup.md). The runbook is the **normative** deliverable; this note is the **retrieval-dated, citation-bearing** evidence that the runbook was drafted against the current state of GitHub's surface on the dates listed below.

In scope for PR-0a:

- Fine-grained PAT scope set required to run every command in the runbook.
- Branch protection mechanism for `main` (classic vs Rulesets).
- Projects v2 board + custom single-select fields via `gh` and GraphQL.
- Auto-add workflow that places new Issues / PRs on the board.
- Milestone + label bootstrap recipe.
- Repository-ownership default (user vs org) for the runbook examples.

Out of scope (handled in a later PR):

- Actually executing the runbook to apply labels / milestones / protection / project — see `p0-issues`.
- Repository license decision — ADR-0008 in PR-3.
- Required-status-check **content** (i.e. what each workflow does) — PR-4 `p0-ci`.

## Sources (retrieved 2026-05-14)

All retrieval dates are within the 14-day freshness window required by [`research-note-per-phase.mdc`](../../.cursor/rules/research-note-per-phase.mdc) (rule lands in PR-2).

### S1 — Fine-grained PAT permissions matrix

- URL: <https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens?apiVersion=2026-03-10>
- Retrieved: 2026-05-14
- Quoted relevance: organisation-level `projectsV2` endpoints (POST drafts / fields / items / views and GET projects / fields / items) all require `Projects: write` or `Projects: read`; account-level equivalents apply to user-owned projects. Repository administration endpoints (branch protection, CODEOWNERS dismissal, etc.) require `Administration: write`.

### S2 — Endpoints available for fine-grained PATs

- URL: <https://docs.github.com/en/rest/authentication/endpoints-available-for-fine-grained-personal-access-tokens>
- Retrieved: 2026-05-14
- Quoted relevance: catalogues every endpoint the PR-0a runbook touches (repo create, branches/main/protection, milestones, labels, projectsV2, issues) and the permission each requires.

### S3 — About rulesets

- URL: <https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets>
- Retrieved: 2026-05-14
- Quoted relevance: rulesets supersede classic branch protection; up to 75 per repo; available on Team and Enterprise plans. Decision Q2 below: we are on a public Free repo with classic protection only — rulesets are a future migration tracked by a deferred ADR.

### S4 — Available rules for rulesets

- URL: <https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets>
- Retrieved: 2026-05-14
- Quoted relevance: enumerates the rule set (required signatures, required linear history, required pull request, required status checks, restrict deletions, restrict pushes that create matching branches). Used to validate that every control in parent-plan §6.1 has a one-to-one mapping when we migrate.

### S5 — About protected branches (classic)

- URL: <https://docs.github.com/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches>
- Retrieved: 2026-05-14
- Quoted relevance: documents every classic control we use in `branch-protection.json` — required reviews (count + dismiss-stale + require code-owner), required status checks (strict + contexts), require signed commits, require linear history, require conversation resolution, enforce for admins, restrict force pushes, restrict deletions.

### S6 — Using the API to manage Projects v2

- URL: <https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/using-the-api-to-manage-projects>
- Retrieved: 2026-05-14
- Quoted relevance: GraphQL query shape for both `user(login: $login).projectsV2` and `organization(login: $login).projectsV2`; node-id capture pattern (`user(login).projectV2(number).id`) reused in the runbook.

### S7 — `gh project field-create` reference

- URL: <https://cli.github.com/manual/gh_project_field-create>
- Retrieved: 2026-05-14
- Quoted relevance: exact flag list for SINGLE_SELECT field creation (`--data-type SINGLE_SELECT --single-select-options "<csv>"`) and `--owner @me` for user-owned projects.

### S8 — `actions/add-to-project`

- URL: <https://github.com/actions/add-to-project>
- Retrieved: 2026-05-14
- Quoted relevance: pinned `v1.0.2`, June 2024; requires `project-url` plus a `github-token` with `project:write` (we use a secret `ADD_TO_PROJECT_PAT`); supports `labeled` + `label-operator` filtering (`OR` / `AND` / `NOT`).

## Decisions log

### D1 — Label count is 42, not 52 (resolves Q1)

Parent-plan §6.6 prose says "52 total" but the enumeration sums to **42** (10 `type/*` + 12 `phase/*` + 4 `prio/*` + 8 `area/*` + 8 special). The `p0-issues` todo body also says 42. The runbook documents **42** as the canonical count.

Follow-up: open an issue against the parent plan to either (a) correct §6.6 prose to "42" or (b) extend the enumeration to reach 52. Tracked here, not in the runbook.

### D2 — Classic branch protection now, Rulesets later (resolves Q2)

Classic branch protection via a single `branch-protection.json` applied with `gh api -X PUT /repos/{owner}/{repo}/branches/main/protection` is:

- exactly what the parent plan implies (`gh api .../branches/main/protection`);
- compatible with the GitHub Free plan (Rulesets-as-replacement is Team/Enterprise-only per S3);
- one JSON file, one command, easy to diff / review.

Rulesets are strictly more expressive (S3, S4) and will be migrated to in a future ADR (provisionally ADR-0009) once (a) the parent plan licenses the gap and (b) the workflows from PR-4 are stable.

### D3 — User-owned repository (resolves Q3)

Repository is `github.com/<username>/tethys` (single-owner portfolio project, no org). Implications baked into the runbook:

- PAT scope set uses **Account → Projects: read+write**, not Organization → Projects.
- Project URL form is `https://github.com/users/<username>/projects/<n>`.
- `CODEOWNERS` uses `@<username>` directly — no team handles.
- `gh project create --owner @me` is the canonical owner flag.

### D4 — Real auto-add workflow file lands in PR-0a (resolves Q4)

Q4 was reconsidered: the file is included in PR-0a alongside the runbook. Rationale: the workflow is dependency-free of every other PR — it points at a project URL, uses a single secret, and is harmless before the project exists (action exits cleanly when the project isn't found). Including it now lets the user wire the secret + project URL once and forget.

Scope adjustment: deliverables for PR-0a are now (a) runbook, (b) index, (c) research note, **plus** (d) `.github/workflows/auto-add-to-project.yml`.

## Open follow-ups (post-PR-0a)

- **F1.** Parent-plan §6.6 prose typo "52 total" — file an issue once the repo is alive.
- **F2.** Migration ADR for classic protection → Rulesets — drafted at PR-3 or later, ADR-0009.
- **F3.** `actions/add-to-project` next-major (v2 RC observed but not pinned by upstream as of 2026-05-14) — re-evaluate at PR-4.
- **F4.** Secret rotation policy for `ADD_TO_PROJECT_PAT` — covered in `docs/runbooks/supply-chain-and-sbom.md` (PR-6).

## ADR citations (forward references)

The runbook itself cites the following ADRs that will land in PR-3 (`p0-docs`):

- ADR-0001 — XCP as a development-time protocol (informs why branch protection is dev-grade not flight-grade).
- ADR-0008 — License-free toolchain + repo license — informs `gh repo create --license` choice.

Provisional future ADR:

- ADR-0009 — Migrate `main` from classic branch protection to a Repository Ruleset (drafted post-PR-4 once status checks have stabilised).

## Implementation Reference

<!-- status-sync step (sub-plan todo `status-sync`) appends the merged PR URL here once PR-0a is merged. -->

- PR: *to be filled at merge*
- Merged on: *to be filled at merge*
