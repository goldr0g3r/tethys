# Tethys user guide

> An end-to-end recipe for engineers who want to **use**, **run**, **modify**,
> and **wire Tethys to real STM32 / HIL hardware** without first paging through
> 35 standards and 21 research notes.
>
> Audience: an embedded / calibration engineer who has used (or just heard of)
> ETAS INCA / Vector CANape and wants the same workflow over a free toolchain
> on a Nucleo board or HIL bench.
>
> Companion docs:
>
> - First-principles XCP refresher: [`docs/learn/xcp-101.md`](learn/xcp-101.md).
> - Per-task recipes (release, supply-chain, demo capture): [`docs/runbooks/`](runbooks/).
> - Why the design is the way it is: [`docs/adr/`](adr/) (ADR-0001..ADR-0010).
> - System context + dep graph: [`docs/architecture/system-context.md`](architecture/system-context.md).

## Table of contents

1. [What Tethys is](#1-what-tethys-is)
2. [Repository layout](#2-repository-layout)
3. [Prerequisites](#3-prerequisites)
4. [Install the master + simulator (Python)](#4-install-the-master--simulator-python)
5. [Build the slave library (C)](#5-build-the-slave-library-c)
6. [Run the loopback bench in 60 seconds](#6-run-the-loopback-bench-in-60-seconds)
7. [Run the GUI](#7-run-the-gui)
8. [Transports - pick one](#8-transports---pick-one)
9. [Configuration reference](#9-configuration-reference)
10. [Run the test suite](#10-run-the-test-suite)
11. [Connect Tethys to your STM32 board](#11-connect-tethys-to-your-stm32-board)
12. [Wire Tethys into a HIL bench](#12-wire-tethys-into-a-hil-bench)
13. [Troubleshooting](#13-troubleshooting)
14. [Where to go next](#14-where-to-go-next)

---

## 1. What Tethys is

Tethys is a **license-free, two-part XCP system**:

- A **PC master** (`tethys-master`, Python 3.11+) - CLI plus optional PySide6
  GUI. This is the CANape / INCA replacement.
- A **portable C11 embedded slave** (`tethys-slave`) - one library that
  cross-compiles for both `posix` (host simulator) and `stm32f4` / `stm32f7` /
  `stm32h7` (Nucleo).
- A **PC-hosted simulator** (`tethys-sim`) - a Python functional twin of the C
  slave used for the acceptance bench and for developing the master without
  hardware.

The protocol is ASAM XCP 1.4 (Part 1: protocol layer, Part 2: command set).
Wire transports shipped today are **UDP**, **SocketCAN** (Linux + CANable
2.0), **UART / SxI** (raw byte stream for the space bench), plus an
in-process **loopback** for tests. CAN-FD, TCP, and CCSDS COP-1 wraps are
scaffolded but land in later phases.

What "extreme environments" means here:

- **Marine profile** (parent plan section 3.3): CAN-FD + Ethernet (UDP),
  runtime-detect endian, optional CRC on CAL pages, optional watchdog kick
  on DAQ tick.
- **Space profile**: UART/SxI + 1-wire FT CAN, compile-time-fixed endian,
  mandatory EDAC wrap on RAM, mandatory watchdog, mandatory AES-128
  seed-and-key.

Both profiles share the same C source; the profile is selected at slave
build time with `-DTETHYS_PROFILE=marine|space`.

## 2. Repository layout

```text
tethys/
|-- master/              Python PC tool (tethys-master)
|   |-- src/tethys_master/
|   |   |-- cli.py                # `tethys-master` entry point (click)
|   |   |-- config.py             # pydantic-settings (env / .env loading)
|   |   |-- logging_setup.py      # structlog wiring
|   |   |-- protocol/             # XCP frames + client (CONNECT, UPLOAD, ...)
|   |   |-- transport/            # UDP, SocketCAN, UART/SxI, loopback
|   |   `-- gui/                  # PySide6 main window + panes (optional extras)
|   |-- tests/                    # pytest suite (incl. pyxcp diff test)
|   `-- pyproject.toml            # uv-managed; pinned per version-pinning.mdc
|
|-- simulator/           Python posix-sim XCP slave (tethys-sim)
|   |-- src/tethys_sim/
|   |   |-- cli.py                # `tethys-sim serve` entry point
|   |   |-- slave.py              # functional twin of the C dispatcher
|   |   `-- transport/            # loopback + UART pty for tests
|   `-- tests/
|
|-- slave/               Portable C11 embedded slave library (tethys-slave)
|   |-- include/tethys/           # public headers
|   |-- src/
|   |   |-- core/                 # xcp_dispatcher.c (Phase 1+2 command set)
|   |   |-- transport/            # loopback, socketcan, uart_sxi, transport.c
|   |   `-- platform/             # posix.c + stm32/*.c HAL stubs
|   |-- profiles/                 # marine.cmake + space.cmake
|   |-- tests/                    # Unity + Ceedling harness (`ceedling test:all`)
|   `-- CMakeLists.txt + CMakePresets.json
|
|-- hil/                 HIL bench (placeholder; Phase 9 fills it)
|-- docs/                ADRs, runbooks, learn, research, traceability, this guide
|-- infrastructure/      CI workflow definitions, branch-protection JSON, docker
`-- .cursor/             Plans + rules (the agent / human contract)
```

The slave does **not** know about Python, and the master does **not** require
the C library. They talk over the wire (XCP frames). The simulator and the
C slave are two implementations of the same protocol - you can use either
one from the master.

## 3. Prerequisites

| Tool | Version | Purpose | Install |
| --- | --- | --- | --- |
| Python | 3.11 - 3.13 | Master + simulator | [python.org](https://www.python.org/) or `winget install Python.Python.3.11` |
| `uv` | 0.4+ | Python package + project manager | `pip install uv` or `winget install astral-sh.uv` |
| CMake | 3.20+ | Slave build orchestration | [cmake.org](https://cmake.org/download/) |
| Ninja | any | Build backend | bundled in Visual Studio / `brew install ninja` / `apt install ninja-build` |
| GCC / Clang | any | Native slave build | system package manager |
| arm-none-eabi-gcc | 12+ | STM32 cross-compile (Phase 7+) | [Arm Developer site](https://developer.arm.com/Tools%20and%20Software/GNU%20Toolchain) |
| Ruby + Ceedling | 0.31+ | Unity-based slave unit tests | `gem install ceedling` |
| Docker | 24+ | Run the bench in containers (optional) | [docs.docker.com](https://docs.docker.com/get-docker/) |

You can use Tethys with just **Python + uv** if you only want to exercise the
master against the simulator. CMake / GCC are only required when you build
the C slave (which is what gives the project its "embedded" credibility).

## 4. Install the master + simulator (Python)

From a clean clone:

```bash
git clone https://github.com/goldr0g3r/tethys.git
cd tethys

# Master (headless CLI + Python API)
cd master
uv sync             # installs the locked dependency set
cd ..

# Simulator (depends on master via local path source)
cd simulator
uv sync
cd ..
```

Each uv project carries its own `uv.lock` so the install is reproducible.
The GUI extras (PySide6 + pyqtgraph + asammdf) are not pulled in by
default. To get them:

```bash
cd master && uv sync --all-extras   # adds [gui] + [dev]
```

## 5. Build the slave library (C)

The slave uses `cmake-init` layout with profile + platform select at
configure time.

```bash
cd slave

# Host posix-sim build (no profile - protocol-core only, for unit tests).
cmake --preset=dev
cmake --build --preset=dev

# Marine profile cross-compile (STM32F7, NUCLEO-F767ZI baseline).
cmake --preset=marine-stm32f7
cmake --build --preset=marine-stm32f7

# Space profile cross-compile (STM32H7).
cmake --preset=space-stm32h7
cmake --build --preset=space-stm32h7
```

The output static library lives at `slave/build/<preset>/libtethys_slave.a`.
ELF section sizes are reported by `arm-none-eabi-size -A` and the CI matrix
publishes per-MCU artefacts on every PR.

## 6. Run the loopback bench in 60 seconds

This is the Phase 1 acceptance bench - the master CLI talking to the
simulator slave over UDP loopback.

```bash
# Terminal 1 - simulator (host-side XCP slave)
cd simulator
uv run tethys-sim serve --transport udp --port 5555

# Terminal 2 - master CLI
cd master
uv run tethys-master connect --target udp://127.0.0.1:5555
```

Expected master output (under 1 ms wall-clock on UDP loopback):

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

## 7. Run the GUI

```bash
cd master
uv sync --all-extras     # installs PySide6 + pyqtgraph + asammdf
uv run tethys-master gui
```

The PySide6 main window opens with:

- Connection wizard (profile + transport + target picker)
- A2L tree view (MEASUREMENT + CHARACTERISTIC browser)
- Real-time pyqtgraph plot pane
- Calibration editor with A2L limit-checks
- MDF4 record / playback panel
- Diagnostics pane (CTR + loss + transport events)

CI runs the same window headless via `pytest-qt` + the Qt `offscreen`
platform plugin (set automatically when `CI=true`).

## 8. Transports - pick one

| Transport | When to use | Wire format | Master arg | Slave preset |
| --- | --- | --- | --- | --- |
| **UDP** | Default for marine; the loopback bench. | UDP datagram, MTU 1472. | `udp://host:port` | host posix / stm32 marine |
| **SocketCAN** | Linux + CANable 2.0 for CAN-FD calibration. | CAN-FD frames, 64-byte payload. | `socketcan://can0` | host Linux / stm32 marine |
| **UART / SxI** | Space bench (LVDS / RS-422 / TTL UART). | Raw byte stream, fixed 8N1 today; SLIP framing on roadmap. | `serial://COM3:115200` | host posix / stm32 space |
| **Loopback** | In-process tests; conformance suite. | None (memory queue). | `loopback://` | n/a |

Picking the wrong transport for your hardware just fails on connect with a
clear error; no silent corruption.

## 9. Configuration reference

The master uses [`pydantic-settings`](https://docs.pydantic.dev/latest/concepts/pydantic_settings/);
every CLI flag has a matching `TETHYS_MASTER_*` env var.

| Setting | Env var | Default | Notes |
| --- | --- | --- | --- |
| Log level | `TETHYS_MASTER_LOG_LEVEL` | `INFO` | One of DEBUG/INFO/WARNING/ERROR/CRITICAL. |
| Log format | `TETHYS_MASTER_LOG_FORMAT` | `plain` | `plain` or `json` (for ingest into a SIEM). |
| Connect timeout | `TETHYS_MASTER_CONNECT_TIMEOUT_MS` | `1000` | Per-command timeout floor. |
| Target URI | `TETHYS_MASTER_TARGET` | none | Default `--target` if not on the CLI. |

The simulator mirrors the same env-var pattern under `TETHYS_SIM_*`.

## 10. Run the test suite

```bash
# Master (pytest + pytest-asyncio + pytest-qt when GUI extras installed)
cd master && uv run pytest

# Simulator
cd simulator && uv run pytest

# Slave (Unity via Ceedling)
cd slave/tests && ceedling test:all
```

Test totals (Phase 1 baseline): 49 tests passing; full project suite as of
Phase 2 + 5 + 6 + 7/8 foundation is ~327 tests across master, simulator,
slave, and STM32 cross-compile.

## 11. Connect Tethys to your STM32 board

The full procedure is in [`docs/runbooks/hardware-setup-stm32.md`](runbooks/hardware-setup-stm32.md).
TL;DR for the marine profile on NUCLEO-F767ZI:

1. Flash the marine profile slave (cross-compiled via `cmake --preset=marine-stm32f7`).
2. Wire the board to your PC over Ethernet (W5500 add-on) or USB-CDC for UART.
3. From the host: `uv run tethys-master connect --profile marine --target udp://192.168.1.50:5555`.

For the space profile on NUCLEO-H753ZI follow [`docs/runbooks/hardware-setup-stm32.md`](runbooks/hardware-setup-stm32.md)
section 4 (UART / SxI transport).

## 12. Wire Tethys into a HIL bench

See [`docs/runbooks/hil-bench-setup.md`](runbooks/hil-bench-setup.md) for the
closed-loop recipe (Tethys master driving the STM32 slave, MATLAB + Simulink
plant model via `py.` interface). No Vector / ETAS / MathWorks paid licence
required.

## 13. Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `CONNECT failed: timed out` | Simulator / slave not running, or wrong port. | `tethys-sim serve --port 5555` in a separate terminal. |
| `Address already in use` | Two simulators on the same port. | `lsof -i :5555` (Linux/macOS) or `Get-NetTCPConnection -LocalPort 5555` (Windows). |
| GUI never opens | PySide6 missing. | `uv sync --all-extras` in `master/`. |
| `ceedling: command not found` | Ruby + ceedling not installed. | `gem install ceedling`. |
| Cross-compile complains about `arm-none-eabi-gcc` | Toolchain not on PATH. | Install Arm GNU Toolchain and add `bin/` to PATH. |
| `pip install -r docs/site/requirements.txt` errors | Sphinx 9.x not on PyPI yet. | requirements.txt pins 8.2.x; ensure the venv is Python 3.13. |

## 14. Where to go next

- **Calibrate / measure** with the GUI on real hardware: [`docs/runbooks/hardware-setup-stm32.md`](runbooks/hardware-setup-stm32.md).
- **Run the HIL bench**: [`docs/runbooks/hil-bench-setup.md`](runbooks/hil-bench-setup.md).
- **Cut a release**: [`docs/runbooks/release-process.md`](runbooks/release-process.md).
- **Understand the protocol**: [`docs/learn/xcp-101.md`](learn/xcp-101.md).
- **Read why decisions were made**: [`docs/adr/`](adr/) (ADR-0001..0010).
- **Verify standards trace**: [`docs/traceability.md`](traceability.md) +
  [`docs/research/phase-0-standards-matrix.md`](research/phase-0-standards-matrix.md).

This guide is intentionally compact. For deep-dives, follow the cross-links;
every `docs/*` file states its audience and scope in its first paragraph.
