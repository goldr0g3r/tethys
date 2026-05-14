---
name: Phase acceptance
about: Phase acceptance gate (one per Phase 0..11)
title: "Phase N acceptance"
labels: phase-acceptance, type/chore, prio/p0
assignees: ''
---

## Phase

Phase N (replace with the actual phase number 0..11).

## Acceptance checklist

A phase is accepted when **all** of the following are demonstrably true:

- [ ] All child PRs from the Phase-N Epic merged.
- [ ] Phase-N acceptance criteria from the parent plan satisfied.
- [ ] Demo or evidence attached here (screen recording / metric report / soak result).

When this checklist is fully ticked, close with `gh issue close --reason completed`.

## Parent plan

[.cursor/plans/xcp_extreme-env_tool_14019278.plan.md](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md)
