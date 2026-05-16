# HIL artifacts

> Bundled outputs of an end-to-end recorded demo, per
> [`docs/runbooks/demo-recording.md`](../../docs/runbooks/demo-recording.md).
> Phase 9 produces; Phase 11 release pipeline uploads to the GitHub Release
> as `.zip` archives.
>
> Files are git-ignored (see [`.gitignore`](.gitignore)) except this README.

## Bundle structure (per `demo-recording.md`)

```text
hil/artifacts/<scenario>-<UTC-yyyymmdd>/
  README.md           # one-paragraph human summary
  recording.mp4       # OBS screen capture
  recording.srt       # closed captions, when available
  master.mdf4         # MDF4 from hil/recordings/
  master.csv          # decimated CSV (LibreOffice-friendly)
  plant.csv           # Simulink scope dump (or reference-plant CSV)
  report.html         # HTML report from hil/reports/
  bench-photo.jpg     # phone snap of physical bench
```

## Why git-ignore the binaries

- Repository size budget (MP4 captures are 50-200 MB each).
- Demo artefacts are reproducible from the source scenario + slave + master.
- GitHub Releases (Phase 11) is the canonical distribution channel; the
  repo just keeps the slot reserved.

If a particular recording becomes a regression-test anchor (e.g. a
demo that demonstrates a specific MISRA deviation rationale), promote
it by:

1. Open an Issue with `type/test` + `phase/9` labels.
2. Land a small CSV-only artefact (drop the MP4) under `slave/tests/regression-corpus/`.
3. Reference the Issue from this README's history block.

## Cross-references

- [`docs/runbooks/demo-recording.md`](../../docs/runbooks/demo-recording.md).
- [`docs/runbooks/release-process.md`](../../docs/runbooks/release-process.md).
- Parent plan section 11 (public deliverables).
