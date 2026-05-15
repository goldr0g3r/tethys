"""Tethys master CLI entry-point.

Cite: click v8 (https://click.palletsprojects.com/)
Cite: parent plan section 3.1 (master CLI)
"""

from __future__ import annotations

import asyncio
import sys
from typing import TYPE_CHECKING

import click

from tethys_master import __version__
from tethys_master.config import MasterSettings
from tethys_master.logging_setup import configure_logging, get_logger
from tethys_master.protocol.client import XcpClient, XcpProtocolError
from tethys_master.transport.udp import UdpTransport

if TYPE_CHECKING:
    from tethys_master.protocol.frame import ConnectResponse, GetStatusResponse, GetVersionResponse


_SETTINGS_KEY = "settings"
_LOGGER_KEY = "logger"


def _parse_target(target: str) -> tuple[str, str, int]:
    """Parse ``<scheme>://<host>:<port>``.

    Supported schemes (Phase 1): ``udp``. Phase 5 adds ``tcp``, ``can``,
    ``serial``.
    """
    if "://" not in target:
        msg = f"Target must be <scheme>://<host>:<port>, got {target!r}"
        raise click.BadParameter(msg)
    scheme, rest = target.split("://", 1)
    scheme = scheme.lower()
    if scheme != "udp":
        msg = f"Phase-1 supports udp:// only; got {scheme!r}"
        raise click.BadParameter(msg)
    if ":" not in rest:
        msg = f"Target needs explicit port, got {target!r}"
        raise click.BadParameter(msg)
    host, port_str = rest.rsplit(":", 1)
    try:
        port = int(port_str)
    except ValueError as exc:
        msg = f"Port must be an integer: {port_str!r}"
        raise click.BadParameter(msg) from exc
    return scheme, host, port


@click.group()
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False),
    default=None,
    help="Override log level (env: TETHYS_MASTER_LOG_LEVEL).",
)
@click.option(
    "--log-format",
    type=click.Choice(["plain", "json"], case_sensitive=False),
    default=None,
    help="Override log format (env: TETHYS_MASTER_LOG_FORMAT).",
)
@click.version_option(__version__, prog_name="tethys-master")
@click.pass_context
def cli(ctx: click.Context, log_level: str | None, log_format: str | None) -> None:
    """Tethys master - license-free XCP 1.4 calibration and measurement tool."""
    settings = MasterSettings()
    effective_level = log_level or settings.log_level
    effective_fmt = log_format or settings.log_format
    configure_logging(effective_level, effective_fmt)

    ctx.ensure_object(dict)
    ctx.obj[_SETTINGS_KEY] = settings
    ctx.obj[_LOGGER_KEY] = get_logger("tethys-master.cli")


@cli.command()
@click.pass_context
def version(ctx: click.Context) -> None:
    """Print the tethys-master version."""
    logger = ctx.obj[_LOGGER_KEY]
    logger.info("tethys-master.version", version=__version__)
    click.echo(f"tethys-master {__version__}")


@cli.command()
@click.option(
    "--target",
    default="udp://127.0.0.1:5555",
    show_default=True,
    help="<scheme>://<host>:<port>",
)
@click.option(
    "--connect-timeout-ms",
    type=int,
    default=None,
    help="CONNECT timeout (default: TETHYS_MASTER_CONNECT_TIMEOUT_MS or 1000).",
)
@click.option(
    "--mode",
    type=int,
    default=0,
    show_default=True,
    help="CONNECT mode byte (0 = normal, 1 = user-defined).",
)
@click.pass_context
def connect(ctx: click.Context, target: str, connect_timeout_ms: int | None, mode: int) -> None:
    """Single-shot XCP CONNECT (and immediate DISCONNECT) over the target transport."""
    settings: MasterSettings = ctx.obj[_SETTINGS_KEY]
    logger = ctx.obj[_LOGGER_KEY]
    _scheme, host, port = _parse_target(target)
    timeout_ms = connect_timeout_ms if connect_timeout_ms is not None else settings.connect_timeout_ms
    timeout_s = timeout_ms / 1000.0

    async def _run() -> int:
        transport = UdpTransport(host, port)
        async with XcpClient(transport, default_timeout_s=timeout_s) as client:
            try:
                connect_response: ConnectResponse = await client.connect(mode=mode)
                version_response: GetVersionResponse = await client.get_version()
                status_response: GetStatusResponse = await client.get_status()
            except (TimeoutError, XcpProtocolError, OSError) as exc:
                logger.error("xcp.connect.failed", target=target, error=str(exc))
                click.echo(f"CONNECT failed: {exc}", err=True)
                return 1
            click.echo("CONNECT OK")
            click.echo(f"  resource = 0x{connect_response.resource:02X}")
            click.echo(f"  comm     = 0x{connect_response.comm_mode_basic:02X}")
            click.echo(f"  max_cto  = {connect_response.max_cto}")
            click.echo(f"  max_dto  = {connect_response.max_dto}")
            click.echo(
                f"  protocol = 0x{connect_response.protocol_version:02X}, "
                f"transport = 0x{connect_response.transport_version:02X}"
            )
            click.echo(
                f"  version  = protocol {version_response.protocol_major}.{version_response.protocol_minor}, "
                f"transport {version_response.transport_major}.{version_response.transport_minor}"
            )
            click.echo(
                f"  status   = session 0x{status_response.current_session_status:02X}, "
                f"protect 0x{status_response.current_resource_protection:02X}"
            )
            click.echo("DISCONNECT OK")
        return 0

    sys.exit(asyncio.run(_run()))


@cli.command()
@click.argument("gui_args", nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def gui(ctx: click.Context, gui_args: tuple[str, ...]) -> None:
    """Launch the PySide6 master GUI (parent plan §3.1, Phase 6).

    Requires the ``[gui]`` optional-dependency group (PySide6 + pyqtgraph).
    Install with ``uv sync --all-extras`` or ``pip install
    'tethys-master[gui]'``. Extra positional arguments are forwarded to
    Qt as ``QApplication`` argv (e.g. ``--platform offscreen``).
    """
    logger = ctx.obj[_LOGGER_KEY]
    logger.info("gui.launch.invoked", extra_args=list(gui_args) or None)
    from tethys_master.gui.app import main as gui_main

    argv = ["tethys-master-gui", *gui_args]
    sys.exit(gui_main(argv))


if __name__ == "__main__":  # pragma: no cover
    cli()
