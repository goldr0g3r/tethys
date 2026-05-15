"""Tethys simulator CLI entry-point.

Cite: click v8 (https://click.palletsprojects.com/)
Cite: parent plan section 7 (Phase-1 acceptance bench)
"""

from __future__ import annotations

import asyncio
import signal
import sys
from typing import TYPE_CHECKING

import click
from tethys_master.logging_setup import configure_logging, get_logger

from tethys_sim import __version__
from tethys_sim.slave import XcpSimSlave

if TYPE_CHECKING:
    pass


@click.group()
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False),
    default="INFO",
)
@click.option(
    "--log-format",
    type=click.Choice(["plain", "json"], case_sensitive=False),
    default="plain",
)
@click.version_option(__version__, prog_name="tethys-sim")
def cli(log_level: str, log_format: str) -> None:
    """Tethys simulator - posix-sim XCP slave."""
    configure_logging(log_level, log_format)


@cli.command()
@click.option(
    "--transport",
    type=click.Choice(["udp"], case_sensitive=False),
    default="udp",
    show_default=True,
)
@click.option("--host", default="127.0.0.1", show_default=True, help="Bind host")
@click.option("--port", type=int, default=5555, show_default=True, help="Bind UDP port")
@click.option(
    "--profile",
    type=click.Choice(["marine", "space"], case_sensitive=False),
    default="marine",
    show_default=True,
)
def serve(transport: str, host: str, port: int, profile: str) -> None:
    """Start the posix-sim XCP slave listening for master commands."""
    if transport.lower() != "udp":
        raise click.BadParameter(f"Phase-1 supports udp only; got {transport!r}")

    async def _run() -> int:
        logger = get_logger("tethys-sim.serve")
        slave = XcpSimSlave(host=host, port=port, profile=profile)
        await slave.start()
        click.echo(f"tethys-sim listening on udp://{host}:{port} (profile={profile})")
        click.echo("Ctrl-C to stop.")

        stop_event = asyncio.Event()

        def _on_signal() -> None:
            logger.info("sim.signal.shutdown")
            stop_event.set()

        loop = asyncio.get_running_loop()
        for sig in _supported_signals():
            try:
                loop.add_signal_handler(sig, _on_signal)
            except (NotImplementedError, RuntimeError):  # Windows asyncio.ProactorEventLoop
                pass

        try:
            await stop_event.wait()
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            await slave.stop()
        return 0

    sys.exit(asyncio.run(_run()))


def _supported_signals() -> list[int]:
    candidates = [getattr(signal, name, None) for name in ("SIGINT", "SIGTERM")]
    return [s for s in candidates if isinstance(s, signal.Signals)]


__all__ = ["cli", "serve"]
