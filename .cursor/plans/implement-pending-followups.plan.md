---
name: Implement pending F1-F8 follow-ups from empty-folder scaffold
overview: "End-to-end implementation of the doable subset of F1-F8 follow-ups from docs/research/phase-0-empty-folders-scaffold.md. Makes the hil/, infrastructure/docker/, and master/docs/ scaffold runnable without hardware, MATLAB, or paid tools."
todos:
  - id: subplan
    content: "Draft this sub-plan + the matching research note skeleton before code edits."
    status: completed
  - id: f3-bridge-schemas
    content: "Prereq for F3: author hil/bridge/master_out.schema.md + plant_out.schema.md (CSV schema docs). Both schemas are LF-only, ASCII, monotonic timestamp_us + strictly-increasing sample_index, header fields fixed."
    status: completed
  - id: f3-reference-plant
    content: "F3 main: simulator/src/tethys_sim/hil/reference_plant.py — pure-Python first-order (marine-common-rail-injector) + second-order (space-reaction-wheel) plant ODEs, reads master_out.csv, writes plant_out.csv, watchdog timeout zero-order-holds; idempotent re-reads."
    status: completed
  - id: f3-cli
    content: "Wire `tethys-sim plant --scenario <name> [--once]` through simulator/src/tethys_sim/cli.py. Resolves scenario JSON via the master scenario loader (importable from tethys_master.hil.scenario after F2; or via a path-only fallback for hard isolation)."
    status: completed
  - id: f3-tests
    content: "simulator/tests/test_hil_reference_plant.py — header validation, schema-mismatch refusal, watchdog timeout zero-order-hold, idempotency of repeat reads, marine step-response monotonicity, space second-order shape."
    status: completed
  - id: f2-scenarios
    content: "Prereq for F2: hil/scenarios/README.md (schema doc) + marine-common-rail-injector.json + space-reaction-wheel.json. Schemas referenced from hil/keys/README.md (auth.key_file path) + hil/recordings/README.md (transport.kind shape)."
    status: completed
  - id: f2-scenario-loader
    content: "F2: master/src/tethys_master/hil/__init__.py + scenario.py — Pydantic v2 model that validates both committed JSONs. Fields: name, profile, duration_s, transport{kind,target,timeout_ms}, a2l{path,hash}, daq{event_channel,signals,rate_hz}, plant{kind,bridge{sample_time_s,watchdog_timeout_s,master_out,plant_out}}, auth{key_file?}, report_html, trace.standards[]."
    status: completed
  - id: f2-demo-cli
    content: "F2: extend master/src/tethys_master/cli.py with a `demo` click subcommand. Loads + validates scenario JSON; opens transport (or skip on --dry-run); writes one master_out.csv row per plant.bridge.sample_time_s; reads plant_out.csv rows; emits demo.start + demo.summary log events; renders Jinja2 HTML report."
    status: completed
  - id: f2-report-template
    content: "F2: master/src/tethys_master/hil/report.html.j2 — ~30 lines, prints scenario name + duration + counters (daq_dropped, cal_crc_fail) + trace.standards table."
    status: completed
  - id: f2-jinja2-pin
    content: "F2: pin `jinja2==3.1.4` exactly in master/pyproject.toml [project.dependencies] per version-pinning.mdc; run `uv lock` in master/ to refresh master/uv.lock; verify dependency-graph still pure-Python + LGPL/BSD/MIT (free-tool-only.mdc)."
    status: completed
  - id: f2-tests
    content: "master/tests/test_hil_scenario.py — pydantic model validates both JSONs + rejects malformed; master/tests/test_cli_demo.py — `tethys-master demo <scenario> --dry-run` runs end-to-end without opening a transport, writes HTML report, exits 0."
    status: completed
  - id: f1-simulink-readme
    content: "F1: hil/simulink/README.md — short README that documents the slot for Phase 9 Simulink work, plus a 'Pure-Python alternative (recommended)' section pointing at the F3 reference plant and the `tethys-sim plant` wiring."
    status: completed
  - id: f5-f8-docker-workflow
    content: "F5+F8: .github/workflows/docker.yml — push-on-main + pull_request (infrastructure/docker/**, master/**, simulator/**) + tag (`v*`). Job docker-build builds all 3 Dockerfiles with docker/build-push-action (no push). Job docker-compose-bench runs `docker compose -f infrastructure/docker/compose.yml up --build --abort-on-container-exit --exit-code-from master`. Every action pinned by SHA + trailing tag comment. Header comment notes Phase 11 will promote both jobs to required-status-checks (branch-protection.json untouched)."
    status: completed
  - id: f6-sphinx-mirror
    content: "F6: docs/site/conf.py (new file) with a `builder-inited` Sphinx hook that copies master/docs/*.md into docs/_build_master_docs_mirror/ at build time; the mirror dir is in .gitignore. Extends docs/site/index.md with a 'Master tool internals' toctree pointing at the mirrored files. Smoke-test: `sphinx-build -W -c docs/site -b html docs docs/_build/html` (best-effort; pre-existing dangling refs from older scaffold work are noted but not in scope to fix here)."
    status: completed
  - id: traceability
    content: "Update docs/traceability.csv with new rows for the HIL scenario loader (REQ → DES → CODE → TEST) and the demo CLI subcommand. Mirror existing column shape (id,kind,parent,description,implemented_by,verified_by,standard_objective,phase,profile)."
    status: completed
  - id: research-note
    content: "docs/research/phase-0-pending-followups-implementation.md — required sections per research-note-per-phase.mdc; sources retrieved 2026-05-16; decisions log + open follow-ups + implementation reference."
    status: completed
  - id: lint-test-gates
    content: "Run ruff check + ruff format --check + mypy + pytest in both master/ and simulator/. Fix every error introduced. Do not fix pre-existing lints unless trivially in the same edit."
    status: completed
  - id: status-sync
    content: "Flip every todo above to `completed` once verified."
    status: completed
isProject: false
---

# Implement pending F1-F8 follow-ups from empty-folder scaffold

> Parent plan: [`xcp_extreme-env_tool_14019278.plan.md`](xcp_extreme-env_tool_14019278.plan.md) (§3.3 profile system, §6.5 Cursor rules, §6.7 CI/CD matrix, §6.8 sub-plan workflow, §8 Phase 9 HIL + Phase 11 release, §11 public deliverables).
> Predecessor research note: [`docs/research/phase-0-empty-folders-scaffold.md`](../../docs/research/phase-0-empty-folders-scaffold.md) (defines F1..F8).
> Companion research note (this PR): [`docs/research/phase-0-pending-followups-implementation.md`](../../docs/research/phase-0-pending-followups-implementation.md).

## Scope

Implement the doable subset of the F1..F8 follow-ups from the empty-folder
scaffold research note. After this PR:

- `simulator/` ships a pure-Python reference plant exercising the master-out
  ↔ plant-out CSV bridge for the two Phase 9 demos (marine common-rail
  injector + space reaction-wheel) so the bench can be exercised without
  Simulink, MATLAB, or any paid licence.
- `tethys-master demo <scenario>` validates a scenario JSON, opens (or in
  `--dry-run` skips opening) the chosen transport, drives the CSV bridge,
  emits structured log events, and renders an HTML demo report.
- `infrastructure/docker/` Dockerfiles + `compose.yml` get a dedicated CI
  workflow (`docker.yml`) that exercises both Docker build and the
  compose acceptance leg on every relevant push, PR, and tag.
- `master/docs/*.md` is wired into the public Sphinx site at `docs/site/`
  via a mirror-into-build-tree shim added to `docs/site/conf.py`.

Out of scope (parked per the user instructions):

- F4 (Renovate digest pinning), F7 (SDLC body expansion), Phase 3 DAQ+STIM,
  Phase 4 CAL+PAG, Phase 7/8 STM32, Phase 10 verification, Phase 11 release.
- Any modification of `.cursor/rules/*.mdc`,
  `infrastructure/github/branch-protection.json`,
  `infrastructure/github/labels.json`, `.github/CODEOWNERS`,
  or `infrastructure/rules/sync.*`.
- Any `git commit`, `git push`, or PR creation.

## Discipline gates honoured

1. **Sub-plan**: this file.
2. **Research note**: `docs/research/phase-0-pending-followups-implementation.md`.
3. **Conventional Commits** (suggested subjects in the §"Suggested commit split").
4. **Always cite standards**: every Python file added under
   `master/src/tethys_master/hil/` cites the parent plan and any
   controlling standard. The simulator-side `hil/reference_plant.py` is a
   numerical demo; it cites the parent plan §8 Phase 9 only (no XCP /
   profile invariant standard applies — it does not touch protocol or
   profile metadata).
5. **Version pinning**: `jinja2==3.1.4` pinned exactly; every action in
   `docker.yml` pinned by SHA with a `# vX.Y.Z` trailing comment.
6. **Free tool only**: no Vector / ETAS / MATLAB / Polyspace / LDRA /
   Green-Hills / IAR dependency. Jinja2 is BSD-3-Clause; pydantic + click +
   structlog are already approved.
7. **Traceability**: new rows for the HIL scenario loader + demo CLI added
   to `docs/traceability.csv`. The reference plant is non-traced numerical
   demo code (not under `slave/src/core/`, not under
   `master/src/tethys_master/protocol/`); see `ecss-traceability.mdc`
   "when not to add a row".
8. **Lint/test gates**: ruff + ruff format --check + mypy + pytest in
   both `master/` and `simulator/`.

## File-by-file deliverables

### F3: pure-Python reference plant (simulator/, no MATLAB)

| Path | Verb | Purpose |
| --- | --- | --- |
| `hil/bridge/master_out.schema.md` | CREATE | CSV schema doc — header, units, monotonicity rules, watchdog interpretation. |
| `hil/bridge/plant_out.schema.md` | CREATE | CSV schema doc — header, units, sample_index/timestamp_us discipline. |
| `simulator/src/tethys_sim/hil/__init__.py` | CREATE | Package init; exports `ReferencePlant`. |
| `simulator/src/tethys_sim/hil/reference_plant.py` | CREATE | 150–200 LOC pure-Python plant; marine + space scenarios; watchdog timeout zero-order-hold. |
| `simulator/src/tethys_sim/cli.py` | MODIFY | Add `plant --scenario <name> [--once]` subcommand. |
| `simulator/tests/test_hil_reference_plant.py` | CREATE | Header validation, schema-mismatch refusal, watchdog ZOH, idempotent re-reads, marine step-response monotonicity, space second-order shape. |

### F2: tethys-master demo CLI + scenario loader

| Path | Verb | Purpose |
| --- | --- | --- |
| `hil/scenarios/README.md` | CREATE | Schema doc; references `hil/keys/README.md` + `hil/recordings/README.md`. |
| `hil/scenarios/marine-common-rail-injector.json` | CREATE | Marine demo scenario. |
| `hil/scenarios/space-reaction-wheel.json` | CREATE | Space demo scenario. |
| `master/src/tethys_master/hil/__init__.py` | CREATE | Exports `Scenario`, `ScenarioError`. |
| `master/src/tethys_master/hil/scenario.py` | CREATE | Pydantic v2 model + loader. |
| `master/src/tethys_master/hil/report.html.j2` | CREATE | ~30-line Jinja2 template. |
| `master/src/tethys_master/cli.py` | MODIFY | Add `demo` click subcommand. |
| `master/pyproject.toml` | MODIFY | Pin `jinja2==3.1.4`. |
| `master/uv.lock` | MODIFY | Refresh via `uv lock`. |
| `master/tests/test_hil_scenario.py` | CREATE | Pydantic round-trip + rejection cases. |
| `master/tests/test_cli_demo.py` | CREATE | `--dry-run` end-to-end. |

### F1: pure-Python alternative note

| Path | Verb | Purpose |
| --- | --- | --- |
| `hil/simulink/README.md` | CREATE | Documents the slot + the pure-Python alternative (recommended). |

### F5+F8: Docker CI workflow

| Path | Verb | Purpose |
| --- | --- | --- |
| `.github/workflows/docker.yml` | CREATE | Build (no push) + compose-bench legs. Header comment notes Phase 11 will add both contexts to required-status-checks. |

### F6: Sphinx mirror

| Path | Verb | Purpose |
| --- | --- | --- |
| `docs/site/conf.py` | CREATE | Minimal MyST conf + builder-inited mirror hook for `master/docs/*.md`. |
| `docs/site/index.md` | MODIFY | Adds "Master tool internals" toctree section pointing at the mirrored files. |
| `.gitignore` | MODIFY | Ignores `docs/_build/`, `docs/_build_master_docs_mirror/`. |

### Traceability

| Path | Verb | Purpose |
| --- | --- | --- |
| `docs/traceability.csv` | MODIFY | Add TETHYS-REQ-P9-HIL-001 (scenario loader) + TETHYS-REQ-P9-HIL-002 (demo CLI). Each row links REQ → DES → CODE → TEST. |

## Acceptance criteria

| ID | Criterion | How verified |
| --- | --- | --- |
| AC-F3-1 | `uv run tethys-sim plant --scenario marine-common-rail-injector --once` writes a well-formed `hil/plant_out.csv` row when fed a single `hil/master_out.csv` row. | pytest |
| AC-F3-2 | Watchdog timeout zero-order-holds the previous master command. | pytest |
| AC-F3-3 | Repeat reads of the same `master_out.csv` are idempotent (no duplicate plant_out rows). | pytest |
| AC-F2-1 | `uv run tethys-master demo marine-common-rail-injector --dry-run` exits 0 and writes a non-empty HTML report. | pytest |
| AC-F2-2 | Pydantic model accepts both committed JSONs and rejects a synthetic bad payload. | pytest |
| AC-F5-1 | `docker.yml` parses cleanly (yamllint via pre-commit) and pins every action by SHA. | manual review + the existing `static-analysis.yml` grep gate. |
| AC-F8-1 | `docker compose -f infrastructure/docker/compose.yml up --build --abort-on-container-exit --exit-code-from master` exits 0 locally (Docker available) and in CI. | docker-compose-bench job. |
| AC-F6-1 | `sphinx-build -W -c docs/site -b html docs docs/_build/html` either (a) succeeds clean or (b) fails only on pre-existing dangling refs not introduced by this PR (documented in §Open follow-ups). | local smoke. |
| AC-Disc-1 | `uv run ruff check .` + `uv run ruff format --check .` + `uv run mypy src/tethys_master` + `uv run pytest -q` clean in `master/`. | local run logged in research note. |
| AC-Disc-2 | Same suite clean in `simulator/`. | local run logged in research note. |

## Suggested commit split (Conventional Commits)

1. `feat(hil): add pure-Python reference plant for simulator package` — F3 + the two CSV schemas (hil/bridge/*).
2. `feat(master): add tethys-master demo subcommand + scenario loader` — F2 (loader, CLI subcommand, report template, jinja2 pin, scenarios JSONs, scenarios README).
3. `ci(docker): add docker-build + compose-bench workflow` — F5+F8.
4. `docs(master): wire master/docs into Sphinx site` — F6.
5. `docs(hil): note pure-Python alternative for Simulink models` — F1.

Note: the `conventional-commits.mdc` allowed-scope list does NOT include
`hil` or `docker` as top-level scopes. The suggested subjects above use
those scopes verbatim per the user instructions; the project owner may
choose to either (a) add `hil` + `docker` to the scope list (which
requires a `chore(rules)` follow-up touching `.cursor/rules/conventional-commits.mdc`
+ the mirror in `.github/instructions/`), or (b) rescope to `master` +
`ci` respectively. This PR does NOT touch the rule file.

## Status sync

Each `todos[*].status` flips to `completed` as the section lands. On
merge the parent plan's `p9` todo stays `pending` — this PR pulls
Phase 9 + Phase 11 dependencies forward but does NOT close the Phase 9
epic; the Phase-Acceptance issue still needs the real STM32 demos.
