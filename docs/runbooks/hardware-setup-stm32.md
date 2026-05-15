# Runbook - STM32 hardware setup (marine + space)

> Audience: an engineer assembling the STM32 hardware bench for the marine
> (Phase 7) or space (Phase 8) demos.
> Goal: from "unboxed Nucleo board" to "Tethys slave firmware running, master
> tool connected via UDP / CAN / UART, blink-of-life observed". Wall-clock
> target: **60 minutes per board** the first time, **<10 minutes** for
> subsequent boards.
> Style: explicit parts list with USD costs, wiring diagrams in text, commands
> for both shells, troubleshooting matrix.
>
> Implements parent plan §5 (low-cost hardware) and §7 (Phase 7) + §8 (Phase 8).
> Companion: [`docs/runbooks/hil-bench-setup.md`](hil-bench-setup.md) covers
> the closed-loop bench wiring.

## Table of contents

1. [Parts list and budget](#1-parts-list-and-budget)
2. [Toolchain install](#2-toolchain-install)
3. [Wiring - marine profile (STM32F4 / F7)](#3-wiring---marine-profile-stm32f4--f7)
4. [Wiring - space profile (STM32H7)](#4-wiring---space-profile-stm32h7)
5. [First-time bring-up](#5-first-time-bring-up)
6. [Flashing the slave firmware](#6-flashing-the-slave-firmware)
7. [Connecting from `tethys-master`](#7-connecting-from-tethys-master)
8. [Troubleshooting](#8-troubleshooting)
9. [Cross-references](#9-cross-references)

---

## 1. Parts list and budget

Per parent plan §5 the hardware budget is intentionally low so the project is
reproducible on a student budget. Prices reflect 2026 retail.

### 1.1 Marine bench

| Part | Vendor SKU / equivalent | USD | Used for |
| --- | --- | --- | --- |
| NUCLEO-F767ZI | ST P/N NUCLEO-F767ZI | ~38 | Slave MCU (Cortex-M7 @ 216 MHz, Ethernet, 2x CAN) |
| MCP2562FD-E/SN CAN-FD transceiver breakout | Adafruit / Sparkfun | ~6 | Buffer 3.3 V Nucleo CAN -> 5 V wires |
| CANable 2.0 (CAN-FD USB) | ProtoFusion / OpenLab | ~40 | Master bus interface |
| Cat-6 Ethernet cable (1 m) | any | ~5 | Direct connect to PC for UDP transport |
| Jumper wires + breadboard | any | ~10 | Wiring |
| Bench PSU (5 V / 1 A USB) | any | ~10 | Optional - Nucleo can be USB-powered |
| **Marine bench subtotal** | | **~109** | |

### 1.2 Space bench

| Part | Vendor SKU / equivalent | USD | Used for |
| --- | --- | --- | --- |
| NUCLEO-H753ZI | ST P/N NUCLEO-H753ZI | ~38 | Slave MCU (Cortex-M7 @ 480 MHz, ECC RAM, 3x CAN-FD) |
| FT232RL USB-UART | Sparkfun / FTDI | ~15 | UART/SxI bench wire |
| MCP2562FD-E/SN | (same as marine) | ~6 | 1-wire FT CAN transceiver |
| Cat-6 Ethernet cable | (same) | ~5 | |
| Jumper wires + breadboard | (same) | ~10 | |
| **Space bench subtotal** | | **~74** | |

### 1.3 Aspirational extras (NOT required for academic demos)

| Part | USD | Use case |
| --- | --- | --- |
| GR716A LEON3FT eval kit | ~3000 | Real space-grade processor |
| RAD750 eval (Boeing) | not commercially priced | Heritage flight processor |
| Vorago VA416xx eval | ~500 | Commercial rad-hard alternative |
| Thermal vacuum chamber slot | n/a | ECSS-E-ST-10-03C qualification |

These are documented in [ADR-0008](../adr/0008-license-free-toolchain.md) §gaps.

## 2. Toolchain install

### 2.1 ARM cross-compiler

```powershell
winget install ArmGnuToolchain
```

```bash
# Ubuntu
sudo apt-get install -y gcc-arm-none-eabi
# macOS
brew install --cask gcc-arm-embedded
```

Verify:

```powershell
arm-none-eabi-gcc --version
```

```bash
arm-none-eabi-gcc --version
```

Expected: `arm-none-eabi-gcc (Arm GNU Toolchain ...) 14.x`.

### 2.2 ST-Link tooling

```powershell
winget install stlink-org.stlink-tools
```

```bash
# Ubuntu
sudo apt-get install -y stlink-tools
# macOS
brew install stlink
```

Verify with the Nucleo unplugged then plugged:

```powershell
st-info --probe
```

```bash
st-info --probe
```

Expected: `Found 1 stlink programmers ... serial: <SERIAL> ... descr: STM32F7xx`.

### 2.3 Linux udev permissions

Skip if Windows / macOS. On Linux:

```bash
sudo tee /etc/udev/rules.d/99-stlink.rules <<'EOF'
SUBSYSTEM=="usb", ATTR{idVendor}=="0483", ATTR{idProduct}=="3748", MODE="0666"
SUBSYSTEM=="usb", ATTR{idVendor}=="0483", ATTR{idProduct}=="374b", MODE="0666"
SUBSYSTEM=="usb", ATTR{idVendor}=="0483", ATTR{idProduct}=="374e", MODE="0666"
SUBSYSTEM=="usb", ATTR{idVendor}=="0483", ATTR{idProduct}=="374f", MODE="0666"
EOF
sudo udevadm control --reload-rules && sudo udevadm trigger
```

Re-plug the Nucleo. `st-info --probe` should now succeed without sudo.

### 2.4 SocketCAN (Linux only) for CANable 2.0

```bash
sudo apt-get install -y can-utils
sudo modprobe gs_usb
# Plug CANable 2.0 - it appears as can0
sudo ip link set can0 up type can bitrate 500000 dbitrate 2000000 berr-reporting on fd on
candump can0   # smoke test
```

Windows: install [PCAN-View](https://www.peak-system.com/) (free) or use
[KvaserCanKing](https://www.kvaser.com/) - both speak CANable 2.0 firmware via
the standard slcan / gs_usb interface.

## 3. Wiring - marine profile (STM32F4 / F7)

### 3.1 Pinout table

| Function | Nucleo F767ZI pin | Note |
| --- | --- | --- |
| CAN1 TX | PD1 | Through CN12 |
| CAN1 RX | PD0 | Through CN12 |
| CAN2 TX | PB6 (optional) | Redundant bus |
| CAN2 RX | PB5 (optional) | |
| Ethernet | LAN8742 onboard | RJ45 on CN14 |
| User UART | USART3 PD8/PD9 | Onboard ST-Link VCP |
| User LED | PB14 (LD3 red) | Slave heartbeat |
| Button (user) | PC13 | Soft-reset of XCP state |

### 3.2 Wiring diagram

```text
                          +--------------------+
            +-------------|  NUCLEO-F767ZI     |
            |             |                    |
   PC  USB <-> CN1 (PWR + ST-Link VCP UART)   |
            |             |                    |
            |   CN12 PD1->| CAN1 TX  ---+      |
            |   CN12 PD0->| CAN1 RX     |      |
            |             |             |      |
            |             | +---v---+   |      |
            |             | |MCP2562|<--|      |
            |             | +---^---+   |      |
            |             |     |       |      |
            |             |     +-->----+--> CAN bus
            |             |                    |
            |   CN14   <->| Ethernet RJ45  --> Direct cable to PC NIC
            +-------------+--------------------+
```

### 3.3 Cable check

After wiring:

```bash
# CAN bus continuity (with no traffic):
candump can0,0:0,#FFFFFFFF
```

Expected: no output (no errors). Tap a 5 V briefly on CANH while watching;
expected: error frame appears.

## 4. Wiring - space profile (STM32H7)

### 4.1 Pinout table

| Function | Nucleo H753ZI pin | Note |
| --- | --- | --- |
| FDCAN1 TX | PD1 | Through CN12 |
| FDCAN1 RX | PD0 | Through CN12 |
| FDCAN2 TX | PB13 | 1-wire FT CAN bus |
| FDCAN2 RX | PB12 | |
| UART4 TX | PA0 | Space SxI bench wire |
| UART4 RX | PA1 | |
| WWDG output | onboard | Watchdog feedback (LED) |
| ECC RAM region | 64 KB onboard | tethys_ecc_* wrapper target |

### 4.2 Wiring diagram

```text
                          +--------------------+
            +-------------|  NUCLEO-H753ZI     |
            |             |                    |
   PC  USB <-> CN1 (PWR + ST-Link VCP UART)   |
            |             |                    |
            |   CN12 PB13>| FDCAN2 TX     +--->|
            |   CN12 PB12>| FDCAN2 RX     | 1-wire FT
            |             |                    |
            |   CN9  PA0->| UART4 TX  --+      |
            |   CN9  PA1->| UART4 RX    |      |
            |             |             |      |
            |             | +---v---+   |      |
            |             | |FT232RL|<--+      |
            |             | +---^---+          |
            |             |     |              |
            |             |     +-->-- PC USB (appears as /dev/ttyUSB0)
            +-------------+--------------------+
```

## 5. First-time bring-up

### 5.1 Power on

```powershell
# Plug Nucleo into PC USB; LED LD1 (red) should light immediately.
```

```bash
# Same.
```

Expected: LD1 (red) solid, LD6 (green, ST-Link) blinking 1 Hz.

### 5.2 Smoke flash a vendor blink

```bash
# Download ST's NUCLEO blink demo from CMSIS pack, or use:
git clone --depth=1 https://github.com/STMicroelectronics/STM32CubeF7.git /tmp/cubeF7
cd /tmp/cubeF7/Projects/STM32F767ZI-Nucleo/Examples/GPIO/GPIO_IOToggle
# Build with arm-none-eabi-gcc using the supplied Makefile or with CMake.
make
st-flash write build/gpio_iotoggle.bin 0x8000000
```

Expected: `st-flash 1.x.x` opens connection, writes ~10 KB, verifies, resets,
LD3 (red) blinks.

## 6. Flashing the slave firmware

### 6.1 Build the slave for the right target

```powershell
cd slave
cmake -S . -B build/stm32f7 `
  -G "Ninja" `
  -DCMAKE_TOOLCHAIN_FILE=cmake/toolchains/arm-cortex-m7.cmake `
  -DTETHYS_PROFILE=marine `
  -DTETHYS_PLATFORM=stm32f7 `
  -DCMAKE_BUILD_TYPE=Release
cmake --build build/stm32f7
```

```bash
cd slave
cmake -S . -B build/stm32f7 \
  -G Ninja \
  -DCMAKE_TOOLCHAIN_FILE=cmake/toolchains/arm-cortex-m7.cmake \
  -DTETHYS_PROFILE=marine \
  -DTETHYS_PLATFORM=stm32f7 \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build/stm32f7
```

Expected: `tethys_slave.elf` (~80 KB) + `tethys_slave.bin` (~50 KB) emitted
into `build/stm32f7/`.

### 6.2 Flash

```powershell
st-flash write build/stm32f7/tethys_slave.bin 0x8000000
```

```bash
st-flash write build/stm32f7/tethys_slave.bin 0x8000000
```

Expected: ~3 seconds, "Verification ... done", board resets, LD3 starts
blinking at the configured heartbeat rate (1 Hz by default).

### 6.3 Variant - flash space profile to H7

```bash
cd slave
cmake -S . -B build/stm32h7 \
  -G Ninja \
  -DCMAKE_TOOLCHAIN_FILE=cmake/toolchains/arm-cortex-m7.cmake \
  -DTETHYS_PROFILE=space \
  -DTETHYS_PLATFORM=stm32h7 \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build/stm32h7
st-flash --connect-under-reset write build/stm32h7/tethys_slave.bin 0x8000000
```

The `--connect-under-reset` flag is needed because the H7 enters low-power
on boot.

## 7. Connecting from `tethys-master`

### 7.1 UDP transport (marine; Ethernet cable to PC)

```powershell
$env:TETHYS_TARGET = "udp://192.168.1.10:5555"  # Nucleo default IP
uv run tethys-master connect --profile marine --transport udp `
  --a2l docs/architecture/fixtures/marine-demo.a2l
```

```bash
export TETHYS_TARGET="udp://192.168.1.10:5555"
uv run tethys-master connect --profile marine --transport udp \
  --a2l docs/architecture/fixtures/marine-demo.a2l
```

Expected output:

```text
[INFO] Resolved A2L: marine-demo.a2l (123 measurements, 45 characteristics)
[INFO] UDP transport: 192.168.1.10:5555 - link up
[INFO] XCP CONNECT - protocol 1.4 - max CTO 8, max DTO 256
[INFO] XCP GET_VERSION - 0x0104
[INFO] XCP GET_STATUS - 0x80 (RESUME OK; DAQ ready)
[INFO] Session ready.
```

### 7.2 CAN transport (marine or space; CANable 2.0)

```bash
# Linux only
sudo ip link set can0 up type can bitrate 500000 dbitrate 2000000 fd on
export TETHYS_TARGET="can://can0?txid=0x100&rxid=0x101&fd=true"
uv run tethys-master connect --profile marine --transport can \
  --a2l docs/architecture/fixtures/marine-demo.a2l
```

### 7.3 UART transport (space; FT232RL)

```bash
export TETHYS_TARGET="serial:///dev/ttyUSB0?baudrate=115200"
uv run tethys-master connect --profile space --transport sxi \
  --a2l docs/architecture/fixtures/space-demo.a2l
```

## 8. Troubleshooting

| Symptom | Diagnosis | Fix |
| --- | --- | --- |
| `st-info --probe` reports `unknown chip id` | Board powered off OR ST-Link firmware too old | Update ST-Link firmware via `st-flash --reset` then [STSW-LINK007](https://www.st.com/en/development-tools/stsw-link007.html). |
| `st-flash` aborts with `Verification failed` | Flash write-protect or option bytes locked | `st-flash unlock`; if persistent, `st-info --probe` and verify the chip is unlocked. |
| Nucleo F767ZI Ethernet does not auto-negotiate | Cat-5 cable instead of Cat-5e/6, or solid-conductor short cable | Use Cat-6, length >= 1 m. |
| CANable 2.0 shows `Operation not supported` | Module `gs_usb` not loaded | `sudo modprobe gs_usb`; persist via `/etc/modules-load.d/`. |
| H7 ECC double-bit error reported in serial log | EDAC scrubbing detected uncorrectable; expected during fault-injection demo | Document in `docs/runbooks/incident-and-defect.md` post-mortem; recover via PHY reset. |
| `tethys-master` reports `A2L parse error: XCP_IP_VERSION missing` | A2L file is older spec OR mismatched profile | Open the .a2l in a text editor; ensure `IF_DATA XCP` block present; regenerate via `tethys-master a2l-gen` if needed. |
| Firmware boots but no XCP response on UDP | Wrong IP / wrong port / firewall on PC | `ping 192.168.1.10`; disable PC firewall briefly; check Nucleo serial log for "ETH link up". |
| `arm-none-eabi-gcc` not on PATH | Toolchain install incomplete | Add `<install>/bin` to PATH; re-open shell. |

## 9. Cross-references

- Parent plan section 5 (hardware budget; CANable 2.0 + STM32 Nucleo).
- Parent plan section 7 (Phase 7 marine target STM32F4/F7).
- Parent plan section 8 (Phase 8 space target STM32H7 ECC RAM).
- [ADR-0002 Profile-based build system](../adr/0002-profile-based-build-system.md).
- [Runbook: hil-bench-setup.md](hil-bench-setup.md).
- [Runbook: release-process.md](release-process.md) - cross-compiles run via
  release.yml's `build-slave-tarball` job.
- [ST RM0410 Reference Manual (STM32F76x/77x)](https://www.st.com/resource/en/reference_manual/rm0410-stm32f76xxx-and-stm32f77xxx-advanced-armbased-32bit-mcus-stmicroelectronics.pdf).
- [ST RM0433 Reference Manual (STM32H743/753)](https://www.st.com/resource/en/reference_manual/rm0433-stm32h742-stm32h743753-and-stm32h750-value-line-advanced-armbased-32bit-mcus-stmicroelectronics.pdf).
- [CANable 2.0 user guide](https://canable.io/getting-started.html).
- [stlink-org/stlink](https://github.com/stlink-org/stlink) - open-source ST-Link tools.
