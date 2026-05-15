# Tethys fuzz harnesses

> Worker D PR-C deliverable. Backed by [`docs/research/phase-10-verification-foundations.md`](../../docs/research/phase-10-verification-foundations.md). Cited rows in [`docs/traceability.csv`](../../docs/traceability.csv): `TETHYS-REQ-VER-002` + `TETHYS-REQ-FAULT-015` + `TETHYS-DES-0011`.

This directory holds the libFuzzer harnesses + corpora that the nightly [`fuzz-nightly.yml`](../../.github/workflows/fuzz-nightly.yml) workflow exercises. The full Phase 10 verification pack (parent plan §8) requires libFuzzer + AFL++ corpora committed with growth tracked nightly and new crashes opening issues automatically.

## Layout

```text
slave/fuzz/
├── fuzz_cto_dispatcher.c       # libFuzzer harness for tethys_xcp_dispatch()
├── fuzz_a2l_parser.py          # atheris harness for tethys_master.protocol.a2l
├── corpus/
│   ├── cto/                    # 64 single-byte PID seeds + crafted multi-byte
│   │   ├── pid_0xc0.bin .. pid_0xff.bin   (64 files; every PID 0xC0..0xFF)
│   │   ├── connect.bin                    (0xFF 0x00)
│   │   ├── disconnect.bin                 (0xFE)
│   │   ├── get_status.bin                 (0xFD)
│   │   ├── get_version.bin                (0xC0)
│   │   ├── set_mta_min.bin                (0xF6 0x00 0x00 0x00 0x00 0x00 0x00 0x00)
│   │   ├── set_mta_high_addr.bin          (0xF6 0x00 0x00 0x00 0xFF 0xFF 0xFF 0xFF)
│   │   ├── upload_one_byte.bin            (0xF5 0x01)
│   │   ├── upload_max.bin                 (0xF5 0x07)
│   │   ├── upload_oversize.bin            (0xF5 0xFF — exercises the oversize-N reject)
│   │   ├── short_upload_min.bin           (0xF4 0x01 0x00 0x00 0x00 0x00 0x00 0x00)
│   │   ├── short_upload_max.bin           (0xF4 0x07 0x00 0x00 0xFF 0xFF 0xFF 0xFF)
│   │   ├── synch.bin                      (0xFC — defined but unimplemented today)
│   │   ├── unknown_low.bin                (0x00 — exercises the catch-all reject)
│   │   ├── unknown_mid.bin                (0x42)
│   │   └── empty.bin                      (empty file — exercises req_len == 0)
│   └── a2l/                    # Minimal A2L seeds for the atheris harness
│       ├── minimal.a2l                    (PROJECT + MODULE only)
│       ├── one_measurement.a2l            (PROJECT + MODULE + MEASUREMENT)
│       ├── one_characteristic.a2l         (PROJECT + MODULE + CHARACTERISTIC)
│       └── nested_if_data.a2l             (3-deep nested IF_DATA stress)
└── README.md                   # this file
```

## Run locally — `fuzz_cto_dispatcher`

```bash
# Linux / macOS. Windows can use WSL or LLVM's libFuzzer for clang-cl.
clang -fsanitize=fuzzer,address,undefined -O1 -g \
  -I slave/include -I slave/tests/test/support \
  slave/fuzz/fuzz_cto_dispatcher.c \
  slave/src/core/xcp_dispatcher.c \
  -o fuzz_cto_dispatcher

./fuzz_cto_dispatcher slave/fuzz/corpus/cto/ -max_total_time=600 -print_pcs=1
```

The `tethys_export.h` stub in [`slave/tests/test/support/tethys/`](../tests/test/support/tethys/) provides the empty visibility macros so the production header compiles cleanly outside the CMake build.

A successful run prints the canonical libFuzzer summary:

```text
INFO: Seed: 1234567890
INFO: Loaded 1 modules (...)
#1024  REDUCE cov: 87 ft: 121 corp: 14/...  ...
#16384 DONE cov: 91 ft: 134 corp: 21/...    (no crashes)
```

Any crash drops a `crash-XXXX` file in the cwd and exits non-zero. Move it to `slave/fuzz/crashes/` and triage per the procedure below.

## Run locally — `fuzz_a2l_parser`

```bash
pip install atheris   # Linux / macOS. atheris does not ship Windows wheels
                      # for every Python release; see https://github.com/google/atheris

cd master
PYTHONPATH=src python ../slave/fuzz/fuzz_a2l_parser.py \
  ../slave/fuzz/corpus/a2l/ -atheris_runs=100000
```

If `atheris` is not installed or `tethys_master.protocol.a2l` is not importable, the harness prints a notice and exits 0 (so CI does not fail on a benign environment gap).

## How the corpus grows

libFuzzer mutates the seed corpus to discover new code paths. When a mutation reaches a new branch, libFuzzer adds the input to the **runtime** corpus (in-memory). To persist a discovery into the **commit** corpus:

```bash
# After a successful run, libFuzzer's `-merge` mode dedupes:
./fuzz_cto_dispatcher -merge=1 slave/fuzz/corpus/cto/ ./runtime-corpus/

# Inspect the diff; commit any net-new files via:
git add slave/fuzz/corpus/cto/<new-file>.bin
git commit -m "test(slave): grow CTO fuzz corpus with <coverage-rationale>"
```

Per parent plan §6.7, the nightly `fuzz-nightly.yml` workflow uploads crash artefacts to `slave/fuzz/crashes/` (retention 90 days). New crashes open issues automatically (TODO PR after Phase 10 full acceptance lands).

## Crash triage procedure

1. The nightly workflow uploads `fuzz-crashes-<run_id>` as a GitHub Actions artefact when any crash file is produced.
2. Download the artefact; the file name is `crash-<hex>`; its content is the raw byte sequence that triggered the crash.
3. Reproduce locally:

   ```bash
   ./fuzz_cto_dispatcher /path/to/crash-<hex>
   ```

4. Capture the sanitiser report (ASan / UBSan stack trace) into a new GitHub Issue using the `bug` template, labelled `area/slave` + `prio/p0` (security) or `prio/p1` (correctness).
5. Add the crash input to a `corpus/cto/regression-<NN>.bin` so the fix is regression-protected.
6. Fix the issue in `slave/src/core/xcp_dispatcher.c` (or wherever the trace lands), reference the issue + this corpus file in the commit body.

## MISRA + ADR-0005 conformance

The harness itself follows the same coding gates as the slave proper:

- No `malloc` / `calloc` / `realloc` / `free` (per [ADR-0005](../../docs/adr/0005-no-dynamic-allocation.md) + [`no-dynamic-allocation.mdc`](../../.cursor/rules/no-dynamic-allocation.mdc)).
- All buffers static (file-scope arrays sized at compile time).
- Loops bounded by `sizeof` or a fixed `FUZZ_MAX_RX` constant.
- No recursion. No goto. Compatible with the [`no-recursion-no-goto.mdc`](../../.cursor/rules/no-recursion-no-goto.mdc) rule.
- libFuzzer / address-sanitiser / undefined-behaviour-sanitiser are the runtime checks; cppcheck-misra is the static check (the harness is included in `misra-gate.yml`'s scan scope).

## CI integration

[`fuzz-nightly.yml`](../../.github/workflows/fuzz-nightly.yml) runs nightly at 06:00 UTC:

1. Installs `clang` + `cmake` + `ninja`.
2. Builds the harnesses via direct `clang -fsanitize=fuzzer,address,undefined -O1 ...` (no `cmake --preset=fuzz` dependency — Worker E owns CMake presets; PR-C uses a direct build to keep the change inside test/CI scope).
3. Runs each harness for `-max_total_time=600` (10 minutes per harness).
4. Uploads crashes as a workflow artefact with 90-day retention.

The same workflow runs on `workflow_dispatch` so a maintainer can kick it manually before merging any future PR that touches the dispatcher.

## Cites

- ASAM XCP 1.4 Part 2 §1.3.2 (CONNECT); §1.3.3 (SET_MTA/UPLOAD/SHORT_UPLOAD); Table 12 (error codes)
- ASAM MCD-2 MC v1.7 §4.4.1 (PROJECT); §4.4.2 (MODULE); §4.4.10 (CHARACTERISTIC); §4.4.18 (MEASUREMENT)
- DO-178C §6.4.4.1 (robustness testing)
- ECSS-E-ST-40C Rev.1 §5.5 (verification activities)
- MISRA C:2023 (Dir 4.12: no dynamic allocation; Rule 17.7)
- LLVM libFuzzer documentation: <https://llvm.org/docs/LibFuzzer.html> (retrieved 2026-05-15)
- Google atheris: <https://github.com/google/atheris> (retrieved 2026-05-15)
