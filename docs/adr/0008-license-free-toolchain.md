# ADR-0008 - License-free toolchain + repo license

- **Status:** accepted
- **Date:** 2026-05-14
- **Deciders:** @goldr0g3r (project owner)
- **Consulted:** parent plan §5 (toolchain), §9 (commercial-equivalence), §10 (gaps)
- **Informed:** every PR; CI; downstream consumers
- **Supersedes:** —
- **Superseded by:** —
- **Accepted by:** PR-3 `docs(architecture)`

## Context and Problem Statement

Tethys is positioned as a portfolio-grade, license-free XCP system (parent §1). The "license-free" claim has two facets:

1. **Toolchain:** every tool used to develop, build, test, lint, fuzz, document, package, and release Tethys must be available at zero cost for normal use. No PR may introduce a paid-license-required dependency.
2. **Repo license:** Tethys's own source code must be released under an open-source licence that downstream consumers can adopt without legal friction.

The questions: (a) what is the canonical allowed-tool list; (b) what licence does the Tethys repo itself carry?

## Decision Drivers

- The [`free-tool-only.mdc`](../../.cursor/rules/free-tool-only.mdc) Cursor rule needs an authoritative list to enforce against.
- Parent §13 parks the repo-license choice as an open question (MIT vs Apache-2.0).
- The `gh repo create` invocation in PR-0a's runbook defaulted to MIT; the GitHub repo currently carries MIT.
- Downstream commercial users want either MIT (most permissive) or Apache-2.0 (explicit patent grant).
- The [`free-tool-only.mdc`](../../.cursor/rules/free-tool-only.mdc) rule was authored against parent §5 - this ADR formalises the list and adds the gap declarations from parent §9.

## Considered Options (toolchain)

1. **Stay strictly free** - every tool zero-cost; no paid-license dependencies even when free alternatives are weaker.
2. **Allow paid tools as optional augmenters** - free tools as the baseline; paid tools allowed when a contributor has access (e.g. Polyspace at an academic site licence) but never as a hard requirement.

## Considered Options (repo license)

1. **MIT.** Maximum permissiveness; no explicit patent grant.
2. **Apache-2.0.** Permissive; explicit patent grant; longer header.
3. **GPLv3.** Copyleft; restricts downstream proprietary use.
4. **MPL-2.0.** Weak copyleft; per-file.

## Decision Outcome

### Toolchain: Option 2 (free baseline + optional paid augmenters)

The canonical allowed-tool list (from parent §5):

| Concern | Tools |
| --- | --- |
| Python ecosystem | Python 3.11+, uv (Astral), pyxcp (LGPLv3), Sauci/pya2l (BSD-3) preferred / christoph2/pyA2L (GPLv2) fallback, asammdf, PySide6 (LGPL), pyqtgraph, matplotlib, pytest, pytest-qt, ruff, mypy |
| Build | GCC, Clang, arm-none-eabi-gcc, CMake, Ninja |
| Static analysis | cppcheck --addon=misra, clang-tidy, gcc -fanalyzer, scan-build, optional Frama-C/WP |
| Coverage | gcovr, lcov, coverage.py |
| Unit test | Unity + Ceedling (C), pytest (Python) |
| Fuzzing | libFuzzer (built into Clang), AFL++ |
| CI | GitHub Actions free tier |
| Docs | Sphinx + Breathe + Doxygen, MyST-Parser, PlantUML, Mermaid |
| SBOM + supply chain | CycloneDX, Renovate, Dependabot, pip-audit, osv-scanner |
| Hardware | CANable 2.0 (~USD 40), STM32F4/F7/H7 Nucleo (~USD 25-40 each) |

**Banned (without explicit ADR exception):**

- ETAS INCA, Vector CANape, Vector CANoe (paid; replaced by Tethys-master per [ADR-0007](0007-python-master-not-matlab.md))
- MATLAB Vehicle Network Toolbox (paid add-on; bypass via MATLAB `py.` interface per [ADR-0007](0007-python-master-not-matlab.md))
- LDRA, Polyspace Bug Finder, Polyspace Code Prover (paid; replaced by cppcheck-misra + clang-tidy + gcc -fanalyzer per [ADR-0003](0003-misra-c-2023-as-coding-gate.md))
- Green Hills MULTI, IAR Safety (paid qualified compilers; gap declared below)

### Declared gaps (parent §9 + §10)

| Commercial tool | Free replacement | Gap |
| --- | --- | --- |
| Vector CANape / ETAS INCA | Tethys-master | Lost: certified A2L UI, OEM-specific extensions, vendor support |
| MATLAB Vehicle Network Toolbox | MATLAB `py.` interface to Tethys-master | None for measurement/calibration scripted use |
| Polyspace Bug Finder / Code Prover | cppcheck-misra + clang-tidy + gcc -fanalyzer + scan-build + (optional) Frama-C/WP | Absolute coverage gap on MISRA rule set vs Polyspace; some abstract-interp scenarios not covered |
| LDRA Testbed / LDRA TBvision | cppcheck-misra + gcovr MC/DC + Sphinx-generated traceability | Full LDRA tool-qualification artefacts out of scope |
| Green Hills MULTI / IAR Safety | GCC + Clang with -Werror -pedantic -fanalyzer + clang-tidy | Tool-qualification gap; real flight code would need a qualified compiler |
| ETAS RTA-OS / Vector MICROSAR | not in scope; AUTOSAR XCP module spec read as reference only | AUTOSAR Classic Platform conformance not claimed |
| Doors / Polarion | Sphinx-needs or sdoc + docs/traceability.csv + GitHub Issues with phase/* labels | Enterprise-scale requirements management gaps |

### Repo licence: Option 1 (MIT)

The Tethys repository ships under the **MIT License**. The `LICENSE` file at the repo root was created by `gh repo create --license MIT` in PR-0a and is canonical.

Rationale:

- Maximum permissiveness lets downstream commercial consumers integrate Tethys without copyleft constraints.
- Aligns with PR-0a's existing `gh repo create` default.
- The repo is portfolio-grade demonstrator code; permissive licensing matches the intent.
- No patent grant is required because Tethys uses widely-published cipher primitives (AES-128 per [ADR-0006](0006-aes-128-seed-and-key.md)) with no known relevant patents.

LGPLv3 components (pyxcp, PySide6) and GPLv2 components (christoph2/pyA2L as fallback) are **consumed**, not bundled into the Tethys source tree; their licences apply to themselves and propagate via standard linking rules.

## Consequences

- **Positive:** Anyone can clone, build, demo, and integrate Tethys at zero licence cost.
- **Positive:** Reviewers familiar with the commercial chain see the gaps named explicitly rather than discovering them mid-project.
- **Positive:** MIT licence is the most familiar OSI-approved licence; reduces friction for downstream adoption.
- **Negative:** Lacking certified MISRA coverage (no Polyspace) and lacking a qualified compiler means Tethys cannot directly target safety-of-life flight without bringing those paid tools back in. This is acceptable for a demonstrator and is declared.
- **Negative:** MIT does not protect contributors against downstream patent litigation; switching to Apache-2.0 in the future would require a re-licence ceremony if any external contributors have made commits.
- **Risk:** A future contributor introduces a paid-license dependency by accident. **Mitigation:** [`free-tool-only.mdc`](../../.cursor/rules/free-tool-only.mdc) rule + PR-4 `dependency-review.yml` workflow flag every new dependency for licence review.

## References

- Parent plan §5 (toolchain), §9 (commercial-equivalence), §10 (gaps), §13 (open question on licence).
- [`free-tool-only.mdc`](../../.cursor/rules/free-tool-only.mdc) - machine-readable enforcement.
- [ADR-0003](0003-misra-c-2023-as-coding-gate.md) - MISRA tool choice.
- [ADR-0007](0007-python-master-not-matlab.md) - master tool stack choice.
- `LICENSE` at the repo root (MIT, current).
- MIT License text: <https://opensource.org/license/mit/>.
