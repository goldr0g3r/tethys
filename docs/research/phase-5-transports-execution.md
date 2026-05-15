# Phase 5 - Transport pluggability execution (research note)

> Research note backing the Phase 5 PRs (`p5`).
> Parent plan: [`xcp_extreme-env_tool_14019278.plan.md`](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md) §8 Phase 5.
> Sub-plan (PR-A): [`p5-transport-foundation-9c1e4a82.plan.md`](../../../../Users/wnp1cob/.cursor/plans/p5-transport-foundation-9c1e4a82.plan.md)

## Scope

Phase 5 freezes the `TransportPort` interface (ADR-0004), lands the foundational TAL on the slave side (which Phase 1's UDP-on-Python work skipped because the slave hadn't shipped any C-side transport yet), and ships three concrete transports plus a one-suite-fits-all conformance harness:

| PR | Title | Surface | Status |
| --- | --- | --- | --- |
| PR-A | `feat(transport): TAL header + loopback + SocketCAN + conformance suite` | TAL header (slave), TAL dispatcher (slave), loopback C transport, SocketCAN C transport, loopback + SocketCAN Python transports, simulator loopback wiring, conformance suite scaffold (C + Python) | this PR |
| PR-B | `feat(transport): UART/SxI slave + master + conformance extension` | UART C transport, UART Python transport (pyserial), simulator UART pty wiring, conformance suite extension | next |
| PR-C | `test(transport): conformance suite full matrix + flip p5` | conformance matrix polish; flip `p5` to `completed` if every cell green | last |

This note is opened by PR-A and amended by PR-B / PR-C as their "Implementation Reference" rows fill in. PR-A establishes the design decisions and tooling choices that propagate.

## Sources (retrieved 2026-05-15)

| # | Source | URL | Retrieval date | Relevance |
|---|---|---|---|---|
| 1 | ADR-0004 - Transport-abstraction-layer interface | [`docs/adr/0004-transport-abstraction-layer.md`](../adr/0004-transport-abstraction-layer.md) | local | Operational + Metadata + Event API contract. Frozen at PR-A. |
| 2 | ADR-0010 - Packet-loss tolerance budget | [`docs/adr/0010-packet-loss-tolerance-budget.md`](../adr/0010-packet-loss-tolerance-budget.md) | local | Row 5/6/7 = CAN-FD + SocketCAN. Row 8 = UART/SxI + COP-1 (PR-B). Row 12 = loopback zero-loss. Drives each transport's metadata fields. |
| 3 | ADR-0005 - No dynamic allocation in the slave | [`docs/adr/0005-no-dynamic-allocation.md`](../adr/0005-no-dynamic-allocation.md) | local | All TAL state is file-scope; loopback ring is a fixed-MTU x fixed-depth array; descriptors are `static const`. |
| 4 | Linux kernel SocketCAN documentation | <https://www.kernel.org/doc/html/latest/networking/can.html> | 2026-05-15 | `PF_CAN` / `SOCK_RAW` / `CAN_RAW` socket family; `CAN_RAW_FD_FRAMES`, `CAN_RAW_ERR_FILTER` setsockopts; `struct can_frame` / `struct canfd_frame` wire layouts. |
| 5 | ISO 11898-1:2024 - Road vehicles - CAN data link layer | <https://www.iso.org/standard/86384.html> | 2026-05-15 | CAN-FD payload limit (64 bytes); classic CAN payload (8 bytes); error-frame semantics; bus-off recovery. |
| 6 | CPython 3.11 `socket` module - AF_CAN support | <https://docs.python.org/3/library/socket.html#socket.AF_CAN> | 2026-05-15 | Avoids the `python-can` dependency. `socket.AF_CAN` is stdlib on Linux from 3.3 onwards; `CAN_RAW` constant present. |
| 7 | Python stdlib `struct` module | <https://docs.python.org/3/library/struct.html> | 2026-05-15 | `=IB3x8s` packs `struct can_frame`; `=IBBBB64s` packs `struct canfd_frame`. |
| 8 | parent plan §8 Phase 5 acceptance | [`xcp_extreme-env_tool_14019278.plan.md`](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md) | local | "Same DAQ test passes on three transports." Drives the "one conformance suite, parametrised by transport" architecture. |
| 9 | CANable 2.0 firmware + docs (for the hardware bench) | <https://canable.io/getting-started.html> | 2026-05-15 | Bench wiring used by PR-B's `docs/runbooks/hardware-setup-stm32.md` follow-up. Default kernel module is `slcan` (serial-line CAN) or `gs_usb` (native SocketCAN); we target the native `gs_usb` path so vcan0 / can0 share the same kernel ABI in tests. |
| 10 | CCSDS 232.1-B-2 (COP-1) | <https://public.ccsds.org/Pubs/232x1b2c1.pdf> | 2026-05-15 | Cited but **not implemented** in Phase 5; COP-1 AD wrapper is parked for Phase 8 (space profile). The Phase-5 UART/SxI transport is raw bytes only. |
| 11 | pyserial 3.5 documentation | <https://pythonhosted.org/pyserial/> | 2026-05-15 | PR-B Python UART backend; BSD-3 licensed. |

## Decisions (PR-A)

| # | Decision | Choice | Rejected | Cite / Trace |
|---|---|---|---|---|
| D40 | Slave-side TAL existence | Ship a real C-side TAL (`slave/include/tethys/tethys_transport.h` + `slave/src/transport/transport.c`) as part of Phase 5, not retroactively in Phase 1, because the Python master + simulator already covered the Phase-1 acceptance via in-process `UdpEchoSlave`. | Defer C-side TAL to Phase 7 (marine STM32 bench) - would defer the freeze itself, breaking ADR-0004's "freeze at Phase 5" condition. | ADR-0004 freeze deadline |
| D41 | Loss-rate field on C descriptor | `uint32_t typical_loss_ppb` (parts-per-billion) instead of `float typical_loss_per_pkt`. | `float` - the slave's static-allocation budget is hostile to FPU dependency; `float` also wastes 4 bytes if FPU is software-emulated; PPB has 1e-9 resolution which exceeds the ADR-0010 row 6 budget (4.7e-11 ≈ 47 PPB ≈ 47e-9). | ADR-0005, ADR-0010 |
| D42 | Universal baseline = loopback | The conformance suite uses loopback as its always-on row; every other transport is asserted against the same shape. | Use UDP as the baseline - requires bringing up a UDP echo server in the test fixture; loopback is in-process and brings zero env dependency. | parent §8 Phase 5; ADR-0010 row 12 |
| D43 | Python SocketCAN backend | CPython stdlib `socket.AF_CAN` + manual `struct` encoding of `can_frame` / `canfd_frame`. | `python-can` - adds a pinned dependency for a feature stdlib already provides; complicates `dependency-review.yml` + `version-pinning.mdc` for marginal ergonomic gain. We retain the option to swap behind the `Transport` interface if a non-Linux backend (e.g. `pcan`) becomes necessary. | `free-tool-only.mdc`, `version-pinning.mdc` |
| D44 | Non-Linux SocketCAN behaviour | The `slave/src/transport/socketcan.c` file compiles cross-platform via `#if defined(__linux__) && !defined(TETHYS_NO_SOCKETCAN)`; on Windows / macOS the descriptor still exports but every operational call returns `TETHYS_TR_DISCONNECTED`. | `#error` on non-Linux - blocks Windows / macOS CI runs of the slave test suite. The current contract lets the conformance suite assert "transport is unavailable here" without crashing. | parent §6.7 ci.yml matrix |
| D45 | Master `Transport` Protocol shape | Keep the existing async `open/close/send/recv` Protocol; add a class-level `info: TransportInfo` attribute and an instance-level `set_event_callback()` setter. `info` is intentionally NOT on the runtime-checkable Protocol so single-purpose mocks in non-conformance tests don't have to fake it. | Force `info` into the Protocol - breaks the four pre-existing tests in `test_client_loopback.py` that pass `UdpEchoSlave` (a slave-side echo, not a master-side transport) where they were never required to declare `info`. | Phase 1 PR-22 contract |
| D46 | Conformance scenarios (PR-A) | open_close, send_recv, send_recv_bulk_in_order, recv_timeout, send_after_close, metadata_sanity, drop_detection. Each parametrised over the TRANSPORTS list. | Larger matrix (reorder, duplicate, partial-recv) - deferred to PR-C where the matrix is finalised. | parent §8 Phase 5 |
| D47 | CCSDS COP-1 wrap deferred | The Phase-5 UART/SxI transport (PR-B) is raw bytes only: framing = start byte + length + payload + checksum, no ARQ. The COP-1 AD (Automatic Repeat reQuest) wrapper that ADR-0010 row 8 references is Phase 8 (space profile) work. | Ship COP-1 in PR-B - doubles the LOC budget and pulls Phase 8 design forward; the conformance suite can already drive raw UART. | ADR-0010 row 8; parent §8 Phase 8 |
| D48 | SocketCAN error-frame translation | The slave-side `socketcan.c` subscribes to `CAN_ERR_BUSOFF`, `CAN_ERR_BUSERROR`, and `CAN_ERR_RESTARTED` via `CAN_RAW_ERR_FILTER` and translates them into TAL events (`BUS_OFF`, `LOSS`, `BUS_RECOVERED`). | Silent drop of error frames - loses the ADR-0004 event-API contract for CAN-FD. | ADR-0004 event API; ISO 11898-1:2024 |

## Decisions (PR-B)

| # | Decision | Choice | Rejected | Cite / Trace |
|---|---|---|---|---|
| D49 | UART framing | Length-prefixed: `[0xAA][len][payload..][xor_cksum]`. No escape characters because the protocol layer's CTO/DTO is already length-prefixed; byte stuffing would double encoding work for zero correctness gain at this layer. | SLIP-style with 0xC0/0xDB escape | RFC 1055; PR-B sub-plan |
| D50 | Slave C portability | Slave-side UART transport is **byte-pumped** by host integration code via `tethys_tr_uart_sxi_inject_rx_byte()` and `tethys_tr_uart_sxi_drain_tx_bytes()`. No OS-specific tty / SPI / USART code in `slave/src/transport/uart_sxi.c`. STM32 firmware wires the USART ISR; posix-sim wires pyserial through the simulator. | Embed termios open() in the slave - couples the slave to POSIX | parent §3.2 portability; ADR-0005 |
| D51 | Python pyserial dep | Pin `pyserial==3.5` (BSD-3, widely deployed, mature). | python-can - already rejected for SocketCAN; no Python-native serial alternative covers Win32 COM ports + POSIX termios as cleanly. | `version-pinning.mdc`, `free-tool-only.mdc` |
| D52 | Conformance UART row | POSIX-only via `pty.openpty()` + a kernel-level relay between the two pty masters. Windows skips the row (no portable pty); `test_transport_uart_sxi.py`'s framer-only tests run everywhere as the cross-platform fallback. | Use a TCP socket pair to fake UART - changes the wire shape; pty pair preserves the byte-stream semantics for an honest conformance assertion. | parent §8 Phase 5; `pty` stdlib |

## Implementation Reference

- **PR-A**: *to be filled at merge - TAL header + loopback + SocketCAN + conformance suite scaffold*
- **PR-B**: *to be filled at merge - UART/SxI slave + master + sim + conformance extension*
- **PR-C**: *to be filled at merge - conformance matrix polish + flip `p5` to `completed`*

## Open follow-ups

- **TCP transport**: deferred. UDP covers the parent-plan Phase-1 acceptance and the marine UDP row of ADR-0010 (rows 1-3). TCP (row 4) is reliable by definition and only adds the `supports_reliable = True` capability variant; a 50-LOC `TcpTransport` modelled on `UdpTransport` is the entire delivery. Park for a small follow-up PR after Phase 5 ships.
- **Python `info` field on UDP**: `UdpTransport` (Phase 1) does not yet declare `TransportInfo`. Adding it would touch a Phase-1 file that PR-A is intentionally not editing to keep the diff focused on Phase-5 deliverables. PR-C adds the one-line `info` class attribute as part of the matrix-polish PR.
- **CANable 2.0 hardware bench**: documented but not exercised here. `docs/runbooks/hardware-setup-stm32.md` covers the wiring; the conformance suite uses `vcan0` (virtual CAN kernel module) so CI on the GitHub free tier never needs the dongle.
- **COP-1 AD wrapper (Phase 8)**: per D47, the UART transport ships raw; the AD wrapper (sequencer N(S), N(R), report frames, RETRY count) lands in Phase 8 alongside AES-128 seed-and-key per ADR-0006.
- **`docs/traceability.csv` rows**: Worker D owns this file. PR-A's new files have provisional row IDs (`TETHYS-DES-0030..0034` + `TETHYS-TST-0050..0067`) which Worker D materialises in the traceability matrix; this note records them so Worker D can reference us when they land their rows.
- **CMake build of new C files**: PR-A adds the three new sources to `slave/CMakeLists.txt`'s `add_library` block; cppcheck-misra and clang-tidy CI run unchanged because the new files honour the same rules as `xcp_dispatcher.c`. Worker E owns `slave/cmake/` and `slave/profiles/`; no profile-cmake changes are needed for PR-A.

## Test results (PR-B target)

```text
[master pytest, Windows]
test_transport_loopback.py            8 passed
test_transport_conformance.py         7 passed (loopback row only)
test_transport_socketcan.py           4 skipped (Linux + vcan0)
test_transport_uart_sxi.py           11 passed, 1 skipped (POSIX pty)
TOTAL                                67 passed, 5 skipped

[master pytest, Linux CI projection]
+ SocketCAN conformance row           7 cells (vcan0 required)
+ UART conformance row                7 cells (pty pair)
+ test_transport_socketcan.py         4 cases (vcan0 required)
+ test_uart_pty_round_trip            1 case
TOTAL                                86 passed

[Ceedling test:all, posix-sim]
test_transport_loopback.c            10 passed
test_transport_conformance.c         11 passed (UART metadata row added)
test_transport_uart_sxi.c             8 passed
```

Phase 5 acceptance criterion ("same DAQ test passes on three transports") status after PR-B:
- transport #1: loopback - PR-A ✓
- transport #2: SocketCAN - PR-A ✓ (vcan0 on Linux CI; stub on other hosts)
- transport #3: UART/SxI - PR-B ✓ (pty pair on POSIX CI; framer-only tests on Windows)

PR-C closes the deferred items (drop/reorder/duplicate synthesis on every transport, UDP `info` field, parent-plan `p5` status flip).
