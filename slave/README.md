# tethys-slave

The portable C11 embedded slave library for [Tethys][tethys-repo] - a
license-free XCP master + slave for marine and space extreme environments.

This subtree is the C library `tethys-slave`. The PC-side `tethys-master`
Python tool, the simulator, and HIL bench live in sibling directories
(`master/`, `simulator/`, `hil/`).

## Quick start

See [BUILDING.md](BUILDING.md) for the cmake-init derived build instructions.

```bash
cmake -S . -B build/dev --preset=dev
cmake --build build/dev
ctest --test-dir build/dev
```

## Layout

```text
slave/
  include/tethys/         <- public headers
  src/{core,transport,platform}/  <- production C (Phase 1+)
  cmake/                  <- CMake helpers (cmake-init defaults + tethys patches)
  profiles/               <- marine.cmake + space.cmake (Phase 7+)
  tests/                  <- Unity + Ceedling test harness (PR-1a)
  fuzz/                   <- libFuzzer harnesses (Phase 2+)
```

## License

MIT (per ADR-0008). See repository root `LICENSE` once Phase 11 ships it.

## Cross-references

- Parent plan section 14 (layout).
- [ADR-0002 Profile-based build system](../docs/adr/0002-profile-based-build-system.md).
- [ADR-0005 No dynamic allocation](../docs/adr/0005-no-dynamic-allocation.md).
- [docs/coding-standard.md](../docs/coding-standard.md) - naming, header guards,
  banned constructs.
- [slave/tests/README.md](tests/README.md) - test harness quick-start.

[tethys-repo]: https://github.com/goldr0g3r/tethys
