# Phase 10 — Verification pack foundations (research note)

> Research note backing the Phase 10 foundation PR cluster (Worker D in the multi-worker push).
> Parent plan: [`xcp_extreme-env_tool_14019278.plan.md`](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md) §8 Phase 10 + todo `p10`.
> Sub-plan: [`p10_verification_foundations_4f8d2a91.plan.md`](../../../../Users/wnp1cob/.cursor/plans/p10_verification_foundations_4f8d2a91.plan.md).

## 1. Scope

Phase 10 acceptance per parent §8 is the **full** verification pack — "generated traceability matrix, fuzz corpora, robustness suite, coverage report, MISRA report, all published as a downloadable PDF bundle on the docs site". The headline metrics are gcovr ≥95% statement + ≥90% MC/DC on the protocol core and zero open MISRA mandatory/required deviations. Those metrics require the **code being measured** to exist — Phases 2-8 must land first.

This note covers the **foundation** that Worker D ships in three PRs:

| PR | Title | Deliverables |
| --- | --- | --- |
| PR-A | `chore(standards): seed docs/traceability.csv + docs/traceability.md + phase-10 research note` | 79 traceability rows + grouped markdown view + this note |
| PR-B | `test(slave): A2L fixtures + robustness Unity suite (16 scenarios)` | 2 new A2L fixtures + 16-row Unity catalogue + `slave/tests/project.yml` glob update |
| PR-C | `test(slave): libFuzzer CTO harness + seed corpora + atheris a2l harness + fuzz-nightly wiring` | libFuzzer harness + 64+ corpus seeds + Python A2L harness + fuzz-nightly.yml direct-clang invocation |

The full Phase 10 acceptance (coverage + MISRA + MDF/PDF bundle) flips `p10` to `completed` only after Phases 2-8 land. Today this PR cluster ships the **scaffolding** so every downstream worker fills in measurements without re-litigating structure.

## 2. Sources (retrieved 2026-05-15)

| # | Source | URL / path | Retrieval date | Relevance |
| --- | --- | --- | --- | --- |
| 1 | `ecss-traceability.mdc` rule (CSV header definition) | [`.cursor/rules/ecss-traceability.mdc`](../../.cursor/rules/ecss-traceability.mdc) | 2026-05-15 | Locks the header to `id,kind,parent,description,implemented_by,verified_by,standard_objective,phase,profile` |
| 2 | `always-cite-standards.mdc` rule (citation format) | [`.cursor/rules/always-cite-standards.mdc`](../../.cursor/rules/always-cite-standards.mdc) | 2026-05-15 | Citation form `ASAM XCP 1.4 Part 2 §1.3.2.4` etc. |
| 3 | ADR-0010 Packet-loss tolerance budget (§6.1 budget table; §10 fault catalogue references) | [`docs/adr/0010-packet-loss-tolerance-budget.md`](../adr/0010-packet-loss-tolerance-budget.md) | 2026-05-15 | 12 LOSS rows + drives 16 FAULT rows |
| 4 | `phase-0-system-requirements.md` §10 — Fault-injection test catalogue | [`docs/research/phase-0-system-requirements.md`](phase-0-system-requirements.md) | 2026-05-15 | Canonical 16-row fault catalogue with detection layer + expected behaviour + pass criterion |
| 5 | `phase-0-standards-matrix.csv` (S1-S35 source IDs) | [`docs/research/phase-0-standards-matrix.csv`](phase-0-standards-matrix.csv) | 2026-05-15 | Standards naming + version pinning for the `standard_objective` column |
| 6 | ADR README index (10 accepted ADRs) | [`docs/adr/README.md`](../adr/README.md) | 2026-05-15 | One traceability row per ADR (TETHYS-ADR-0001..0010) |
| 7 | Existing `slave/src/core/xcp_dispatcher.{c,h}` (Phase 1 + Phase 2 read path landed) | [`slave/include/tethys/xcp_dispatcher.h`](../../slave/include/tethys/xcp_dispatcher.h) | 2026-05-15 | Drives DES-0001..0010 rows; FAULT-014 + FAULT-015 run against this API |
| 8 | `fuzz-nightly.yml` workflow (PR-4) | [`.github/workflows/fuzz-nightly.yml`](../../.github/workflows/fuzz-nightly.yml) | 2026-05-15 | Already-scaffolded nightly cron + crash artefact upload; PR-C activates it |
| 9 | `a2l-roundtrip.yml` workflow (PR-4) | [`.github/workflows/a2l-roundtrip.yml`](../../.github/workflows/a2l-roundtrip.yml) | 2026-05-15 | Already-scaffolded fixture-driven A2L round-trip; PR-B adds fixtures |
| 10 | libFuzzer documentation (LLVM) | <https://llvm.org/docs/LibFuzzer.html> | 2026-05-15 | Harness signature `LLVMFuzzerTestOneInput(const uint8_t*, size_t)`; corpus convention |
| 11 | Google atheris fuzzer (Python binding for libFuzzer) | <https://github.com/google/atheris> | 2026-05-15 | Python-side A2L parser harness; works against `tethys_master.protocol.a2l.A2LFile` |
| 12 | Sauci/pya2l reference (planned A2L engine per ADR-0007) | <https://github.com/Sauci/pya2l> | 2026-05-15 | Phase-2 PR-30 swaps the Phase-2 facade for Sauci/pya2l; PR-C's atheris harness imports Tethys's facade so it survives the swap |
| 13 | Unity test framework — TEST_IGNORE_MESSAGE | <https://github.com/ThrowTheSwitch/Unity> | 2026-05-15 | Robustness rows that depend on Phase-2..8 code are marked TEST_IGNORE_MESSAGE so the suite runs cleanly today and converts to real assertions as code lands |

## 3. Decisions

| # | Decision | Choice | Rejected | Rationale |
| --- | --- | --- | --- | --- |
| D1 | CSV header column order | `id,kind,parent,description,implemented_by,verified_by,standard_objective,phase,profile` per `ecss-traceability.mdc` row format | Reordering to lead with `standard_objective` (would break the rule + every existing tool that reads the CSV) | Rule is the single source of truth; downstream consumers (CI gates lined up for PR-10's full acceptance) parse by position |
| D2 | Row sort order | Alphabetical by `id` | Insertion order (drifts and creates merge conflicts when two workers add rows simultaneously) | Stable ordering makes the `git diff` of a CSV change obvious |
| D3 | Forward-tracker rows | Keep the row; flag `TODO(Phase-N)` in `description`; `implemented_by` and `verified_by` columns point at the eventual target file path | Skip the row until Phase-N lands (loses tracker function; defeats the purpose of a living matrix) | Per user instruction in the worker brief; downstream workers find the row by `id`, replace TODO with the real implementation |
| D4 | Description comma handling | Semicolons inside descriptions; never escape | Quote-escape commas (works but harder to grep) | CSV stays plain-text-readable without a parser; sort works trivially |
| D5 | Sort granularity | Sort by full `id` string (so `TETHYS-REQ-FAULT-001` sorts before `TETHYS-REQ-LOSS-001` because F < L) | Sort by category then number (more semantic but harder to maintain) | Single rule, no clever logic needed |
| D6 | Profile column separator | `|` between values when a row applies to both profiles (`marine|space`) | Comma (collides with CSV) | Matches the rule example exactly |
| D7 | A2L fuzz harness language | Python + [atheris](https://github.com/google/atheris) against `tethys_master.protocol.a2l.A2LFile.loads()` | Hand-rolled C A2L fuzz harness (would require a C A2L parser which we don't have) | Worker A's a2l.py facade lands in Phase-2 PR-30; atheris harness imports the facade so it survives the planned engine swap to Sauci/pya2l |
| D8 | A2L fixture scope | 3 fixtures: `trivial.a2l` (1 MEASUREMENT + 1 CHARACTERISTIC) + `marine_demo.a2l` (Worker A's existing fixture; realistic) + `edge_case_if_data.a2l` (deeply-nested IF_DATA + comments + skipped blocks) | 1 fixture only (insufficient coverage; a2l-roundtrip.yml workflow can't exercise edge cases) | Three points cover trivial / realistic / edge-case; gives Worker A's parser + future Sauci/pya2l engine a meaningful round-trip surface |
| D9 | Fuzz harness build path | Direct `clang -fsanitize=fuzzer,address,undefined` invocation documented in `slave/fuzz/README.md`; `.github/workflows/fuzz-nightly.yml` updated to use the same invocation | Add a `fuzz` preset to `slave/CMakePresets.json` (Worker E territory; cross-worker dependency) | Keeps the change inside test/CI scope; no coordination with Worker E required |
| D10 | CTO corpus seeding | One 1-byte file per PID byte (`pid_0xC0.bin .. pid_0xFF.bin` — 64 files covering every defined PID range start) + a handful of crafted multi-byte starts (CONNECT, GET_VERSION, SET_MTA prelude, UPLOAD, SHORT_UPLOAD) | Random byte seeds only (libFuzzer's mutation engine needs structure hints to discover deep paths efficiently) | libFuzzer documentation explicitly recommends seeding with valid inputs at every length boundary; 64 PID-byte files + ~8 crafted seeds covers Tethys's command surface |
| D11 | Robustness suite location | `slave/tests/robustness/` directory with `+:robustness/**` glob added to `slave/tests/project.yml` | Inline in `slave/tests/test/` (loses scenario separation; harder to filter by ceedling group) | Mirrors the user-requested layout exactly; one small project.yml addition is the only build-system change |
| D12 | Robustness pending-row pattern | `TEST_IGNORE_MESSAGE("Pending Phase-N <what>")` for each row whose dependency hasn't landed | `#if 0` block (compile-time invisible — coverage gate doesn't see the row; loses the tracker function) | Unity's `TEST_IGNORE` runs the test framework's row + emits a visible "ignored" in the output; downstream worker flips the assertion to real |
| D13 | Fault-injection coverage now | FAULT-014 (MTU overflow CTO) + FAULT-015 (malformed PID) run against the existing `tethys_xcp_dispatch` — every other row is pending the relevant phase | Skip the runnable-today rows because the rest are ignored (loses immediate signal that the dispatcher is sane today) | Two rows running today against the real API gives the suite an non-empty signal from day one |

## 4. Standards anchoring per deliverable

### 4.1 `docs/traceability.csv`

- **ECSS-E-ST-40C Rev.1 §5.7** — software requirements specification traceability obligations.
- **NPR 7150.2D §3** — NASA SW engineering process: requirements ↔ design ↔ code ↔ test traceability.
- **DO-178C §11.21** — software life-cycle data: traceability data items.
- **`.cursor/rules/ecss-traceability.mdc`** — repo-local source of truth for column ordering.

### 4.2 `slave/fuzz/` (libFuzzer)

- **DO-178C §6.4.4.1** — robustness testing; abnormal inputs.
- **MISRA C:2023** — applies to the harnesses themselves (static buffers; no recursion; no goto; no dynamic allocation per [ADR-0005](../adr/0005-no-dynamic-allocation.md)).
- **ECSS-E-ST-40C Rev.1 §5.5** — verification activities including robustness.
- **Parent plan §6.7** — `fuzz-nightly.yml` cron schedule + corpus growth tracked + new crashes open issues automatically.

### 4.3 `slave/tests/robustness/`

- **IEC 61784-3 ed.4 §6** — safe-comm residual-error testing.
- **AUTOSAR PRS E2E §4.3.3** — fault-class vocabulary (Repetition / Loss / Delay / Insertion / Corruption / Masquerade / Addressing); every fault scenario maps to one of these.
- **DO-178C §6.4.2** — requirements-based testing on equivalence classes; the 16 scenarios are the equivalence-class skeleton.
- **`phase-0-system-requirements.md` §10** — the catalogue is the canonical specification (16 rows) Worker D scaffolds against.

### 4.4 `slave/tests/fixtures/*.a2l`

- **ASAM MCD-2 MC v1.7 §4.4.1** — PROJECT block.
- **ASAM MCD-2 MC v1.7 §4.4.2** — MODULE block.
- **ASAM MCD-2 MC v1.7 §4.4.10** — CHARACTERISTIC block.
- **ASAM MCD-2 MC v1.7 §4.4.18** — MEASUREMENT block.
- **Worker A's `tethys_master.protocol.a2l`** docstring — the Tethys-side subset of A2L we currently support.

## 5. Fault-catalogue mapping

Per the user brief, every row of `phase-0-system-requirements.md` §10.1 (16 fault scenarios) maps to one row in `docs/traceability.csv` (TETHYS-REQ-FAULT-001..016) and one Unity test in `slave/tests/robustness/test_robustness_catalogue.c`.

| Catalogue # | Traceability id | Detection layer | Existing rule + ADR coverage | Maps to phase |
| --- | --- | --- | --- | --- |
| 1 | TETHYS-REQ-FAULT-001 | XCP CTR | ADR-0010 row 2/6/9/11; `xcp-protocol-discipline.mdc` | Phase-3 (DAQ) + Phase-5 (UDP) |
| 2 | TETHYS-REQ-FAULT-002 | XCP CTR + master timestamp | ADR-0010 §6.2 blackout bounds | Phase-3 + Phase-5 |
| 3 | TETHYS-REQ-FAULT-003 | XCP CTR | AUTOSAR E2E §4.3.3 Insertion | Phase-3 + Phase-5 |
| 4 | TETHYS-REQ-FAULT-004 | XCP CTR | AUTOSAR E2E §4.3.3 Repetition | Phase-3 + Phase-5 |
| 5 | TETHYS-REQ-FAULT-005 | Transport CRC | ADR-0004 transport interface; IEC 61784-3 §6 | Phase-5 |
| 6 | TETHYS-REQ-FAULT-006 | Transport CRC + CTO retry | ADR-0010 row 1 residual budget | Phase-5 |
| 7 | TETHYS-REQ-FAULT-007 | Master timeout + retry | ADR-0010 §6.2; XCP §1.3.1 | Phase-5 |
| 8 | TETHYS-REQ-FAULT-008 | CONNECT mismatch on reconnect | XCP §1.3.2.4 | Phase-3 |
| 9 | TETHYS-REQ-FAULT-009 | Master A2L hash check on CONNECT | ADR-0001 §3 (A2L hash); ASAM MCD-2 MC | Phase-2 PR-30 |
| 10 | TETHYS-REQ-FAULT-010 | Master checksum verification | XCP §1.5 BUILD_CHECKSUM | Phase-4 |
| 11 | TETHYS-REQ-FAULT-011 | CAN controller TEC/REC + bus-off recovery | ISO 11898-1:2024 §10 | Phase-5 |
| 12 | TETHYS-REQ-FAULT-012 | EDAC SEC-DED Hamming | ADR-0002 (space profile); ECSS-E-ST-40C §5.4.3.4 | Phase-8 |
| 13 | TETHYS-REQ-FAULT-013 | Slave seed-and-key state machine | ADR-0006 AES-128 | Phase-8 |
| 14 | TETHYS-REQ-FAULT-014 | XCP slave dispatcher (`req_len > MAX_CTO`) | `xcp-protocol-discipline.mdc`; ADR-0010 transport-MTU contract | **RUNS NOW** (Phase-1 dispatcher) |
| 15 | TETHYS-REQ-FAULT-015 | XCP slave dispatcher (unknown PID → `ERR_CMD_UNKNOWN`) | `xcp-protocol-discipline.mdc`; MISRA C:2023 (no-UB on unknown input) | **RUNS NOW** (Phase-1 dispatcher) |
| 16 | TETHYS-REQ-FAULT-016 | Master blackout timer | ADR-0010 §6.2 | Phase-3 |

Rows 14 + 15 are immediate signal — they exercise `tethys_xcp_dispatch()` (Phase-1 + Phase-2 read path, landed in PR #22 + PR #28). The other 14 rows are TEST_IGNORE_MESSAGE'd today and convert to real assertions as Phases 2-8 land.

## 6. Worker boundary respected (parallel push)

| Worker | Owns | Did I touch? |
| --- | --- | --- |
| A — `slave/src/core/` + `master/src/tethys_master/protocol/` + simulator | xcp_dispatcher, a2l parser, daq, cal | NO (I cite their files in traceability columns; I never edit) |
| B — `slave/src/transport/` + `master/src/tethys_master/transport/` | UDP/TCP/SocketCAN/UART transports | NO (I add traceability rows that point at the future files) |
| C — `master/src/tethys_master/gui/` | PySide6 GUI | NO |
| D — **me** | `docs/traceability.csv`, `docs/traceability.md`, `slave/fuzz/**`, `slave/tests/robustness/**`, `slave/tests/fixtures/**`, this research note | YES |
| E — `slave/cmake/`, `slave/profiles/`, `slave/src/platform/stm32/` | CMake presets, profile cmake, STM32 BSP | NO (I avoid `slave/CMakePresets.json` by building the fuzz harness via direct clang invocation in `fuzz-nightly.yml`) |

The only file in shared scope is `.github/workflows/fuzz-nightly.yml`. Per worker boundary table the workflow lives in test/CI scope; I update it to switch from the missing `cmake --preset=fuzz` to a direct `clang -fsanitize=fuzzer,address,undefined ...` invocation so the nightly cron actually runs without requiring Worker E's CMake changes.

Worker A's `marine_demo.a2l` (currently uncommitted in `slave/tests/fixtures/`) is **not** touched. PR-B adds `trivial.a2l` and `edge_case_if_data.a2l` alongside it. If Worker A's branch lands first, `marine_demo.a2l` is the "realistic" fixture in my 3-fixture set; if PR-B lands first, Worker A's branch absorbs my files via fast-forward without conflict.

## 7. What this PR cluster does NOT deliver (deferred to later PRs)

The full Phase 10 acceptance still requires:

| Deferred deliverable | Blocker | Owner | Lands after |
| --- | --- | --- | --- |
| Coverage gate: gcovr ≥95% statement + ≥90% MC/DC on protocol core | needs Phase 2-3 protocol core to exist | Worker A | Phase-2 PR-29 (DOWNLOAD + BUILD_CHECKSUM + SYNCH) + Phase-3 (DAQ) |
| MISRA zero-deviation gate (mandatory + required) | needs the bulk of slave code to exist | Workers A+B+E | Phase-7 + Phase-8 |
| Full robustness suite assertions (rows 1-13, 16) | needs Phase 2-8 code | A+B+E | rolling: each row flips from `TEST_IGNORE` to real as its phase lands |
| Sphinx PDF bundle of the verification pack | needs all of the above + the Sphinx docs site (Phase 11) | (TBD) | Phase 11 |
| AFL++ corpora (in addition to libFuzzer) | not blocking — libFuzzer covers the corpus growth metric | D | future PR after PR-C lands |
| Frama-C/WP ACSL contracts on dispatcher bounds checks | optional per parent §3.2 | (TBD) | Phase 8 optional |
| Generated A2L fixture corpus growth | Phase 2 PR-30 swaps the parser engine; will reshape the fixture surface | A + D | post Phase-2 PR-30 |

The `p10` parent-plan todo stays at `pending` after this PR cluster merges — flipping it to `completed` requires the deferred deliverables above.

## 8. Implementation Reference

- **PR-A**: *to be filled at merge* — `chore(standards): seed docs/traceability.csv + docs/traceability.md + phase-10 research note`
- **PR-B**: *to be filled at merge* — `test(slave): A2L fixtures + robustness Unity suite (16 scenarios)`
- **PR-C**: *to be filled at merge* — `test(slave): libFuzzer CTO harness + seed corpora + atheris a2l harness + fuzz-nightly wiring`

## 9. Open follow-ups

- **OF1** — A coverage check gate that verifies every file in `slave/src/core/`, `master/src/tethys_master/protocol/`, and `slave/tests/` is referenced by at least one row in `docs/traceability.csv` (per `ecss-traceability.mdc` "Verification" §). Lands in the PR that ships full Phase 10.
- **OF2** — The traceability CSV → markdown view is currently hand-edited. PR-6 runbook (`docs/runbooks/traceability-matrix-maintenance.md`) is referenced from `traceability.md`; the regeneration script that runbook implies still has to be written.
- **OF3** — Robustness suite TEST_IGNORE → real-assertion conversion is per-row work that the owning worker does as their phase lands. Worker D does not re-touch the suite after PR-B.
- **OF4** — AFL++ corpus is referenced in the parent plan §6.7 alongside libFuzzer. Adding AFL++ is straightforward (`afl-fuzz -i corpus/cto -o findings -- ./fuzz_cto_dispatcher`) but requires `afl-clang-fast` in the CI image; deferred until libFuzzer surfaces value.
- **OF5** — `master/src/tethys_master/protocol/a2l.py` is Worker A's WIP (uncommitted at the time of this note). The atheris harness in PR-C imports it; if Worker A's PR-30 lands a Sauci/pya2l-based engine before PR-C merges, the import surface is unchanged (the facade `A2LFile.loads()` stays), so PR-C's harness needs no edit.
