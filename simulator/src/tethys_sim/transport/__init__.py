"""Virtual transport stubs for the Tethys simulator.

These are thin glue layers on top of :mod:`tethys_master.transport` so the
simulator's :class:`XcpSimSlave` can be driven by any transport the master
supports — used by the Phase 5 conformance suite to drive the same slave
through loopback, SocketCAN (vcan), and (Phase 5 PR-B) UART/SxI.

Cite: parent plan §8 Phase 5
Cite: ADR-0004 (transport-abstraction-layer interface)
"""

from __future__ import annotations

from tethys_sim.transport.loopback import (
    SlaveLoopbackPair,
    make_slave_loopback_pair,
)

__all__ = ["SlaveLoopbackPair", "make_slave_loopback_pair"]
