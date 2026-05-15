# tethys-sim

PC-hosted XCP slave simulator used by the Tethys [acceptance bench][bench]
to validate the master tool without requiring real STM32 hardware. Mirrors
the wire-level behaviour of the C slave in `slave/src/core/xcp_dispatcher.c`.

## Quick start

```bash
cd simulator
uv sync
uv run tethys-sim serve --transport udp --port 5555
```

Then connect from another shell using the master:

```bash
cd master
uv run tethys-master connect --target udp://127.0.0.1:5555
```

## Configuration

CLI flags + env vars (prefix `TETHYS_SIM_`):

| Flag | Default | Purpose |
| --- | --- | --- |
| `--transport` | `udp` | Phase-1 supports `udp` only |
| `--host` | `127.0.0.1` | Bind host |
| `--port` | `5555` | Bind port |
| `--profile` | `marine` | `marine` or `space` |
| `--log-level` | `INFO` | |
| `--log-format` | `plain` | `plain` or `json` |

## Cross-references

- [Parent plan](../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md) §7 (Phase 1 acceptance).
- [Master README](../master/README.md).
- [Slave C dispatcher](../slave/src/core/xcp_dispatcher.c).

[bench]: ../docs/research/phase-1-shared-infrastructure-execution.md#acceptance-bench
