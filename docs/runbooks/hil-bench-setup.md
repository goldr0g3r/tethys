# Runbook - HIL bench setup (master + slave + Simulink plant)

> Audience: an engineer building the hardware-in-the-loop bench used for
> Phase 9 demos.
> Goal: from "STM32 board flashed (see hardware-setup-stm32.md) + MATLAB
> academic licence available" to "closed-loop test running with the master
> tool driving the slave on real silicon, fed by a Simulink plant model".
> Wall-clock target: **90 minutes** the first time, **<15 minutes** for
> subsequent runs of the same scenario.
> Style: numbered sections, topology diagram, commands for both shells.
>
> Implements parent plan §9 (Phase 9 HIL + MATLAB integration) and §5
> (CANable 2.0 + STM32 baseline).

## Table of contents

1. [Prerequisites](#1-prerequisites)
2. [Bench topology](#2-bench-topology)
3. [Software install](#3-software-install)
4. [Plant model preparation](#4-plant-model-preparation)
5. [Bench bring-up](#5-bench-bring-up)
6. [Closed-loop demo - marine (common-rail injector)](#6-closed-loop-demo---marine-common-rail-injector)
7. [Closed-loop demo - space (reaction wheel)](#7-closed-loop-demo---space-reaction-wheel)
8. [Recording artefacts](#8-recording-artefacts)
9. [Troubleshooting](#9-troubleshooting)
10. [Cross-references](#10-cross-references)

---

## 1. Prerequisites

- STM32 Nucleo flashed per
  [`hardware-setup-stm32.md`](hardware-setup-stm32.md) §5-6.
- MATLAB academic licence (any release >=R2024a). Vehicle Network Toolbox is
  **NOT** required - parent §5 explicitly avoids it.
- Python 3.11+ on the PC running the master tool.
- CANable 2.0 (Linux only) or PCAN-USB (Windows/Linux) for CAN bench.
- 1 m Ethernet cable for UDP bench.
- FT232RL USB-UART for space SxI bench.

Verify each:

```powershell
matlab -batch "ver" | Select-String -Pattern "MATLAB Version"
uv --version
python --version
```

```bash
matlab -batch "ver" | grep "MATLAB Version"
uv --version
python --version
```

## 2. Bench topology

```text
                 +---------- PC (Linux preferred) -----------+
                 |                                           |
                 |  +---------------+    +----------------+  |
                 |  | tethys-master |<-->|  Simulink      |  |
                 |  |  (Python CLI) |    |  plant model   |  |
                 |  +-------^-------+    +-------^--------+  |
                 |          |                    |            |
                 |          | py.tethys_master() | shared CSV |
                 |          |                    | + MDF4     |
                 +----------|---------+----------|------------+
                            | XCP     |          |
                            |  frames |          |
                            v         |          v
                +---- USB --|-- Etherne|t/CAN/UART -----+
                            |          |
                +-----------v----------v---------+
                |          STM32 Nucleo          |
                |         (Tethys slave)         |
                +--------------------------------+
                            |
                +-----------v--------------------+
                |  Test article (real or         |
                |  simulated via plant model)    |
                +--------------------------------+
```

The closed loop:

1. Master sends XCP DAQ requests to the slave on the Nucleo.
2. Slave samples internal variables and DTO-streams them back to master.
3. Master logs DAQ stream to MDF4 AND forwards key signals to Simulink via the
   shared CSV / shared-memory bridge.
4. Simulink plant model integrates the test-article dynamics in real time
   (typically 1 kHz step).
5. Simulink writes back plant outputs into a CSV the master reads, which then
   sends XCP CAL writes to the slave (closing the loop).

## 3. Software install

### 3.1 Install master tool

```powershell
uv tool install tethys-master
```

```bash
uv tool install tethys-master
```

Expected: tool entry point `tethys-master` on PATH.

### 3.2 Configure MATLAB to call Python

Open MATLAB; in the Command Window:

```matlab
pyenv('Version', '/path/to/python3.11', 'ExecutionMode', 'InProcess')
```

Expected: `PythonEnvironment` printout listing the path. Persist via
`pyversion` in `startup.m`.

### 3.3 Verify MATLAB <-> Python bridge

```matlab
py.print('hello from MATLAB calling Python')
py.tethys_master.__version__
```

Expected: prints the message and the master version string.

## 4. Plant model preparation

The two reference Simulink models live in `hil/simulink/` (added in Phase 9):

- `marine_common_rail_injector.slx` - cylinder pressure dynamics + injector
  solenoid model.
- `space_reaction_wheel.slx` - rigid-body dynamics + motor torque + bearing
  friction.

Open one:

```matlab
cd hil/simulink
open_system('marine_common_rail_injector')
```

In the model's "Tethys bridge" block, set:

- `Master CSV path`: `${HIL_BENCH_DIR}/master_out.csv`
- `Plant CSV path`: `${HIL_BENCH_DIR}/plant_out.csv`
- `Sample time`: `0.001` (1 kHz).
- `Mode`: `external` (real-time slave-driven).

Compile to RT-CGen:

```matlab
slbuild('marine_common_rail_injector')
```

Expected: `marine_common_rail_injector.exe` (Linux: `.elf`) written to
`hil/simulink/codegen/`. This is the standalone real-time executable Simulink
runs in external mode.

## 5. Bench bring-up

### 5.1 Power up Nucleo + connect transport

Per [`hardware-setup-stm32.md`](hardware-setup-stm32.md) §7 - verify
`tethys-master connect --profile marine` shows session ready.

### 5.2 Start the master in DAQ mode

```bash
tethys-master daq start \
  --profile marine \
  --transport udp \
  --a2l hil/fixtures/marine-injector.a2l \
  --rate 1000 \
  --list cylinder_pressure,injector_pulse_us,fuel_temp_c \
  --out hil/recordings/run-$(date +%Y%m%d-%H%M%S).mdf4 \
  --bridge hil/master_out.csv
```

Expected:

```text
[INFO] XCP CONNECT OK
[INFO] DAQ list 0 configured: 3 signals @ 1 kHz, ODT size 12 bytes
[INFO] DAQ STARTED
[INFO] Bridge: writing master_out.csv every 50 ms
```

### 5.3 Start the plant model

```matlab
set_param('marine_common_rail_injector', 'SimulationMode', 'external')
set_param('marine_common_rail_injector', 'SimulationCommand', 'connect')
set_param('marine_common_rail_injector', 'SimulationCommand', 'start')
```

Expected: Simulink scope shows pressure tracking the injector pulse.

### 5.4 Verify closed loop

In a third terminal:

```bash
tail -f hil/recordings/run-*.mdf4 \
  | tethys-master mdf-tail --signals cylinder_pressure,injector_pulse_us
```

Expected: rolling display of the two signals. Pressure should rise when
injector_pulse_us increases.

## 6. Closed-loop demo - marine (common-rail injector)

Goal: 1 kHz DAQ on the slave + 1 kHz plant + 100 Hz CAL writes (master
adjusts injector_pulse_us via XCP CAL) for 5 minutes; record MDF4.

### 6.1 Run the canned demo

```bash
tethys-master demo marine-injector \
  --duration 300 \
  --target udp://192.168.1.10:5555 \
  --plant hil/simulink/codegen/marine_common_rail_injector.elf \
  --record hil/recordings/marine-demo.mdf4 \
  --report hil/reports/marine-demo.html
```

Expected: 5-minute run; final report shows zero DAQ overflows + zero CAL CRC
mismatches + closed-loop steady-state error < 5%.

### 6.2 Verify report

Open `hil/reports/marine-demo.html` in a browser; sections:

- DAQ statistics: count + dropped frames (target: 0).
- CAL statistics: writes attempted / acknowledged / CRC failures.
- Plant statistics: simulation overrun count (target: 0).
- Closed-loop performance: rise time, overshoot, steady-state error.

## 7. Closed-loop demo - space (reaction wheel)

Goal: same as §6 but with the space-profile slave on STM32H7 + space.cmake
build + UART/SxI transport + AES-128 seed-and-key authentication + reaction-
wheel plant model. Watchdog is active; any DAQ tick that misses its deadline
trips the WWDG and the demo logs the trip.

### 7.1 Run the canned demo

```bash
tethys-master demo space-reaction-wheel \
  --duration 300 \
  --target serial:///dev/ttyUSB0?baudrate=115200 \
  --plant hil/simulink/codegen/space_reaction_wheel.elf \
  --record hil/recordings/space-demo.mdf4 \
  --report hil/reports/space-demo.html \
  --auth-key-file hil/keys/space-test.key
```

Expected: 5-minute run; report shows zero WWDG trips, AES auth handshake OK,
and closed-loop torque control within 2% of plant model setpoint.

## 8. Recording artefacts

Per [`demo-recording.md`](demo-recording.md) - the OBS Studio screen capture
plus the MDF4 + HTML report + Simulink scope screenshots are bundled into:

```text
hil/artifacts/<demo>-<YYYYMMDD>/
  recording.mp4
  recording.srt          # closed-captions if available
  master.mdf4
  master.csv             # decimated copy of MDF4 (LibreOffice-friendly)
  plant.csv              # Simulink scope dump
  report.html
  bench-photo.jpg        # phone snap of physical bench
  README.md              # one-paragraph summary
```

Archive into the GitHub Release (see
[`release-process.md`](release-process.md) §7).

## 9. Troubleshooting

| Symptom | Diagnosis | Fix |
| --- | --- | --- |
| Master shows `[WARN] DAQ overflow at frame 12345` | Slave CTO buffer underrun (transport too slow OR DAQ rate too high) | Drop DAQ rate to 500 Hz; verify Ethernet link 100 Mbit/s; for CAN ensure no error frames. |
| Simulink reports "External mode connection refused" | Plant model `.exe`/`.elf` is not running OR firewall blocks port 17725 | Manually start the executable: `./marine_common_rail_injector -external`. |
| `py.tethys_master.__version__` errors `module not found` | `pyenv` mismatch between MATLAB and `uv tool install` location | `pyenv('Version', '/full/path/to/uv/tools/tethys-master/bin/python')`. |
| Closed-loop oscillates uncontrollably | PID gains in the Simulink controller incorrect | Use the canned `--gains-from hil/fixtures/<demo>-tuned.json`. |
| H7 watchdog tripped mid-demo | DAQ tick blocking (a CAL write blocked the DAQ loop) | Verify space profile build has `TETHYS_PROFILE_SPACE=1`; check `space-profile-invariants.mdc` deviations; reduce CAL write rate to 10 Hz. |
| AES seed-and-key handshake fails | Wrong key file OR key length mismatch | Verify `--auth-key-file` is a 16-byte raw key (no PEM, no base64); regenerate via `openssl rand 16 > hil/keys/space-test.key`. |
| Master MDF4 truncated mid-record | Master ran out of disk OR transport disconnected | Check `df -h`; check Nucleo serial log for "ETH link down". |

## 10. Cross-references

- Parent plan section 5 (HIL toolchain - free).
- Parent plan section 9 (Phase 9 HIL + MATLAB integration).
- [ADR-0002 Profile-based build system](../adr/0002-profile-based-build-system.md).
- [ADR-0006 AES-128 seed and key](../adr/0006-aes-128-seed-and-key.md).
- [ADR-0007 Python master, not MATLAB](../adr/0007-python-master-not-matlab.md).
- [Runbook: hardware-setup-stm32.md](hardware-setup-stm32.md).
- [Runbook: demo-recording.md](demo-recording.md).
- [Runbook: release-process.md](release-process.md).
- [asammdf - MDF4 toolkit](https://github.com/danielhrisca/asammdf).
- [MATLAB py interface docs](https://www.mathworks.com/help/matlab/call-python-libraries.html).
