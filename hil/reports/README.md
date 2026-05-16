# HIL reports

> Runtime output directory for **HTML demo reports** emitted by
> `tethys-master demo <scenario> --report hil/reports/...`.
>
> Files are git-ignored (see [`.gitignore`](.gitignore)) except this
> README and the `.gitignore`. Phase 9 produces; Phase 11 release
> pipeline can embed the HTML in the docs site.

## File naming

```text
hil/reports/<scenario>-<UTC-yyyymmdd-HHMMSS>.html
```

## Report sections (per `docs/runbooks/hil-bench-setup.md` §6.2)

| Section | Content |
| --- | --- |
| DAQ statistics | Frame count, dropped count, latency histogram. Target: dropped == 0. |
| CAL statistics | Writes attempted / acknowledged / CRC failures. Target: CRC failures == 0. |
| Plant statistics | Simulation overrun count; bridge_master_timeout count. Target: overruns == 0. |
| Closed-loop performance | Rise time, overshoot, steady-state error per controlled CHARACTERISTIC. |
| Traceability | Lists every standards row from `scenarios.<name>.trace` that the run touched. |

## Renderer

The HTML is emitted by the master's report renderer (Phase 9 add to
`master/src/tethys_master/hil/report.py`) using Jinja2 against a static
template. No JavaScript runtime dependencies; the HTML opens in any
browser including the Vector free MDF Viewer's embedded HTML pane.

## What NOT to commit here

- Real reports (`*.html`, `*.json`, `*.svg` from a run).
- Any image embedded as base64 (those bloat the diff).

Attach a representative report to a GitHub Issue or PR for review.
