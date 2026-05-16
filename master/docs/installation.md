# Installation

> **Audience:** engineer installing `tethys-master` for the first time.
> **Scope:** from "nothing installed" to "`tethys-master version`
> prints". Covers Windows / macOS / Linux + the four optional extras.
> **Length budget:** 1 page.

## 1. Prerequisites

| Tool | Minimum | Why |
| --- | --- | --- |
| Python | 3.11 | `pyproject.toml` `requires-python` lower bound. |
| [`uv`](https://github.com/astral-sh/uv) | 0.4 | Project + tool installer (parent plan section 5). |
| git | 2.40 | Cloning the repo (only needed for development install). |

Verify:

```powershell
python --version ; uv --version ; git --version
```

```bash
python --version && uv --version && git --version
```

Expected: three version banners, no errors.

## 2. Install options

### 2.1 As an end-user CLI tool (preferred)

```bash
uv tool install tethys-master
```

Test:

```bash
tethys-master version
```

Expected: `tethys-master 0.1.0` (or whatever the current package
version is - see [`master/src/tethys_master/__init__.py`](../src/tethys_master/__init__.py)).

This installs the package + its CLI entry point into uv's tool venv;
the binary `tethys-master` is added to PATH.

### 2.2 As a Python library

```bash
uv pip install tethys-master
```

Then in your own project:

```python
from tethys_master.protocol.client import XcpClient
from tethys_master.transport.udp import UdpTransport
```

API reference: [api.md](api.md).

### 2.3 From source (development)

```bash
git clone https://github.com/goldr0g3r/tethys.git
cd tethys/master
uv sync --all-extras  # picks up [gui] + [dev] + [diff-test]
uv run tethys-master version
```

## 3. Optional extras

`tethys-master` ships with four pip-install extras, all pinned per
[`.cursor/rules/version-pinning.mdc`](../../.cursor/rules/version-pinning.mdc):

| Extra | Pulls in | Use when |
| --- | --- | --- |
| `[gui]` | PySide6, pyqtgraph, asammdf | You want the desktop GUI (`tethys-master gui`). |
| `[dev]` | mypy, pytest, pytest-qt, pytest-asyncio, pytest-cov, ruff | You are running the test suite or static checks. |
| `[diff-test]` | pyxcp (LGPL-3) | You are running the Phase-2 differential acceptance test against the pyxcp reference master. |

Install one extra:

```bash
uv pip install 'tethys-master[gui]'
```

Install all extras (development install):

```bash
cd master
uv sync --all-extras
```

The GUI extras pull in ~150 MB of binary wheels (PySide6 ships its own
Qt runtime); the headless CLI install stays at ~12 MB.

## 4. Environment variables

`tethys-master` reads its defaults from environment variables prefixed
`TETHYS_MASTER_` or from a `.env` file in CWD. CLI flags override.

| Variable | Default | Purpose |
| --- | --- | --- |
| `TETHYS_MASTER_LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `TETHYS_MASTER_LOG_FORMAT` | `plain` | `plain` or `json` (structlog renderer) |
| `TETHYS_MASTER_PROFILE` | `marine` | Default profile if scenario doesn't set one. |
| `TETHYS_MASTER_UDP_DEFAULT_HOST` | `127.0.0.1` | |
| `TETHYS_MASTER_UDP_DEFAULT_PORT` | `5555` | |
| `TETHYS_MASTER_CONNECT_TIMEOUT_MS` | `1000` | Initial CONNECT timeout. |
| `TETHYS_MASTER_RESPONSE_TIMEOUT_MS` | `500` | Per-CTO response timeout. |

Source: [`master/src/tethys_master/config.py`](../src/tethys_master/config.py)
(`MasterSettings` Pydantic model).

## 5. Verifying the install

Three smoke tests, ordered cheapest first:

```bash
# 1. CLI exists
tethys-master --help

# 2. CLI version
tethys-master version

# 3. CLI talks to the simulator over UDP loopback (needs tethys-sim running)
tethys-master connect --target udp://127.0.0.1:5555
```

Run the simulator in another shell first:

```bash
cd simulator
uv run tethys-sim serve --transport udp --port 5555
```

## 6. Uninstall

```bash
uv tool uninstall tethys-master
```

Or the from-source install:

```bash
cd master
uv venv remove
```

## 7. Troubleshooting

| Symptom | Diagnosis | Fix |
| --- | --- | --- |
| `command not found: tethys-master` | uv tool not on PATH | Run `uv tool update-shell` or add `$HOME/.local/bin` to PATH. |
| `ImportError: PySide6` | GUI extra not installed | `uv pip install 'tethys-master[gui]'`. |
| GUI fails to start under CI | Qt needs a display | `export QT_QPA_PLATFORM=offscreen` (already set in `ci.yml`). |
| `CONNECT failed: TimeoutError` | Simulator not running or wrong port | Check `tethys-sim serve` is up; ports match. |

## Cross-references

- [`cli.md`](cli.md).
- [`api.md`](api.md).
- [`master/README.md`](../README.md).
- [`docs/runbooks/hardware-setup-stm32.md`](../../docs/runbooks/hardware-setup-stm32.md).
