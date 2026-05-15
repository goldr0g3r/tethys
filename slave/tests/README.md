# slave/tests - Unity + Ceedling test harness

Test harness for the Tethys slave C library. Driven by [Ceedling][ceedling] +
[Unity][unity] + [CMock][cmock] from
[ThrowTheSwitch.org][throwtheswitch].

## Quick start

```bash
gem install ceedling
cd slave/tests
ceedling test:all
```

```powershell
gem install ceedling
cd slave/tests
ceedling test:all
```

Expected output:

```text
TESTED:  N
PASSED:  N
FAILED:  0
IGNORED: 0
```

## Layout

```text
slave/
  src/                 <- production C code (Ceedling pulls from here)
  include/             <- public headers
  tests/
    project.yml        <- Ceedling configuration; paths point at ../src/ + ../include/
    test/
      test_<module>.c  <- one Unity test file per module under test
    test/support/      <- shared mocks / fixtures
    build/             <- generated; gitignored
    docs/              <- vendored Unity / CMock / CException docs
```

## Why Unity + Ceedling

- **Unity** is the bare-metal-friendly C test framework matching ECSS / DO-178C
  style of structured assertions (see ADR-0003 for the coding gate; Unity
  surfaces failures cleanly enough for DAL-B grade test reports).
- **Ceedling** is the Ruby-based test runner that generates `*_runner.c` files
  from your `test_*.c` files, links against Unity + your source, and produces
  the pass/fail summary plus optional gcov coverage reports.
- **CMock** generates type-safe mocks for any header you declare; the project
  enables the `module_generator` plugin so `ceedling module:create:<module>`
  scaffolds source + header + test in one shot.

## Naming convention

Per [`docs/coding-standard.md`](../../docs/coding-standard.md) §3.3:

- One test file per module: `test_<module>.c`
- Multi-scenario tests within the same file: `test_<module>__<scenario>`
  (double underscore separator).
- Mocks for `<module>.h` are named `mock_<module>.h` (CMock default).

## Coverage

`ceedling gcov:all` runs the suite with gcov enabled. Coverage report drops
into `tests/build/artifacts/gcov/`. The `coverage.yml` workflow (PR-4) collects
the artefact and posts the gcovr summary in the PR conversation.

Coverage targets per parent §6.7:

- `slave/src/core/` >= 95% statement, >= 90% MC/DC
- `slave/src/transport/` + `slave/src/platform/` >= 85% statement

## Cross-references

- Parent plan section 6.7 (CI gate matrix; unit-test rows).
- Parent plan section 14 (repository layout).
- [ADR-0003 - MISRA C:2023 as the coding gate](../../docs/adr/0003-misra-c-2023-as-coding-gate.md).
- [docs/coding-standard.md](../../docs/coding-standard.md) §3.3 + §8.

[ceedling]: https://github.com/ThrowTheSwitch/Ceedling
[unity]: https://github.com/ThrowTheSwitch/Unity
[cmock]: https://github.com/ThrowTheSwitch/CMock
[throwtheswitch]: https://throwtheswitch.org/
