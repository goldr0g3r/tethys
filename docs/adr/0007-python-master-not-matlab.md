# ADR-0007 - Python master tool, MATLAB is consumer not driver

- **Status:** accepted
- **Date:** 2026-05-14
- **Deciders:** @goldr0g3r (project owner)
- **Consulted:** parent plan §3.1, §5, §9
- **Informed:** Phase 1 / 2 / 6 / 9 implementers
- **Supersedes:** —
- **Superseded by:** —
- **Accepted by:** PR-3 `docs(architecture)`

## Context and Problem Statement

The XCP master tool is the largest single component of Tethys. The two industry-default master tools (Vector CANape, ETAS INCA) are commercial. Academic and small-team settings frequently reach for MATLAB + the Vehicle Network Toolbox for the same job - but the Vehicle Network Toolbox is a paid MATLAB add-on, not included in academic Campus licences.

The free-tool constraint per [ADR-0008](0008-license-free-toolchain.md) forces a choice: do we build the master tool in Python (consuming pyxcp), in MATLAB (without Vehicle Network Toolbox), or in some other language?

## Decision Drivers

- The [`free-tool-only.mdc`](../../.cursor/rules/free-tool-only.mdc) Cursor rule + [ADR-0008](0008-license-free-toolchain.md) rule out paid MATLAB add-ons.
- The strongest open-source XCP library is [pyxcp](https://github.com/christoph2/pyxcp) (LGPLv3), Python. No equivalent exists in MATLAB without Vehicle Network Toolbox.
- The strongest open-source A2L parser is [Sauci/pya2l](https://github.com/Sauci/pya2l) (BSD-3) / christoph2/pyA2L (GPLv2). Both Python.
- The standard measurement-data format is MDF4; the leading open-source library is [asammdf](https://github.com/danielhrisca/asammdf), Python.
- The GUI requirement (parent §3.1) is well-served by PySide6 (LGPL) + pyqtgraph.
- MATLAB academic users still want to script Tethys; MATLAB R2022a+ has a built-in `py.` interface that calls Python with **zero extra licence cost**.
- Cross-platform requirement (parent §11) means Win/Linux/macOS; Python ships on all three.

## Considered Options

1. **Python master, MATLAB consumer via `py.` interface.** Python is the implementation language; MATLAB calls Python when scripted MATLAB integration is needed.
2. **MATLAB master without Vehicle Network Toolbox.** Reimplement XCP wire protocol + A2L parsing in MATLAB; no licence cost beyond base MATLAB.
3. **C++ master with PySide bindings.** Maximum performance; significant duplication of pyxcp work.
4. **Rust master.** Modern; ecosystem for XCP / A2L / MDF4 is thin or absent.

## Decision Outcome

Chose **Option 1**: Python master + MATLAB consumer via the built-in `py.` interface.

### Composition

| Concern | Component |
| --- | --- |
| Protocol | [pyxcp](https://github.com/christoph2/pyxcp) (LGPLv3) |
| A2L parser | [Sauci/pya2l](https://github.com/Sauci/pya2l) (BSD-3 preferred) + [christoph2/pyA2L](https://github.com/christoph2/pyA2L) (GPLv2 fallback) |
| MDF4 logger | [asammdf](https://github.com/danielhrisca/asammdf) |
| GUI | PySide6 (LGPL) |
| Plots (real-time) | pyqtgraph |
| Plots (post-analysis) | matplotlib |
| Package manager | uv (Astral) |
| Packaging | PyInstaller (per-OS single-file binaries) + pip distribution |

### MATLAB bridge

MATLAB users script Tethys via:

```matlab
tm = py.tethys_master.connect(struct('transport', 'udp', 'host', '127.0.0.1', 'port', 5555));
py.tethys_master.start_daq(tm, py.list({'engine_rpm', 'coolant_temp'}));
% ... run experiment ...
data = py.tethys_master.stop_daq(tm);
py.tethys_master.record_mdf4(data, 'run_001.mf4');
```

No Vehicle Network Toolbox required. The MATLAB academic Campus licence is sufficient.

## Consequences

- **Positive:** Replaces ETAS INCA and Vector CANape (both paid) for the core measurement and calibration flow (per parent §9 commercial-equivalence table).
- **Positive:** Cross-platform out of the box (Win/Linux/macOS) thanks to Python + PySide6.
- **Positive:** MATLAB users keep their workflow without buying Vehicle Network Toolbox.
- **Positive:** A2L parsing reuses two mature libraries instead of reimplementing.
- **Negative:** Hard dependency on the pyxcp project; if pyxcp goes unmaintained, Tethys inherits the maintenance burden. Mitigation: pyxcp is LGPLv3, Tethys can fork if needed.
- **Negative:** GIL-bound Python may struggle at very high DAQ rates (> 1 kHz on multiple ODTs). Mitigation: time-critical paths use C extensions or asyncio; revisit at Phase 3 with empirical data.
- **Risk:** PyInstaller single-file binaries can trigger antivirus false-positives on Windows. Mitigation: sign the bundle once code-signing certificate is procured (out-of-scope for v1.0).

## References

- Parent plan §3.1 (PC master tool stack); §5 (toolchain); §9 (commercial-equivalence table).
- [`free-tool-only.mdc`](../../.cursor/rules/free-tool-only.mdc), [`version-pinning.mdc`](../../.cursor/rules/version-pinning.mdc) - machine-readable enforcement.
- pyxcp - <https://github.com/christoph2/pyxcp>.
- Sauci/pya2l - <https://github.com/Sauci/pya2l>.
- asammdf - <https://github.com/danielhrisca/asammdf>.
- [ADR-0008](0008-license-free-toolchain.md) - records the wider toolchain decision.
