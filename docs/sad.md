# Software Architecture Description (SAD)

> **Status:** living draft - Phase 0 seed. The architecture overview
> already lives at [`docs/architecture/system-context.md`](architecture/system-context.md);
> this document is the *standards-referenced view* of the same content,
> structured so a reviewer under ECSS-E-ST-40C Rev.1 §5.4.3 / IEC
> 61508-3 §7.4.3 can find the architecture concerns they expect.
> **Length budget at v1.0:** 30-45 pages.

## 0. Document control

| Field | Value |
| --- | --- |
| Identifier | TETHYS-SAD-001 |
| Revision | 0.1 (seed) |
| Audit date | 2026-05-15 |
| Owner | Project owner |
| Status | Living draft |

## 1. Scope

The Software Architecture Description maps the system's components,
their interfaces, and the rationale for the structural choices. It is
the **what-and-why** document; the [SDP](sdp.md) is the **how**.

This document satisfies:

- ECSS-E-ST-40C Rev.1 §5.4.3 (architectural design).
- IEC 61508-3 §7.4.3 (software safety architecture).
- IACS UR E22 Rev.3 (software architecture documentation for marine systems).
- DO-178C §11.10 (software design description; informational).

## 2. Architectural views (ISO/IEC/IEEE 42010 viewpoints)

| View | Content | Source |
| --- | --- | --- |
| Context | System boundary, external interfaces. | [`docs/architecture/system-context.md`](architecture/system-context.md) §1 |
| Logical | Components: master, slave, transport, profiles, simulator, HIL. | [`docs/architecture/system-context.md`](architecture/system-context.md) §2 |
| Process | Threads, IPC, scheduling (master = asyncio; slave = single-stack + DAQ timer ISR). | seed - expand Phase 7 |
| Deployment | PC, simulator, STM32F4/F7 (marine), STM32H7 (space). | parent plan §3.3 |
| Information | A2L description, MDF4 log, CSV bridge, scenario JSON. | parent plan §3 + `hil/bridge/` |
| Variability | Profiles (marine, space). | parent plan §3.3 |

## 3. Architectural decisions

All cross-cutting design choices are captured as ADRs in MADR v3.0:

- [ADR-0001 XCP as a development-time protocol](adr/0001-xcp-as-development-protocol.md)
- [ADR-0002 Profile-based build system](adr/0002-profile-based-build-system.md)
- [ADR-0003 MISRA C:2023 as the coding gate](adr/0003-misra-c-2023-as-coding-gate.md)
- [ADR-0004 Transport-abstraction layer with frozen interface](adr/0004-transport-abstraction-layer.md)
- [ADR-0005 No dynamic allocation in the slave](adr/0005-no-dynamic-allocation.md)
- [ADR-0006 AES-128 seed-and-key (space profile)](adr/0006-aes-128-seed-and-key.md)
- [ADR-0007 Python master, not MATLAB](adr/0007-python-master-not-matlab.md)
- [ADR-0008 License-free toolchain + repo license](adr/0008-license-free-toolchain.md)
- [ADR-0009 Rulesets migration](adr/0009-rulesets-migration.md)
- [ADR-0010 Packet-loss tolerance budget](adr/0010-packet-loss-tolerance-budget.md)

## 4. Component decomposition

### 4.1 `tethys-master` (Python)

[`master/docs/api.md`](../master/docs/api.md) §6 module map. Public
modules: `protocol`, `transport`, `config`, `profiles`. Internal:
`gui`, `logging_setup`.

### 4.2 `tethys-slave` (C11)

[`slave/src/`](../slave/src/) and [`slave/include/tethys/`](../slave/include/tethys/).
Layered design per parent §3.2.

### 4.3 `tethys-sim` (Python)

[`simulator/src/tethys_sim/`](../simulator/src/tethys_sim/). Host-side
slave; mirrors `slave/src/core/xcp_dispatcher.c` wire-level.

### 4.4 HIL bench

[`hil/`](../hil/). Closed-loop bench - parent §9.

## 5. Interfaces

### 5.1 XCP wire interface

ASAM XCP 1.4. Cited inline in every protocol file's header per
[`.cursor/rules/xcp-protocol-discipline.mdc`](../.cursor/rules/xcp-protocol-discipline.mdc).

### 5.2 Transport interface

Frozen at Phase 5 per ADR-0004. Definition:
[`master/src/tethys_master/transport/__init__.py`](../master/src/tethys_master/transport/__init__.py)
+ C-side [`slave/include/tethys/tethys_transport.h`](../slave/include/tethys/tethys_transport.h).

### 5.3 A2L

ASAM MCD-2 MC v1.6.1. Parsed by Sauci/pya2l (BSD-3) on the master.
Round-trip preserved by [`a2l-roundtrip.yml`](../.github/workflows/a2l-roundtrip.yml).

### 5.4 HIL CSV bridge

[`hil/bridge/`](../hil/bridge/). Schemas:
[`master_out.schema.md`](../hil/bridge/master_out.schema.md),
[`plant_out.schema.md`](../hil/bridge/plant_out.schema.md).

## 6. Safety architecture (IEC 61508-3 §7.4.3)

- Single-failure independence: marine profile permits CAL writes
  on a dev bench but the production-mode flight whitelist (parent §3.3)
  restricts to a curated read-only DAQ list.
- ECC / EDAC on space profile CAL pages (ADR-0006).
- Watchdog kick in DAQ tick is OPTIONAL on marine, MANDATORY on space.
- No dynamic allocation anywhere (ADR-0005); eliminates a large class
  of safety hazards (`malloc` failure, heap fragmentation).
- No recursion / no goto on space profile (parent §3.3 +
  `no-recursion-no-goto.mdc`).
- Authenticated service-mode unlock for space-profile CAL (ADR-0006).

## 7. Variability (profiles)

Single body of code, two compile-time profiles selected via
`cmake -DTETHYS_PROFILE=marine|space`. Each profile is governed by
its invariants rule:

- [`marine-profile-invariants.mdc`](../.cursor/rules/marine-profile-invariants.mdc)
- [`space-profile-invariants.mdc`](../.cursor/rules/space-profile-invariants.mdc)

Master-side surface: [`master/docs/profiles.md`](../master/docs/profiles.md).

## 8. Quality attributes

- **Reliability**: parent §12 scorecard (coverage, MISRA, fuzz).
- **Maintainability**: Conventional Commits + ADRs + research notes.
- **Portability**: posix-sim + STM32F4/F7/H7 platforms; the slave
  protocol core is pure C11 with no platform headers.
- **Security**: AES-128 seed-and-key (space); secret-scan workflow on
  every push.
- **Performance**: 1 kHz DAQ baseline; ODT scheduling deterministic
  per parent §3.3 + Phase 8 acceptance.

## 9. Open items

- F1: Process view (§2) expansion at Phase 7 with the FreeRTOS task
  layout + ISR boundaries.
- F2: Information view diagram (Sphinx + PlantUML) at Phase 11.
- F3: Risk-driven architecture decisions (e.g. CCSDS COP-1
  retransmit) - some currently in ADR draft, formalised at Phase 8.

## Cross-references

- [`docs/architecture/system-context.md`](architecture/system-context.md).
- [`docs/architecture/dep-graph.mmd`](architecture/dep-graph.mmd).
- All ADRs under [`docs/adr/`](adr/).
- Parent plan §2 (system architecture) + §3 (component breakdown).
- ISO/IEC/IEEE 42010 - Systems and software engineering - Architecture description.
- ECSS-E-ST-40C Rev.1: https://ecss.nl/standard/ecss-e-st-40c-rev-1-software-engineering/.
