# ADR-0009 - Migrate `main` from classic branch protection to a Repository Ruleset

- **Status:** proposed
- **Date:** 2026-05-14
- **Deciders:** @goldr0g3r (project owner)
- **Consulted:** PR-0a [`docs/runbooks/github-setup.md`](../runbooks/github-setup.md) §4.2 (classic-vs-Rulesets discussion); [`docs/research/phase-0-github-setup.md`](../research/phase-0-github-setup.md) decision D2
- **Informed:** future maintainers; auditors
- **Supersedes:** —
- **Superseded by:** —
- **Accepted by:** *(proposed - acceptance deferred to a future PR after PR-4 stabilises status checks)*

## Context and Problem Statement

`main` is currently protected by **classic branch protection** (`gh api PUT /repos/.../branches/main/protection --input infrastructure/github/branch-protection.json`). The runbook in PR-0a [`docs/runbooks/github-setup.md`](../runbooks/github-setup.md) §4.2 records this choice as decision D2 in [`docs/research/phase-0-github-setup.md`](../research/phase-0-github-setup.md): "Classic now, Rulesets later via deferred ADR-0009 once workflows are stable."

GitHub Repository Rulesets are the newer, more flexible replacement:

- Up to 75 rulesets per repo (vs one classic protection per branch).
- Layered evaluation (multiple rulesets compose).
- Better audit log integration.
- Explicit `bypass actors` list (cleaner than the classic `enforce_admins` toggle).
- Native support for required signatures, required linear history, required pull request reviews with `require_last_push_approval`, required status checks with `strict_required_status_checks_policy`, etc.

The question is **when** to migrate, not **if**.

## Decision Drivers

- Classic branch protection has worked through PR-0a, PR-4, PR-5, PR-6, PR-7, PR-8 with `--admin` overrides during the bootstrap window (no required status checks exist yet because PR-4 has not landed).
- Rulesets re-do every control we currently express in `branch-protection.json`; migration is a one-time rewrite + apply.
- GitHub's documentation for Rulesets is current and improving; classic protection is still supported but increasingly de-emphasised.
- We do not want to migrate before PR-4 lands the workflows; the bootstrap window already pushes the limits of admin overrides.

## Considered Options

1. **Stay on classic protection indefinitely.** Works fine for a single-maintainer project.
2. **Migrate to Rulesets immediately (this ADR).** Take the cost now.
3. **Migrate after PR-4 stabilises the 9 required status checks.** Most disruptive moment is over; migration is a clean swap.

## Decision Outcome (provisional - still `proposed`)

**Provisional decision: Option 3** - migrate after PR-4 stabilises the 9 required status checks. This ADR is left in `proposed` status until that migration PR is filed and merged; that PR (call it `chore(ruleset): migrate main from classic protection to Repository Ruleset`) will write the successor ADR (provisionally ADR-0011) that supersedes this one and flips the status to `accepted`.

### Sketch of the migration steps

1. Export the current `infrastructure/github/branch-protection.json` to a `infrastructure/github/ruleset-main.json` Ruleset JSON.
2. `gh api -X POST /repos/goldr0g3r/tethys/rulesets --input ruleset-main.json`.
3. Verify the new ruleset enforces the same nine status checks + signatures + linear history + reviews.
4. Delete the classic protection: `gh api -X DELETE /repos/goldr0g3r/tethys/branches/main/protection`.
5. Re-run smoke checks; confirm a test PR is gated identically to before.
6. Update [`docs/runbooks/github-setup.md`](../runbooks/github-setup.md) §4 to document Rulesets as the canonical mechanism (with classic as historical context).

## Consequences (anticipated)

- **Positive:** Modern GitHub controls (composable rulesets, audit log integration, cleaner bypass-actor model).
- **Positive:** Better-documented surface for future maintainers.
- **Negative:** One-time migration cost (rewrite the JSON, swap the apply command, re-verify).
- **Risk:** A misconfigured ruleset could fail open (no protection) until verified. **Mitigation:** apply the new ruleset *before* deleting the classic protection; verify; only then delete classic.

## Forward references

- `infrastructure/github/ruleset-main.json` - lands in the migration PR.
- Updated [`docs/runbooks/github-setup.md`](../runbooks/github-setup.md) §4 - same migration PR.
- ADR-0011 (provisional number) - successor; supersedes this ADR.

## References

- [`docs/runbooks/github-setup.md`](../runbooks/github-setup.md) §4.2 - classic-vs-Rulesets discussion.
- [`docs/research/phase-0-github-setup.md`](../research/phase-0-github-setup.md) decision D2.
- GitHub Rulesets docs: <https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets>.
- Available rules for rulesets: <https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets>.
