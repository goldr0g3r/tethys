# Phase 0 - pending follow-ups implementation (research note)

> Research note backing the "implement pending F1-F8 follow-ups from
> empty-folder scaffold" PR.
> Parent plan: [`xcp_extreme-env_tool_14019278.plan.md`](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md).
> Sub-plan: [`.cursor/plans/implement-pending-followups.plan.md`](../../.cursor/plans/implement-pending-followups.plan.md).
> Predecessor research note: [`phase-0-empty-folders-scaffold.md`](phase-0-empty-folders-scaffold.md) (defines F1..F8).

## Scope

Implement the doable subset of the F1-F8 follow-ups recorded in the
empty-folder scaffold research note. The work makes the `hil/`,
`infrastructure/docker/`, and `master/docs/` scaffold actually runnable
on a developer laptop without Simulink, MATLAB, paid static-analysis
tools, or STM32 hardware.

Items implemented:

- **F1** (Phase 9): `hil/simulink/README.md` documents the slot + the
  pure-Python alternative.
- **F2** (Phase 9): `tethys-master demo <scenario>` CLI subcommand,
  Pydantic v2 scenario loader, Jinja2 HTML report, two committed
  scenario JSONs.
- **F3** (Phase 9): `simulator/src/tethys_sim/hil/reference_plant.py`
  pure-Python first-order (marine) + second-order (space) plant ODEs
  driven over a CSV bridge, plus `tethys-sim plant` CLI wiring.
- **F5** (Phase 11): `.github/workflows/docker.yml` builds all three
  Dockerfiles in CI.
- **F6** (Phase 11): Sphinx site `conf.py` mirrors `master/docs/*.md`
  into the build tree at build time.
- **F8** (Phase 11): the same `docker.yml` workflow's
  `docker-compose-bench` job runs the compose acceptance leg.

Items NOT implemented (parked):

- **F4** (Phase 11): Renovate docker-manager digest pinning.
- **F7** (Phase 10): SDLC document body expansion to full standard
  section list.

## Sources (retrieved 2026-05-16)

| Source | Retrieved | Edition / version | Used for |
| --- | --- | --- | --- |
| Parent plan `.cursor/plans/xcp_extreme-env_tool_14019278.plan.md` §3.3, §6.5, §6.7, §6.8, §8 Phase 9, §11 | 2026-05-16 | rev as in repo HEAD | Defines the Phase 9 + Phase 11 scope this PR pulls forward. |
| Predecessor research note `docs/research/phase-0-empty-folders-scaffold.md` | 2026-05-16 | rev as in repo HEAD | F1..F8 follow-up definitions. |
| `.cursor/rules/free-tool-only.mdc` | 2026-05-16 | rev as in repo HEAD | Jinja2 BSD-3-Clause vetting; Dockerfile base image vetting. |
| `.cursor/rules/version-pinning.mdc` | 2026-05-16 | rev as in repo HEAD | Exact-version `jinja2==3.1.4` pin; SHA pin for every GH Action. |
| `.cursor/rules/conventional-commits.mdc` | 2026-05-16 | rev as in repo HEAD | Suggested commit split (scope caveat noted in sub-plan). |
| `.cursor/rules/always-cite-standards.mdc` | 2026-05-16 | rev as in repo HEAD | Citation discipline on traced code under `master/src/tethys_master/hil/`. |
| `.cursor/rules/research-note-per-phase.mdc` | 2026-05-16 | rev as in repo HEAD | Section template for this note. |
| `.cursor/rules/ecss-traceability.mdc` | 2026-05-16 | rev as in repo HEAD | Justification for not adding a traceability row for the numerical reference plant. |
| `.cursor/rules/marine-profile-invariants.mdc` | 2026-05-16 | rev as in repo HEAD | Marine scenario JSON fields (watchdog optional, 4-byte seed-and-key optional). |
| `.cursor/rules/space-profile-invariants.mdc` | 2026-05-16 | rev as in repo HEAD | Space scenario JSON fields (auth.key_file mandatory, watchdog mandatory). |
| `hil/keys/README.md` | 2026-05-16 | rev as in repo HEAD | `auth.key_file` path shape (16-byte raw AES-128 seed). |
| `hil/recordings/README.md` | 2026-05-16 | rev as in repo HEAD | `daq.signals` + `transport.kind` shape. |
| `hil/reports/README.md` | 2026-05-16 | rev as in repo HEAD | Report section list rendered by `report.html.j2`. |
| Pydantic v2 documentation | 2026-05-16 | 2.9.2 (already pinned in `master/pyproject.toml`) | Scenario model. https://docs.pydantic.dev/2.9/ |
| Click 8 documentation | 2026-05-16 | 8.1.7 (already pinned) | CLI subcommand. https://click.palletsprojects.com/en/8.1.x/ |
| Jinja2 documentation | 2026-05-16 | 3.1.4 (newly pinned) | HTML report template. https://jinja.palletsprojects.com/en/3.1.x/ |
| `docker/build-push-action` | 2026-05-16 | v6.10.0 (SHA `48aba3b46d1b1fec4febb7c5d0c644b249a11355`) | Docker build job in `docker.yml`. https://github.com/docker/build-push-action/releases/tag/v6.10.0 |
| `docker/setup-buildx-action` | 2026-05-16 | v3.7.1 (SHA `c47758b77c9736f4b2ef4073d4d51994fabfe349`) | buildx setup. https://github.com/docker/setup-buildx-action/releases/tag/v3.7.1 |
| `actions/checkout` | 2026-05-16 | v4.2.2 (SHA `11bd71901bbe5b1630ceea73d27597364c9af683`) | Source checkout. Reused from `ci.yml`. |
| Sphinx 8.2.3 documentation | 2026-05-16 | 8.2.3 (installed in `.venv-docs`) | `builder-inited` hook. https://www.sphinx-doc.org/en/master/extdev/appapi.html#sphinx.application.Sphinx.connect |
| MyST-Parser 4.0.1 documentation | 2026-05-16 | 4.0.1 (installed in `.venv-docs`) | Markdown-in-Sphinx wiring. https://myst-parser.readthedocs.io/en/v4.0.1/ |
| ASAM XCP 1.4 Part 1 §1 + Part 2 §1.3.2 | (standard, no retrieval rule) | 1.4 | Scenario JSON `transport` + `daq` field semantics. |
| ASAM MCD-2 MC v1.7 §1 | (standard, no retrieval rule) | 1.7 | Scenario JSON `a2l` field semantics. |
| ECSS-E-ST-40C Rev.1 §5 + §6 | (standard, no retrieval rule) | Rev 1 (April 2025) | Demo-report sectioning (verifications trace). |
| IACS UR E22 Rev.3 | (standard, no retrieval rule) | Rev 3 (in force 1 Jul 2024) | Marine profile metadata in scenario. |
| NIST FIPS-197 | (standard, no retrieval rule) | 2001 | Space scenario auth.key_file (16-byte AES-128 seed). |

Standards documents are exempt from the 14-day rule per
`research-note-per-phase.mdc`. Every non-standard source above was
retrieved within the 14-day window.

## Decisions

| ID | Decision | Rationale |
| --- | --- | --- |
| D1 | Land the reference plant under `simulator/src/tethys_sim/hil/` (NOT under `hil/plant/`). | The simulator package already ships via `uv tool install`, depends on `tethys-master`, and has the Pydantic + structlog deps available. A second copy under `hil/plant/` would be unreachable from `tethys-sim`'s entry point and would force a duplicate dep graph. |
| D2 | Read the scenario JSON in the simulator-side plant by file-path resolution only; do NOT import the master-side Pydantic loader. | Keeps the simulator-side plant independent of pydantic; it parses the minimal scenario subset it needs (plant.kind, plant.bridge.{sample_time_s, watchdog_timeout_s, master_out, plant_out}) with `json` + a manual check. Avoids a circular dep on `tethys_master.hil.scenario`. |
| D3 | Pin `jinja2==3.1.4` exactly (latest stable as of 2026-05-16). | Version-pinning rule. 3.1.4 is the line that fixed CVE-2024-56326 + CVE-2024-56201 (sandbox escapes) — landing the line means the report renderer is post-CVE. Renovate proposes future bumps via PR. |
| D4 | Use the `builder-inited` event to mirror `master/docs/*.md` into `docs/_build_master_docs_mirror/` at sphinx-build time. The mirror dir is git-ignored. | Sphinx's `source_suffix` + the MyST loader resolve files from the Sphinx srcdir only. Two simpler alternatives — symlinks or explicit `myst_parser`-include directives — both lose on Windows / on the GitHub Pages builder. A `shutil.copy2()`-on-startup hook costs ~30 lines, keeps the mirror in sync each build, and never pollutes the repo. |
| D5 | The Sphinx smoke-test (`sphinx-build -W`) is best-effort in this PR. The site index.md has pre-existing toctree entries (`/USER_GUIDE`, `/architecture/dep-graph.svg` references) for files that do NOT exist in this repo. Phase 11 own those gaps. | Adding USER_GUIDE.md or scrubbing the toctree would balloon the PR. The PR adds the `master/docs/` mirror infrastructure without making `-W` pass; the Phase 11 PR (or a small dedicated docs-clean PR) finishes the job. |
| D6 | The `docker.yml` workflow does NOT push to GHCR. F5 originally said "build + push"; we intentionally limit to "build" here so the workflow can land before the Phase 11 secret/registry setup. The Phase 11 PR adds push + the GHCR PAT. | Avoids a partial-credential dance and matches the existing `release.yml` pattern (Phase 11 owns push). |
| D7 | The `docker-build` + `docker-compose-bench` jobs are NOT added to `infrastructure/github/branch-protection.json` by this PR. The workflow's header comment notes the Phase 11 PR will promote them. | branch-protection.json is project-owner-governed; per the user instructions, this PR does not touch it. The note in the workflow header is the bookmark. |
| D8 | The reference plant is non-traced numerical demo code; it does not get a `docs/traceability.csv` row. The scenario loader + the `tethys-master demo` CLI DO get rows (they validate XCP scenarios + drive the master CLI which is traced). | Matches `.cursor/rules/ecss-traceability.mdc` "when not to add a row" (numerical demo, no behaviour change to traced code). |
| D9 | `feat(hil)` + `ci(docker)` are NOT in the allowed-scope list of `.cursor/rules/conventional-commits.mdc`. We use the subjects the user proposed verbatim. | The project owner can either rescope or extend the rule; this PR does not unilaterally extend the rule (governance gate). |
| D10 | Both scenario JSONs declare `profile=marine` and `profile=space` respectively and follow the row constraints in `marine-profile-invariants.mdc` (optional 4-byte seed-and-key, default off) and `space-profile-invariants.mdc` (mandatory `auth.key_file` to a `hil/keys/<scenario>.key` path, mandatory watchdog). | Profile invariants apply to slave code, but the scenario JSON is the master-side declaration of which invariants the bench is expected to honour. Aligning the JSONs to the rule means the loader cannot accept an invalid space scenario. |

## Open follow-ups

| ID | Phase | Description |
| --- | --- | --- |
| G1 | 11 | Push the three Docker images to GHCR on tag from `docker.yml` (uncomment the push job + add `permissions: packages: write` + GHCR PAT). |
| G2 | 11 | Promote `docker-build` + `docker-compose-bench` to required-status-checks in `infrastructure/github/branch-protection.json` (governance PR by project owner). |
| G3 | 11 | Make `sphinx-build -W -c docs/site -b html docs docs/_build/html` pass clean — add `docs/USER_GUIDE.md` (or scrub the broken toctree entries), wire `/architecture/dep-graph` as a real Mermaid include, etc. Out of scope for this PR. |
| G4 | 9 | Replace the simulator reference plant's first-order / second-order toy models with Simulink-grade dynamics once a Simulink licence is available — keep the CSV bridge interface unchanged so this is a drop-in. |
| G5 | 10 | Expand the SDLC documents (`docs/sd*.md`) to full standard-required content; cross-link to the demo report template that this PR adds. |
| G6 | 11 | Renovate docker-manager — switch the three Dockerfile base images from exact tags to immutable digests. |
| G7 | (governance) | Decide whether `hil` + `docker` become allowed scopes in `.cursor/rules/conventional-commits.mdc`. If yes, mirror to `.github/instructions/`. |

## Implementation Reference

- PR: *to be filled at merge*
- Merged on: *to be filled at merge*
- Files touched (count): 18 new files + 8 modified files (see end-of-PR summary).
- Verification — full results in §"Verification commands" below. Summary:
  - All linter / type / test errors introduced by THIS PR are zero.
  - 5 ruff errors + 3 mypy errors remain on `main`; every one of them
    is pre-existing in files this PR does not touch (the prior
    `Seed docs, HIL scaffold, and DAQ phase 3 work` commit landed
    them). Per the user instructions we do NOT fix pre-existing
    lints.
  - `tests/test_sim_daq.py` has a pre-existing `ImportError: cannot
    import name 'DtoPacket'` introduced in the same prior commit;
    we exclude that file from the pytest run for the simulator gate.
  - Sphinx `sphinx-build -W` crashes with
    `KeyError: 'anchorname'` inside Sphinx 8.2.3 / Furo 2024.8.6 /
    MyST 4.0.1 — verified to be pre-existing by `git stash` + rerun
    (same crash without our F6 changes). G3 in §Open follow-ups
    tracks the remediation. The F6 mirror infrastructure DOES land
    correctly: the mirror directory is populated on every run
    (verified) and the new "Master tool internals" toctree is wired.

### Verification commands

| Command | Workdir | Outcome |
| --- | --- | --- |
| `uv run ruff check .` | `master/` | exit code 1; 5 errors, **0 introduced by this PR** (all in `src/tethys_master/protocol/daq.py`, `src/tethys_master/protocol/mdf4_recorder.py`, `tests/test_mdf4_recorder.py`, `tests/test_protocol_daq.py`). |
| `uv run ruff format --check .` | `master/` | exit code 1; 15 files would reformat; **the files I touched are formatted** (verified by `ruff format --check src/tethys_master/cli.py src/tethys_master/hil/ tests/test_cli_demo.py tests/test_hil_scenario.py` → exit 0). |
| `uv run mypy src/tethys_master` | `master/` | exit code 1; 3 errors, **0 introduced by this PR** (all in `src/tethys_master/protocol/daq.py`). |
| `uv run pytest -q` | `master/` | exit code 0; **283 passed, 5 skipped** in 5.34s. Includes the 18 new tests in `test_hil_scenario.py` + `test_cli_demo.py`. |
| `uv run ruff check .` | `simulator/` | exit code 1; 9 errors, **0 introduced by this PR** (pre-existing in `src/tethys_sim/daq.py` PLR0911 / PLR0912; `tests/test_client_daq.py` F401 / RUF100; `tests/test_sim_daq.py` I001; `tests/test_sim_daq_emission.py` RUF002 / UP041). |
| `uv run ruff format --check .` | `simulator/` | exit code 1; 6 pre-existing files would reformat; **my files are formatted** (verified by `ruff format --check src/tethys_sim/hil tests/test_hil_reference_plant.py src/tethys_sim/cli.py` → exit 0). |
| `uv run mypy src/tethys_sim` | `simulator/` | exit code 1; 1 error, **0 introduced by this PR** (pre-existing `XcpDaqCommand.CLEAR_DAQ_LIST` in `src/tethys_sim/daq.py`). |
| `uv run pytest tests/test_hil_reference_plant.py -q` | `simulator/` | exit code 0; **15 passed** in 1.04s. The 15 new tests cover the F3 acceptance criteria. |
| `uv run pytest --ignore=tests/test_sim_daq.py tests/test_hil_reference_plant.py tests/test_slave_dispatch.py tests/test_client_daq.py -q` | `simulator/` | exit code 0; **41 passed** in 1.29s. Confirms my F3 work does not regress the pre-existing pytest passes. |
| `uv run pytest tests/test_sim_daq_emission.py -q` | `simulator/` | exit code 0; **5 passed** in 368s — pre-existing slow UDP-loopback tests. Not in my work. |
| `uv run pytest -q` (whole tree) | `simulator/` | exit code 2; **collection error** in `tests/test_sim_daq.py` (`ImportError: cannot import name 'DtoPacket' from tethys_master.protocol.daq`). Pre-existing; file added by commit `d4c5fe5`. Not in my work. |
| `.venv-docs\Scripts\python.exe -m sphinx -W -c docs/site -b html docs docs/_build/html` | repo root | exit code 2; pre-existing `KeyError: 'anchorname'` inside Sphinx 8.2.3 / Furo / MyST 4.0.1 while writing `coding-standard`. Verified pre-existing by `git stash` + rerun → identical crash. G3 in §Open follow-ups. |

### Files created (18)

```
.cursor/plans/implement-pending-followups.plan.md
.github/workflows/docker.yml
docs/research/phase-0-pending-followups-implementation.md
docs/site/conf.py
hil/bridge/master_out.schema.md
hil/bridge/plant_out.schema.md
hil/scenarios/README.md
hil/scenarios/marine-common-rail-injector.json
hil/scenarios/space-reaction-wheel.json
hil/simulink/README.md
master/src/tethys_master/hil/__init__.py
master/src/tethys_master/hil/scenario.py
master/src/tethys_master/hil/report.html.j2
master/tests/test_hil_scenario.py
master/tests/test_cli_demo.py
simulator/src/tethys_sim/hil/__init__.py
simulator/src/tethys_sim/hil/reference_plant.py
simulator/tests/test_hil_reference_plant.py
```

### Files modified (8)

```
.gitignore                                # docs/_build/ + docs/_build_master_docs_mirror/ entries
docs/site/index.md                        # "Master tool internals" toctree
docs/traceability.csv                     # TETHYS-REQ-P9-HIL-001 + -002 rows
master/pyproject.toml                     # jinja2==3.1.4 pin
master/uv.lock                            # uv lock refresh
master/src/tethys_master/cli.py           # demo subcommand + bridge loop + report renderer
simulator/src/tethys_sim/cli.py           # plant subcommand
simulator/uv.lock                         # uv lock refresh (transitive: jinja2 + markupsafe)
```
