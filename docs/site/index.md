# Tethys - XCP for extreme environments

```{image} https://img.shields.io/badge/license-MIT-blue.svg
:alt: MIT licensed
:target: https://github.com/goldr0g3r/tethys/blob/main/LICENSE
```

> *Tethys* is both a Greek sea titan (mother of the rivers and oceans) and an icy
> moon of Saturn - the single word that natively binds the marine and space
> domains this tool targets.

**Tethys** is a portfolio-grade, **license-free**, two-part XCP system:

- a Python PC master (CANape / INCA replacement) for online calibration +
  measurement
- a portable C11 embedded slave library, configurable via marine + space
  profiles

Built with a PR-driven, ADR-backed, research-note-per-phase development
workflow patterned on serious safety-critical engineering practice, and
mapped against ECSS-E-ST-40C Rev.1, NPR 7150.2D, IACS UR E22 Rev.3,
IEC 61508, ISO 26262:2018, MISRA C:2023, and DO-178C.

::::{grid} 1 1 2 2
:gutter: 3

:::{grid-item-card} User guide
:link: /USER_GUIDE
:link-type: doc
Single end-to-end recipe: install, run, modify, and wire Tethys to STM32 / HIL hardware.
:::

:::{grid-item-card} Architecture
:link: /architecture/system-context
:link-type: doc
System context, components, transports, profiles, dependency graph.
:::

:::{grid-item-card} Architecture Decision Records
:link: /adr/README
:link-type: doc
Ten MADR v3.0 ADRs covering protocol, profile, MISRA gate, transport,
seed-and-key, license posture, packet-loss budget.
:::

:::{grid-item-card} Runbooks
:link: /runbooks/README
:link-type: doc
Eight step-by-step recipes: GitHub setup, release process, STM32 hardware,
HIL bench, traceability, incident response, supply chain, demo recording.
:::

:::{grid-item-card} Learn
:link: /learn/README
:link-type: doc
Long-form explainers - XCP from first principles, future deep-dives on A2L,
MISRA, CCSDS, AUTOSAR E2E, ECSS SDLC.
:::

:::{grid-item-card} Research notes
:link: /research/phase-0-system-requirements
:link-type: doc
Per-phase evidence trail. 14+ notes, retrieval-dated sources, decisions log.
:::

:::{grid-item-card} Standards trace
:link: /traceability
:link-type: doc
Live trace of requirements / design / code / tests to ECSS, NPR, IACS, ISO,
IEC, ASAM, MISRA objectives.
:::

::::

## Quick links

- **Source repository:** [github.com/goldr0g3r/tethys](https://github.com/goldr0g3r/tethys)
- **Releases:** [github.com/goldr0g3r/tethys/releases](https://github.com/goldr0g3r/tethys/releases) - pre-1.0 today; v0.1.0 cuts at Phase 11 close.
- **Issue tracker:** [github.com/goldr0g3r/tethys/issues](https://github.com/goldr0g3r/tethys/issues)
- **CI dashboard:** [GitHub Actions](https://github.com/goldr0g3r/tethys/actions) - `build`, `misra-gate`, `static-analysis`, `coverage`, `secret-scan`, `dependency-review`, `pr-title` are branch-protection required.

## Architecture at a glance

```{mermaid}
flowchart LR
    subgraph PC ["PC master (tethys-master)"]
        gui["PySide6 GUI<br/>+ pyqtgraph"]
        core["XCP core"]
        a2l["A2L parser"]
        mdf["asammdf<br/>logger"]
        gui --> core
        core --> a2l
        core --> mdf
    end

    subgraph Transport ["Transport (license-free)"]
        eth["UDP/TCP via<br/>std socket"]
        can["SocketCAN +<br/>CANable 2.0"]
        sxi["UART/SxI<br/>(space link)"]
    end

    subgraph Slave ["Embedded slave (tethys-slave, C11)"]
        prot["XCP protocol core"]
        tal["Transport abstraction"]
        hal["Platform HAL"]
        prof["Profile config<br/>marine | space"]
        prot --> tal
        prot --> prof
        tal --> hal
    end

    core <-->|XCP frames| eth
    core <-->|XCP frames| can
    core <-->|XCP frames| sxi
    eth <--> tal
    can <--> tal
    sxi <--> tal
```

Full description: [System context](/architecture/system-context).

## Site contents

```{toctree}
:caption: Start here
:maxdepth: 2

/USER_GUIDE
```

```{toctree}
:caption: Architecture
:maxdepth: 2

/architecture/system-context
```

```{toctree}
:caption: Architecture Decision Records
:maxdepth: 1

/adr/README
/adr/0001-xcp-as-development-protocol
/adr/0002-profile-based-build-system
/adr/0003-misra-c-2023-as-coding-gate
/adr/0004-transport-abstraction-layer
/adr/0005-no-dynamic-allocation
/adr/0006-aes-128-seed-and-key
/adr/0007-python-master-not-matlab
/adr/0008-license-free-toolchain
/adr/0009-rulesets-migration
/adr/0010-packet-loss-tolerance-budget
```

```{toctree}
:caption: Runbooks
:maxdepth: 1

/runbooks/README
/runbooks/github-setup
/runbooks/release-process
/runbooks/hardware-setup-stm32
/runbooks/hil-bench-setup
/runbooks/traceability-matrix-maintenance
/runbooks/incident-and-defect
/runbooks/supply-chain-and-sbom
/runbooks/demo-recording
```

```{toctree}
:caption: Learn
:maxdepth: 1

/learn/README
/learn/xcp-101
```

```{toctree}
:caption: Research notes
:maxdepth: 1
:glob:

/research/phase-0-*
/research/phase-1-*
/research/phase-2-*
/research/phase-5-*
/research/phase-6-*
/research/phase-7-8-*
/research/phase-10-*
/research/phase-11-*
```

```{toctree}
:caption: Engineering reference
:maxdepth: 1

/coding-standard
/misra-deviations
/traceability
```

(The 35-row standards matrix lives at
[/research/phase-0-standards-matrix](/research/phase-0-standards-matrix) inside
the Research notes section above.)

## License

[MIT](https://github.com/goldr0g3r/tethys/blob/main/LICENSE). Toolchain license
posture: [ADR-0008](/adr/0008-license-free-toolchain).
