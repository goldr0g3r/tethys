# Transports

> **Audience:** engineer choosing which transport to point
> `tethys-master` at - UDP, TCP, SocketCAN, UART/SxI.
> **Scope:** what each transport supports, how to pick one, OS
> requirements, hardware requirements.
> **Length budget:** 2 pages.
>
> Frozen contract: [ADR-0004 Transport abstraction layer](../../docs/adr/0004-transport-abstraction-layer.md).
> Capability metadata: `TransportInfo` in
> [`master/src/tethys_master/transport/__init__.py`](../src/tethys_master/transport/__init__.py).

## 1. Comparison table

| Transport | OS | Hardware | Use when | Phase |
| --- | --- | --- | --- | --- |
| `loopback` | any | none | Unit / integration tests in-process. | 1 |
| `udp` | any | Ethernet (or `lo`) | LAN bench, simulator on loopback, marine demo over W5500 + STM32. | 1 |
| `tcp` | any | Ethernet | Reliable streaming when bus is lossy (DAQ over WiFi). | 5 |
| `socketcan` | Linux | CANable 2.0 (or any SocketCAN-compatible adapter) | CAN-FD bench; marine CAN-FD demo. | 5 |
| `uart_sxi` | any | USB-UART (FT232RL, CP2102) | Space SxI bench. | 5 |
| `ccsds_cop1_ad` | any | UART or low-rate link | Space production-style retransmit (lab). | 5+ |
| `can_1wire` | Linux | Single-wire CAN transceiver | Space 1-wire fault-tolerant bench. | 8+ |

## 2. Target URI scheme

The CLI accepts a single `--target` URI:

```text
<scheme>://<host-or-device>[:<port>][?<params>]
```

| Scheme | Form | Example |
| --- | --- | --- |
| `udp` | `udp://<host>:<port>` | `udp://192.168.1.10:5555` |
| `tcp` | `tcp://<host>:<port>` | `tcp://192.168.1.10:5555` |
| `can` | `can://<channel>?bitrate=<int>&tx_id=<hex>&rx_id=<hex>` | `can://can0?bitrate=500000&tx_id=0x551&rx_id=0x552` |
| `serial` | `serial://<device>?baudrate=<int>&parity=<N/E/O>&stopbits=<1/2>` | `serial:///dev/ttyUSB0?baudrate=115200&parity=N&stopbits=1` |

The Phase 1 CLI accepts `udp://` only; Phase 5 wires the rest.

## 3. UDP

- Phase: 1.
- Module: [`tethys_master.transport.udp.UdpTransport`](../src/tethys_master/transport/udp.py).
- Defaults: `127.0.0.1:5555` (matches simulator default).
- Loss budget: ADR-0010 row "UDP CTO" - `<= 1e-9/cmd post-retry`.
- Notes: asyncio `DatagramProtocol` backed; MTU honours `TransportInfo.mtu` (1472 by default - 1500 link MTU minus 8-byte UDP header minus 20-byte IPv4 header).

## 4. TCP

- Phase: 5.
- Module: `tethys_master.transport.tcp` (lands in Phase 5 PR).
- Use when transport reliability is mandatory (DAQ over WiFi, debug
  over the internet via a port forward).
- TCP guarantees ordering + reliability, so `TransportInfo.supports_reliable = True`.

## 5. SocketCAN

- Phase: 5.
- Module: [`tethys_master.transport.socketcan`](../src/tethys_master/transport/socketcan.py).
- OS: Linux only (uses the `socket(AF_CAN, SOCK_RAW, CAN_RAW)` family).
- Hardware: CANable 2.0 (USD ~40, parent plan section 5).
- Bring-up:

  ```bash
  sudo ip link set can0 up type can bitrate 500000
  ip -s link show can0
  ```

- Frame format: XCP-over-CAN per ASAM XCP 1.4 Part 3-2; ID pair (tx,
  rx) configured at `XcpClient` construction.

## 6. UART / SxI

- Phase: 5.
- Module: [`tethys_master.transport.uart_sxi`](../src/tethys_master/transport/uart_sxi.py).
- OS: any with [`pyserial`](https://pyserial.readthedocs.io) (parent plan section 5).
- Hardware: FT232RL or CP2102 USB-to-UART adapter.
- Frame format: XCP-on-SxI v1.0 per ASAM XCP 1.4 Part 3-3.
- Loss budget: ADR-0010 row "UART-SxI" - `<= 1e-9/cmd` with COP-1 layered on top, else higher.

## 7. Adding your own transport

The contract is the `Transport` Protocol + `TransportInfo` dataclass
([`api.md`](api.md) §3). To add a new transport:

1. Create a module under `master/src/tethys_master/transport/<name>.py`.
2. Implement `open / close / send / recv` with the documented
   semantics + raise the standard exceptions.
3. Expose an `info: TransportInfo` (use the existing transports as
   reference for `max_burst_loss`, `typical_latency_us`).
4. Add a row to `TransportId` (keep IDs in lockstep with the C
   `tethys_tr_id_t` enum).
5. Add a conformance row to
   [`master/tests/test_transport_conformance.py`](../tests/test_transport_conformance.py).
6. Update this file's §1 table.

Per [ADR-0004](../../docs/adr/0004-transport-abstraction-layer.md), the
interface is **frozen at Phase 5**; new transports may be added but the
methods + return types may not change without a new ADR.

## Cross-references

- [`api.md`](api.md) §3 `tethys_master.transport`.
- [`cli.md`](cli.md) §3.2 `connect --target`.
- [ADR-0004 Transport abstraction layer](../../docs/adr/0004-transport-abstraction-layer.md).
- [ADR-0010 Packet-loss tolerance budget](../../docs/adr/0010-packet-loss-tolerance-budget.md).
- [`docs/research/phase-5-transports-execution.md`](../../docs/research/phase-5-transports-execution.md).
- ASAM XCP 1.4 Part 3 (transport layers).
- [Linux SocketCAN docs](https://www.kernel.org/doc/html/latest/networking/can.html).
- [pyserial docs](https://pyserial.readthedocs.io).
