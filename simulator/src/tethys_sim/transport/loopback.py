"""Loopback-wired simulator slave for the Phase-5 conformance suite.

Wires :class:`tethys_master.transport.loopback.LoopbackTransport` to the
simulator's :class:`tethys_sim.slave.XcpSimSlave` so the conformance suite
can drive the slave through a pure in-process loopback — no socket, no
ports, no host networking needed. Used as the universal baseline that every
other transport in the conformance matrix is compared against.

Cite: parent plan §8 Phase 5
Cite: ADR-0010 row 12 (loopback zero-loss budget)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from tethys_master.logging_setup import get_logger
from tethys_master.transport.loopback import LoopbackTransport

from tethys_sim.slave import XcpSimSlave

logger = get_logger(__name__)


@dataclass(slots=True)
class SlaveLoopbackPair:
    """Holder for a master-side transport + the background dispatch task.

    The slave is the :class:`XcpSimSlave`; the master uses
    :attr:`master_transport` to talk to it. Both ends share the same
    :class:`LoopbackTransport` pair (created by
    :meth:`LoopbackTransport.create_pair`); the dispatch task reads from the
    slave side and writes the slave's CTO/DTO responses back through the
    same pair.
    """

    master_transport: LoopbackTransport
    slave: XcpSimSlave
    _slave_transport: LoopbackTransport
    _task: asyncio.Task[None]

    async def stop(self) -> None:
        """Cancel the dispatch task and close both transports."""
        self._task.cancel()
        try:
            await self._task
        except (asyncio.CancelledError, Exception):  # noqa: S110
            # Cleanup path: details (if any) are logged inside the dispatch loop.
            pass
        await self.master_transport.close()
        await self._slave_transport.close()


async def make_slave_loopback_pair(
    *,
    profile: str = "marine",
    name: str = "sim-loopback",
) -> SlaveLoopbackPair:
    """Construct an :class:`XcpSimSlave` wired up to a loopback transport pair.

    :returns: a :class:`SlaveLoopbackPair`. Use ``pair.master_transport`` as
              the master-side ``Transport`` and call ``await pair.stop()``
              when done.
    """
    master_side, slave_side = LoopbackTransport.create_pair(names=(f"{name}-master", f"{name}-slave"))
    await master_side.open()
    await slave_side.open()
    slave = XcpSimSlave(profile=profile)

    async def _dispatch_loop() -> None:
        """Read CTOs from the master, hand to the slave dispatcher, return CTOs."""
        try:
            while True:
                packet = await slave_side.recv()
                response = slave.dispatch(packet)
                if response is not None:
                    try:
                        await slave_side.send(response)
                    except (RuntimeError, asyncio.QueueFull) as exc:
                        logger.warning("sim.loopback.send_failed", exc=str(exc))
                        return
        except asyncio.CancelledError:
            raise
        except RuntimeError as exc:
            logger.info("sim.loopback.exit", exc=str(exc))

    task = asyncio.create_task(_dispatch_loop(), name=f"{name}-dispatch")
    logger.info("sim.loopback.ready", profile=profile, name=name)
    return SlaveLoopbackPair(
        master_transport=master_side,
        slave=slave,
        _slave_transport=slave_side,
        _task=task,
    )
