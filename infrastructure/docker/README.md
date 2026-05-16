# Tethys Docker images

> Three Dockerfiles + one `compose.yml` covering the master tool, the
> Python simulator slave, and the slave C-library build environment.
> Used by the CI (`ci.yml` slave matrix legs + `misra-gate.yml`) and
> targeted as a Phase 11 release artefact ([parent §11](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md#11-public-deliverables-what-someone-reading-the-repo-will-see)).
>
> Parent plan: §5 (license-free toolchain), §6.7 (`ci.yml` slave matrix),
> §11 (release artefacts).
> ADR anchor: [ADR-0008 — license-free toolchain](../../docs/adr/0008-license-free-toolchain.md).

## Why three images

| Image | Built from | Used for | Phase |
| --- | --- | --- | --- |
| `tethys-master` | [`Dockerfile.master`](Dockerfile.master) | Run `tethys-master` CLI in an isolated environment. CI integration tests use this to drive the simulator from a clean container. Release pipeline pushes it to GHCR. | 9 + 11 |
| `tethys-sim` | [`Dockerfile.simulator`](Dockerfile.simulator) | Host-side simulator slave. Stand it up next to the master in `compose.yml` for the acceptance bench. | 1+ (already runs) |
| `tethys-slave-builder` | [`Dockerfile.slave-builder`](Dockerfile.slave-builder) | C library build container. GCC + Clang + arm-none-eabi-gcc + Ceedling + cppcheck + clang-tidy + gcovr. CI uses this for the slave matrix legs without juggling apt installs per job. | 0+ (CI today) |

## License posture (parent §5 + ADR-0008)

Every base image is OSI / free:

- `python:3.12.7-slim-bookworm` — PSF + Debian. PSF licence.
- `debian:bookworm-slim` — Debian project. Free.

No paid Vector / ETAS / Polyspace / LDRA / MULTI image appears. The
[`free-tool-only.mdc`](../../.cursor/rules/free-tool-only.mdc) rule
fires on every Dockerfile change.

## Pinning policy (parent §6.1 + version-pinning.mdc)

- Base image tags carry the **exact** patch version (`3.12.7`,
  `bookworm-slim` is bound to the December 2024 point release).
- A Phase 11 PR will switch every base image to a digest pin
  (`python@sha256:…`) when Renovate's docker manager is enabled.
- Python wheels in every image read from
  [`master/pyproject.toml`](../../master/pyproject.toml) /
  [`simulator/pyproject.toml`](../../simulator/pyproject.toml) — already
  pinned exactly.

## Build + run

### Master (CLI)

```bash
cd infrastructure/docker
docker build -t tethys-master:dev -f Dockerfile.master ../..
docker run --rm tethys-master:dev tethys-master version
```

Expected: `tethys-master 0.1.0` (matches
[`master/src/tethys_master/__init__.py`](../../master/src/tethys_master/__init__.py)).

### Simulator (slave)

```bash
cd infrastructure/docker
docker build -t tethys-sim:dev -f Dockerfile.simulator ../..
docker run --rm -p 5555:5555/udp tethys-sim:dev tethys-sim serve --port 5555
```

### Slave-builder (CI use)

```bash
cd infrastructure/docker
docker build -t tethys-slave-builder:dev -f Dockerfile.slave-builder ../..
docker run --rm -v "$PWD/../..:/workspace" tethys-slave-builder:dev \
  cmake --preset dev && \
  docker run --rm -v "$PWD/../..:/workspace" tethys-slave-builder:dev \
  cmake --build --preset dev
```

### Master <-> simulator acceptance bench

```bash
cd infrastructure/docker
docker compose up --build --abort-on-container-exit --exit-code-from master
```

Compose stitches `tethys-sim serve` on a private UDP network and runs
`tethys-master connect --target udp://simulator:5555` in the master
container; exit-code-from `master` means the run pass/fail is the
master's exit code. The whole bench finishes in <10 seconds.

## Maintenance

- Bump base-image tag → open PR with title `chore(docker): bump
  python to <version>` and quote the Python security release notes
  in the body.
- Renovate proposes upgrades via PR; never bump silently.
- Image-size regression > 25% triggers a `chore(docker): investigate
  size bump` issue (parent §6.7 implicit budget; CI does NOT yet gate
  image size — Phase 11 task).

## Cross-references

- Parent plan section 5 (toolchain).
- Parent plan section 6.7 (`ci.yml` slave matrix; `misra-gate.yml`).
- Parent plan section 11 (release artefacts).
- [`docs/runbooks/release-process.md`](../../docs/runbooks/release-process.md).
- [`docs/runbooks/supply-chain-and-sbom.md`](../../docs/runbooks/supply-chain-and-sbom.md).
- [ADR-0008 license-free toolchain](../../docs/adr/0008-license-free-toolchain.md).
- [`.cursor/rules/free-tool-only.mdc`](../../.cursor/rules/free-tool-only.mdc).
- [`.cursor/rules/version-pinning.mdc`](../../.cursor/rules/version-pinning.mdc).
