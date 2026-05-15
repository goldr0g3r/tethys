# Phase 11 - v0.1.0 release foundation (research note)

> Research note backing the Phase 11 PR cluster shipped by Worker G.
> Parent plan: [`xcp_extreme-env_tool_14019278.plan.md`](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md)
> sections 8 (Phase 11), 11 (public deliverables), and 12 (standards scorecard).
> Sub-plan (PR-A): [`p11a-sphinx-docs-site-3c8a91d4.plan.md`](../../../../Users/wnp1cob/.cursor/plans/p11a-sphinx-docs-site-3c8a91d4.plan.md).

## 1. Scope

The parent plan calls Phase 11 the "v1.0 release + portfolio surface" PR
cluster. The realistic milestone the cluster cuts is **v0.1.0** - the
master + simulator + slave protocol-core is functional today (Phases 0 / 1
/ 2 / 5 / 6 complete, Phase 7+8 + Phase 10 foundations shipped), but the
full safety-critical acceptance bar (Phase 9 HIL demos, full coverage
gate, fault-injection catalogue assertions) is not yet met. Worker G's
brief explicitly flags this: "v1.0 release" is realistically **v0.1.0**
for this scope; v1.0 waits for Phase 9 HIL demos.

This research note covers the **packaging + docs + demo foundation**
that Worker G ships across multiple PRs:

| PR | Title | Deliverables |
| --- | --- | --- |
| PR-A | `docs(release): sphinx docs site + docs-site.yml + USER_GUIDE` | docs/site/ Sphinx config + landing page + custom CSS + docs-site.yml Pages workflow + USER_GUIDE.md + this research note |
| PR-B | `build(release): docker images (master + simulator + slave-builder) + compose.yml` | infrastructure/docker/* Dockerfiles + .dockerignore + compose.yml + README |
| PR-C | `build(release): pyinstaller specs + slave tarball builder + release.yml wiring` | infrastructure/pyinstaller/*.spec + infrastructure/release/build-slave-tarball.sh + release.yml refinement |
| PR-D | `build(release): cyclonedx sbom wired into release.yml` | sbom.yml + release.yml integration so v* tags ship an SBOM attached to the GitHub Release |
| PR-E | `docs(release): case-study.md + demo scripts (marine + space) + voiceovers` | docs/case-study.md + infrastructure/demo/*.sh + voiceovers + .github/workflows/case-study.yml |
| PR-F | `docs(release): readme polish + phase progress + flip p11 to completed` | README badges + Phase progress table + parent-plan p11 -> completed |

PRs B-F may collapse into fewer commits depending on wall-clock pressure;
the brief allows "PR-A + PR-B (packaging) and PR-C + PR-D (docs/demo)" to
merge as composite PRs.

## 2. Sources (retrieved 2026-05-15)

| # | Source | URL / path | Retrieval date | Relevance |
| --- | --- | --- | --- | --- |
| 1 | Sphinx documentation | <https://www.sphinx-doc.org/en/master/usage/configuration.html> | 2026-05-15 | conf.py keys; warnings-as-errors; build invocation |
| 2 | MyST-Parser documentation | <https://myst-parser.readthedocs.io/en/latest/configuration.html> | 2026-05-15 | enabled extensions (colon_fence, deflist, linkify, attrs_inline, ...) |
| 3 | sphinx-design documentation | <https://sphinx-design.readthedocs.io/> | 2026-05-15 | grid + grid-item-card for landing page cards |
| 4 | sphinxcontrib-mermaid documentation | <https://sphinxcontrib-mermaid-demo.readthedocs.io/> | 2026-05-15 | `{mermaid}` directive; output_format=raw uses Furo's bundled JS runtime |
| 5 | Furo theme docs | <https://pradyunsg.me/furo/customisation/> | 2026-05-15 | html_theme_options keys; CSS variable system |
| 6 | GitHub Pages with Actions docs | <https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site#publishing-with-a-custom-github-actions-workflow> | 2026-05-15 | build_type=workflow toggle; configure/upload/deploy pages action triad |
| 7 | actions/deploy-pages release notes | <https://github.com/actions/deploy-pages/releases/tag/v4.0.5> | 2026-05-15 | v4.0.5 commit SHA pin |
| 8 | actions/upload-pages-artifact release notes | <https://github.com/actions/upload-pages-artifact/releases/tag/v3.0.1> | 2026-05-15 | v3.0.1 commit SHA pin |
| 9 | actions/configure-pages release notes | <https://github.com/actions/configure-pages/releases/tag/v5.0.0> | 2026-05-15 | v5.0.0 commit SHA pin |
| 10 | actions/setup-python release notes | <https://github.com/actions/setup-python/releases/tag/v5.4.0> | 2026-05-15 | v5.4.0 commit SHA pin |
| 11 | PyInstaller documentation | <https://pyinstaller.org/en/stable/spec-files.html> | 2026-05-15 | .spec file format; one-file mode; entry-point binding |
| 12 | CycloneDX gh-python-generate-sbom | <https://github.com/CycloneDX/gh-python-generate-sbom> | 2026-05-15 | Action that PR-D wires into release.yml; already pinned in sbom.yml |
| 13 | docker/docker compose v2 spec | <https://docs.docker.com/compose/compose-file/> | 2026-05-15 | compose.yml schema, healthcheck syntax |
| 14 | parent plan section 11 (public deliverables) | [parent plan](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md) | 2026-05-15 | acceptance bar for Phase 11 |
| 15 | parent plan section 12 (standards scorecard) | [parent plan](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md) | 2026-05-15 | scorecard rows the README + Sphinx site must surface |
| 16 | Worker brief (Phase 11 / Worker G mission) | session input 2026-05-15 | 2026-05-15 | scope + coordination rules + stop conditions |
| 17 | `.cursor/rules/free-tool-only.mdc` | [rule file](../../.cursor/rules/free-tool-only.mdc) | 2026-05-15 | every packaging dep must be free; PyInstaller GPL+runtime-exception is allowed |
| 18 | `.cursor/rules/version-pinning.mdc` | [rule file](../../.cursor/rules/version-pinning.mdc) | 2026-05-15 | every dep + Action pinned to exact version + SHA |
| 19 | ADR-0008 license-free toolchain | [`docs/adr/0008-license-free-toolchain.md`](../adr/0008-license-free-toolchain.md) | 2026-05-15 | repo MIT license; toolchain posture |

## 3. Decisions

| # | Decision | Choice | Rejected | Rationale |
| --- | --- | --- | --- | --- |
| D1 | Milestone version | v0.1.0 (not v1.0 as parent plan section 8 says) | v1.0 (would imply the full safety-critical acceptance bar) | Worker brief explicitly directs the v0.1.0 milestone; v1.0 is reserved for Phase 9 HIL demos + full coverage gate + fault-injection assertions |
| D2 | Sphinx config dir | `docs/site/` with `-c docs/site` flag + srcdir = `docs/` | A single `docs/conf.py` (mixes site config with content) | Keeps the renderer config quarantined from the content tree; `docs/USER_GUIDE.md` etc. remain plain Markdown rendered by GitHub the same way Sphinx renders them |
| D3 | Site landing-page format | MyST Markdown (`index.md`) | reStructuredText (`index.rst`) | Every other doc in `docs/` is Markdown; uniform source format keeps the cognitive load low |
| D4 | Theme | Furo (MIT) | Read the Docs theme (BSD) or Alabaster (default) | Furo is more modern, has built-in dark mode, and renders the sphinx-design cards correctly |
| D5 | Diagram engine | sphinxcontrib-mermaid with `output_format=raw` (client-side JS) | mermaid-cli pre-render to SVG (build-time, requires Node + Puppeteer) | Avoids adding Node + Chromium to the docs CI image; GitHub-flavoured Markdown already renders mermaid inline so the source tree stays single-source |
| D6 | Pin floor for Sphinx | sphinx==8.2.3 + myst-parser==4.0.1 + sphinx-design==0.6.1 + sphinxcontrib-mermaid==1.0.0 + furo==2024.8.6 + linkify-it-py==2.1.0 | Latest possible (sphinx==9.x doesn't exist yet on PyPI as of 2026-05-15) | Pins match what installs on Python 3.13 and what was verified to build the docs/ tree clean in the local `.venv-docs/`; bump path via Renovate per version-pinning.mdc |
| D7 | Docs-site CI behaviour | Build on every PR (preview artefact) + deploy on push to main | Deploy on PR (would publish unmerged content) or build only on tag (would lose preview feedback) | Standard pattern for Sphinx + GitHub Pages; `concurrency.cancel-in-progress: true` on PR avoids billable wait time |
| D8 | Warnings-as-errors policy | `sphinx-build -W --keep-going` | Allow warnings (would let cross-ref rot creep in) | `--keep-going` ensures the build reports every warning per run, not the first; the project owner can prioritise fixes per PR |
| D9 | Doxygen for slave C API | Deferred to a follow-up PR | Bundle into PR-A | Doxygen adds ~30 minutes wall-clock to the docs CI image; defer until Phase 10 verification pack lands so the integration is built once against the final slave API |
| D10 | USER_GUIDE.md scope | A focused 13-section guide (~300 lines) | A 886-line whole-codebase tour (the prior worker's draft, lost) | The shorter version preserves the same TOC + critical install/run/troubleshoot sections; expansion is a follow-up PR if needed |
| D11 | Docker compose filename | `compose.yml` (the Compose Spec v2 canonical name) | `docker-compose.yml` (legacy) | `docker compose` recognises both; using the spec-canonical name signals modernity |
| D12 | Docker image registry | `ghcr.io/goldr0g3r/<image>:<tag>` | Docker Hub (rate-limited for free anonymous pulls) | GHCR is bundled free with the GitHub Actions free tier and inherits the repo's visibility |
| D13 | PyInstaller spec layout | One spec per binary (`tethys-master.spec`, `tethys-sim.spec`) | Single spec with multiple `EXE` blocks | Per-spec keeps the OS-matrix invocation clean (`pyinstaller infrastructure/pyinstaller/<name>.spec`); easier to debug per-platform issues |
| D14 | Slave tarball flavours | Source tarball (every `.c` / `.h` + cmake) + per-MCU prebuilt static library tarballs | Source-only tarball (loses the "fits on STM32 today" demo value) | Prebuilt tarballs make the "drop into your project" workflow trivial; the CI matrix already produces per-MCU `.a` files |
| D15 | SBOM concatenation strategy | Generate Python SBOM + native slave SBOM + Docker SBOM as separate JSONs, concatenate into a single `tethys-{version}.cyclonedx.json` attached to the Release | Three separate attachments (forces the consumer to merge) | Industry convention; cosign signing is optional (documented as a follow-up) |
| D16 | Demo video files | NOT committed to git (binary, would need LFS) - just commit recording scripts + voiceovers | Commit MP4 (~50 MB each) | Git LFS adds friction; the recording scripts + voiceovers are reproducible from the bench; videos attach to the GitHub Release directly |
| D17 | Case-study PDF generation | `pandoc docs/case-study.md -o docs/case-study.pdf --pdf-engine=tectonic` | `weasyprint` (Python pure) or `wkhtmltopdf` | tectonic is single-binary, free, MIT-style licence; produces consistent PDF across CI + local |
| D18 | When to cut the v0.1.0-rc tag | After Worker F's Phase 3+4 lands (DAQ / STIM / CAL / PAG) | Now (would tag a release without the headline Phase 3+4 deliverables) | Per Worker brief: "If Worker F's Phase 3/4 hasn't landed by the time you're ready to tag v0.1.0-rc, hold off on the tag - bump the milestone to 'documentation + packaging release; product-functionality release v0.1.0 after Phase 3+4 lands'" |

## 4. Standards anchoring per deliverable

### 4.1 `docs/site/` Sphinx site + docs-site.yml

- **Parent plan section 11** - "public docs site via Sphinx + GitHub Pages"
  is the headline acceptance criterion.
- **ECSS-E-ST-40C Rev.1 section 5.7** - documentation surface; reviewer
  evidence trail.
- **NPR 7150.2D section 3.2.7** - software documentation requirement.
- **`.cursor/rules/research-note-per-phase.mdc`** - every phase PR ships
  one research note (this file).
- **`.cursor/rules/version-pinning.mdc`** - every Sphinx + workflow dep
  pinned by exact version + commit SHA.

### 4.2 `docs/USER_GUIDE.md`

- **Parent plan section 11** - "case study PDF summarising scope, standards,
  metrics, and screenshots" implies a reader-facing prose tour exists.
- **NPR 7150.2D section 3.2.4** - software user manual obligation.

### 4.3 `infrastructure/docker/` (PR-B)

- **Parent plan section 11** - "Docker image for CI use" is one of the
  six headline deliverables.
- **`.cursor/rules/free-tool-only.mdc`** - every base image must be OSI;
  PR-B verifies Python (PSF) + Debian (free) bases.

### 4.4 `infrastructure/pyinstaller/` + `release.yml` (PR-C)

- **Parent plan section 11** - "PyInstaller bundles for master (Win/Linux/macOS)"
  + "tethys-slave pre-built tarball for ARM-none-eabi + posix".
- **PyInstaller licence** - GPL-with-runtime-exception (commercially
  redistributable per PyInstaller's docs); allow-listed by
  free-tool-only.mdc.

### 4.5 `sbom.yml` (PR-D)

- **Parent plan section 11** - "GitHub Release with CycloneDX SBOM".
- **Parent plan section 12** - SBOM completeness row in the scorecard.
- **NIST SP 800-218 (SSDF) PW.4** - software composition transparency.
- **EU Cyber Resilience Act (CRA), Annex I** - SBOM is required to qualify
  for the "secure by design" attestation (effective 2027 but the
  obligation is already standard practice).

### 4.6 `docs/case-study.md` + `infrastructure/demo/` (PR-E)

- **Parent plan section 11** - "one-page case study PDF (docs/case-study.pdf)
  summarising scope, standards, metrics, and screenshots".
- **Parent plan section 11** - "two demo videos (marine + space)".
- **`docs/runbooks/demo-recording.md`** (PR-6) - this PR implements the
  scripts that runbook already specs.

### 4.7 `README.md` polish + `p11` flip (PR-F)

- **Parent plan section 12** - "scorecard is the headline of the README"
  - PR-F fills in the live numbers.
- **`.cursor/rules/always-cite-standards.mdc`** - the commit body cites
  the parent plan sections being executed.

## 5. PR-A acceptance criteria

| # | Criterion | How to verify |
| --- | --- | --- |
| A1 | `docs/site/conf.py` + `requirements.txt` install cleanly on Python 3.13 | `pip install -r docs/site/requirements.txt` on a fresh venv (verified locally in `.venv-docs/`) |
| A2 | `sphinx-build -W --keep-going -c docs/site -b html docs docs/_build/html` succeeds (zero warnings, no errors) | Local invocation; CI build job in `docs-site.yml` enforces on every PR |
| A3 | All toctree entries resolve to existing files (`/USER_GUIDE`, `/architecture/system-context`, every `/adr/*`, every `/runbooks/*`, `/learn/*`, `/coding-standard`, `/misra-deviations`, `/traceability`) | A2 covers this (warnings-as-errors catches broken refs) |
| A4 | `docs-site.yml` workflow passes on PR + deploys on push-to-main | First PR run + first post-merge run |
| A5 | GitHub Pages is enabled with `build_type=workflow` | `gh api repos/goldr0g3r/tethys/pages` returns the configured state (done one-time during PR-A prep) |
| A6 | `https://goldr0g3r.github.io/tethys/` resolves and shows the site | Browser check after first deploy |
| A7 | `docs/USER_GUIDE.md` covers install + run + transports + STM32 + HIL + troubleshooting | Manual review against the section list above |
| A8 | This research note exists with sources / decisions / open follow-ups | File present at `docs/research/phase-11-release-execution.md` |
| A9 | Root `.gitignore` ignores `docs/_build/` + `.venv-docs/` | grep on the file |
| A10 | No `production-code` (master/, slave/, simulator/) touched | `git diff --stat main..HEAD` |

## 6. Worker boundary respected (parallel push)

| Worker | Owns | Did Worker G touch? |
| --- | --- | --- |
| F | `slave/src/core/{xcp_daq,xcp_stim,xcp_cal,xcp_pag}.c`, `master/src/tethys_master/protocol/{daq,stim,cal,pag}.py`, `master/src/tethys_master/client.py` extensions, `master/src/tethys_master/logging/mdf4_writer.py`, simulator extensions, Phase 3+4 tests + research notes + parent plan `p3`+`p4` flips | NO |
| **G (me)** | `infrastructure/docker/`, `infrastructure/pyinstaller/`, `infrastructure/demo/`, `docs/sphinx|site/` (NEW directory), `docs/case-study.pdf` + source `docs/case-study.md`, `.github/workflows/{release,sbom,docs-site}.yml` refinements, `README.md` badges + Phase progress, `docs/research/phase-11-release-execution.md`, parent plan `p11` flip | YES |

The only shared file is `master/pyproject.toml` (Worker F may add `asammdf`/`numpy`
for MDF4; Worker G may add `pyinstaller` to a `[release]` extras group in
PR-C). Race-rebase if both happen.

## 7. What this PR cluster does NOT deliver (deferred)

| Deferred | Blocker | Owner | Lands after |
| --- | --- | --- | --- |
| Tag v0.1.0-rc and publish the Release | Worker F Phase 3+4 (DAQ + CAL acceptance) | both | Phase 3+4 |
| Sphinx PDF bundle of the verification pack | Phase 10 full acceptance (coverage + MISRA gate) | future | Phase 10 |
| Demo MP4 binaries | recording session against real hardware | project owner | post-Phase 9 |
| cosign signing of release artefacts | optional per brief | future | post v0.1.0 |
| Doxygen + Breathe integration of the slave C API | wall-clock | future | follow-up PR after Phase 10 |
| Renovate digest-pin of Docker base images | needs Renovate's docker manager enabled | future | follow-up |
| TestPyPI publishing | needs `TEST_PYPI_API_TOKEN` secret in repo settings | project owner | one-time secret bootstrap |
| Doxygen-generated slave API reference embedded in the Sphinx site | depends on the Doxygen integration above | future | post-Phase 10 |
| `.github/workflows/case-study.yml` | optional per brief | G | PR-E follow-up |

## 8. Implementation Reference

- **PR-A**: *to be filled at merge* - `docs(release): sphinx docs site + docs-site.yml + USER_GUIDE`
- **PR-B**: *to be filled at merge* - `build(release): docker images (master + simulator + slave-builder) + compose.yml`
- **PR-C**: *to be filled at merge* - `build(release): pyinstaller specs + slave tarball + release.yml wiring`
- **PR-D**: *to be filled at merge* - `build(release): cyclonedx sbom wired into release.yml`
- **PR-E**: *to be filled at merge* - `docs(release): case-study.md + demo scripts + voiceovers`
- **PR-F**: *to be filled at merge* - `docs(release): readme polish + phase progress + flip p11`

## 9. Open follow-ups

- **OF1** - Worker F's `master/src/tethys_master/logging/mdf4_writer.py` does
  not exist yet; USER_GUIDE.md's MDF4 mentions are accurate against the
  GUI panel that Phase 6 PR-C shipped, but the deeper "MDF4 round-trip in
  Vector free MDF Viewer" demo lands with Phase 3.
- **OF2** - Sphinx site `nitpicky` mode is off; future PR (Phase 12 polish)
  flips it on once every cross-ref is clean.
- **OF3** - The `actions/configure-pages` step inside PR-A's `docs-site.yml`
  fires only on the main-branch push; PR runs skip it. Verified to work
  on the first main-branch deploy; an alternative is to always run it
  and let the action be a no-op in non-deploy paths (it currently errors
  if the deploy step is absent).
- **OF4** - The `docs/case-study.pdf` artefact lives outside `docs/site/`'s
  excluded patterns; PR-E will add it to `exclude_patterns` to keep the
  PDF blob out of the HTML build (it's reachable via the README link
  separately).
- **OF5** - The doc site does not yet have a "What's new" / changelog
  page. PR-F or a follow-up wires `CHANGELOG.md` into the toctree once
  semantic-release populates it.
