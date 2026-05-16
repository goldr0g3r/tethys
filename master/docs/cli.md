# CLI reference

> **Audience:** anyone driving `tethys-master` from a shell, a CI job,
> a Makefile, or a MATLAB `py.` call.
> **Scope:** mirror of `tethys-master --help` annotated with examples,
> exit codes, and cross-references to the deeper Python API.
> **Length budget:** 2 pages.
>
> Source: [`master/src/tethys_master/cli.py`](../src/tethys_master/cli.py).

## 1. Invocation shape

```text
tethys-master [GLOBAL OPTIONS] <COMMAND> [COMMAND OPTIONS] [ARGS]
```

All commands return a POSIX exit code:

| Exit | Meaning |
| --- | --- |
| `0` | Success. |
| `1` | Command failed at runtime (transport error, protocol error, timeout). |
| `2` | Bad invocation (click `BadParameter`). |
| `130` | User interrupted (Ctrl-C). |

## 2. Global options

| Flag | Type | Default | Meaning |
| --- | --- | --- | --- |
| `--log-level` | `DEBUG \| INFO \| WARNING \| ERROR \| CRITICAL` | `INFO` (or `$TETHYS_MASTER_LOG_LEVEL`) | structlog root level. |
| `--log-format` | `plain \| json` | `plain` (or `$TETHYS_MASTER_LOG_FORMAT`) | structlog renderer. JSON for CI / structured ingestion; plain for humans. |
| `--version` | flag | - | Print `tethys-master <version>` and exit. |
| `--help` | flag | - | Print global help and exit. |

Examples:

```bash
tethys-master --log-level DEBUG --log-format json version
tethys-master --version
```

## 3. Commands

### 3.1 `version`

Print the package version. Useful as a CI smoke test.

```bash
tethys-master version
# tethys-master 0.1.0
```

### 3.2 `connect`

Single-shot CONNECT (with immediate DISCONNECT) against an XCP slave.
Verifies the protocol handshake works end-to-end without any DAQ or
calibration side-effects.

| Flag | Type | Default | Meaning |
| --- | --- | --- | --- |
| `--target` | string | `udp://127.0.0.1:5555` | `<scheme>://<host>:<port>`. Phase 1 supports `udp://`; Phase 5 adds `tcp://`, `can://`, `serial://`. |
| `--connect-timeout-ms` | int | `1000` (or `$TETHYS_MASTER_CONNECT_TIMEOUT_MS`) | CONNECT response timeout in ms. |
| `--mode` | int | `0` | `CONNECT` mode byte. `0` = normal, `1` = user-defined per XCP 1.4 §1.3.2.4. |

Example:

```bash
tethys-master connect \
  --target udp://192.168.1.10:5555 \
  --connect-timeout-ms 2000
```

Exit code `0` + the formatted CONNECT + GET_VERSION + GET_STATUS
response.

### 3.3 `gui`

Launch the PySide6 desktop GUI (requires the `[gui]` extra).

```bash
tethys-master gui
```

Trailing arguments are forwarded to Qt as `QApplication` argv. To run
the GUI headless under CI:

```bash
QT_QPA_PLATFORM=offscreen tethys-master gui
```

The GUI window panes are described in [`gui.md`](gui.md).

## 4. Planned commands (later phases)

| Command | Phase | Description |
| --- | --- | --- |
| `tethys-master daq start` | 3 | Start a DAQ list. Writes MDF4 to `--out`. |
| `tethys-master cal write` | 4 | Write a CHARACTERISTIC. Honours profile invariants. |
| `tethys-master demo <scenario>` | 9 | Run a canned HIL scenario from `hil/scenarios/`. |
| `tethys-master fuzz-replay <case>` | 10 | Replay a fuzz corpus case against a target slave. |

Plan reference:
[`xcp_extreme-env_tool_14019278.plan.md`](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md)
section 8.

## 5. Logging

`tethys-master` uses [structlog](https://www.structlog.org) with two
renderers:

- `plain` - colourised human-readable lines (default).
- `json` - one JSON object per line (CI, log aggregators).

Set globally via `--log-format` or `TETHYS_MASTER_LOG_FORMAT`.

Per-event keys recorded by the CLI:

| Event | Keys |
| --- | --- |
| `tethys-master.version` | `version` |
| `xcp.connect.failed` | `target`, `error` |
| `gui.launch.invoked` | `extra_args` |

## 6. CI usage

The repository's CI (`ci.yml`) exercises the CLI under both
`uv run tethys-master ...` and via the Docker image
(`infrastructure/docker/Dockerfile.master`).

For local CI parity:

```bash
QT_QPA_PLATFORM=offscreen TETHYS_MASTER_LOG_FORMAT=json \
  uv run tethys-master version
```

## Cross-references

- [`installation.md`](installation.md).
- [`api.md`](api.md).
- [`master/src/tethys_master/cli.py`](../src/tethys_master/cli.py).
- [click v8 docs](https://click.palletsprojects.com/).
- [structlog docs](https://www.structlog.org/).
