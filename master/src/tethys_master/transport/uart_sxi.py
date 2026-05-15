"""Raw UART / SxI byte-stream transport for the Tethys master.

Mirrors the C-side framer in ``slave/src/transport/uart_sxi.c``:

::

    [0]    start byte 0xAA
    [1]    length L (1..MTU)
    [2..]  payload
    [2+L]  checksum (XOR of bytes [0..2+L-1])

Cite: ADR-0004 (transport-abstraction-layer interface)
Cite: ADR-0010 row 8 (UART/SxI raw budget; COP-1 AD wrap is Phase 8)
Trace: docs/traceability.csv row TETHYS-DES-0035 (lands at PR-10)

Implementation notes:

1. **pyserial** as the backend. BSD-3 licensed; widely used; pinned via
   ``master/pyproject.toml`` per ``.cursor/rules/version-pinning.mdc``.
2. **No COP-1**: this transport is raw bytes. The Phase 8 space profile
   adds the COP-1 AD wrapper on top of this in a follow-up PR.
3. **Cross-platform**: pyserial works on Windows / macOS / Linux, but the
   conformance test fixture uses a Linux/macOS ``pty`` pair so the suite
   skips on Windows for the UART row (no portable pty on Windows).
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from typing import TYPE_CHECKING

from tethys_master.logging_setup import get_logger
from tethys_master.transport import (
    TransportEvent,
    TransportEventKind,
    TransportId,
    TransportInfo,
)

if TYPE_CHECKING:
    import serial  # type: ignore[import-untyped]

logger = get_logger(__name__)

UART_MTU: int = 64
"""Max payload size per frame; matches the C-side TETHYS_UART_MTU."""

UART_START_BYTE: int = 0xAA
"""Wire start byte; matches the C-side TETHYS_UART_START_BYTE."""

UART_FRAME_OVERHEAD: int = 3
"""Bytes added per payload: start + length + checksum."""

UART_DEFAULT_BAUD: int = 115200
"""Default baud; matches the bench setup for STM32F7/H7 USART."""


def _xor_checksum(data: bytes) -> int:
    """Single-byte XOR checksum over ``data``. Mirrors the C framer."""
    x = 0
    for b in data:
        x ^= b
    return x & 0xFF


def encode_frame(payload: bytes) -> bytes:
    """Encode one payload as a wire frame.

    :raises ValueError: if ``payload`` is empty or exceeds ``UART_MTU``.
    """
    if not payload:
        msg = "encode_frame: empty payload"
        raise ValueError(msg)
    if len(payload) > UART_MTU:
        msg = f"encode_frame: payload {len(payload)} bytes exceeds MTU {UART_MTU}"
        raise ValueError(msg)
    header = bytes([UART_START_BYTE, len(payload)])
    cksum = _xor_checksum(header + payload)
    return header + payload + bytes([cksum])


class _Framer:
    """Stream byte decoder matching the C-side framer state machine."""

    _STATE_WAIT_START = 0
    _STATE_WAIT_LEN = 1
    _STATE_WAIT_PAYLOAD = 2
    _STATE_WAIT_CKSUM = 3

    def __init__(self) -> None:
        self._state = _Framer._STATE_WAIT_START
        self._pending_len = 0
        self._pending: bytearray = bytearray()
        self._running_xor = 0
        self._on_loss: Callable[[int], None] | None = None

    def set_on_loss(self, cb: Callable[[int], None] | None) -> None:
        self._on_loss = cb

    def reset(self) -> None:
        self._state = _Framer._STATE_WAIT_START
        self._pending_len = 0
        self._pending = bytearray()
        self._running_xor = 0

    def _emit_loss(self, count: int = 1) -> None:
        if self._on_loss is not None:
            self._on_loss(count)

    def feed(self, chunk: bytes) -> list[bytes]:
        """Feed inbound bytes and yield zero or more decoded payloads."""
        out: list[bytes] = []
        for raw_byte in chunk:
            b = raw_byte & 0xFF
            if self._state == _Framer._STATE_WAIT_START:
                if b == UART_START_BYTE:
                    self._state = _Framer._STATE_WAIT_LEN
                    self._running_xor = b
                # else: discard for resync
            elif self._state == _Framer._STATE_WAIT_LEN:
                if b == 0 or b > UART_MTU:
                    self._emit_loss()
                    self.reset()
                else:
                    self._pending_len = b
                    self._pending = bytearray()
                    self._running_xor ^= b
                    self._state = _Framer._STATE_WAIT_PAYLOAD
            elif self._state == _Framer._STATE_WAIT_PAYLOAD:
                self._pending.append(b)
                self._running_xor ^= b
                if len(self._pending) == self._pending_len:
                    self._state = _Framer._STATE_WAIT_CKSUM
            elif self._state == _Framer._STATE_WAIT_CKSUM:
                if b == self._running_xor:
                    out.append(bytes(self._pending))
                else:
                    self._emit_loss()
                self.reset()
        return out


class UartSxiTransport:
    """Raw UART/SxI transport backed by pyserial.

    :param port:   Serial port name (``/dev/ttyUSB0``, ``COM3``, or a path
                   to a pseudo-terminal slave for the conformance suite).
    :param baud:   Baud rate (default 115200).
    :param timeout_s: Per-read timeout passed to pyserial; we wrap our own
                   asyncio timeout on top so the value here is for the
                   blocking syscall budget only.

    The constructor does NOT open the port; call :meth:`open` (or use as
    an async context manager).
    """

    def __init__(
        self,
        port: str,
        *,
        baud: int = UART_DEFAULT_BAUD,
        timeout_s: float = 0.05,
    ) -> None:
        if not port:
            msg = "port must be non-empty"
            raise ValueError(msg)
        if baud <= 0:
            msg = f"baud must be > 0, got {baud}"
            raise ValueError(msg)
        if timeout_s <= 0.0:
            msg = f"timeout_s must be > 0, got {timeout_s}"
            raise ValueError(msg)
        self._port = port
        self._baud = baud
        self._timeout_s = timeout_s
        self._serial: serial.Serial | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._rx_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._reader_task: asyncio.Task[None] | None = None
        self._on_event: Callable[[TransportEvent], None] | None = None
        self._framer = _Framer()
        self._framer.set_on_loss(self._handle_loss)

    @property
    def info(self) -> TransportInfo:
        return TransportInfo(
            id=TransportId.UART_SXI,
            name="uart_sxi",
            mtu=UART_MTU,
            supports_reliable=False,
            supports_ordering=True,
            max_burst_loss=8,
            typical_latency_us=2000,
            typical_loss_per_pkt=1e-7,
            extra={"port": self._port, "baud": str(self._baud)},
        )

    @property
    def is_open(self) -> bool:
        return self._serial is not None and self._serial.is_open

    @property
    def port(self) -> str:
        return self._port

    def set_event_callback(self, cb: Callable[[TransportEvent], None] | None) -> None:
        """Register or detach the out-of-band event callback."""
        self._on_event = cb

    async def open(self) -> None:
        if self._serial is not None:
            return
        # pyserial ships without PEP-561 stubs; the TYPE_CHECKING import
        # above carries the type: ignore, so the runtime import here can
        # be plain.
        import serial

        ser = serial.Serial(
            port=self._port,
            baudrate=self._baud,
            timeout=self._timeout_s,
        )
        self._serial = ser
        self._loop = asyncio.get_running_loop()
        self._reader_task = self._loop.create_task(
            self._reader_loop(),
            name=f"uart-rx[{self._port}]",
        )
        logger.info("uart_sxi.opened", port=self._port, baud=self._baud)

    async def close(self) -> None:
        if self._reader_task is not None:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except (asyncio.CancelledError, Exception):  # noqa: S110
                pass
            self._reader_task = None
        if self._serial is not None and self._serial.is_open:
            self._serial.close()
            self._serial = None
            logger.info("uart_sxi.closed", port=self._port)

    async def send(self, data: bytes) -> None:
        if self._serial is None:
            msg = "UartSxiTransport.send: not open"
            raise RuntimeError(msg)
        if not data:
            msg = "UartSxiTransport.send: empty payload"
            raise ValueError(msg)
        if len(data) > UART_MTU:
            msg = f"UartSxiTransport.send: payload {len(data)} > MTU {UART_MTU}"
            raise ValueError(msg)
        frame = encode_frame(data)
        loop = self._loop or asyncio.get_running_loop()
        await loop.run_in_executor(None, self._serial.write, frame)
        logger.debug("uart_sxi.send", bytes=len(data))

    async def recv(self, *, timeout: float | None = None) -> bytes:
        if self._serial is None:
            msg = "UartSxiTransport.recv: not open"
            raise RuntimeError(msg)
        if timeout is None:
            return await self._rx_queue.get()
        return await asyncio.wait_for(self._rx_queue.get(), timeout=timeout)

    def _handle_loss(self, count: int) -> None:
        if self._on_event is None:
            return
        ev = TransportEvent(kind=TransportEventKind.LOSS, timestamp_us=0, count=count)
        self._on_event(ev)

    async def _reader_loop(self) -> None:
        assert self._serial is not None
        assert self._loop is not None
        ser = self._serial
        loop = self._loop
        try:
            while True:
                # pyserial's read is blocking; run it in the default executor
                # so we don't stall the asyncio loop. Each chunk is up to
                # 256 bytes which keeps the latency under one ms at 115200.
                chunk = await loop.run_in_executor(None, ser.read, 256)
                if not chunk:
                    # timeout - tick and continue
                    continue
                for payload in self._framer.feed(chunk):
                    self._rx_queue.put_nowait(payload)
        except asyncio.CancelledError:
            raise
        except OSError as exc:
            logger.warning("uart_sxi.reader_error", port=self._port, exc=str(exc))

    async def __aenter__(self) -> UartSxiTransport:
        await self.open()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()


# Re-export so callers can encode/decode for testing without instantiating the
# transport (pyserial isn't needed for the framer-only tests).
_HAS_PYSERIAL = sys.platform.startswith(("linux", "darwin", "win"))
"""Indicator used by tests to skip pyserial-dependent cases gracefully."""

__all__ = [
    "UART_DEFAULT_BAUD",
    "UART_FRAME_OVERHEAD",
    "UART_MTU",
    "UART_START_BYTE",
    "UartSxiTransport",
    "encode_frame",
]
