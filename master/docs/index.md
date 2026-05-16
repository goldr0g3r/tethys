# `tethys-master` - PC-side XCP master tool

> **Audience:** anyone landing on the `tethys-master` package docs page.
> **Scope:** what the package is, what state it is in today (Phase 6
> complete), how to install + run it, how the docs are organised.
> **Length budget:** 1 page.

`tethys-master` is the PC half of [Tethys](https://github.com/goldr0g3r/tethys):
a license-free Python implementation of an ASAM XCP 1.4 calibration and
measurement master tool. It replaces the core flows of ETAS INCA and
Vector CANape (connect, A2L browse, DAQ, calibration, MDF4 record) under
an MIT licence, with marine + space profile awareness built in.

## Status today (2026-05)

| Capability | Phase | Status |
| --- | --- | --- |
| Async XCP CONNECT / DISCONNECT / GET_VERSION / GET_STATUS | 1 | done |
| SET_MTA / UPLOAD / SHORT_UPLOAD / DOWNLOAD / BUILD_CHECKSUM / SYNCH | 2 | done |
| DAQ + STIM + ODT engine | 3 | pending |
| CAL + PAG (online calibration, page switching) | 4 | pending |
| TransportPort interface + UDP / TCP / SocketCAN / UART-SxI | 5 | done |
| PySide6 GUI (connection wizard, A2L tree, plots, cal editor) | 6 | done |
| Marine profile demo (STM32F4/F7) | 7 | pending |
| Space profile demo (STM32H7 + ECC) | 8 | pending |
| HIL + MATLAB integration | 9 | pending |
| Verification pack (traceability, fuzz, robustness) | 10 | pending |
| v1.0 release + portfolio | 11 | pending |

Authoritative status: parent plan top-of-file todos in
[`xcp_extreme-env_tool_14019278.plan.md`](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md).

## Quick links

- [Installation](installation.md) - `uv tool install tethys-master`.
- [CLI reference](cli.md) - mirrors `tethys-master --help`.
- [Python API](api.md) - `tethys_master.protocol.XcpClient`,
  `tethys_master.transport.*`.
- [GUI](gui.md) - PySide6 application; `tethys-master gui`.
- [Transports](transports.md) - UDP, TCP, SocketCAN, UART/SxI; how to
  pick one.
- [Profiles](profiles.md) - marine vs space, what changes on the master.

## 60-second example

In one shell, start the simulator slave:

```bash
cd simulator
uv sync
uv run tethys-sim serve --transport udp --port 5555
```

In another shell, connect:

```bash
cd master
uv sync
uv run tethys-master connect --target udp://127.0.0.1:5555
```

Output (Phase 1 onward):

```text
CONNECT OK
  resource = 0x05
  comm     = 0x80
  max_cto  = 8
  max_dto  = 256
  protocol = 0x01, transport = 0x01
  version  = protocol 1.4, transport 1.4
  status   = session 0x80, protect 0x00
DISCONNECT OK
```

## Where this package fits

```text
+---- PC ----+              +---- Target ----+
| tethys-    |  XCP frames  |   tethys-      |
| master     +<------------>+   slave (C11)  |
| (Python)   |  over UDP /  |   + simulator  |
|            |  CAN / UART  |   (Python)     |
+------------+              +----------------+
```

- The C slave runs on STM32 hardware (Phases 7-8) or as the host
  simulator (Phase 1+).
- The master speaks the wire format; it never depends on
  vendor-specific protocols.
- The GUI and CLI share the same protocol core; both pull from
  `tethys_master.protocol` and `tethys_master.transport`.

## Licence

MIT. Toolchain posture:
[ADR-0008 license-free toolchain](../../docs/adr/0008-license-free-toolchain.md).

## Cross-references

- Parent plan section 3.1 (PC master tool).
- [`master/README.md`](../README.md).
- [`docs/USER_GUIDE.md`](../../docs/USER_GUIDE.md) - whole-project recipe.
- [`docs/learn/xcp-101.md`](../../docs/learn/xcp-101.md) - protocol primer.
- [ADR-0001 XCP as development protocol](../../docs/adr/0001-xcp-as-development-protocol.md).
- [ADR-0004 Transport abstraction](../../docs/adr/0004-transport-abstraction-layer.md).
- [ADR-0007 Python master, not MATLAB](../../docs/adr/0007-python-master-not-matlab.md).
