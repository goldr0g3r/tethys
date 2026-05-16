# Phase 0 - Empty-folder scaffold (research note)

> Research note backing the `chore(scaffold): fill parent-plan §14
> empty-folder slots (hil + docker + master-docs)` PR.
> Parent plan: [`xcp_extreme-env_tool_14019278.plan.md`](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md).
> Sub-plan: [`.cursor/plans/scaffold-empty-folders.plan.md`](../../.cursor/plans/scaffold-empty-folders.plan.md).

## Scope

Repository audit on 2026-05-15 flagged six gaps between the parent plan
§14 layout and the actual repo tree:

1. `hil/` had only `.gitkeep`. The plan reserves it for Phase 9 (HIL +
   MATLAB) but the slot was empty even though several deliverables
   (declarative scenario JSONs, A2L fixtures, CSV bridge schemas) need
   no physical hardware or MATLAB licence to land.
2. `infrastructure/docker/` had only `.gitkeep`. The plan reserves it
   for Phase 11 (release artefacts) but the CI already needs at least
   one container image (slave-builder for the apt-cached toolchain) to
   land before the Phase 7/8 STM32 work begins.
3. `master/docs/` had only `.gitkeep`. The plan §14 names it as
   "local docstrings; Sphinx pulls from here" - which is Phase 11
   wiring, but the local Markdown files themselves can land now and
   render on the GitHub source view.
4. `master/src/tethys_master/profiles/` is listed under §14 but never
   created. The `Profile` enum + metadata is inlined in
   `gui/profile_selector.py` instead.
5. Five SDLC documents at `docs/` root listed by §14 (`sdp.md sad.md
   svcp.md scmp.md sqap.md`) had never been seeded.
6. Six redundant `.gitkeep` files persist in directories that now
   have real content.

This PR is **not a phase milestone** - it is a `chore(scaffold)` PR
that prepares the slots so Phase 9 + Phase 11 do not waste cycles on
the directory shape.

## Sources (retrieved 2026-05-15)

| Source | Retrieved | Edition / version | Used for |
| --- | --- | --- | --- |
| Parent plan `.cursor/plans/xcp_extreme-env_tool_14019278.plan.md` §9 + §11 + §14 | 2026-05-15 | rev as in repo HEAD | Defines what each empty folder must eventually hold. |
| Runbook `docs/runbooks/hil-bench-setup.md` | 2026-05-15 | rev as in repo HEAD | Topology + scenario shape + AES key handling. |
| Runbook `docs/runbooks/release-process.md` | 2026-05-15 | rev as in repo HEAD | Image tag + SBOM expectations for Docker scaffold. |
| Runbook `docs/runbooks/demo-recording.md` | 2026-05-15 | rev as in repo HEAD | hil/artifacts/ bundle structure. |
| `.cursor/rules/free-tool-only.mdc` | 2026-05-15 | rev as in repo HEAD | Docker base-image vetting + Dockerfile content. |
| `.cursor/rules/version-pinning.mdc` | 2026-05-15 | rev as in repo HEAD | Image-tag + uv-version pin policy. |
| `.cursor/rules/research-note-per-phase.mdc` | 2026-05-15 | rev as in repo HEAD | Required section template for this note. |
| `.cursor/rules/always-cite-standards.mdc` | 2026-05-15 | rev as in repo HEAD | Commit-body citation requirement. |
| `master/src/tethys_master/gui/profile_selector.py` | 2026-05-15 | git rev as in repo HEAD | Pre-refactor location of the `Profile` enum + dicts. |
| `master/tests/test_gui_profile_selector.py` | 2026-05-15 | git rev as in repo HEAD | Import path the refactor must preserve. |
| Astral `uv` releases | 2026-05-15 | v0.5.4 | Dockerfile `UV_VERSION` argument default. https://github.com/astral-sh/uv/releases |
| Python release calendar | 2026-05-15 | 3.12.7 | Dockerfile `PYTHON_VERSION` argument default. https://www.python.org/downloads/ |
| Debian `bookworm-slim` image | 2026-05-15 | December 2024 point release | `Dockerfile.slave-builder` base. https://hub.docker.com/_/debian |
| Ceedling releases | 2026-05-15 | 0.31.1 | `Dockerfile.slave-builder` Ceedling pin. https://github.com/ThrowTheSwitch/Ceedling/releases |
| docker compose v2 schema | 2026-05-15 | Compose v2.30 | `compose.yml` healthcheck + `depends_on.condition` shape. https://docs.docker.com/compose/compose-file/ |
| ASAM MCD-2 MC v1.6.1 | (standard, no retrieval rule) | 1.6.1 | A2L fixture syntax. https://www.asam.net/standards/detail/mcd-2-mc/ |
| ECSS-Q-ST-80C | (standard, no retrieval rule) | Rev 1 | SDP / SCMP / SQAP section list. |
| ECSS-E-ST-40C | (standard, no retrieval rule) | Rev 1 (April 2025) | SAD section list. |
| IEC 61508-3 | (standard, no retrieval rule) | 2010 | SDP / SVCP / SQAP section list. |
| NPR 7150.2D | (standard, no retrieval rule) | 2024 | SDP / SCMP / SVCP section list. |
| NIST FIPS-197 | (standard, no retrieval rule) | 2001 | AES-128 hil/keys/ provenance note. |
| IACS UR E22 Rev.3 | (standard, no retrieval rule) | Rev 3 (in force 1 Jul 2024) | marine profile metadata. |

Standards documents are exempt from the 14-day rule per
`research-note-per-phase.mdc`. Every non-standard source above was
retrieved within the 14-day window.

## Decisions

| ID | Decision | Rationale |
| --- | --- | --- |
| D1 | Scaffold the three empty folders now under `chore(scaffold)`, not in their owning phase PR. | The slot shape is decoupled from the phase work. Landing the README + structural files now reduces churn in the much larger Phase 9 + Phase 11 PRs and gives reviewers a stable map of intent. |
| D2 | Do NOT fabricate Phase 9 deliverables that require MATLAB (`.slx`, demo recordings). Replace with README placeholders that document the slot. | The plan defers MATLAB work to Phase 9 explicitly; faking it would violate ECSS evidence-of-work discipline. |
| D3 | Ship REAL Dockerfiles + compose.yml now, even though the formal Docker release work is Phase 11. | CI (`ci.yml`, `misra-gate.yml`) benefits immediately from a pinned toolchain image; the master + simulator compose-bench is a regression test for the Phase 1 acceptance criterion. |
| D4 | Replicate the existing `Profile` enum into a new `tethys_master/profiles/` package and re-export from `gui/profile_selector.py`. | Parent §14 layout names the package; making the GUI module a thin re-export preserves the existing test imports (zero test-file changes) while concentrating profile metadata where non-GUI callers (CLI flag work in Phase 3+, MDF4 header writer, HIL report renderer) can find it without pulling PySide6 in. |
| D5 | Seed the five SDLC docs with the standards-referenced section list only - link to existing canonical artefacts for the body content. | The bodies live elsewhere already (SVCP body == CI workflow set; SCMP body == release-process runbook + version-pinning rule). Repeating them in five new files would create three-way drift. The seeded docs are the standards-referenced **view** of the existing content. |
| D6 | Remove `.gitkeep` files only where the directory now has real tracked content. Keep `slave/tests/test/support/.gitkeep` (Ceedling-managed placeholder). | `git` does not version empty directories; `.gitkeep` is the only way to commit one. Removing them where they are superseded keeps the tree clean. |
| D7 | Keep `hil/recordings/`, `hil/reports/`, `hil/keys/`, `hil/artifacts/` runtime-output dirs with a `.gitignore` that excludes every file except the README + `.gitignore`. | Slot is reserved, no key / recording / report can leak via `git add`. Defence-in-depth alongside `secret-scan.yml`. |
| D8 | Pin all Docker base images to exact tags now; defer digest pinning to Phase 11 when Renovate's docker manager fires. | Renovate is the right place to manage digest pins; the project does not yet have Renovate's docker manager turned on. Exact tags match the discipline of `version-pinning.mdc` until then. |
| D9 | The `master/docs/` Markdown files render on the GitHub source view today; Phase 11 wires them into the Sphinx site via a `myst_parser` include. Until then, the site `index.md` does NOT toctree them (Sphinx srcdir is `docs/`, would require additional include config). | Avoids breaking the existing `sphinx-build -W` invocation; keeps the change-set small. |
| D10 | The five SDLC files DO land under `docs/sd*.md` and ARE wired into `docs/site/index.md` via a new `Engineering process` toctree. | They live inside the Sphinx srcdir already; zero conf.py change required. |

## Open follow-ups

| ID | Phase | Description |
| --- | --- | --- |
| F1 | 9 | Land real Simulink `.slx` models under `hil/simulink/`; document the bridge block. |
| F2 | 9 | Wire the `tethys-master demo <scenario>` CLI to consume `hil/scenarios/*.json` + emit MDF4 + HTML report. |
| F3 | 9 | Add a 150-LOC Python reference plant at `hil/plant/reference_plant.py` for MATLAB-free acceptance. |
| F4 | 11 | Switch Dockerfile base images from exact tags to digests via Renovate's docker manager. |
| F5 | 11 | Push the three Docker images to GHCR on tag via `release.yml`; add a new `docker.yml` workflow that builds + pushes. |
| F6 | 11 | Add a `myst_parser` include directive to `docs/site/conf.py` so the site pulls in `master/docs/*.md`. |
| F7 | 10 | Expand each SDLC document body to the full standard-required content; cross-link traceability rows. |
| F8 | 11 | Wire `docker compose -f infrastructure/docker/compose.yml up --abort-on-container-exit` into `ci.yml` as a top-level acceptance leg. |

## Implementation Reference

- PR: *to be filled at merge*
- Merged on: *to be filled at merge*
- Files touched (count): 26 new files + 1 modified file + 6 deletions.
- Affected paths:
  - `hil/**` (12 new files across 7 subdirectories)
  - `infrastructure/docker/**` (6 new files)
  - `master/docs/**` (8 new files)
  - `master/src/tethys_master/profiles/__init__.py` (new file)
  - `master/src/tethys_master/gui/profile_selector.py` (modified - imports from new package)
  - `docs/{sdp,sad,svcp,scmp,sqap}.md` (5 new files)
  - `docs/site/index.md` (toctree extended)
  - `.cursor/plans/scaffold-empty-folders.plan.md` (sub-plan, new file)
  - `docs/research/phase-0-empty-folders-scaffold.md` (this file)
  - Removed: 6 `.gitkeep` files in directories now populated.
