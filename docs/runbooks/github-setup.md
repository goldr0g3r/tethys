# Runbook — GitHub setup for the Tethys repository

> Audience: any engineer (or future me) bootstrapping the public Tethys GitHub surface from scratch.
> Goal: get from "I have a GitHub account" to "labels / milestones / Projects v2 / branch protection / Phase-0 issues are all in place" in **under 60 minutes**.
> Style: every command is given in **both PowerShell 7 and bash 5** form; every step states the expected output so failures surface immediately.
>
> This runbook is the implementation of parent-plan todo `p0-github-setup-runbook` ([PR-0a](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md)). The accompanying research note with retrieval-dated citations lives at [`docs/research/phase-0-github-setup.md`](../research/phase-0-github-setup.md).

## Conventions

- `<owner>` — your GitHub username (this runbook assumes a **user-owned** repo; see §15 for org variant).
- `<repo>` — repository name, default `tethys`.
- Code blocks tagged `powershell` are PowerShell 7 on Windows. Code blocks tagged `bash` are bash 5 on Linux / macOS / WSL.
- Where the two shells diverge, both are shown. Where they don't, only one is shown and a one-line note explains.
- All commands are **idempotent or have a documented teardown** — see §13.

## Table of contents

1. [Prerequisites](#1-prerequisites)
2. [Fine-grained personal access token](#2-fine-grained-personal-access-token)
3. [Repository creation](#3-repository-creation)
4. [Branch protection on `main`](#4-branch-protection-on-main)
5. [CODEOWNERS](#5-codeowners)
6. [Projects v2 board](#6-projects-v2-board)
7. [Four custom single-select fields](#7-four-custom-single-select-fields)
8. [Auto-add workflow](#8-auto-add-workflow)
9. [Milestones](#9-milestones)
10. [Label set](#10-label-set)
11. [Phase-0 bootstrap issues](#11-phase-0-bootstrap-issues)
12. [Smoke verification](#12-smoke-verification)
13. [Rollback and re-run](#13-rollback-and-re-run)
14. [Cross-references](#14-cross-references)
15. [Appendix A — org-owned variant](#15-appendix-a--org-owned-variant)

---

## 1. Prerequisites

Install / verify the following on the workstation that will execute the runbook:

| Tool | Minimum version | Why |
| --- | --- | --- |
| `gh` (GitHub CLI) | 2.50 | All API calls and `gh project` commands. |
| `git` | 2.40 | Signed commits + initial push. |
| `jq` | 1.6 | Parse API responses in smoke checks (§12). |
| GPG **or** SSH commit signing key | any | Required by branch protection (§4). |
| PowerShell 7 **or** bash 5 | latest | Either shell works for every step. |

Verify in your shell:

```powershell
gh --version ; git --version ; jq --version
```

```bash
gh --version && git --version && jq --version
```

Expected output: three version banners, no errors.

**Owner identity** — pick **one** of:

- User-owned: `OWNER=<your-username>`, project lives at `https://github.com/users/<your-username>/projects/<n>`. This is the default path through the runbook.
- Org-owned: `OWNER=<your-org>`, project lives at `https://github.com/orgs/<your-org>/projects/<n>`. See §15 for diffs.

Export the env vars used throughout:

```powershell
$env:GH_OWNER = "<your-username>"
$env:GH_REPO  = "tethys"
```

```bash
export GH_OWNER="<your-username>"
export GH_REPO="tethys"
```

---

## 2. Fine-grained personal access token

A fine-grained PAT scoped to the new repo + your user account is sufficient for every command in this runbook.

### 2.1 Create the PAT

Browser: <https://github.com/settings/tokens?type=beta>.

- **Token name:** `tethys-bootstrap-2026-05`
- **Expiration:** 90 days (rotate at each phase boundary; tracked in `docs/runbooks/supply-chain-and-sbom.md`)
- **Resource owner:** your user account
- **Repository access:** "Only select repositories" → select `<owner>/tethys` (you'll add the repo here after §3 — for now, choose "All repositories" then narrow once the repo exists)

**Repository permissions:**

| Permission | Access | Used for |
| --- | --- | --- |
| Administration | Read and write | Branch protection (§4), repo settings |
| Contents | Read and write | Initial push, CODEOWNERS file (§5) |
| Issues | Read and write | Bootstrap issues (§11), labels (§10) |
| Metadata | Read-only | Required for every fine-grained PAT |
| Pull requests | Read and write | PR-template uploads in later PRs |
| Workflows | Read and write | Auto-add workflow (§8) |

**Account permissions:**

| Permission | Access | Used for |
| --- | --- | --- |
| Projects | Read and write | Projects v2 board + fields (§§6–7) |

Click **Generate token**, copy once.

### 2.2 Store the token

```powershell
$env:GH_TOKEN = "github_pat_xxx..."
gh auth status
```

```bash
export GH_TOKEN="github_pat_xxx..."
gh auth status
```

Expected: `Logged in to github.com account <owner> (GH_TOKEN)`, token scopes reflect the matrix above.

> If you prefer `gh auth login` over `GH_TOKEN`, run `gh auth login --with-token` and paste; the rest of the runbook works either way.

---

## 3. Repository creation

### 3.1 Create the repo

```powershell
gh repo create "$env:GH_OWNER/$env:GH_REPO" `
  --public `
  --description "Tethys — portfolio-grade XCP master + slave for marine and space profiles" `
  --homepage "https://$($env:GH_OWNER).github.io/$($env:GH_REPO)" `
  --license MIT `
  --gitignore "" `
  --add-readme=false
```

```bash
gh repo create "$GH_OWNER/$GH_REPO" \
  --public \
  --description "Tethys — portfolio-grade XCP master + slave for marine and space profiles" \
  --homepage "https://${GH_OWNER}.github.io/${GH_REPO}" \
  --license MIT \
  --gitignore "" \
  --add-readme=false
```

Expected output: `https://github.com/<owner>/tethys`.

> License choice is **MIT** by default per ADR-0008 (lands in PR-3). Swap to `Apache-2.0` there if the ADR concludes differently.
>
> The runbook intentionally suppresses GitHub's auto-`README`, auto-`.gitignore`, and auto-`LICENSE`; these are landed by PR-1 / PR-3 / PR-5 so they go through review like everything else. The `--license MIT` flag above creates a `LICENSE` file directly — if you would rather defer that to PR-3, swap it for `--license=""`.

### 3.2 Push the existing local repo

```powershell
git remote add origin "https://github.com/$env:GH_OWNER/$env:GH_REPO.git"
git push -u origin main
```

```bash
git remote add origin "https://github.com/${GH_OWNER}/${GH_REPO}.git"
git push -u origin main
```

Expected: `Branch 'main' set up to track 'origin/main'`.

### 3.3 Configure repository features

```bash
gh api -X PATCH "/repos/${GH_OWNER}/${GH_REPO}" \
  -F has_issues=true \
  -F has_discussions=true \
  -F has_projects=false \
  -F has_wiki=false \
  -F allow_squash_merge=true \
  -F allow_merge_commit=false \
  -F allow_rebase_merge=false \
  -F allow_auto_merge=true \
  -F delete_branch_on_merge=true \
  -F squash_merge_commit_title="PR_TITLE" \
  -F squash_merge_commit_message="PR_BODY"
```

PowerShell: same call; backslashes become backticks.

Expected: a JSON dump of the repo settings with the flags above set.

> `has_projects=false` disables the **classic** Projects tab; **Projects v2** is unaffected and is wired up in §6.
> `allow_merge_commit=false` + `allow_rebase_merge=false` keeps history strictly squash-only, which combines with `required_linear_history` (§4) to give a clean linear log.

### 3.4 Require signed commits at the user / org level

Browser: <https://github.com/settings/security> → enable **Flag unsigned commits as unverified**. This pairs with branch protection's `required_signatures` (§4) — both layers are needed for a robust signing posture.

---

## 4. Branch protection on `main`

We use **classic branch protection** in PR-0a (decision D2 in the research note). A future ADR-0009 will migrate to Repository Rulesets once the workflows from PR-4 stabilise.

### 4.1 The `branch-protection.json` template

Save the following exactly as `infrastructure/github/branch-protection.json` when PR `p0-issues` creates the file. For PR-0a it lives **inline only**, here:

```json
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "build",
      "misra-gate",
      "static-analysis",
      "coverage",
      "fuzz-smoke",
      "secret-scan",
      "dependency-review",
      "a2l-roundtrip",
      "pr-title"
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": true,
    "require_last_push_approval": true
  },
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true,
  "lock_branch": false,
  "allow_fork_syncing": false,
  "required_signatures": true
}
```

Notes:

- The nine `contexts` are the workflow **job names** registered by PR-4. They are accepted by the API even before the workflows exist; they activate as soon as the workflow file lands on `main`.
- `strict: true` forces "branch must be up to date before merging" — combined with squash-only this gives a linear, rebased history.
- `require_last_push_approval: true` re-requires approval if the PR author force-pushes after approval (defence against last-minute substitution).
- `required_signatures: true` is the second half of §3.4.

### 4.2 Apply it

```bash
gh api -X PUT "/repos/${GH_OWNER}/${GH_REPO}/branches/main/protection" \
  -H "Accept: application/vnd.github+json" \
  --input branch-protection.json
```

```powershell
gh api -X PUT "/repos/$env:GH_OWNER/$env:GH_REPO/branches/main/protection" `
  -H "Accept: application/vnd.github+json" `
  --input branch-protection.json
```

Expected output: JSON echo of the applied protection rules.

> Until PR-4 lands the workflows, every required check will report as "Expected — Waiting for status to be reported". This is fine — branch protection blocks merging, which is the desired behaviour during bootstrap. To unblock yourself for the first PR after PR-0a, temporarily merge with the `--admin` flag (`gh pr merge --squash --admin`) and document the override in the PR body.

---

## 5. CODEOWNERS

The `CODEOWNERS` file lands in `p0-issues` at `.github/CODEOWNERS`. The template — single-owner, per-directory — is:

```text
# CODEOWNERS — Tethys
# Syntax: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners

# Default — every path requires owner approval unless overridden below.
*                       @<owner>

# Slave (embedded C library)
/slave/                 @<owner>
/slave/include/         @<owner>
/slave/src/core/        @<owner>
/slave/src/transport/   @<owner>
/slave/src/platform/    @<owner>
/slave/profiles/        @<owner>
/slave/tests/           @<owner>
/slave/fuzz/            @<owner>

# Master (Python PC tool)
/master/                @<owner>

# Simulator + HIL
/simulator/             @<owner>
/hil/                   @<owner>

# Documentation
/docs/                  @<owner>
/docs/adr/              @<owner>
/docs/runbooks/         @<owner>
/docs/traceability.csv  @<owner>
/docs/misra-deviations.md @<owner>

# CI + repo plumbing
/.github/               @<owner>
/.cursor/               @<owner>
/cmake/                 @<owner>
/infrastructure/        @<owner>
```

Replace `@<owner>` with your username before committing. Add additional collaborators by listing more handles space-separated on the relevant line.

> Per-directory ownership exists from day 1 because `require_code_owner_reviews=true` (§4) blocks merges that touch a path lacking an owner. Add the line **before** you make the first PR touching that path.

---

## 6. Projects v2 board

### 6.1 Create the board

```bash
gh project create --owner "@me" --title "Tethys Roadmap" --format json
```

Expected output: JSON with `number`, `id`, `url`, `title`. Capture `number` into `$PROJECT_NUMBER`.

```bash
PROJECT_NUMBER=$(gh project create --owner @me --title "Tethys Roadmap" --format json | jq -r '.number')
echo "Project number: $PROJECT_NUMBER"
```

```powershell
$PROJECT_NUMBER = (gh project create --owner "@me" --title "Tethys Roadmap" --format json | ConvertFrom-Json).number
Write-Host "Project number: $PROJECT_NUMBER"
```

### 6.2 Capture the GraphQL node id

The node id is needed by `actions/add-to-project` and for any subsequent GraphQL mutation.

```bash
PROJECT_NODE_ID=$(gh api graphql -f query='
  query($login: String!, $number: Int!) {
    user(login: $login) {
      projectV2(number: $number) { id }
    }
  }' -F login="${GH_OWNER}" -F number=${PROJECT_NUMBER} | jq -r '.data.user.projectV2.id')
echo "Project node id: $PROJECT_NODE_ID"
```

```powershell
$query = @'
query($login: String!, $number: Int!) {
  user(login: $login) {
    projectV2(number: $number) { id }
  }
}
'@
$PROJECT_NODE_ID = (gh api graphql -f query=$query -F login=$env:GH_OWNER -F number=$PROJECT_NUMBER | ConvertFrom-Json).data.user.projectV2.id
Write-Host "Project node id: $PROJECT_NODE_ID"
```

Expected: a string like `PVT_kwHOAA...`.

### 6.3 Set the project URL env var

```bash
export PROJECT_URL="https://github.com/users/${GH_OWNER}/projects/${PROJECT_NUMBER}"
```

```powershell
$env:PROJECT_URL = "https://github.com/users/$env:GH_OWNER/projects/$PROJECT_NUMBER"
```

This is the value the auto-add workflow consumes in §8.

---

## 7. Four custom single-select fields

Parent-plan §6.6 mandates four custom fields. Each is a `SINGLE_SELECT` with an exact option set.

### 7.1 `Phase`

```bash
gh project field-create $PROJECT_NUMBER \
  --owner "@me" \
  --name "Phase" \
  --data-type SINGLE_SELECT \
  --single-select-options "Phase 0,Phase 1,Phase 2,Phase 3,Phase 4,Phase 5,Phase 6,Phase 7,Phase 8,Phase 9,Phase 10,Phase 11"
```

### 7.2 `Workstream`

```bash
gh project field-create $PROJECT_NUMBER \
  --owner "@me" \
  --name "Workstream" \
  --data-type SINGLE_SELECT \
  --single-select-options "Master,Slave,Profile,Standards,Docs,CI"
```

### 7.3 `Layer`

```bash
gh project field-create $PROJECT_NUMBER \
  --owner "@me" \
  --name "Layer" \
  --data-type SINGLE_SELECT \
  --single-select-options "Protocol,Transport,Platform,GUI,Tests,Docs"
```

### 7.4 `Type`

```bash
gh project field-create $PROJECT_NUMBER \
  --owner "@me" \
  --name "Type" \
  --data-type SINGLE_SELECT \
  --single-select-options "Feature,Bug,Chore,Research,Standards-trace"
```

PowerShell: identical commands; line-continuation is backtick instead of backslash.

Expected output for each: JSON echo of the new field with its `id` and `options[]`.

### 7.5 Verify all four

```bash
gh project field-list $PROJECT_NUMBER --owner "@me" --format json \
  | jq '.fields[] | select(.dataType=="SINGLE_SELECT") | {name, options: [.options[].name]}'
```

Expected: four objects matching §§7.1–7.4 exactly.

---

## 8. Auto-add workflow

Every new Issue and PR is auto-added to the Projects v2 board by `actions/add-to-project@v1.0.2`.

### 8.1 Configure the secret

The workflow needs a PAT with `Projects: read+write` on your account. Reuse the §2 token, **or** mint a tighter-scoped token just for this workflow.

```bash
gh secret set ADD_TO_PROJECT_PAT --repo "${GH_OWNER}/${GH_REPO}" --body "$GH_TOKEN"
```

```powershell
gh secret set ADD_TO_PROJECT_PAT --repo "$env:GH_OWNER/$env:GH_REPO" --body $env:GH_TOKEN
```

Expected: `✓ Set Actions secret ADD_TO_PROJECT_PAT for <owner>/<repo>`.

### 8.2 The workflow file

The file lives at `.github/workflows/auto-add-to-project.yml` and lands as part of PR-0a (decision D4 in the research note). Its contents:

```yaml
name: auto-add-to-project

on:
  issues:
    types: [opened, reopened, transferred]
  pull_request_target:
    types: [opened, reopened, ready_for_review]

permissions:
  contents: read

jobs:
  add-to-project:
    name: Add to Tethys Roadmap
    runs-on: ubuntu-latest
    steps:
      - name: Add new item to project
        uses: actions/add-to-project@244f685bbc3b7adfa8466e08b698b5577571133e # v1.0.2
        with:
          project-url: https://github.com/users/<owner>/projects/<number>
          github-token: ${{ secrets.ADD_TO_PROJECT_PAT }}
```

Replace `<owner>` and `<number>` with the values from §6 **before** committing the file. If `$PROJECT_URL` from §6.3 isn't ready yet (you ran the runbook out of order), the workflow is harmless until the URL is real — it will fail gracefully on every event.

The action is pinned by commit SHA (`244f685bbc3b7adfa8466e08b698b5577571133e`), not by tag, per [GitHub's hardening guidance for third-party actions](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions#using-third-party-actions). The trailing `# v1.0.2` is the human-readable version; Renovate / Dependabot will keep both in lockstep when the action is bumped.

### 8.3 Verify the workflow

After the workflow file is on `main`:

```bash
gh workflow list --repo "${GH_OWNER}/${GH_REPO}"
gh workflow view "auto-add-to-project.yml" --repo "${GH_OWNER}/${GH_REPO}"
```

Expected: one workflow named `auto-add-to-project`, state `active`.

Open a throwaway Issue to smoke-test:

```bash
ISSUE_URL=$(gh issue create --repo "${GH_OWNER}/${GH_REPO}" \
  --title "test: auto-add smoke" --body "Delete me." --label "type/chore" \
  | tail -n 1)
echo "$ISSUE_URL"
```

Wait ~10 seconds, then check the project:

```bash
gh project item-list $PROJECT_NUMBER --owner "@me" --format json | jq '.items[].content.title'
```

Expected: `"test: auto-add smoke"` appears. Close + delete the test issue after verification.

---

## 9. Milestones

Twelve milestones, one per phase. Titles match the parent-plan headings verbatim.

### 9.1 Create them

```bash
declare -a MILESTONES=(
  "Phase 0 — Foundation|Scaffold, rules, ADRs, CI, coding standards, runbooks, GitHub setup. Parent-plan todos: p0-scaffold .. p0-issues."
  "Phase 1 — Shared infrastructure|Master pyproject + slave CMake foundation + Unity/Ceedling baseline + A2L fixtures + posix-sim entry point. Acceptance: hello-world XCP CONNECT/DISCONNECT over UDP loopback."
  "Phase 2 — XCP protocol core|Command dispatcher, CTO/DTO framing, time-stamping, A2L MEASUREMENT/CHARACTERISTIC parser. Acceptance: 100% statement + ≥95% MC/DC on dispatcher; differential test against pyxcp."
  "Phase 3 — DAQ + STIM|ODT engine, DAQ list config, event channel binding, optional PTP. MDF4 logger + pyqtgraph plots. Acceptance: 1 kHz DAQ on simulator, zero loss for 60 minutes."
  "Phase 4 — CAL + PAG|Online calibration write, CAL page switching, CRC validation, A2L-driven limit-checks, persistent CAL via flash mirror. Acceptance: round-trip calibrate-restart-verify."
  "Phase 5 — Transport pluggability|Freeze TransportPort interface; UDP/TCP, SocketCAN, UART/SxI. One conformance suite across all transports."
  "Phase 6 — Master GUI|PySide6: connection wizard, A2L tree, pyqtgraph plots, calibration editor, profile selector, MDF4 record/playback, diagnostics pane."
  "Phase 7 — Marine profile on STM32F4/F7|BSP, FreeRTOS, CAN-FD + Ethernet (W5500), marine.cmake, synthetic engine workload at 1 kHz DAQ. Acceptance: 24h soak."
  "Phase 8 — Space profile on STM32H7|EDAC wrap on CAL pages, watchdog kick in DAQ tick, AES-128 seed-and-key, authenticated service-mode, fault-injection bench. Acceptance: MC/DC ≥95% on protocol core."
  "Phase 9 — HIL + MATLAB|Closed-loop bench with Simulink plant. Two demos: marine common-rail injector and satellite reaction-wheel."
  "Phase 10 — Verification pack|Generated traceability matrix, fuzz corpora, robustness suite, coverage + MISRA reports."
  "Phase 11 — v1.0 release + portfolio|PyInstaller bundles, slave tarballs, Docker image, pip release, GitHub Release + SBOM, Sphinx docs site, demo videos, case-study PDF."
)

for entry in "${MILESTONES[@]}"; do
  title="${entry%%|*}"
  desc="${entry##*|}"
  gh api -X POST "/repos/${GH_OWNER}/${GH_REPO}/milestones" \
    -f title="$title" \
    -f state=open \
    -f description="$desc"
done
```

PowerShell equivalent:

```powershell
$milestones = @(
  @{ title = "Phase 0 — Foundation"; desc = "Scaffold, rules, ADRs, CI, coding standards, runbooks, GitHub setup. Parent-plan todos: p0-scaffold .. p0-issues." }
  @{ title = "Phase 1 — Shared infrastructure"; desc = "Master pyproject + slave CMake foundation + Unity/Ceedling baseline + A2L fixtures + posix-sim entry point. Acceptance: hello-world XCP CONNECT/DISCONNECT over UDP loopback." }
  @{ title = "Phase 2 — XCP protocol core"; desc = "Command dispatcher, CTO/DTO framing, time-stamping, A2L MEASUREMENT/CHARACTERISTIC parser. Acceptance: 100% statement + >=95% MC/DC on dispatcher; differential test against pyxcp." }
  @{ title = "Phase 3 — DAQ + STIM"; desc = "ODT engine, DAQ list config, event channel binding, optional PTP. MDF4 logger + pyqtgraph plots. Acceptance: 1 kHz DAQ on simulator, zero loss for 60 minutes." }
  @{ title = "Phase 4 — CAL + PAG"; desc = "Online calibration write, CAL page switching, CRC validation, A2L-driven limit-checks, persistent CAL via flash mirror. Acceptance: round-trip calibrate-restart-verify." }
  @{ title = "Phase 5 — Transport pluggability"; desc = "Freeze TransportPort interface; UDP/TCP, SocketCAN, UART/SxI. One conformance suite across all transports." }
  @{ title = "Phase 6 — Master GUI"; desc = "PySide6: connection wizard, A2L tree, pyqtgraph plots, calibration editor, profile selector, MDF4 record/playback, diagnostics pane." }
  @{ title = "Phase 7 — Marine profile on STM32F4/F7"; desc = "BSP, FreeRTOS, CAN-FD + Ethernet (W5500), marine.cmake, synthetic engine workload at 1 kHz DAQ. Acceptance: 24h soak." }
  @{ title = "Phase 8 — Space profile on STM32H7"; desc = "EDAC wrap on CAL pages, watchdog kick in DAQ tick, AES-128 seed-and-key, authenticated service-mode, fault-injection bench. Acceptance: MC/DC >=95% on protocol core." }
  @{ title = "Phase 9 — HIL + MATLAB"; desc = "Closed-loop bench with Simulink plant. Two demos: marine common-rail injector and satellite reaction-wheel." }
  @{ title = "Phase 10 — Verification pack"; desc = "Generated traceability matrix, fuzz corpora, robustness suite, coverage + MISRA reports." }
  @{ title = "Phase 11 — v1.0 release + portfolio"; desc = "PyInstaller bundles, slave tarballs, Docker image, pip release, GitHub Release + SBOM, Sphinx docs site, demo videos, case-study PDF." }
)

foreach ($m in $milestones) {
  gh api -X POST "/repos/$env:GH_OWNER/$env:GH_REPO/milestones" `
    -f title=$m.title `
    -f state=open `
    -f description=$m.desc
}
```

### 9.2 Verify

```bash
gh api "/repos/${GH_OWNER}/${GH_REPO}/milestones?state=open" | jq 'length'
```

Expected: `12`.

---

## 10. Label set

The canonical 42-label set (decision D1 in the research note). Groups: 10 `type/*`, 12 `phase/*`, 4 `prio/*`, 8 `area/*`, 8 special.

### 10.1 `labels.json`

Save this as `infrastructure/github/labels.json` (file lands in `p0-issues`; included inline here):

```json
[
  { "name": "type/feat",       "color": "0E8A16", "description": "New feature" },
  { "name": "type/fix",        "color": "D73A4A", "description": "Bug fix" },
  { "name": "type/chore",      "color": "CFD3D7", "description": "Maintenance / housekeeping" },
  { "name": "type/docs",       "color": "0075CA", "description": "Documentation only" },
  { "name": "type/ci",         "color": "5319E7", "description": "CI / build pipeline" },
  { "name": "type/refactor",   "color": "FBCA04", "description": "Refactor without behaviour change" },
  { "name": "type/test",       "color": "1D76DB", "description": "Tests added or changed" },
  { "name": "type/perf",       "color": "ED7615", "description": "Performance improvement" },
  { "name": "type/build",      "color": "8B572A", "description": "Build system / toolchain" },
  { "name": "type/revert",     "color": "B60205", "description": "Revert a prior commit" },

  { "name": "phase/0",         "color": "E1E4E8", "description": "Phase 0 — Foundation" },
  { "name": "phase/1",         "color": "D1D5DA", "description": "Phase 1 — Shared infrastructure" },
  { "name": "phase/2",         "color": "C6CBD1", "description": "Phase 2 — XCP protocol core" },
  { "name": "phase/3",         "color": "AFB8C1", "description": "Phase 3 — DAQ + STIM" },
  { "name": "phase/4",         "color": "959DA5", "description": "Phase 4 — CAL + PAG" },
  { "name": "phase/5",         "color": "6A737D", "description": "Phase 5 — Transport pluggability" },
  { "name": "phase/6",         "color": "586069", "description": "Phase 6 — Master GUI" },
  { "name": "phase/7",         "color": "444D56", "description": "Phase 7 — Marine on STM32F4/F7" },
  { "name": "phase/8",         "color": "2F363D", "description": "Phase 8 — Space on STM32H7" },
  { "name": "phase/9",         "color": "24292E", "description": "Phase 9 — HIL + MATLAB" },
  { "name": "phase/10",        "color": "1B1F23", "description": "Phase 10 — Verification pack" },
  { "name": "phase/11",        "color": "0D1117", "description": "Phase 11 — v1.0 release" },

  { "name": "prio/p0",         "color": "B60205", "description": "P0 — blocks current phase" },
  { "name": "prio/p1",         "color": "D93F0B", "description": "P1 — high priority" },
  { "name": "prio/p2",         "color": "FBCA04", "description": "P2 — medium priority" },
  { "name": "prio/p3",         "color": "0E8A16", "description": "P3 — nice to have" },

  { "name": "area/master",         "color": "1D76DB", "description": "PC master tool (Python)" },
  { "name": "area/slave",          "color": "5319E7", "description": "Embedded slave library (C)" },
  { "name": "area/transport",      "color": "0075CA", "description": "Transport abstraction layer" },
  { "name": "area/profile-marine", "color": "006B75", "description": "Marine profile and targets" },
  { "name": "area/profile-space",  "color": "0E2F44", "description": "Space profile and targets" },
  { "name": "area/docs",           "color": "C5DEF5", "description": "Documentation surface" },
  { "name": "area/ci",             "color": "BFD4F2", "description": "CI / build / release plumbing" },
  { "name": "area/standards",      "color": "FEF2C0", "description": "Standards / traceability / MISRA" },

  { "name": "epic",                  "color": "3E4B9E", "description": "Long-running umbrella issue" },
  { "name": "phase-acceptance",      "color": "0E8A16", "description": "Phase-acceptance issue — closes when demo recorded" },
  { "name": "research-note",         "color": "8250DF", "description": "Tracks the per-phase research note" },
  { "name": "security",              "color": "B60205", "description": "Security-sensitive change" },
  { "name": "blocked",               "color": "E11D21", "description": "Blocked by another item" },
  { "name": "good-first-issue",      "color": "7057FF", "description": "Approachable for new contributors" },
  { "name": "help-wanted",           "color": "008672", "description": "Extra eyes wanted" },
  { "name": "standards-deviation",   "color": "FBCA04", "description": "Documented MISRA / standards deviation" }
]
```

Counts: 10 + 12 + 4 + 8 + 8 = **42**.

### 10.2 Apply them

GitHub's default labels (`bug`, `enhancement`, `documentation`, etc.) overlap with `type/*`. Clear them first, then apply the canonical set.

```bash
gh label list --repo "${GH_OWNER}/${GH_REPO}" --json name --jq '.[].name' \
  | xargs -I {} gh label delete {} --repo "${GH_OWNER}/${GH_REPO}" --yes

jq -c '.[]' infrastructure/github/labels.json | while read -r row; do
  name=$(echo "$row" | jq -r '.name')
  color=$(echo "$row" | jq -r '.color')
  desc=$(echo "$row" | jq -r '.description')
  gh label create "$name" \
    --repo "${GH_OWNER}/${GH_REPO}" \
    --color "$color" \
    --description "$desc"
done
```

```powershell
gh label list --repo "$env:GH_OWNER/$env:GH_REPO" --json name --jq '.[].name' |
  ForEach-Object { gh label delete $_ --repo "$env:GH_OWNER/$env:GH_REPO" --yes }

$labels = Get-Content -Raw infrastructure/github/labels.json | ConvertFrom-Json
foreach ($lbl in $labels) {
  gh label create $lbl.name `
    --repo "$env:GH_OWNER/$env:GH_REPO" `
    --color $lbl.color `
    --description $lbl.description
}
```

### 10.3 Verify

```bash
gh label list --repo "${GH_OWNER}/${GH_REPO}" --json name --jq 'length'
```

Expected: `42`.

---

## 11. Phase-0 bootstrap issues

Three issues per phase per parent-plan §6.6: one Research-Note, one Epic, one Phase-Acceptance. We file the **Phase-0** set here. (`p0-issues` will file the rest.)

### 11.1 Phase-0 Research-Note

```bash
gh issue create --repo "${GH_OWNER}/${GH_REPO}" \
  --title "Phase 0 — research note" \
  --label "research-note,phase/0,type/docs,area/docs,prio/p0" \
  --milestone "Phase 0 — Foundation" \
  --body "$(cat <<'EOF'
Tracks the per-phase research note for Phase 0.

- Sub-plan: .cursor/plans/p0_github_setup_runbook_643e9e0e.plan.md (and one per remaining Phase-0 todo as they are drafted)
- Research note: docs/research/phase-0-github-setup.md
- Scope: parent-plan §7 (PR-0a .. PR-6 + p0-issues)

## Sources

See docs/research/phase-0-github-setup.md for the full retrieval-dated source list.

## Decisions

| Q | Resolution |
| - | - |
| Q1 — label count | 42 (D1) |
| Q2 — branch protection | Classic now, Rulesets later (D2) |
| Q3 — repo ownership | User-owned (D3) |
| Q4 — auto-add workflow file | Included in PR-0a (D4) |

## PR references

- PR-0a docs(runbook): _filled at merge_
EOF
)"
```

### 11.2 Phase-0 Epic

```bash
gh issue create --repo "${GH_OWNER}/${GH_REPO}" \
  --title "Epic — Phase 0: Foundation" \
  --label "epic,phase/0,type/chore,prio/p0" \
  --milestone "Phase 0 — Foundation" \
  --body "$(cat <<'EOF'
Umbrella issue for Phase 0. Child PRs:

- [ ] PR-0a docs(runbook): github setup runbook
- [ ] PR-1 chore(scaffold): monorepo bootstrap (uv init, cmake-init, ceedling new)
- [ ] PR-2 chore(rules): .cursor/rules/*.mdc + AGENTS.md + Copilot mirror
- [ ] PR-3 docs(architecture): README + system-context + ADR-0001..ADR-0008
- [ ] PR-4 ci: 11 GitHub Actions workflows + templates + CODEOWNERS
- [ ] PR-5 chore(quality): .clang-format / .clang-tidy / cppcheck.cfg / pre-commit
- [ ] PR-6 docs(runbook): remaining runbooks (release-process, hil-bench-setup, etc.)
- [ ] p0-issues parallel: apply labels + milestones + branch protection + Projects v2 + CODEOWNERS

Closes when every child PR is merged AND the Phase-0 acceptance issue is closed.

## Parent plan

.cursor/plans/xcp_extreme-env_tool_14019278.plan.md
EOF
)"
```

### 11.3 Phase-0 Acceptance

```bash
gh issue create --repo "${GH_OWNER}/${GH_REPO}" \
  --title "Phase 0 acceptance" \
  --label "phase-acceptance,phase/0,type/chore,prio/p0" \
  --milestone "Phase 0 — Foundation" \
  --body "$(cat <<'EOF'
Phase 0 is accepted when **all** of the following are demonstrably true:

- [ ] All Phase-0 PRs merged (see the Phase-0 Epic).
- [ ] `gh api /repos/$OWNER/$REPO/branches/main/protection` returns the JSON in §4 of the runbook.
- [ ] `gh label list` returns 42 labels matching the canonical set.
- [ ] `gh api /repos/$OWNER/$REPO/milestones?state=open` returns 12 milestones.
- [ ] `gh project field-list <n> --owner @me` returns the four single-select fields with the canonical option sets.
- [ ] `gh project item-list <n>` contains every open issue (auto-add workflow confirmed working).
- [ ] `docs/runbooks/README.md` indexes every Phase-0 runbook.
- [ ] All Phase-0 research notes present under `docs/research/`.
- [ ] One ≤5-minute screen recording attached here demonstrating: clone → open in Cursor → trigger a sample CI run.

When this checklist is fully ticked, close with `gh issue close --reason completed`.
EOF
)"
```

### 11.4 Add the three issues to the project

Auto-add (§8) should have already placed them. If you ran §§9–11 before §8, retro-fit:

```bash
for issue in $(gh issue list --repo "${GH_OWNER}/${GH_REPO}" --label "phase/0" --json url --jq '.[].url'); do
  gh project item-add $PROJECT_NUMBER --owner "@me" --url "$issue"
done
```

---

## 12. Smoke verification

A single block of `gh` calls that proves every step landed. Run after each major section, or as a final sweep at the end of the runbook.

```bash
echo "=== repo settings ==="
gh api "/repos/${GH_OWNER}/${GH_REPO}" \
  | jq '{visibility, default_branch, has_issues, has_wiki, has_projects, allow_squash_merge, allow_merge_commit, allow_rebase_merge, delete_branch_on_merge}'

echo "=== branch protection ==="
gh api "/repos/${GH_OWNER}/${GH_REPO}/branches/main/protection" \
  | jq '{
      contexts: .required_status_checks.contexts,
      strict: .required_status_checks.strict,
      reviews: .required_pull_request_reviews.required_approving_review_count,
      code_owner: .required_pull_request_reviews.require_code_owner_reviews,
      linear: .required_linear_history.enabled,
      signatures: .required_signatures.enabled,
      admins: .enforce_admins.enabled,
      conv: .required_conversation_resolution.enabled
    }'

echo "=== milestones (expect 12) ==="
gh api "/repos/${GH_OWNER}/${GH_REPO}/milestones?state=open&per_page=100" | jq 'length'

echo "=== labels (expect 42) ==="
gh label list --repo "${GH_OWNER}/${GH_REPO}" --json name --jq 'length'

echo "=== project fields (expect 4 SINGLE_SELECT) ==="
gh project field-list $PROJECT_NUMBER --owner "@me" --format json \
  | jq '[.fields[] | select(.dataType=="SINGLE_SELECT") | .name]'

echo "=== project items (expect ≥3 — the 3 Phase-0 issues) ==="
gh project item-list $PROJECT_NUMBER --owner "@me" --format json | jq '.items | length'

echo "=== auto-add workflow ==="
gh workflow list --repo "${GH_OWNER}/${GH_REPO}" | grep auto-add-to-project
```

Expected aggregate output:

- Repo: `public`, `main`, issues on, wiki off, classic projects off, squash-only, auto-delete branches on.
- Branch protection: 9 contexts, `strict: true`, ≥1 review, code-owner required, linear history on, signatures on, admins enforced, conversation resolution on.
- Milestones: `12`.
- Labels: `42`.
- Project fields: `["Phase", "Workstream", "Layer", "Type"]` (order may vary).
- Project items: ≥3 (Research-Note + Epic + Phase-Acceptance).
- Workflow: one `auto-add-to-project` row, state `active`.

If any line of the above fails, jump to §13 and re-run the offending step.

---

## 13. Rollback and re-run

Every step in this runbook is idempotent or has a documented teardown. The table below lists the exact teardown command for each section.

| Section | Teardown command | Notes |
| --- | --- | --- |
| §3 repo | `gh repo delete "${GH_OWNER}/${GH_REPO}" --yes` | Destructive — deletes everything. Re-run requires §2 onwards. |
| §3.3 settings | re-run §3.3 with new values | All `PATCH /repos` calls are idempotent. |
| §4 branch protection | `gh api -X DELETE "/repos/${GH_OWNER}/${GH_REPO}/branches/main/protection"` | Re-apply with §4.2. |
| §5 CODEOWNERS | `git rm .github/CODEOWNERS && git commit -m "chore: remove CODEOWNERS"` | Then re-add. |
| §6 project | `gh project delete $PROJECT_NUMBER --owner "@me"` | All fields and items are removed with the project. |
| §7 single field | `gh project field-delete --id <field-id> --owner "@me"` | Use `gh project field-list` to find the id. |
| §8 secret | `gh secret delete ADD_TO_PROJECT_PAT --repo "${GH_OWNER}/${GH_REPO}"` | Workflow file removal: `git rm .github/workflows/auto-add-to-project.yml`. |
| §9 milestones | `for n in $(gh api "/repos/${GH_OWNER}/${GH_REPO}/milestones?state=open" --jq '.[].number'); do gh api -X DELETE "/repos/${GH_OWNER}/${GH_REPO}/milestones/$n"; done` | Re-run §9.1 to recreate. |
| §10 labels | re-run §10.2 (delete-then-create loop) | Idempotent. |
| §11 issues | `gh issue close <n> --reason "not planned"` then `gh issue delete <n>` | Or just close; the project keeps the history. |

Re-running the entire runbook from §1 against an existing repo: every step is safe except §3 (creates the repo) and §6 (creates the project). Skip those two and the rest converges to the documented end state.

---

## 14. Cross-references

Every section of this runbook traces back to one or more sections of the parent plan and (later) ADRs.

| Runbook section | Parent plan section | ADR (after PR-3) |
| --- | --- | --- |
| §1 Prerequisites | §5 Toolchain | — |
| §2 PAT | §6.1 Repository discipline | — |
| §3 Repo creation | §6.1 | ADR-0008 (license) |
| §4 Branch protection | §6.1, §6.7 | _ADR-0009 (Rulesets migration, deferred)_ |
| §5 CODEOWNERS | §6.1, §6.2 | — |
| §6 Projects v2 | §6.6 | — |
| §7 Custom fields | §6.6 | — |
| §8 Auto-add workflow | §6.6, §6.7 | — |
| §9 Milestones | §6.6 | — |
| §10 Labels | §6.6 | — |
| §11 Bootstrap issues | §6.6 | — |
| §12 Smoke verification | §12 (scorecard) | — |
| §13 Rollback | §6.8 (status-sync) | — |

Also see:

- Sub-plan: [`.cursor/plans/p0_github_setup_runbook_643e9e0e.plan.md`](../../.cursor/plans/p0_github_setup_runbook_643e9e0e.plan.md)
- Research note: [`docs/research/phase-0-github-setup.md`](../research/phase-0-github-setup.md)
- Runbooks index: [`docs/runbooks/README.md`](README.md)

---

## 15. Appendix A — org-owned variant

If you decide to host Tethys under a GitHub organisation instead of a personal account:

| Change | User-owned (default) | Org-owned |
| --- | --- | --- |
| `GH_OWNER` | your username | the org login |
| PAT scope | Account → Projects: r+w | Organization → Projects: r+w |
| `gh project create --owner` | `@me` | `<org-login>` |
| Project URL | `https://github.com/users/<owner>/projects/<n>` | `https://github.com/orgs/<owner>/projects/<n>` |
| GraphQL root | `user(login: $login)` | `organization(login: $login)` |
| CODEOWNERS handles | `@<owner>` | `@<org>/<team>` (after creating the team) |
| Auto-add workflow `project-url` | `/users/<owner>/projects/<n>` | `/orgs/<owner>/projects/<n>` |

Everything else (branch protection, milestones, labels, bootstrap issues, smoke checks) is identical.
