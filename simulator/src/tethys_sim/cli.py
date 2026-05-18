"""Tethys simulator CLI entry-point.

Cite: click v8 (https://click.palletsprojects.com/)
Cite: parent plan section 7 (Phase-1 acceptance bench)
Cite: parent plan section 8 (Phase 9 HIL bench) - ``plant`` subcommand.
"""

from __future__ import annotations

import asyncio
import json
import signal
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

import click
from tethys_master.logging_setup import configure_logging, get_logger

from tethys_sim import __version__
from tethys_sim.hil.reference_plant import (
    SUPPORTED_SCENARIOS,
    BridgeSchemaError,
    PlantScenario,
    ReferencePlant,
)
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


def _resolve_scenario_path(scenario: str, repo_root: Path) -> Path:
    """Allow ``--scenario`` to be a name or an explicit path."""
    candidate = Path(scenario)
    if candidate.is_file():
        return candidate.resolve()
    by_name = repo_root / "hil" / "scenarios" / f"{scenario}.json"
    if by_name.is_file():
        return by_name
    msg = (
        f"scenario {scenario!r} not found; tried {candidate!s} and {by_name!s}. "
        f"Supported scenario kinds (from hil/scenarios/): {SUPPORTED_SCENARIOS}"
    )
    raise click.BadParameter(msg)


@cli.command()
@click.option(
    "--scenario",
    required=True,
    help="Scenario name (without .json) or path to a scenario JSON.",
)
@click.option(
    "--once",
    is_flag=True,
    default=False,
    help="Run a single plant step against the current master_out.csv tail and exit.",
)
@click.option(
    "--repo-root",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    default=Path.cwd(),
    show_default="cwd",
    help="Repository root - bridge file paths in the scenario JSON resolve under here.",
)
def plant(scenario: str, once: bool, repo_root: Path) -> None:
    """Drive the pure-Python reference plant for ``--scenario``.

    Reads ``hil/master_out.csv`` (schema: ``hil/bridge/master_out.schema.md``),
    integrates the chosen ODE for one tick (or ``duration_s`` of the
    scenario JSON when ``--once`` is unset), and writes
    ``hil/plant_out.csv`` (schema: ``hil/bridge/plant_out.schema.md``).
    """
    repo_root_abs = repo_root.resolve()
    scenario_path = _resolve_scenario_path(scenario, repo_root_abs)
    try:
        plant_scenario = PlantScenario.from_json_file(scenario_path)
    except BridgeSchemaError as exc:
        raise click.ClickException(str(exc)) from exc
    runner = ReferencePlant(plant_scenario, repo_root_abs)
    logger = get_logger("tethys-sim.plant")
    logger.info(
        "plant.start",
        scenario=plant_scenario.name,
        kind=plant_scenario.kind,
        sample_time_s=plant_scenario.sample_time_s,
        once=once,
    )

    if once:
        try:
            wrote = runner.step(now_s=time.monotonic())
        finally:
            runner.close()
        click.echo(f"plant tick complete (wrote_row={wrote})")
        return

    raw = scenario_path.read_text(encoding="utf-8")
    duration_s = float(json.loads(raw).get("duration_s", 1.0))
    written = runner.run(duration_s=duration_s)
    logger.info("plant.summary", scenario=plant_scenario.name, rows_written=written)
    click.echo(f"plant finished: rows_written={written}")


__all__ = ["cli", "plant", "serve"]
