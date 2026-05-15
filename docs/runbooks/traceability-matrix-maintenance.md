# Runbook - Traceability matrix maintenance

> Audience: any engineer adding a requirement / design / test row, or
> reconciling the CI gate failure on `docs/traceability.csv` drift.
> Goal: from "I'm about to add a new row" or "CI just failed on traceability"
> to "matrix is updated, CI green, downstream gates satisfied". Wall-clock
> target: **15 minutes**.
> Style: schema first, common workflows, validation, troubleshooting.
>
> Implements parent plan §4 (safety + standards mapping) and §6.7
> (CI gate matrix). Companion to
> [`.cursor/rules/ecss-traceability.mdc`](../../.cursor/rules/ecss-traceability.mdc).

## Table of contents

1. [Schema](#1-schema)
2. [When to add a row](#2-when-to-add-a-row)
3. [Adding a row](#3-adding-a-row)
4. [Local validation](#4-local-validation)
5. [CI gate behaviour](#5-ci-gate-behaviour)
6. [Periodic re-validation](#6-periodic-re-validation)
7. [Troubleshooting](#7-troubleshooting)
8. [Cross-references](#8-cross-references)

---

## 1. Schema

`docs/traceability.csv` is the canonical source of truth. Each row maps one
requirement / design element / test back to its controlling standard objective.

### 1.1 Header row

```csv
id,kind,parent,description,implemented_by,verified_by,standard_objective,phase,profile
```

### 1.2 Field semantics

| Field | Required | Format / vocabulary |
| --- | --- | --- |
| `id` | yes | `TETHYS-<KIND>-<NNNN>`; KIND ∈ {`REQ`, `DES`, `TST`, `DEV`}; NNNN is zero-padded monotonic |
| `kind` | yes | `REQ` (requirement) / `DES` (design) / `TST` (test) / `DEV` (deviation) |
| `parent` | conditional | Required for `DES`/`TST`/`DEV`; points at the `REQ` row |
| `description` | yes | One-sentence English; quoted if it contains commas |
| `implemented_by` | conditional | Path glob relative to repo root, e.g. `slave/src/core/daq.c` |
| `verified_by` | yes | Path glob to the test file proving it, e.g. `slave/tests/test_daq.c` |
| `standard_objective` | yes | Semicolon-separated list: `ECSS-E-ST-40C-Rev1 §5.4.3.1; ISO 26262-6:2018 §6.4.3` |
| `phase` | yes | Integer 0-11 indicating which Phase the row first appeared in |
| `profile` | yes | Pipe-separated list: `marine\|space` or `marine` or `space` or `all` |

### 1.3 Sample rows

```csv
id,kind,parent,description,implemented_by,verified_by,standard_objective,phase,profile
TETHYS-REQ-0001,REQ,,"XCP CONNECT response within 50 ms",slave/src/core/dispatcher.c,slave/tests/test_connect.c,ASAM XCP 1.4 Part 2 §1.3.2.4,2,all
TETHYS-DES-0001,DES,TETHYS-REQ-0001,"Stateless CONNECT handler in dispatcher",slave/src/core/dispatcher.c,slave/tests/test_connect.c,ASAM XCP 1.4 Part 2 §1.3.2.4,2,all
TETHYS-TST-0001,TST,TETHYS-REQ-0001,"CONNECT round-trip latency p95 < 50 ms over UDP loopback",,slave/tests/test_connect.c,ASAM XCP 1.4 Part 2 §1.3.2.4,2,all
TETHYS-REQ-0042,REQ,,"DAQ logs DAQ_GAP event on CTR mismatch",slave/src/core/daq.c,slave/tests/test_daq_gap.c,ECSS-E-ST-40C-Rev1 §5.4.3.1; ISO 26262-6:2018 §6.4.3,3,marine|space
TETHYS-DEV-0001,DEV,TETHYS-REQ-0042,"MISRA-DEV-0001: union for ASAM CTO payload",slave/src/core/dispatcher.c,slave/tests/test_dispatcher.c,MISRA C:2023 Rule 19.2,2,all
```

## 2. When to add a row

Per [`ecss-traceability.mdc`](../../.cursor/rules/ecss-traceability.mdc), add
a row whenever the PR introduces:

- New protocol command.
- New transport.
- New profile invariant.
- New fault-injection scenario.
- New ADR (each ADR's rationale traces to >=1 standard objective).
- New test that covers a previously untraced behaviour.
- New MISRA deviation (also goes into `docs/misra-deviations.md`; trace row
  uses `kind=DEV`).

**Do NOT** add a row for:

- Refactor that preserves semantics (no behaviour change).
- Pure scaffolding (uv init / cmake-init emissions).
- Comment-only / docs-only changes.
- CI workflow tweaks that do not change gate semantics.

## 3. Adding a row

### 3.1 Find the next id

```powershell
$nextReq = (Get-Content docs/traceability.csv | Select-String "^TETHYS-REQ-" | ForEach-Object {
  ($_ -split ",")[0] -replace "TETHYS-REQ-", ""
} | Sort-Object {[int]$_} -Descending | Select-Object -First 1)
$nextReq = ([int]$nextReq + 1).ToString("D4")
"Next REQ id: TETHYS-REQ-$nextReq"
```

```bash
NEXT_REQ=$(grep -E "^TETHYS-REQ-" docs/traceability.csv \
  | cut -d, -f1 | sed 's/TETHYS-REQ-//' | sort -n | tail -n1)
NEXT_REQ=$(printf "TETHYS-REQ-%04d" $((NEXT_REQ + 1)))
echo "Next REQ id: $NEXT_REQ"
```

Repeat for `TST` / `DES` / `DEV` as needed.

### 3.2 Append the row

Open `docs/traceability.csv` in any editor; append at the end (do not reorder
existing rows - the file is sorted by id ascending). Quote any field
containing a comma or newline.

```csv
TETHYS-REQ-0123,REQ,,"GET_STATUS returns RESUME bit after warm boot",slave/src/core/dispatcher.c,slave/tests/test_get_status.c,ASAM XCP 1.4 Part 2 §1.3.2.5,2,all
```

### 3.3 Commit with the cite

Per [`always-cite-standards.mdc`](../../.cursor/rules/always-cite-standards.mdc),
the PR body must include the standard citation:

```text
Cite: ASAM XCP 1.4 Part 2 §1.3.2.5
Trace: docs/traceability.csv row TETHYS-REQ-0123
Closes: #NN
```

## 4. Local validation

A minimal validation script (Python, no external deps):

```python
# scripts/trace_check.py - lands in PR-10 p10-verification
import csv
import pathlib
import sys

CSV_PATH = pathlib.Path("docs/traceability.csv")
ALLOWED_KINDS = {"REQ", "DES", "TST", "DEV"}
ALLOWED_PROFILES = {"all", "marine", "space"}

def main():
    if not CSV_PATH.exists():
        print(f"::error::{CSV_PATH} not found")
        return 1
    with CSV_PATH.open(newline="") as fh:
        reader = csv.DictReader(fh)
        ids = set()
        errors = []
        for row_num, row in enumerate(reader, start=2):
            rid = row["id"]
            if not rid.startswith("TETHYS-"):
                errors.append(f"row {row_num}: bad id {rid!r}")
            if rid in ids:
                errors.append(f"row {row_num}: duplicate id {rid!r}")
            ids.add(rid)
            if row["kind"] not in ALLOWED_KINDS:
                errors.append(f"row {row_num}: bad kind {row['kind']!r}")
            for prof in row["profile"].split("|"):
                if prof not in ALLOWED_PROFILES:
                    errors.append(f"row {row_num}: bad profile {prof!r}")
            if row["kind"] != "REQ" and not row["parent"]:
                errors.append(f"row {row_num}: {row['kind']} requires parent")
        for err in errors:
            print(f"::error::{err}")
        return 1 if errors else 0

if __name__ == "__main__":
    sys.exit(main())
```

Run:

```bash
python scripts/trace_check.py && echo "OK"
```

Expected: `OK` and exit 0.

## 5. CI gate behaviour

`PR-10 p10-verification` adds a CI workflow that:

1. Runs `scripts/trace_check.py` on every PR.
2. Greps the diff for new files under `slave/src/core/`,
   `master/src/tethys_master/protocol/`, `slave/tests/`, `slave/fuzz/`.
3. For each new file, checks if it appears as a value in any `implemented_by`
   or `verified_by` column.
4. If a new file is untraced, the workflow fails with an actionable error
   message including the suggested row template.

The gate runs as part of `static-analysis.yml` (single workflow keeps PR check
count manageable).

## 6. Periodic re-validation

Quarterly maintenance:

```bash
# Verify every implemented_by + verified_by path still exists
python scripts/trace_orphans.py
```

The output is a list of rows whose `implemented_by` or `verified_by` paths no
longer exist (file deleted in a refactor). Each orphan needs:

- File replaced (path update in the row), OR
- Row marked `obsolete` (move to `docs/traceability-archive.csv` with a date).

Quarterly review issue auto-opened by `release.yml` on the first push of each
quarter (cron `0 0 1 1,4,7,10 *`).

## 7. Troubleshooting

| Symptom | Diagnosis | Fix |
| --- | --- | --- |
| `trace_check.py` reports `duplicate id` | Two rows with same TETHYS-NNNN | Bump the second to the next free id; re-sort the file |
| CI fails: `new file slave/src/core/foo.c not traced` | Forgot to add a row | Add the row in the same PR; re-push |
| CSV refuses to open in LibreOffice | Embedded comma not quoted | Wrap the description in `"..."` |
| `verified_by` path is a glob and the gate fails | Globs not yet supported by the gate (PR-10 + 1) | Use a single concrete path; add a follow-up `kind=TST` row for each test file if needed |
| ADR rationale not traceable to a standard | The ADR is purely tooling (e.g. ADR-0008 license) | Use `standard_objective=N/A`; the gate allows `N/A` for `kind=DES` rows tied to license / process ADRs |

## 8. Cross-references

- Parent plan section 4 (safety + standards mapping).
- Parent plan section 6.7 (CI gate matrix).
- [.cursor/rules/ecss-traceability.mdc](../../.cursor/rules/ecss-traceability.mdc).
- [.cursor/rules/always-cite-standards.mdc](../../.cursor/rules/always-cite-standards.mdc).
- [docs/research/phase-0-standards-matrix.csv](../research/phase-0-standards-matrix.csv) - S1-S35 standards index.
- [docs/coding-standard.md](../coding-standard.md) - MISRA deviation procedure (TETHYS-DEV-NNNN rows).
- [docs/misra-deviations.md](../misra-deviations.md) - linked register.
- [Runbook: incident-and-defect.md](incident-and-defect.md) - DEV row creation
  during incident review.
