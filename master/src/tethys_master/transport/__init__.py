"""Transport layer implementations for the Tethys master.

Phase 1 ships UDP only; Phase 5 (parent §8) adds TCP, SocketCAN, UART/SxI.
The :class:`Transport` protocol is the freeze point per [ADR-0004].
"""

from __future__ import annotations

from typing import Protocol


class Transport(Protocol):
    """Minimal transport interface every concrete transport implements.

    See `ADR-0004 Transport abstraction layer <../adr/0004-transport-abstraction-layer.md>`_.
    """

    async def open(self) -> None: ...

    async def close(self) -> None: ...

    async def send(self, data: bytes) -> None: ...

    async def recv(self, *, timeout: float | None = None) -> bytes: ...
