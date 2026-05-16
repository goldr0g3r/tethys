# Python API

> **Audience:** developer importing `tethys_master` into their own code
> (test harness, MATLAB `py.` call, CI script, custom GUI).
> **Scope:** the three modules that form the supported public surface:
> `tethys_master.protocol`, `tethys_master.transport`,
> `tethys_master.config`. GUI internals are NOT public API.
> **Length budget:** 3 pages.

## 1. Stability promise

The shape declared in this file is the **public** surface. The Phase 11
release will:

- Treat any breaking change to these signatures as a SemVer MAJOR bump.
- Treat additions (new methods, new optional kwargs) as MINOR.
- Treat bug fixes as PATCH.

Anything under `tethys_master.gui.*` or starting with `_` (single
underscore) is **internal** and may change without notice.

## 2. `tethys_master.config`

### `MasterSettings`

```python
from tethys_master.config import MasterSettings

settings = MasterSettings()           # loads from env + .env
settings.profile                       # "marine" | "space"
settings.udp_default_port              # int
```

Pydantic `BaseSettings` model. Env prefix `TETHYS_MASTER_`. Source:
[`master/src/tethys_master/config.py`](../src/tethys_master/config.py).

Full field set: see [`installation.md`](installation.md) §4 environment
variables table.

## 3. `tethys_master.transport`

### `Transport` (Protocol)

Frozen interface per [ADR-0004](../../docs/adr/0004-transport-abstraction-layer.md).

```python
from tethys_master.transport import Transport

class Transport(Protocol):
    async def open(self) -> None: ...
    async def close(self) -> None: ...
    async def send(self, data: bytes) -> None: ...
    async def recv(self, *, timeout: float | None = None) -> bytes: ...
```

Concrete transports also expose:

- `info: TransportInfo` - capability flags + metadata.
- `on_event` setter - register a `Callable[[TransportEvent], None]`
  for out-of-band events (loss / bus-off / reconnect).

### `TransportInfo`

```python
@dataclass(frozen=True, slots=True)
class TransportInfo:
    id: TransportId
    name: str
    mtu: int
    supports_reliable: bool
    supports_ordering: bool
    max_burst_loss: int = 0
    typical_latency_us: int = 0
    typical_loss_per_pkt: float = 0.0
    extra: dict[str, str] = field(default_factory=dict)
```

The C-side mirror is `tethys_tr_descriptor_t` in
[`slave/include/tethys/tethys_transport.h`](../../slave/include/tethys/tethys_transport.h).
Field values are pinned to those structs so MDF4 logs decode the same
way on both sides.

### `TransportId`

```python
class TransportId(IntEnum):
    UNDEFINED = 0
    LOOPBACK = 1
    UDP = 2
    TCP = 3
    CAN_FD = 4
    SOCKETCAN = 5
    UART_SXI = 6
    CCSDS_COP1_AD = 7
    CCSDS_TM = 8
    CAN_1WIRE = 9
```

### Concrete transports

| Class | Module | Phase | Notes |
| --- | --- | --- | --- |
| `LoopbackTransport` | `tethys_master.transport.loopback` | 1 | In-memory; used in tests. |
| `UdpTransport` | `tethys_master.transport.udp` | 1 | asyncio datagram protocol. |
| `SocketCanTransport` | `tethys_master.transport.socketcan` | 5 | Linux SocketCAN; CANable 2.0 baseline. |
| `UartSxiTransport` | `tethys_master.transport.uart_sxi` | 5 | `pyserial`-backed UART. |

## 4. `tethys_master.protocol`

### `XcpClient`

```python
from tethys_master.protocol.client import XcpClient, XcpProtocolError
from tethys_master.transport.udp import UdpTransport
import asyncio

async def main() -> None:
    transport = UdpTransport("127.0.0.1", 5555)
    async with XcpClient(transport, default_timeout_s=0.5) as client:
        connect_response = await client.connect(mode=0)
        version = await client.get_version()
        status = await client.get_status()
        # ... SET_MTA / UPLOAD / DOWNLOAD / BUILD_CHECKSUM ...
```

The async context manager calls `open()` + `connect()` on enter and
`disconnect()` + `close()` on exit. Methods raise `XcpProtocolError` on
slave-side rejection, `asyncio.TimeoutError` on missed deadlines, or
`OSError` on transport faults.

Method coverage (Phase 2 complete):

| Method | XCP §       | Notes |
| --- | --- | --- |
| `connect(mode=0)` | 1.3.2.4 | Returns `ConnectResponse`. |
| `disconnect()` | 1.3.2.5 | Idempotent. |
| `get_version()` | 1.3.2.7 | Returns `GetVersionResponse`. |
| `get_status()` | 1.3.2.6 | Returns `GetStatusResponse`. |
| `synch()` | 1.3.3.7 | Recovers from CTO timeouts. |
| `set_mta(addr, ext=0)` | 1.3.3.2 | MTA bookkeeping. |
| `upload(n)` | 1.3.3.5 | Read N bytes. |
| `short_upload(addr, n, ext=0)` | 1.3.3.6 | Address-carrying single-shot read. |
| `download(data)` | 1.3.3.3 | Write bytes. |
| `build_checksum(blocks)` | 1.3.3.4 | Master-side CRC. |

### Response types

All response dataclasses live in
[`master/src/tethys_master/protocol/frame.py`](../src/tethys_master/protocol/frame.py).
They are `dataclass(frozen=True, slots=True)` so they are hashable and
cheap to pass around.

### A2L parser

```python
from tethys_master.protocol.a2l import A2lParser

parser = A2lParser.from_file("hil/fixtures/marine-injector.a2l")
parser.measurements             # dict[name, Measurement]
parser.characteristics          # dict[name, Characteristic]
```

Backed by [Sauci/pya2l](https://github.com/Sauci/pya2l) (BSD-3). The
parser is tested via the round-trip suite at
[`master/tests/test_a2l.py`](../tests/test_a2l.py) - the same suite the
CI `a2l-roundtrip.yml` workflow runs on every PR touching A2L.

## 5. Examples

### 5.1 Connect + read one byte

```python
async with XcpClient(UdpTransport("192.168.1.10", 5555)) as client:
    await client.set_mta(0x10000100, ext=0)
    data = await client.upload(1)
    print(f"byte at 0x10000100 = 0x{data[0]:02x}")
```

### 5.2 Bind to a SocketCAN transport (Linux)

```python
from tethys_master.transport.socketcan import SocketCanTransport

transport = SocketCanTransport(channel="can0", tx_id=0x551, rx_id=0x552)
async with XcpClient(transport) as client:
    await client.connect()
    # ...
```

### 5.3 Drive from MATLAB

In MATLAB Command Window (with `pyenv` already configured):

```matlab
client = py.tethys_master.protocol.client.XcpClient(
    py.tethys_master.transport.udp.UdpTransport("127.0.0.1", py.int(5555)));
% Use the synchronous wrapper that wraps asyncio.run().
py.asyncio.run(client.connect());
```

See [`docs/runbooks/hil-bench-setup.md`](../../docs/runbooks/hil-bench-setup.md)
§3.2 for the `py.` interface setup.

## 6. Module map

```text
master/src/tethys_master/
  __init__.py            # __version__
  cli.py                 # click CLI entry point
  config.py              # MasterSettings
  logging_setup.py       # structlog config
  py.typed               # PEP 561 marker

  protocol/
    __init__.py          # ASAM XCP 1.4 surface
    client.py            # XcpClient async API
    frame.py             # ConnectResponse / GetVersionResponse / ...
    a2l.py               # pya2l-backed parser
    a2l_roundtrip.py     # round-trip fixture for CI

  transport/
    __init__.py          # Transport protocol + TransportInfo + IDs
    loopback.py
    udp.py
    socketcan.py
    uart_sxi.py

  gui/                   # PySide6 application; internal API
  profiles/              # Profile enum + metadata (parent §3.3)
```

## Cross-references

- [`cli.md`](cli.md).
- [`transports.md`](transports.md).
- [`profiles.md`](profiles.md).
- [ASAM XCP 1.4 Part 2 §1.3.2](https://www.asam.net/standards/detail/mcd-1-xcp/) - command spec.
- [ADR-0004 Transport abstraction layer](../../docs/adr/0004-transport-abstraction-layer.md).
- [ADR-0007 Python master, not MATLAB](../../docs/adr/0007-python-master-not-matlab.md).
