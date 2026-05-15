"""POSIX pseudo-terminal helper for the Phase-5 UART/SxI conformance row.

Creates a ``pty.openpty()`` pair, opens the master end as a pyserial
device, and returns paired :class:`UartSxiTransport` instances so the
conformance suite can drive UART/SxI end-to-end without real hardware.

Windows has no portable pty; the helper raises ``OSError`` there so the
conformance row skips cleanly.

Cite: parent plan §8 Phase 5
Cite: ADR-0010 row 8 (UART/SxI raw budget)
"""

from __future__ import annotations

import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from tethys_master.logging_setup import get_logger
from tethys_master.transport.uart_sxi import UartSxiTransport

logger = get_logger(__name__)


def is_pty_available() -> bool:
    """Return True on POSIX hosts where ``pty.openpty()`` works."""
    return sys.platform.startswith(("linux", "darwin"))


@asynccontextmanager
async def uart_pty_pair(
    *,
    baud: int = 115200,
) -> AsyncIterator[tuple[UartSxiTransport, UartSxiTransport]]:
    """Yield a pair of :class:`UartSxiTransport` wired through a pty pair.

    Traffic sent on ``a`` is received on ``b`` and vice versa.

    :raises OSError: on Windows (no portable pty support).
    """
    if not is_pty_available():
        msg = "uart_pty_pair: POSIX pty required; not available on Windows"
        raise OSError(msg)
    # `pty`, `os.openpty`, and `os.ttyname` are POSIX-only; on Windows mypy
    # doesn't see them at all. The platform fence above guarantees we never
    # reach this branch on Windows; we use plain `# type: ignore` so the
    # comment is valid on both Windows (where pty/openpty/ttyname don't
    # exist) and POSIX (where they do).
    import pty

    fd_a_master, fd_a_slave = pty.openpty()  # type: ignore
    fd_b_master, fd_b_slave = pty.openpty()  # type: ignore
    # We don't use the slave-side fds directly; pyserial opens them via the
    # filesystem path.
    try:
        slave_path_a = os.ttyname(fd_a_slave)  # type: ignore
        slave_path_b = os.ttyname(fd_b_slave)  # type: ignore
    except OSError:
        os.close(fd_a_master)
        os.close(fd_a_slave)
        os.close(fd_b_master)
        os.close(fd_b_slave)
        raise

    # Build a relay: bytes on a's master fd -> b's master fd and vice
    # versa. The pyserial transports below see only the slave-side paths.
    # NOTE: a fully realistic UART bench would use a single shared pty; the
    # pair-with-relay shape lets us instrument both directions independently
    # if we want to inject loss in the future.
    a = UartSxiTransport(slave_path_a, baud=baud, timeout_s=0.05)
    b = UartSxiTransport(slave_path_b, baud=baud, timeout_s=0.05)

    import asyncio

    loop = asyncio.get_running_loop()

    def _relay(src_fd: int, dst_fd: int) -> None:
        try:
            data = os.read(src_fd, 4096)
        except (BlockingIOError, OSError):
            return
        if data:
            try:
                os.write(dst_fd, data)
            except OSError:
                pass

    loop.add_reader(fd_a_master, _relay, fd_a_master, fd_b_master)
    loop.add_reader(fd_b_master, _relay, fd_b_master, fd_a_master)

    await a.open()
    await b.open()
    try:
        yield (a, b)
    finally:
        await a.close()
        await b.close()
        try:
            loop.remove_reader(fd_a_master)
            loop.remove_reader(fd_b_master)
        except (ValueError, OSError):
            pass
        for fd in (fd_a_master, fd_a_slave, fd_b_master, fd_b_slave):
            try:
                os.close(fd)
            except OSError:
                pass
