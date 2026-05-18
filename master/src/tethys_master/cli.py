"""Tethys master CLI entry-point.

Cite: click v8 (https://click.palletsprojects.com/)
Cite: parent plan section 3.1 (master CLI)
Cite: parent plan section 8 (Phase 9 HIL demo) — ``demo`` subcommand.
Cite: ADR-0006 (AES-128 seed-and-key) — drives space-profile auth on demo runs.
"""

from __future__ import annotations

import asyncio
import csv
import json
import sys
import time
import zlib
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING

import click
import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape

from tethys_master import __version__
from tethys_master.config import MasterSettings
from tethys_master.hil import Scenario, ScenarioError, load_scenario
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


_MASTER_OUT_HEADER = (
    "sample_index",
    "timestamp_us",
    "command",
    "setpoint",
    "gain",
    "enable",
    "checksum",
)
_PLANT_OUT_HEADER = (
    "sample_index",
    "timestamp_us",
    "measurement",
    "plant_state",
    "event",
    "checksum",
)


def _row_checksum(fields: tuple[str, ...]) -> int:
    """CRC-32/ZIP of the joined fields (master_out.schema.md)."""
    return zlib.crc32(",".join(fields).encode("ascii")) & 0xFFFFFFFF


def _render_report(scenario: Scenario, context: dict[str, object]) -> str:
    """Render ``report.html.j2`` with the run summary + scenario JSON."""
    template_dir = resources.files("tethys_master.hil")
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "htm", "xml", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("report.html.j2")
    return template.render(scenario=scenario, **context)


def _resolve_repo_root(start: Path) -> Path:
    """Walk up looking for the repo marker (``hil/scenarios/``)."""
    current = start.resolve()
    for parent in (current, *current.parents):
        if (parent / "hil" / "scenarios").is_dir():
            return parent
    return start.resolve()


def _run_bridge_loop(
    scenario: Scenario,
    repo_root: Path,
    logger: structlog.stdlib.BoundLogger,
    *,
    dry_run: bool,
) -> dict[str, int]:
    """Drive the CSV bridge for ``scenario.duration_s`` seconds.

    Writes one master_out.csv row per ``scenario.plant.bridge.sample_time_s``;
    reads any new plant_out.csv rows and counts them. Returns the
    per-run counters the report renders.
    """
    bridge = scenario.plant.bridge
    master_path = repo_root / bridge.master_out
    plant_path = repo_root / bridge.plant_out
    master_path.parent.mkdir(parents=True, exist_ok=True)
    plant_path.parent.mkdir(parents=True, exist_ok=True)

    master_rows_written = 0
    plant_rows_read = 0
    bridge_master_timeouts = 0
    plant_read_offset = 0

    with master_path.open("w", encoding="ascii", newline="") as master_fh:
        writer = csv.writer(master_fh, lineterminator="\n")
        writer.writerow(_MASTER_OUT_HEADER)
        master_fh.flush()
        t0 = time.monotonic()
        next_tick = t0
        sample_index = 0
        end_at = t0 + scenario.duration_s
        while True:
            now = time.monotonic()
            if now >= end_at:
                break
            if now < next_tick:
                time.sleep(min(0.001, next_tick - now))
                continue
            ts_us = int((next_tick - t0) * 1_000_000)
            command = 0.5 if not dry_run else 0.0
            setpoint = 0.0
            gain = 0.0
            enable = 1 if not dry_run else 0
            fields = (
                str(sample_index),
                str(ts_us),
                f"{command:.6f}",
                f"{setpoint:.6f}",
                f"{gain:.6f}",
                str(enable),
            )
            row = (*fields, str(_row_checksum(fields)))
            writer.writerow(row)
            master_fh.flush()
            master_rows_written += 1
            sample_index += 1
            next_tick += bridge.sample_time_s
            if plant_path.exists():
                fresh, plant_read_offset = _drain_plant_csv(plant_path, plant_read_offset)
                plant_rows_read += len(fresh)
                bridge_master_timeouts += sum(1 for f in fresh if f.get("event") == "master_timeout")
    logger.info(
        "demo.bridge.summary",
        scenario=scenario.name,
        master_rows_written=master_rows_written,
        plant_rows_read=plant_rows_read,
        bridge_master_timeouts=bridge_master_timeouts,
    )
    return {
        "master_rows_written": master_rows_written,
        "plant_rows_read": plant_rows_read,
        "bridge_master_timeouts": bridge_master_timeouts,
    }


def _drain_plant_csv(path: Path, offset: int) -> tuple[list[dict[str, str]], int]:
    """Read any plant rows after ``offset`` bytes; return them + the new offset."""
    fresh: list[dict[str, str]] = []
    if not path.is_file():
        return fresh, offset
    with path.open("r", encoding="ascii", newline="") as fh:
        fh.seek(offset)
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("sample_index,"):
                continue
            parts = line.split(",")
            if len(parts) != len(_PLANT_OUT_HEADER):
                continue
            fresh.append(dict(zip(_PLANT_OUT_HEADER, parts, strict=True)))
        new_offset = fh.tell()
    return fresh, new_offset


@cli.command()
@click.argument("scenario", type=str)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Validate the scenario JSON + drive the CSV bridge without opening a transport.",
)
@click.option(
    "--repo-root",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help="Repository root - scenario JSON paths resolve under here. Defaults to walking up from CWD.",
)
@click.pass_context
def demo(ctx: click.Context, scenario: str, dry_run: bool, repo_root: Path | None) -> None:
    """Run a Phase 9 HIL demo end to end against ``hil/scenarios/<scenario>.json``.

    Opens the XCP transport declared in the scenario JSON, drives the
    master_out.csv ↔ plant_out.csv bridge for ``duration_s`` seconds, and
    emits an HTML demo report at ``scenario.report_html``. ``--dry-run``
    skips the transport open so CI can exercise the loader + bridge +
    report renderer without a live slave.

    Cite: parent plan §8 (Phase 9 — HIL + MATLAB integration).
    """
    logger = ctx.obj[_LOGGER_KEY]
    repo_root_abs = repo_root.resolve() if repo_root else _resolve_repo_root(Path.cwd())
    try:
        scenario_obj = load_scenario(scenario, repo_root=repo_root_abs)
    except ScenarioError as exc:
        logger.error("demo.scenario.load_failed", scenario=scenario, error=str(exc))
        raise click.ClickException(str(exc)) from exc

    logger.info(
        "demo.start",
        scenario=scenario_obj.name,
        profile=scenario_obj.profile.value,
        plant_kind=scenario_obj.plant.kind.value,
        duration_s=scenario_obj.duration_s,
        dry_run=dry_run,
    )

    a2l_bytes = scenario_obj.resolve_a2l(repo_root_abs)
    a2l_status = "missing" if a2l_bytes is None else f"{len(a2l_bytes)} bytes"
    logger.info("demo.a2l", path=scenario_obj.a2l.path, status=a2l_status)
    if scenario_obj.profile.value == "space":
        key_bytes = scenario_obj.resolve_key(repo_root_abs)
        key_status = "missing" if key_bytes is None else f"{len(key_bytes)} bytes"
        logger.info("demo.auth", path=(scenario_obj.auth.key_file if scenario_obj.auth else None), status=key_status)

    if not dry_run:
        _open_transport_or_warn(scenario_obj, logger)

    bridge_counters = _run_bridge_loop(scenario_obj, repo_root_abs, logger, dry_run=dry_run)

    counters = {
        "daq_dropped": 0,
        "cal_crc_fail": 0,
        **bridge_counters,
    }
    report_path = repo_root_abs / scenario_obj.report_html
    report_path.parent.mkdir(parents=True, exist_ok=True)
    html = _render_report(
        scenario_obj,
        {
            "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "dry_run": dry_run,
            "scenario_json": json.dumps(scenario_obj.model_dump(mode="json"), indent=2),
            **counters,
        },
    )
    report_path.write_text(html, encoding="utf-8")

    logger.info(
        "demo.summary",
        scenario=scenario_obj.name,
        report_html=str(report_path),
        **counters,
    )
    click.echo(f"demo {scenario_obj.name} complete; report: {report_path}")


def _open_transport_or_warn(scenario_obj: Scenario, logger: structlog.stdlib.BoundLogger) -> None:
    """Open the scenario's transport; on failure, log + raise click.ClickException.

    Phase 3+ wires DAQ; here we only confirm the transport is reachable.
    """
    kind = scenario_obj.transport.kind.value
    target = scenario_obj.transport.target
    timeout_s = scenario_obj.transport.timeout_ms / 1000.0
    if kind != "udp":
        msg = f"demo: transport kind {kind!r} not yet supported (Phase 3+ adds the others)."
        logger.error("demo.transport.unsupported", kind=kind)
        raise click.ClickException(msg)
    _scheme, host, port = _parse_target(target)

    async def _connect() -> None:
        transport = UdpTransport(host, port)
        async with XcpClient(transport, default_timeout_s=timeout_s) as client:
            try:
                await client.connect()
            except (TimeoutError, XcpProtocolError, OSError) as exc:
                logger.error("demo.connect.failed", target=target, error=str(exc))
                raise click.ClickException(f"CONNECT failed: {exc}") from exc

    asyncio.run(_connect())


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
