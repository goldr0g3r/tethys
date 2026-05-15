# tethys-master

[![PyPI](https://img.shields.io/pypi/v/tethys-master.svg)](https://pypi.org/project/tethys-master/)
[![Python](https://img.shields.io/pypi/pyversions/tethys-master.svg)](https://pypi.org/project/tethys-master/)

PC-side XCP 1.4 calibration and measurement tool for the
[Tethys](https://github.com/goldr0g3r/tethys) project. License-free
replacement for ETAS INCA / Vector CANape's core flows: connect, A2L browse,
DAQ, calibration, MDF4 record.

## Phase 1 status

- CONNECT / DISCONNECT / GET_VERSION / GET_STATUS over UDP loopback.
- Phase 2 + onward extends to SET_MTA / UPLOAD / DOWNLOAD / DAQ / STIM / CAL.

## Install

```bash
uv tool install tethys-master
```

Or from source:

```bash
cd master
uv sync
uv run tethys-master version
```

## Quick start

Terminal 1 (start the simulator slave):

```bash
cd simulator
uv run tethys-sim serve --transport udp --port 5555
```

Terminal 2 (connect from master):

```bash
cd master
uv run tethys-master connect --target udp://127.0.0.1:5555
```

Expected output:

```text
CONNECT OK
  resource = 0x05
  comm     = 0x80
  max_cto  = 8
  max_dto  = 256
  protocol = 0x01, transport = 0x01
  version  = protocol 1.4, transport 1.4
  status   = session 0x80, protect 0x00
DISCONNECT OK
```

## Configuration

Environment variables (prefix `TETHYS_MASTER_`) or `.env` file:

| Variable | Default | Purpose |
| --- | --- | --- |
| `LOG_LEVEL` | `INFO` | `DEBUG`/`INFO`/`WARNING`/`ERROR` |
| `LOG_FORMAT` | `plain` | `plain` or `json` |
| `PROFILE` | `marine` | `marine` or `space` |
| `UDP_DEFAULT_HOST` | `127.0.0.1` | |
| `UDP_DEFAULT_PORT` | `5555` | |
| `CONNECT_TIMEOUT_MS` | `1000` | |
| `RESPONSE_TIMEOUT_MS` | `500` | |

## Develop

```bash
uv sync --extra dev
uv run ruff check .
uv run ruff format --check .
uv run mypy src/tethys_master
uv run pytest --cov=tethys_master
```

## Cross-references

- [Parent plan](../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md)
  section 3.1.
- [ADR-0001 XCP as a development-time protocol](../docs/adr/0001-xcp-as-development-protocol.md).
- [ADR-0004 Transport abstraction layer](../docs/adr/0004-transport-abstraction-layer.md).
- [ADR-0007 Python master, not MATLAB](../docs/adr/0007-python-master-not-matlab.md).
- [docs/coding-standard.md](../docs/coding-standard.md) §2.3 Python style.
