# HIL recordings

> Runtime output directory for **MDF4** files produced by
> `tethys-master daq start --out hil/recordings/...` and
> `tethys-master demo <scenario> --record hil/recordings/...`.
>
> Every file in this directory is **ignored by git** (see [`.gitignore`](.gitignore))
> except this `README.md` and the `.gitignore` itself.
> Phase 9 produces; Phase 11 release pipeline bundles into the GitHub Release.

## File naming

```text
hil/recordings/<scenario>-<UTC-yyyymmdd-HHMMSS>.mdf4
```

`<scenario>` matches the `name` field of the matching
[`hil/scenarios/<name>.json`](../scenarios/) descriptor.

## File contents

MDF4 v4.1.1 file written by [`asammdf`](https://github.com/danielhrisca/asammdf)
(LGPL — parent plan §3.1). The header records:

- `tethys-master` version + commit SHA.
- Scenario name + profile.
- Source transport (matches `scenarios.<name>.transport.kind`).
- DAQ rate + signal list.
- Run start / stop UTC timestamps.

The body holds one channel per `daq.signals` entry plus the master's
clock as the timebase channel.

## What NOT to commit here

- Real recordings (any `*.mdf4`, `*.csv`, `*.parquet`).
- Anything containing customer or vehicle PII.
- AES keys (those live in `hil/keys/`, also git-ignored).

If you need to share a recording for review, attach it to the relevant
GitHub Issue or PR; do not push it into the repository.
