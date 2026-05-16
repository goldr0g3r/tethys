# Profiles (master-side)

> **Audience:** engineer choosing between the marine and space profiles
> in the master, or wiring profile-aware flow into a custom script.
> **Scope:** what the profile selector changes in the master's behaviour;
> what *does NOT* change. Slave-side compile flags are documented under
> [`slave/profiles/`](../../slave/profiles/) and the rule mirror.
> **Length budget:** 2 pages.
>
> Source of truth: [`master/src/tethys_master/profiles/`](../src/tethys_master/profiles/)
> (Python) + [`slave/profiles/{marine,space}.cmake`](../../slave/profiles/) (CMake).
> Invariants: [`.cursor/rules/marine-profile-invariants.mdc`](../../.cursor/rules/marine-profile-invariants.mdc),
> [`.cursor/rules/space-profile-invariants.mdc`](../../.cursor/rules/space-profile-invariants.mdc).

## 1. What a profile is

A profile is a **single-string identifier** (`marine` or `space`) plus
the set of feature gates each implies. Tethys uses profiles to:

- Pick the right defaults (transport, DAQ rate, seed-and-key length).
- Filter writable CHARACTERISTICs in the GUI calibration editor.
- Decide whether the master must perform an AES-128 service-mode
  unlock before issuing any CAL write.
- Map the right standards row set into MDF4 headers and the run report
  (HIL).

The slave half of the profile is **compile-time**: the C code is built
with `cmake -DTETHYS_PROFILE=marine` (or `=space`) and ships with a
single profile baked in. The master is **runtime-switchable**: a
single master binary can talk to both kinds of slave because the
master never *runs* the slave-side invariants - it adapts its UX to
them.

## 2. Comparison (master half of parent §3.3)

| Concern | Marine | Space |
| --- | --- | --- |
| Default transport (master view) | UDP, port 5555 (lab) or 60001 (IEC 61162-450). | UART/SxI, 115200 baud. |
| Default DAQ rate | 1 kHz. | 200 Hz. |
| Service-mode unlock required for CAL? | No (default profile). | Yes (AES-128, ADR-0006). |
| CAL writes CRC-checked? | Optional (`TETHYS_MARINE_CAL_PAGE_CRC=1` on slave). | Mandatory. |
| Watchdog awareness in master | Reports kicks if observed. | Reports kicks AND deadline misses as scenario failure. |
| MDF4 logging budget | Unlimited. | Ring buffer with watermark. |
| Allowed transports | UDP, TCP, SocketCAN. | UART/SxI, CCSDS-COP-1-AD, CAN-1wire. |
| Standards row set in MDF4 header | IACS UR E22 Rev.3, IEC 60945, IEC 61784-3. | ECSS-E-ST-40C Rev.1, NPR 7150.2D, DO-178C DAL-B, NIST FIPS-197. |

Source: parent plan section 3.3 profile table + the rule files.

## 3. Selecting the profile

### 3.1 CLI

```bash
tethys-master --log-level DEBUG connect \
  --target udp://192.168.1.10:5555
```

Profile is sourced from the environment:

```bash
export TETHYS_MASTER_PROFILE=marine        # or space
tethys-master connect ...
```

Phase 3+ `daq` / `cal` / `demo` subcommands accept an explicit
`--profile` flag that overrides the env.

### 3.2 GUI

Pane "Active profile" (radio group). The GUI repaints the cal editor
and diagnostics pane when the profile changes; an info banner cites
the relevant ADR + rule file.

### 3.3 Python

```python
from tethys_master.profiles import Profile, PROFILE_DESCRIPTIONS

active = Profile.SPACE
print(PROFILE_DESCRIPTIONS[active])
```

The `Profile` enum is the **canonical** identifier - the
`gui.profile_selector.Profile` you may see in tests is a re-export of
the same enum.

## 4. What stays the same across profiles

- Protocol wire format (XCP 1.4).
- CTO / DTO framing.
- A2L parser (Sauci/pya2l).
- The Transport interface contract (ADR-0004).
- The structlog setup, log fields, and exit-code semantics.

So a Python script written against `tethys_master.protocol.client.XcpClient`
is **profile-agnostic**. The profile only changes which slave configurations
it can talk to and which CAL writes the GUI permits.

## 5. Detecting the slave's profile

Phase 6+ wiring (parked as a Phase 7 follow-up): after `CONNECT`,
issue `GET_VERSION` and read the slave's `tethys_profile.h` magic
marker from the `protocol_version` low nibble; the master then locks
its GUI to that profile (with a confirmation dialog) until a new
session opens.

Until that wiring lands, the user picks the profile manually; a
mismatch with the slave is logged as a `WARNING`.

## 6. Adding a new profile

A new profile is a substantial ADR-level change (parent plan section
6.3). The procedure:

1. Open an ADR `docs/adr/00NN-<profile>-profile.md` in proposed state.
2. Add a `.cursor/rules/<profile>-profile-invariants.mdc` file mirroring
   the marine/space rules.
3. Add a `slave/profiles/<profile>.cmake` matching marine.cmake.
4. Add an entry to `master/src/tethys_master/profiles/__init__.py`'s
   `Profile` enum + the two metadata dicts.
5. Land a research note `docs/research/phase-N-<profile>-profile.md`.
6. Update parent plan section 3.3 + this file.

No PR may add a new profile without all six steps - the `ecss-traceability.mdc`
rule fires on the slave + master code change.

## Cross-references

- Parent plan section 3.3.
- [ADR-0002 Profile-based build system](../../docs/adr/0002-profile-based-build-system.md).
- [ADR-0006 AES-128 seed-and-key (space profile)](../../docs/adr/0006-aes-128-seed-and-key.md).
- [`.cursor/rules/marine-profile-invariants.mdc`](../../.cursor/rules/marine-profile-invariants.mdc).
- [`.cursor/rules/space-profile-invariants.mdc`](../../.cursor/rules/space-profile-invariants.mdc).
- [`slave/profiles/marine.cmake`](../../slave/profiles/marine.cmake).
- [`slave/profiles/space.cmake`](../../slave/profiles/space.cmake).
- IACS UR E22 Rev.3 (in force 1 Jul 2024).
- IEC 60945 (maritime navigation equipment, environmental).
- ECSS-E-ST-40C Rev.1 (April 2025) software engineering.
- NPR 7150.2D NASA software engineering requirements.
