"""SocketCAN transport for the Tethys master (Linux + CANable 2.0 bench).

Uses the Python standard library's ``socket.AF_CAN`` support (Linux-only) to
talk to a SocketCAN interface (``can0``, ``vcan0`` for virtual CAN, etc.) and
exchange XCP CTO/DTO frames as classic CAN or CAN-FD frames.

Cite: ADR-0004 (transport-abstraction-layer interface)
Cite: ADR-0010 row 7 (SocketCAN host-side budget)
Cite: ISO 11898-1:2024 (CAN data-link layer)
Trace: docs/traceability.csv row TETHYS-DES-0032 (lands at PR-10)

Design choices (vs the alternatives):

1. **stdlib ``socket.AF_CAN``** rather than ``python-can``:
   - ``socket.AF_CAN`` is in CPython 3.11+ on Linux at zero dependency cost.
   - ``python-can`` is a fine library but adds another pinned dependency for
     a project that explicitly aims to minimise its dep footprint
     (``free-tool-only.mdc`` + ``version-pinning.mdc``). We keep the option
     of swapping to ``python-can`` later behind the same ``Transport``
     interface if/when an interface backend forces us off raw sockets.

2. **Linux-only at import time**: the module imports on every OS, but the
   constructor raises :class:`OSError` on non-Linux because there is no
   portable equivalent of the Linux raw CAN socket. Pytest skips the
   SocketCAN test cells on Windows / macOS via a ``skipif`` marker.

3. **Classic CAN 8-byte default, FD opt-in**: the constructor takes a
   ``fd`` flag. Most CANable 2.0 setups run FD at 1 Mbit/s data phase, but
   the test vcan loopback works fine on classic frames and avoids the
   ``CAN_RAW_FD_FRAMES`` setsockopt that pre-5.x kernels lacked.
"""

from __future__ import annotations

import asyncio
import socket
import struct
import sys
from collections.abc import Callable

from tethys_master.logging_setup import get_logger
from tethys_master.transport import (
    TransportEvent,
    TransportEventKind,
    TransportId,
    TransportInfo,
)

logger = get_logger(__name__)

SOCKETCAN_MTU_CLASSIC: int = 8
"""Classic CAN payload (ISO 11898-1)."""

SOCKETCAN_MTU_FD: int = 64
"""CAN-FD payload (ISO 11898-1:2024)."""

SOCKETCAN_DEFAULT_CAN_ID: int = 0x123
"""Default XCP-on-CAN ID; A2L IF_DATA overrides on the production bench."""

# struct can_frame: can_id(4) + can_dlc(1) + __pad(1) + __res0(1) + __res1(1) + data(8) = 16 bytes
_CAN_FRAME_FMT = "=IB3x8s"
_CAN_FRAME_SIZE = struct.calcsize(_CAN_FRAME_FMT)

# struct canfd_frame: can_id(4) + len(1) + flags(1) + __res0(1) + __res1(1) + data(64) = 72 bytes
_CANFD_FRAME_FMT = "=IBBBB64s"
_CANFD_FRAME_SIZE = struct.calcsize(_CANFD_FRAME_FMT)

# setsockopt constants not always exposed by stdlib socket module.
_SOL_CAN_BASE = 100
_SOL_CAN_RAW = _SOL_CAN_BASE + 1
_CAN_RAW_FD_FRAMES = 5
_CAN_RAW_ERR_FILTER = 2

_CAN_ERR_FLAG = 0x20000000
_CAN_ERR_BUSOFF = 0x00000040
_CAN_ERR_BUSERROR = 0x00000080
_CAN_ERR_RESTARTED = 0x00000100


def _is_linux() -> bool:
    return sys.platform.startswith("linux")


class SocketCanTransport:
    """SocketCAN ``CAN_RAW`` transport.

    :param ifname: CAN interface name (``can0``, ``vcan0``, ...).
    :param can_id: CAN identifier to put on the wire for outbound frames.
                   Default ``0x123`` matches the slave-side default.
    :param fd:     If True, opt into CAN-FD (64-byte frames). Requires a
                   recent enough kernel (>= 3.6).

    :raises OSError: on non-Linux platforms (no AF_CAN support).
    """

    def __init__(
        self,
        ifname: str = "can0",
        *,
        can_id: int = SOCKETCAN_DEFAULT_CAN_ID,
        fd: bool = False,
    ) -> None:
        if not _is_linux():
            msg = "SocketCanTransport requires Linux (socket.AF_CAN is Linux-only)"
            raise OSError(msg)
        if not ifname:
            msg = "ifname must be non-empty"
            raise ValueError(msg)
        if not (0 <= can_id <= 0x1FFFFFFF):
            msg = f"can_id out of CAN extended range: {can_id:#x}"
            raise ValueError(msg)
        self._ifname = ifname
        self._can_id = can_id
        self._fd = fd
        self._socket: socket.socket | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._rx_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._reader_task: asyncio.Task[None] | None = None
        self._on_event: Callable[[TransportEvent], None] | None = None
        self._frame_size = _CANFD_FRAME_SIZE if fd else _CAN_FRAME_SIZE
        self._frame_fmt = _CANFD_FRAME_FMT if fd else _CAN_FRAME_FMT
        self._mtu = SOCKETCAN_MTU_FD if fd else SOCKETCAN_MTU_CLASSIC

    @property
    def info(self) -> TransportInfo:
        return TransportInfo(
            id=TransportId.SOCKETCAN,
            name="socketcan",
            mtu=self._mtu,
            supports_reliable=False,
            supports_ordering=True,
            max_burst_loss=4,
            typical_latency_us=500,
            typical_loss_per_pkt=1e-6,
            extra={"ifname": self._ifname, "fd": str(self._fd)},
        )

    @property
    def is_open(self) -> bool:
        return self._socket is not None

    @property
    def ifname(self) -> str:
        return self._ifname

    def set_event_callback(self, cb: Callable[[TransportEvent], None] | None) -> None:
        """Register or detach the out-of-band event callback."""
        self._on_event = cb

    async def open(self) -> None:
        if self._socket is not None:
            return
        # socket.AF_CAN / socket.CAN_RAW are only defined on Linux; mypy on
        # other platforms reports them missing. The platform fence in
        # __init__ guarantees we never reach this branch on non-Linux.
        sock = socket.socket(socket.AF_CAN, socket.SOCK_RAW, socket.CAN_RAW)  # type: ignore[attr-defined]
        try:
            if self._fd:
                sock.setsockopt(_SOL_CAN_RAW, _CAN_RAW_FD_FRAMES, 1)
            # Subscribe to error frames so we can translate them into events.
            err_mask = struct.pack("I", _CAN_ERR_BUSOFF | _CAN_ERR_BUSERROR | _CAN_ERR_RESTARTED)
            sock.setsockopt(_SOL_CAN_RAW, _CAN_RAW_ERR_FILTER, err_mask)
            sock.bind((self._ifname,))
            sock.setblocking(False)
        except OSError:
            sock.close()
            raise
        self._socket = sock
        self._loop = asyncio.get_running_loop()
        self._reader_task = self._loop.create_task(self._reader_loop(), name=f"socketcan-rx[{self._ifname}]")
        logger.info("socketcan.opened", ifname=self._ifname, fd=self._fd)

    async def close(self) -> None:
        if self._reader_task is not None:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except (asyncio.CancelledError, Exception):  # noqa: S110
                # Cleanup path: details (if any) are logged inside the reader loop.
                pass
            self._reader_task = None
        if self._socket is not None:
            self._socket.close()
            self._socket = None
            logger.info("socketcan.closed", ifname=self._ifname)

    async def send(self, data: bytes) -> None:
        if self._socket is None:
            msg = "SocketCanTransport.send: not open"
            raise RuntimeError(msg)
        if not data:
            msg = "SocketCanTransport.send: empty payload"
            raise ValueError(msg)
        if len(data) > self._mtu:
            msg = f"SocketCanTransport.send: payload {len(data)} > MTU {self._mtu}"
            raise ValueError(msg)
        frame = self._encode_frame(data)
        # Non-blocking send; on transient WOULDBLOCK we yield to the loop and retry.
        loop = self._loop or asyncio.get_running_loop()
        await loop.sock_sendall(self._socket, frame)
        logger.debug("socketcan.send", bytes=len(data), id=hex(self._can_id))

    async def recv(self, *, timeout: float | None = None) -> bytes:
        if self._socket is None:
            msg = "SocketCanTransport.recv: not open"
            raise RuntimeError(msg)
        if timeout is None:
            return await self._rx_queue.get()
        return await asyncio.wait_for(self._rx_queue.get(), timeout=timeout)

    # ---- Internal: encode / decode / reader loop ------------------

    def _encode_frame(self, data: bytes) -> bytes:
        padded = data.ljust(self._mtu, b"\x00")
        if self._fd:
            return struct.pack(self._frame_fmt, self._can_id, len(data), 0, 0, 0, padded)
        return struct.pack(self._frame_fmt, self._can_id, len(data), padded)

    def _decode_frame(self, raw: bytes) -> tuple[int, bytes] | None:
        if len(raw) < _CAN_FRAME_SIZE:
            return None
        if self._fd and len(raw) >= _CANFD_FRAME_SIZE:
            can_id, dlc, _flags, _r0, _r1, data = struct.unpack(_CANFD_FRAME_FMT, raw[:_CANFD_FRAME_SIZE])
        else:
            can_id, dlc, data = struct.unpack(_CAN_FRAME_FMT, raw[:_CAN_FRAME_SIZE])
        if (can_id & _CAN_ERR_FLAG) != 0:
            kind = TransportEventKind.LOSS
            if can_id & _CAN_ERR_BUSOFF:
                kind = TransportEventKind.BUS_OFF
            elif can_id & _CAN_ERR_RESTARTED:
                kind = TransportEventKind.BUS_RECOVERED
            self._emit_event(kind, count=1)
            return None
        capped = min(int(dlc), self._mtu)
        return can_id, bytes(data[:capped])

    async def _reader_loop(self) -> None:
        assert self._socket is not None
        assert self._loop is not None
        sock = self._socket
        loop = self._loop
        try:
            while True:
                raw = await loop.sock_recv(sock, self._frame_size)
                if not raw:
                    logger.info("socketcan.eof", ifname=self._ifname)
                    return
                decoded = self._decode_frame(raw)
                if decoded is None:
                    continue
                _can_id, payload = decoded
                self._rx_queue.put_nowait(payload)
        except asyncio.CancelledError:
            raise
        except OSError as exc:
            logger.warning("socketcan.reader_error", ifname=self._ifname, exc=str(exc))

    def _emit_event(self, kind: TransportEventKind, *, count: int = 1) -> None:
        if self._on_event is None:
            return
        self._on_event(TransportEvent(kind=kind, timestamp_us=0, count=count))

    async def __aenter__(self) -> SocketCanTransport:
        await self.open()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()
